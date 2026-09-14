"""Углы карты: наклон эклиптики, звёздное время, ASC, MC, Vertex.

Все формулы работают в истинной эклиптике и равноденствии даты — той же
системе, в которой считаются положения планет.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .zodiac import norm360


def true_obliquity(t) -> float:
    """Истинный наклон эклиптики к экватору на момент t, градусы.

    Средний наклон по Capitaine et al. (2003) плюс нутация в наклоне
    по модели IAU 2000B — обе величины Skyfield считает сам.
    """
    _, deps = t._nutation_angles_radians
    return math.degrees(t._mean_obliquity_radians + deps)


def ramc(t, longitude_east: float) -> float:
    """Прямое восхождение середины неба (RAMC), градусы.

    Это местное истинное звёздное время: гринвичское видимое звёздное
    время плюс восточная географическая долгота.
    """
    return float(norm360(t.gast * 15.0 + longitude_east))


def midheaven(ramc_deg: float, obliquity: float) -> float:
    """Эклиптическая долгота MC — точки эклиптики на верхнем меридиане.

    Точка меридиана имеет прямое восхождение, равное RAMC; перевод
    экваториальной координаты в эклиптическую даёт
    tg(λ) = tg(α) / cos(ε), а atan2 сохраняет квадрант.
    """
    ra = math.radians(ramc_deg)
    eps = math.radians(obliquity)
    return norm360(math.degrees(math.atan2(math.sin(ra), math.cos(ra) * math.cos(eps))))


def ascendant(ramc_deg: float, obliquity: float, latitude: float) -> float:
    """Эклиптическая долгота Асцендента — восходящей точки эклиптики.

    Асцендент — пересечение эклиптики с восточной половиной горизонта.
    Стандартное решение системы «точка на эклиптике и на горизонте»:
    tg(λ) = cos(RAMC) / −(sin(RAMC)·cos ε + tg φ · sin ε).
    """
    ra = math.radians(ramc_deg)
    eps = math.radians(obliquity)
    phi = math.radians(latitude)
    y = math.cos(ra)
    x = -(math.sin(ra) * math.cos(eps) + math.tan(phi) * math.sin(eps))
    return norm360(math.degrees(math.atan2(y, x)))


def vertex(ramc_deg: float, obliquity: float, latitude: float) -> float:
    """Эклиптическая долгота Вертекса — западного пересечения с главным вертикалом.

    Главный вертикал — большой круг через зенит, точку востока и точку
    запада. Его полюс лежит на горизонте в точке севера, откуда условие
    принадлежности кругу принимает вид tg δ = tg φ · cos H — то же
    уравнение, что у горизонта широты φ − 90°. Поэтому Вертекс считается
    формулой Асцендента для широты 90° − φ и противоположного меридиана.
    Дополнение берётся со знаком широты, без модуля: иначе в южном
    полушарии точка уходит с главного вертикала.
    """
    return ascendant(norm360(ramc_deg + 180.0), obliquity, 90.0 - latitude)


def east_point(ramc_deg: float, obliquity: float) -> float:
    """Восточная точка (равноториальный Асцендент) — Асцендент для широты 0."""
    return ascendant(ramc_deg, obliquity, 0.0)


def ecliptic_declination(longitude: float, obliquity: float) -> float:
    """Склонение точки эклиптики с нулевой широтой, градусы."""
    return math.degrees(
        math.asin(math.sin(math.radians(obliquity)) * math.sin(math.radians(longitude)))
    )


def ecliptic_right_ascension(longitude: float, obliquity: float) -> float:
    """Прямое восхождение точки эклиптики с нулевой широтой, градусы."""
    lon = math.radians(longitude)
    eps = math.radians(obliquity)
    return norm360(
        math.degrees(math.atan2(math.sin(lon) * math.cos(eps), math.cos(lon)))
    )


def longitude_from_right_ascension(ra_deg: float, obliquity: float) -> float:
    """Обратный перевод: прямое восхождение → долгота, для точки на эклиптике."""
    ra = math.radians(ra_deg)
    eps = math.radians(obliquity)
    return norm360(math.degrees(math.atan2(math.sin(ra), math.cos(ra) * math.cos(eps))))


@dataclass(frozen=True)
class Angles:
    """Набор углов карты."""

    obliquity: float
    ramc: float
    asc: float
    mc: float
    vertex: float
    east_point: float

    @property
    def desc(self) -> float:
        return norm360(self.asc + 180.0)

    @property
    def ic(self) -> float:
        return norm360(self.mc + 180.0)

    @property
    def antivertex(self) -> float:
        return norm360(self.vertex + 180.0)


def compute(t, latitude: float, longitude_east: float) -> Angles:
    """Считает все углы карты для момента и места."""
    eps = true_obliquity(t)
    ra = ramc(t, longitude_east)
    return Angles(
        obliquity=eps,
        ramc=ra,
        asc=ascendant(ra, eps, latitude),
        mc=midheaven(ra, eps),
        vertex=vertex(ra, eps, latitude),
        east_point=east_point(ra, eps),
    )
