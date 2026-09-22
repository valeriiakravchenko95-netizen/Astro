#!/usr/bin/env python3
"""Готовит таблицы эфемерид для расчёта в браузере.

Ядро JPL весит десятки мегабайт и читается только на сервере. Для
браузера из него выбирается то немногое, что нужно астрологии: видимая
эклиптическая долгота и широта каждого тела вместе со скоростями, на
равномерной сетке. Между узлами значения восстанавливаются кубической
интерполяцией Эрмита — она использует и значение, и производную, поэтому
даёт точность в сотые доли угловой секунды при шаге в полсуток.

Долготы и широты хранятся целыми числами в микроградусах: это и вдвое
компактнее восьмибайтового числа, и точнее четырёхбайтового, у которого
на трёхстах шестидесяти градусах остаётся всего десятая доля угловой
секунды.

    python3 scripts/build_web_ephemeris.py
    python3 scripts/build_web_ephemeris.py --from 1900 --to 2050
"""

from __future__ import annotations

import argparse
import json
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from astro import bodies, nodes  # noqa: E402
from astro.ephemeris import load_ephemeris  # noqa: E402

OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "data"
)

#: Шаг сетки для каждого тела, сутки.
#:
#: Определяется не орбитальной скоростью, а тем, насколько быстро меняется
#: видимая с Земли долгота. У внешних планет она колеблется с годовым
#: периодом почти на три градуса — это и есть попятные петли, — поэтому
#: Урану шаг в шестнадцать суток не годится, хотя по орбите он ползёт
#: медленнее всех. Шаги подобраны так, чтобы восстановление оставалось в
#: пределах доли угловой секунды: проверяется в tests/test_web_tables.py.
STEPS = {
    "moon": 0.5,
    "mercury": 1.0,
    "sun": 4.0,
    "venus": 2.0,
    "mars": 2.0,
    "jupiter": 2.0,
    "saturn": 2.0,
    "uranus": 2.0,
    "neptune": 2.0,
    "pluto": 8.0,
    "true_node": 1.0,
    "mean_lilith": 2.0,
}

#: Порядок тел в файле; он же порядок в заголовке.
ORDER = (
    "sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn",
    "uranus", "neptune", "pluto", "true_node", "mean_lilith",
)

MICRO = 1_000_000.0
MAGIC = b"ASTREPH1"


#: Сколько узлов считать за раз. Skyfield работает векторно, но держать в
#: памяти сразу сотню тысяч положений ни к чему.
CHUNK = 20000

#: Шаг численного дифференцирования, сутки.
DERIVATIVE_STEP = 1.0 / 24.0


def _values(eph, body, jds, is_point: bool):
    """Эклиптическая долгота тела в моменты jds (массив)."""
    if is_point:
        t = eph.ts.tt_jd(jds)
        if body.key == "true_node":
            return np.asarray(nodes.true_node_longitude(eph, t), dtype=float)
        if body.key == "mean_lilith":
            return np.asarray(nodes.mean_lilith_longitude(jds), dtype=float)
        return np.asarray(nodes.mean_node_longitude(jds), dtype=float)

    return np.asarray(eph.ecliptic(body, eph.ts.tt_jd(jds))[0], dtype=float)


def sample(eph, body, jd_start: float, jd_end: float, step: float):
    """Снимает долготу и её скорость на равномерной сетке.

    Широта в таблицу не попадает: в расчёте она не участвует вовсе — ни
    дома, ни аспекты, ни достоинства от неё не зависят, — а места заняла
    бы вдвое больше. Это позволило взять более частую сетку и удержать
    восстановление в пределах угловой секунды.

    Всё считается векторно: поэлементный обход тех же точек занимал бы
    десятки минут на одну Луну. Скорость берётся центральной разностью,
    потому что для интерполяции Эрмита нужна производная именно видимой
    долготы, а не орбитальная скорость тела.
    """
    count = int(round((jd_end - jd_start) / step)) + 1
    is_point = nodes.is_lunar_point(body)

    longitudes = np.empty(count)
    rates = np.empty(count)

    h = DERIVATIVE_STEP
    for begin in range(0, count, CHUNK):
        end = min(begin + CHUNK, count)
        jds = jd_start + np.arange(begin, end) * step

        longitudes[begin:end] = _values(eph, body, jds, is_point)
        before = _values(eph, body, jds - h, is_point)
        after = _values(eph, body, jds + h, is_point)
        rates[begin:end] = ((after - before + 180.0) % 360.0 - 180.0) / (2 * h)

    return longitudes, rates


def pack(longitudes, rates) -> bytes:
    """Упаковывает столбцы: долгота целыми в микроградусах, скорость плавающей.

    Микроградус даёт 0.0036 угловой секунды — вчетверо точнее, чем
    четырёхбайтовое плавающее число на диапазоне в триста шестьдесят
    градусов, и вдвое компактнее восьмибайтового.
    """
    units = np.round(longitudes % 360.0 * MICRO).astype("<i4")
    return units.tobytes() + rates.astype("<f4").tobytes()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--from", dest="start_year", type=int, default=1920)
    parser.add_argument("--to", dest="end_year", type=int, default=2035)
    parser.add_argument("--out", default=OUTPUT_DIR)
    args = parser.parse_args()

    eph = load_ephemeris()
    jd_start = eph.ts.utc(args.start_year, 1, 1).tt
    jd_end = eph.ts.utc(args.end_year, 1, 1).tt
    os.makedirs(args.out, exist_ok=True)

    print(f"ядро: {eph.name}, интервал {args.start_year}–{args.end_year}")

    blocks = []
    meta = []
    for key in ORDER:
        body = bodies.get(key)
        step = STEPS[key]
        columns = sample(eph, body, jd_start, jd_end, step)
        payload = pack(*columns)
        meta.append({
            "key": key,
            "step": step,
            "count": len(columns[0]),
            "offset": sum(len(block) for block in blocks),
            "length": len(payload),
        })
        blocks.append(payload)
        print(f"  {body.name:14s} шаг {step:4.1f} сут, {len(columns[0]):7d} узлов, "
              f"{len(payload) / 1e6:5.2f} МБ")

    header = json.dumps(
        {
            "format": MAGIC.decode(),
            "jd_start": jd_start,
            "jd_end": jd_end,
            "micro": int(MICRO),
            "bodies": meta,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")

    path = os.path.join(args.out, "ephemeris.bin")
    with open(path, "wb") as handle:
        handle.write(MAGIC)
        handle.write(struct.pack("<I", len(header)))
        handle.write(header)
        for block in blocks:
            handle.write(block)

    size = os.path.getsize(path)
    print(f"\n{path}: {size / 1e6:.2f} МБ")
    return 0


if __name__ == "__main__":
    sys.exit(main())
