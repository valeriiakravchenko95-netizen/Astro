#!/usr/bin/env python3
"""Готовит эфемериду Хирона (или другого малого тела) для каталога ephemeris/.

Ядра SPK малых тел JPL отдаёт в типе 21, которого не читают ни Skyfield,
ни jplephem, поэтому берётся другой путь: у Horizons запрашивается таблица
векторов состояния, и она сохраняется в компактный файл, который читает
astro/smallbody.py.

    python3 scripts/fetch_chiron.py                       # Хирон, 1850-2150
    python3 scripts/fetch_chiron.py --from 1900 --to 2100
    python3 scripts/fetch_chiron.py --body 2060 --key chiron

Запускается один раз при разворачивании; расчёт карты потом идёт офлайн.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from astro.smallbody import load, save  # noqa: E402

HORIZONS = "https://ssd.jpl.nasa.gov/api/horizons.api"
TARGET_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ephemeris"
)

#: Код NAIF нумерованного астероида — 2000000 плюс его номер.
ASTEROID_OFFSET = 2000000


def request_vectors(body: int, start: str, stop: str, step_days: float) -> str:
    """Запрашивает у Horizons таблицу состояний относительно барицентра."""
    query = {
        "format": "text",
        "COMMAND": f"'{body};'",
        "OBJ_DATA": "'NO'",
        "MAKE_EPHEM": "'YES'",
        "EPHEM_TYPE": "'VECTORS'",
        "CENTER": "'@0'",           # барицентр Солнечной системы
        "REF_PLANE": "'FRAME'",     # система ICRF, как у ядер DE
        "REF_SYSTEM": "'ICRF'",
        "VEC_TABLE": "'2'",         # положение и скорость
        "OUT_UNITS": "'KM-S'",
        "CSV_FORMAT": "'YES'",
        "TLIST_TYPE": "'JD'",
        "START_TIME": f"'{start}'",
        "STOP_TIME": f"'{stop}'",
        "STEP_SIZE": f"'{int(step_days)} d'",
    }
    url = HORIZONS + "?" + urllib.parse.urlencode(query)
    with urllib.request.urlopen(url, timeout=180) as response:
        return response.read().decode("utf-8", "replace")


def parse_vectors(text: str):
    """Разбирает CSV-таблицу Horizons: JD (TDB), положение и скорость."""
    if "$$SOE" not in text or "$$EOE" not in text:
        head = text[:400].strip()
        raise SystemExit(f"Horizons вернул не таблицу, а вот это:\n{head}")

    body = text.split("$$SOE", 1)[1].split("$$EOE", 1)[0]
    times, states = [], []
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        fields = [f.strip() for f in line.split(",")]
        # JD, календарная дата, X, Y, Z, VX, VY, VZ
        numbers = [f for f in fields if f and _is_number(f)]
        if len(numbers) < 7:
            continue
        times.append(float(numbers[0]))
        x, y, z, vx, vy, vz = (float(v) for v in numbers[1:7])
        # Horizons отдаёт скорость в км/с, в файле она в км/сутки
        states.append([x, y, z, vx * 86400.0, vy * 86400.0, vz * 86400.0])

    if len(times) < 2:
        raise SystemExit("в ответе Horizons меньше двух узлов")
    return np.array(times), np.array(states)


def _is_number(text: str) -> bool:
    try:
        float(text)
    except ValueError:
        return False
    return True


def check_uniform(times: np.ndarray, step_days: float) -> None:
    """Сетка должна быть равномерной — интерполяция рассчитана на это."""
    steps = np.diff(times)
    if np.abs(steps - step_days).max() > 1e-6:
        raise SystemExit(
            f"Horizons вернул неравномерную сетку: шаг от {steps.min():.6f} "
            f"до {steps.max():.6f} суток вместо {step_days}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--body", type=int, default=2060, help="номер малого тела")
    parser.add_argument("--key", default="chiron", help="ключ тела в каталоге astro/bodies.py")
    parser.add_argument("--from", dest="start", default="1850-01-01")
    parser.add_argument("--to", dest="stop", default="2150-01-01")
    parser.add_argument("--step", type=float, default=16.0,
                        help="шаг сетки в сутках; 16 суток дают для Хирона "
                             "погрешность заметно меньше тысячной доли секунды дуги")
    args = parser.parse_args()

    os.makedirs(TARGET_DIR, exist_ok=True)
    destination = os.path.join(TARGET_DIR, f"{args.key}.npz")

    print(f"Запрашиваю у Horizons тело {args.body} на {args.start}…{args.stop}")
    text = request_vectors(args.body, args.start, args.stop, args.step)
    times, states = parse_vectors(text)
    check_uniform(times, args.step)

    save(
        destination,
        target=ASTEROID_OFFSET + args.body,
        center=0,
        jd_start=float(times[0]),
        step_days=args.step,
        states=states,
        name=args.key,
    )

    body = load(destination)
    print(
        f"Готово: {destination}, {os.path.getsize(destination) / 1024:.0f} КБ, "
        f"{len(states)} узлов, JD {body.jd_start:.1f}–{body.jd_end:.1f}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
