"""Жребии — точки, которые считаются от углов карты, а не от тел.

Пока нужен один жребий, Часть Фортуны. Её формула зависит от секты: днём
и ночью Солнце и Луна меняются местами, иначе жребий у ночных карт
оказывается зеркальным.
"""

from __future__ import annotations

from .zodiac import norm360


def is_diurnal(sun_longitude: float, ascendant: float) -> bool:
    """Дневная ли карта — то есть стоит ли Солнце над горизонтом.

    Горизонт делит зодиак линией ASC–DSC: дуга от Десцендента до
    Асцендента — это дома с седьмого по двенадцатый, верхняя половина.
    """
    descendant = norm360(ascendant + 180.0)
    return norm360(sun_longitude - descendant) < 180.0


def part_of_fortune(
    ascendant: float,
    sun_longitude: float,
    moon_longitude: float,
    diurnal: bool,
) -> float:
    """Часть Фортуны.

    Днём жребий отмеряется от Солнца к Луне, ночью — наоборот; в обоих
    случаях та же дуга откладывается от Асцендента.
    """
    if diurnal:
        return norm360(ascendant + moon_longitude - sun_longitude)
    return norm360(ascendant + sun_longitude - moon_longitude)
