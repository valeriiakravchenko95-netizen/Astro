"""Транзиты: как положение планеты в небе задевает натальную карту.

Транзит — это не свойство карты, а встреча: планета в небе подходит к
градусу, который в карте чем-то занят. Поэтому здесь считается не «что
происходит», а «за что именно в этой карте цепляется вот этот градус»:
какие тела он аспектирует, в какой дом попадает, какие куспиды задевает
и — через управителей — каких тем это касается.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from . import aspects as aspects_mod
from . import rulers as rulers_mod
from .chart import Chart
from .zodiac import norm180, norm360, to_sign

#: Орбисы транзитов уже натальных: транзитная планета проходит градус за
#: дни или недели, и широкий орбис размазал бы событие на месяцы.
DEFAULT_TRANSIT_ORBS: Dict[str, float] = {
    "conjunction": 3.0,
    "opposition": 3.0,
    "square": 3.0,
    "trine": 3.0,
    "sextile": 2.0,
}

#: Орбис попадания транзита на куспид дома.
DEFAULT_CUSP_ORB = 2.0


@dataclass(frozen=True)
class TransitHit:
    """Аспект транзитной точки к точке натальной карты."""

    transit: str          # что идёт по небу
    natal: str            # к чему в карте
    natal_kind: str       # body | angle | cusp
    aspect: aspects_mod.Aspect
    orb: float
    exact: bool           # точный в пределах четверти градуса
    natal_longitude: float

    @property
    def strength(self) -> float:
        limit = DEFAULT_TRANSIT_ORBS.get(self.aspect.key, 3.0)
        return max(0.0, 1.0 - self.orb / limit) if limit else 0.0

    def describe(self) -> str:
        return (
            f"{self.transit} {self.aspect.name.lower()} "
            f"{self.natal} (орб {self.orb:.1f}°)"
        )


@dataclass(frozen=True)
class TransitReport:
    """Что транзитный градус задевает в конкретной карте."""

    longitude: float
    hits: Tuple[TransitHit, ...]
    house: Optional[int]          # в какой натальный дом попал градус
    houses_touched: Tuple[int, ...]   # дома, задетые через тела и куспиды
    ruled_houses: Mapping[str, Tuple[int, ...]]  # какое тело каким домом правит

    @property
    def touches(self) -> bool:
        return bool(self.hits) or self.house is not None

    @property
    def closest(self) -> Optional[TransitHit]:
        return self.hits[0] if self.hits else None


def _aspect_list(names: Optional[Sequence[str]]) -> Tuple[aspects_mod.Aspect, ...]:
    if names is None:
        return aspects_mod.MAJOR
    return tuple(aspects_mod.BY_KEY[name] for name in names)


def ruled_houses(chart: Chart) -> Dict[str, Tuple[int, ...]]:
    """Какими домами управляет каждое тело карты.

    Дом управляется телом, которому принадлежит знак на его куспиде. Это
    то, что переводит «задета планета» в «задета тема»: транзит к
    управителю второго дома говорит о деньгах, даже если сама планета
    стоит в седьмом.
    """
    houses = chart.primary_houses
    mapping: Dict[str, List[int]] = {}
    for house in range(1, 13):
        sign = to_sign(houses.cusp(house)).sign_index
        ruler = rulers_mod.ruler_of(sign, chart.ruler_scheme)
        mapping.setdefault(ruler, []).append(house)
    return {key: tuple(value) for key, value in mapping.items()}


def examine(
    chart: Chart,
    longitude: float,
    transit_name: str = "транзит",
    orbs: Optional[Mapping[str, float]] = None,
    aspect_names: Optional[Sequence[str]] = None,
    cusp_orb: float = DEFAULT_CUSP_ORB,
    include_angles: bool = True,
    include_cusps: bool = True,
) -> TransitReport:
    """Разбирает, за что в карте цепляется градус ``longitude``.

    Время рождения известно не всегда. Без него нет ни домов, ни углов,
    поэтому проверяются только тела: показывать дома по карте на полдень
    значило бы выдавать выдумку за расчёт.
    """
    limits = dict(DEFAULT_TRANSIT_ORBS)
    if orbs:
        limits.update(orbs)
    aspect_set = _aspect_list(aspect_names)
    has_houses = chart.moment is not None and chart.exact_time

    hits: List[TransitHit] = []

    def check(natal_name: str, natal_longitude: float, kind: str) -> None:
        for aspect in aspect_set:
            limit = limits.get(aspect.key)
            if not limit:
                continue
            delta = norm180(longitude - natal_longitude)
            target = aspect.angle if delta >= 0 else -aspect.angle
            orb = abs(norm180(delta - target))
            if orb <= limit:
                hits.append(TransitHit(
                    transit=transit_name, natal=natal_name, natal_kind=kind,
                    aspect=aspect, orb=orb, exact=orb <= 0.25,
                    natal_longitude=natal_longitude,
                ))
                break  # ближайший аспект для пары найден

    for key, position in chart.positions.items():
        check(key, position.longitude, "body")

    if include_angles and has_houses:
        check("asc", chart.angles.asc, "angle")
        check("mc", chart.angles.mc, "angle")

    if include_cusps and has_houses:
        for house in range(1, 13):
            cusp = chart.primary_houses.cusp(house)
            if abs(norm180(longitude - cusp)) <= cusp_orb:
                hits.append(TransitHit(
                    transit=transit_name, natal=f"куспид {house}",
                    natal_kind="cusp",
                    aspect=aspects_mod.CONJUNCTION,
                    orb=abs(norm180(longitude - cusp)),
                    exact=abs(norm180(longitude - cusp)) <= 0.25,
                    natal_longitude=cusp,
                ))

    hits.sort(key=lambda hit: hit.orb)

    house = chart.primary_houses.house_of(longitude) if has_houses else None

    rulership = ruled_houses(chart) if has_houses else {}
    touched: List[int] = []
    if house is not None:
        touched.append(house)
    for hit in hits:
        if hit.natal_kind == "body":
            touched.extend(rulership.get(hit.natal, ()))
            position = chart.positions.get(hit.natal)
            if position is not None:
                touched.append(position.house)
        elif hit.natal_kind == "cusp":
            touched.append(int(hit.natal.split()[-1]))
        elif hit.natal == "asc":
            touched.append(1)
        elif hit.natal == "mc":
            touched.append(10)

    return TransitReport(
        longitude=norm360(longitude),
        hits=tuple(hits),
        house=house,
        houses_touched=tuple(sorted(set(touched))),
        ruled_houses=rulership,
    )


def positions_at(eph, t, keys: Sequence[str]) -> Dict[str, float]:
    """Долготы транзитных тел на момент."""
    from . import bodies as bodies_mod
    from . import nodes as nodes_mod

    result: Dict[str, float] = {}
    for key in keys:
        body = bodies_mod.get(key)
        if nodes_mod.is_lunar_point(body):
            result[key] = nodes_mod.position(body, eph, t).longitude
        else:
            result[key] = eph.ecliptic(body, t)[0]
    return result
