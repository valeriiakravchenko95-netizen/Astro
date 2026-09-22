#!/usr/bin/env python3
"""Готовит эталонные карты для сверки браузерного расчёта с этим.

Браузерная версия — это перенос, а не обёртка: тот же расчёт написан
заново на другом языке. Единственный способ убедиться, что перенос не
разошёлся с оригиналом, — прогнать через оба одни и те же карты и
сравнить градусы. Этот скрипт делает первую половину работы.

    python3 scripts/make_reference_charts.py --count 500
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402

from astro import houses as houses_mod  # noqa: E402
from astro.chart import Place, compute  # noqa: E402

OUTPUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tests", "data", "reference_charts.json",
)

#: Места подобраны так, чтобы задеть оба полушария, высокие широты и
#: зоны с непростой историей перевода стрелок.
PLACES = [
    ("Донецк", 48.0159, 37.8028, "Europe/Kyiv"),
    ("Москва", 55.7558, 37.6173, "Europe/Moscow"),
    ("Ташкент", 41.2995, 69.2401, "Asia/Tashkent"),
    ("Владивосток", 43.1198, 131.8869, "Asia/Vladivostok"),
    ("Лондон", 51.5074, -0.1278, "Europe/London"),
    ("Нью-Йорк", 40.7128, -74.0060, "America/New_York"),
    ("Буэнос-Айрес", -34.6037, -58.3816, "America/Argentina/Buenos_Aires"),
    ("Кейптаун", -33.9249, 18.4241, "Africa/Johannesburg"),
    ("Сингапур", 1.3521, 103.8198, "Asia/Singapore"),
    ("Мурманск", 68.9585, 33.0827, "Europe/Moscow"),
    ("Сидней", -33.8688, 151.2093, "Australia/Sydney"),
    ("Рейкьявик", 64.1466, -21.9426, "Atlantic/Reykjavik"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--count", type=int, default=400)
    parser.add_argument("--seed", type=int, default=20260922)
    parser.add_argument("--out", default=OUTPUT)
    args = parser.parse_args()

    generator = np.random.default_rng(args.seed)
    charts = []

    for index in range(args.count):
        place = PLACES[index % len(PLACES)]
        year = int(generator.integers(1925, 2030))
        month = int(generator.integers(1, 13))
        day = int(generator.integers(1, 29))
        hour = int(generator.integers(0, 24))
        minute = int(generator.integers(0, 60))

        name, latitude, longitude, zone = place
        try:
            chart = compute(
                datetime(year, month, day, hour, minute),
                Place(latitude, longitude, name),
                zone=zone,
                house_systems=(houses_mod.PLACIDUS, houses_mod.WHOLE_SIGN),
                primary_system=houses_mod.PLACIDUS,
                house_fallback=houses_mod.WHOLE_SIGN,
            )
        except Exception as error:  # noqa: BLE001 — записываем и идём дальше
            print(f"пропущена карта {year}-{month:02d}-{day:02d} {name}: {error}")
            continue

        charts.append({
            "input": {
                "year": year, "month": month, "day": day,
                "hour": hour, "minute": minute,
                "latitude": latitude, "longitude": longitude,
                "timeZone": zone, "place": name,
            },
            "utc": chart.moment.utc.strftime("%Y-%m-%dT%H:%M:%S"),
            "angles": {
                "asc": chart.angles.asc, "mc": chart.angles.mc,
                "vertex": chart.angles.vertex, "obliquity": chart.angles.obliquity,
                "ramc": chart.angles.ramc,
            },
            "positions": {
                key: {"longitude": p.longitude, "speed": p.speed}
                for key, p in chart.positions.items()
            },
            "houses": {
                name: list(built.cusps) for name, built in chart.houses.items()
            },
            "diurnal": chart.diurnal,
            "aspects": [
                {"a": h.body_a, "b": h.body_b, "aspect": h.aspect.key,
                 "orb": h.orb, "applying": h.applying}
                for h in chart.aspects
            ],
            "patterns": [
                {"key": h.key, "bodies": sorted(h.bodies)} for h in chart.patterns
            ],
            "dignities": {
                key: {"state": d.state, "own": list(d.own), "term": d.term, "decan": d.decan}
                for key, d in chart.dignities.items()
            },
            "chart_ruler": chart.chart_ruler,
        })

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(charts, handle, ensure_ascii=False)

    print(f"{args.out}: {len(charts)} карт, {os.path.getsize(args.out) / 1e6:.2f} МБ")
    return 0


if __name__ == "__main__":
    sys.exit(main())
