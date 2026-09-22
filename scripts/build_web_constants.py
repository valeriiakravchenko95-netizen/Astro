#!/usr/bin/env python3
"""Переносит константы расчёта в файл для браузера.

Нутация, шкалы времени и скачки секунд — это длинные таблицы чисел.
Переписывать их руками значит однажды ошибиться в одной цифре и получить
расхождение, которое потом ищешь неделю. Поэтому они выгружаются прямо из
тех данных, на которых считает Python, и браузерный расчёт опирается на
ровно те же числа.

    python3 scripts/build_web_constants.py
"""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skyfield import nutationlib  # noqa: E402
from skyfield.api import load  # noqa: E402

OUTPUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "web", "astro", "constants.js",
)

#: Модель IAU 2000B — это первые 77 членов лунно-солнечного ряда IAU 2000A
#: плюс две постоянные поправки; планетные члены в неё не входят.
LUNISOLAR_TERMS = 77
DPSI_OFFSET = -0.000135e7   # десятые доли микросекунды дуги
DEPS_OFFSET = 0.000388e7

#: Интервал таблицы разницы шкал времени и сколько узлов приходится на год.
#:
#: Годовой сетки не хватает: между соседними годами разница уходит на
#: полсекунды, и линейная прикидка ошибается на сотые доли секунды — а это
#: почти угловая секунда в звёздном времени, то есть в Асценденте.
#: Помесячная сетка убирает это на порядок, стоя лишних двадцати килобайт.
DELTA_T_FIRST_YEAR = 1900
DELTA_T_LAST_YEAR = 2050
DELTA_T_PER_YEAR = 12


def julian_day_utc(year, month, day, hour=0, minute=0, second=0.0):
    """Юлианская дата по григорианскому календарю — как считает браузер."""
    y, m = (year, month) if month > 2 else (year - 1, month + 12)
    a = y // 100
    b = 2 - a + a // 4
    return (
        int(365.25 * (y + 4716)) + int(30.6001 * (m + 1))
        + day + b - 1524.5 + (hour + minute / 60 + second / 3600) / 24
    )


def numbers(values, per_line=6, indent="  "):
    """Раскладывает числа в столбик, чтобы файл читался."""
    text = []
    for start in range(0, len(values), per_line):
        chunk = ", ".join(repr(float(v)) if not float(v).is_integer() else str(int(v))
                          for v in values[start:start + per_line])
        text.append(indent + chunk + ",")
    return "\n".join(text)


def main() -> int:
    timescale = load.timescale()

    arguments = nutationlib.nals_t[:LUNISOLAR_TERMS].astype(int)
    longitude = nutationlib.lunisolar_longitude_coefficients[:LUNISOLAR_TERMS]
    obliquity = nutationlib.lunisolar_obliquity_coefficients[:LUNISOLAR_TERMS]

    # Разница шкал времени: TT минус UT1, по годам. Она меняется плавно,
    # поэтому годовой сетки с линейной интерполяцией хватает с запасом:
    # секунда здесь стоит пятнадцати угловых секунд звёздного времени, а
    # ошибка интерполяции остаётся много меньше сотой доли секунды.
    count = (DELTA_T_LAST_YEAR - DELTA_T_FIRST_YEAR) * DELTA_T_PER_YEAR + 1
    delta_t = []
    for step in range(count):
        year = DELTA_T_FIRST_YEAR + step // DELTA_T_PER_YEAR
        month = step % DELTA_T_PER_YEAR + 1
        delta_t.append(round(float(timescale.utc(year, month, 1).delta_t), 4))

    leap_dates = np.asarray(timescale.leap_dates, dtype=float)
    leap_offsets = np.asarray(timescale.leap_offsets, dtype=float)

    # До первого скачка секунды (июль 1972) разница TAI − UTC своя, и это
    # не значение первой записи таблицы. Берём её не на веру, а измерением:
    # считаем TT для заведомо раннего момента и вычитаем постоянные 32.184.
    early = timescale.utc(1960, 1, 1)
    early_jd = julian_day_utc(1960, 1, 1)
    pre_leap_offset = round((float(early.tt) - early_jd) * 86400 - 32.184, 6)

    lines = [
        "// Файл собран scripts/build_web_constants.py — правки руками",
        "// потеряются при следующей сборке.",
        "",
        "// Аргументы Делоне: постоянная часть и линейный коэффициент,",
        "// в угловых секундах (Simon et al. 1994).",
        "export const FUNDAMENTAL_CONSTANT = [",
        numbers(nutationlib.fa0.ravel(), 5),
        "];",
        "export const FUNDAMENTAL_RATE = [",
        numbers(nutationlib.fa1.ravel(), 5),
        "];",
        "",
        f"// Лунно-солнечный ряд нутации IAU 2000B: {LUNISOLAR_TERMS} членов.",
        "// Для каждого — множители пяти аргументов Делоне.",
        "export const NUTATION_ARGUMENTS = [",
        "\n".join("  " + str(list(map(int, row))) + "," for row in arguments),
        "];",
        "// Коэффициенты при синусе и косинусе, в десятых долях микросекунды дуги.",
        "export const NUTATION_LONGITUDE = [",
        "\n".join("  " + str([float(v) for v in row]) + "," for row in longitude),
        "];",
        "export const NUTATION_OBLIQUITY = [",
        "\n".join("  " + str([float(v) for v in row]) + "," for row in obliquity),
        "];",
        f"export const NUTATION_LONGITUDE_OFFSET = {DPSI_OFFSET!r};",
        f"export const NUTATION_OBLIQUITY_OFFSET = {DEPS_OFFSET!r};",
        "",
        "// Разница шкал времени TT − UT1 по годам.",
        f"export const DELTA_T_FIRST_YEAR = {DELTA_T_FIRST_YEAR};",
        f"export const DELTA_T_PER_YEAR = {DELTA_T_PER_YEAR};",
        "export const DELTA_T = [",
        numbers(delta_t, 8),
        "];",
        "",
        "// Скачки секунды: юлианская дата и накопленная разница TAI − UTC.",
        "export const LEAP_DATES = [",
        numbers(leap_dates, 6),
        "];",
        f"export const PRE_LEAP_OFFSET = {pre_leap_offset!r};",
        "export const LEAP_OFFSETS = [",
        numbers(leap_offsets, 8),
        "];",
        "",
    ]

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))

    print(f"{OUTPUT}: {os.path.getsize(OUTPUT) / 1024:.0f} КБ")
    print(f"  членов нутации: {LUNISOLAR_TERMS}")
    print(f"  разница шкал: {DELTA_T_FIRST_YEAR}–{DELTA_T_LAST_YEAR}, "
          f"{len(delta_t)} значений")
    print(f"  скачков секунды: {len(leap_dates)}, до первого TAI − UTC = {pre_leap_offset}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
