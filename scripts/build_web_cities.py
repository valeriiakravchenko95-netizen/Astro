#!/usr/bin/env python3
"""Готовит список городов для поиска места в браузере.

Поиск места должен работать без сети, как и весь остальной расчёт,
поэтому список городов едет вместе со страницей. Из выгрузки GeoNames
берётся только необходимое: как город называется по-русски и на латинице,
где он, в какой стране и в каком часовом поясе.

    python3 scripts/build_web_cities.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys

OUTPUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "web", "data", "cities.json",
)


def is_cyrillic(text: str) -> bool:
    return any("Ѐ" <= character <= "ӿ" for character in text)


#: Буквы русского алфавита — по ним отсеиваются прочие кириллические языки.
RUSSIAN_LETTERS = set("абвгдеёжзийклмнопрстуфхцчшщъыьэюя")


def is_cyrillic(text: str) -> bool:
    return any("\u0400" <= character <= "\u04FF" for character in text)


def looks_russian(name: str) -> bool:
    """Похоже ли написание на русское.

    Языковых меток в выгрузке нет, поэтому язык определяется по буквам:
    «Юзів» с украинской «і» и «Мæскуы» с осетинской «æ» отсеиваются, а
    «Донецк» остаётся. Различить русский и белорусский так нельзя, но это
    и не нужно — лишнее написание поиску не мешает.
    """
    letters = [c for c in name.lower() if c.isalpha()]
    return bool(letters) and all(c in RUSSIAN_LETTERS for c in letters)


def cyrillic_names(city):
    """Написания города русскими буквами — для поиска.

    Хранятся все подходящие, а не одно: заранее выбрать «то самое» нельзя,
    и любая попытка промахивается — у Москвы короче всего оказывается
    «Муско», у Петербурга «СПб». Показывается потом то написание, по
    которому человек нашёл город.
    """
    names = []
    for name in city.get("alternatenames") or ():
        if len(name) > 40 or not is_cyrillic(name) or not looks_russian(name):
            continue
        if name not in names:
            names.append(name)
    return names


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--min-population", type=int, default=0)
    parser.add_argument("--out", default=OUTPUT)
    args = parser.parse_args()

    import geonamescache

    cache = geonamescache.GeonamesCache()
    countries = {code: data["name"] for code, data in cache.get_countries().items()}

    zones = {}
    rows = []
    for city in cache.get_cities().values():
        if city["population"] < args.min_population:
            continue
        zone = city.get("timezone") or ""
        if zone not in zones:
            zones[zone] = len(zones)
        rows.append([
            city["name"],
            cyrillic_names(city),
            city["countrycode"],
            round(float(city["latitude"]), 4),
            round(float(city["longitude"]), 4),
            int(city["population"]) // 1000,
            zones[zone],
        ])

    # Крупные города идут первыми: при совпадении названий сверху окажется
    # тот, который человек скорее всего и имел в виду.
    rows.sort(key=lambda row: -row[5])

    payload = {
        "fields": ["name", "cyrillic", "country", "lat", "lon", "population_k", "zone"],
        "zones": [zone for zone, _ in sorted(zones.items(), key=lambda item: item[1])],
        "countries": countries,
        "cities": rows,
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))

    size = os.path.getsize(args.out)
    with_cyrillic = sum(1 for row in rows if row[1])
    print(f"{args.out}: {size / 1e6:.2f} МБ")
    print(f"  городов: {len(rows)}, с кириллическим написанием: {with_cyrillic}")
    print(f"  часовых поясов: {len(zones)}, стран: {len(countries)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
