"""Офлайн-поиск места рождения.

Города берутся из geonamescache — это выгрузка GeoNames, упакованная в
пакет, поэтому поиск работает без сети, как и весь остальной расчёт.
Названия ищутся и по-русски: в выгрузке есть кириллические варианты.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from typing import List, Optional, Tuple

#: Сколько вариантов показывать, когда название неоднозначно.
MAX_SUGGESTIONS = 6


@dataclass(frozen=True)
class Place:
    """Найденное место."""

    name: str
    country: str
    latitude: float
    longitude: float
    population: int
    timezone: Optional[str] = None

    def label(self) -> str:
        country = country_name(self.country)
        if self.population:
            return f"{self.name}, {country} ({self.population // 1000} тыс.)"
        return f"{self.name}, {country}"

    def short(self) -> str:
        return f"{self.name}, {country_name(self.country)}"


@lru_cache(maxsize=1)
def _cache():
    import geonamescache

    return geonamescache.GeonamesCache()


@lru_cache(maxsize=1)
def _index() -> dict:
    """Строит указатель «нормализованное имя → города»."""
    index: dict = {}
    for city in _cache().get_cities().values():
        names = [city["name"]] + list(city.get("alternatenames") or ())
        for name in names:
            key = normalize(name)
            if not key:
                continue
            index.setdefault(key, []).append(city)
    return index


@lru_cache(maxsize=1)
def _countries() -> dict:
    return {
        code: data["name"] for code, data in _cache().get_countries().items()
    }


def country_name(code: str) -> str:
    return _countries().get(code, code)


def normalize(text: str) -> str:
    """Приводит название к виду, удобному для сравнения.

    Регистр, дефисы и диакритика в написании городов гуляют, поэтому всё
    это снимается: «Санкт-Петербург», «санкт петербург» и «Sankt-Peterburg»
    должны находить одно и то же.
    """
    text = unicodedata.normalize("NFKD", text.strip().lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    for separator in ("-", "'", "’", "`", ".", ","):
        text = text.replace(separator, " ")
    return " ".join(text.split())


def search(query: str, limit: int = MAX_SUGGESTIONS) -> List[Place]:
    """Ищет город по названию: сперва точное совпадение, потом по началу.

    Результаты идут по убыванию населения — при одинаковых названиях
    первым оказывается тот город, который имелся в виду с большей
    вероятностью.
    """
    key = normalize(query)
    if not key:
        return []

    index = _index()
    found = list(index.get(key, ()))

    if not found:
        for name, cities in index.items():
            if name.startswith(key):
                found.extend(cities)
                if len(found) > limit * 20:
                    break

    unique = {}
    for city in found:
        unique[city["geonameid"]] = city

    places = [
        Place(
            name=city["name"],
            country=city["countrycode"],
            latitude=float(city["latitude"]),
            longitude=float(city["longitude"]),
            population=int(city["population"]),
            timezone=city.get("timezone"),
        )
        for city in unique.values()
    ]
    places.sort(key=lambda place: (-place.population, place.name))
    return places[:limit]


def parse_coordinates(text: str) -> Optional[Tuple[float, float]]:
    """Разбирает координаты, введённые вручную: «48.02, 37.80»."""
    cleaned = text.replace(";", " ").replace(",", " ").strip()
    parts = cleaned.split()
    if len(parts) != 2:
        return None
    try:
        latitude, longitude = float(parts[0]), float(parts[1])
    except ValueError:
        return None
    if not -90.0 <= latitude <= 90.0 or not -180.0 <= longitude <= 180.0:
        return None
    return latitude, longitude
