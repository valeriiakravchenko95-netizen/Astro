"""Сборка натальной карты: позиции, дома, аспекты, диспозиторы."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Mapping, Optional, Sequence, Tuple

from . import angles as angles_mod
from . import aspects as aspects_mod
from . import bodies as bodies_mod
from . import houses as houses_mod
from . import lots as lots_mod
from . import nodes as nodes_mod
from . import patterns as patterns_mod
from . import rulers as rulers_mod
from . import timeutil
from .bodies import Body
from .ephemeris import Ephemeris, RawPosition, load_ephemeris
from .zodiac import SignPosition, format_longitude, to_sign

#: Переменная окружения с солью для хеша карты.
SALT_ENV = "ASTRO_HASH_SALT"


@dataclass(frozen=True)
class Place:
    """Место рождения."""

    latitude: float
    longitude: float
    name: Optional[str] = None

    def __post_init__(self) -> None:
        if not -90.0 <= self.latitude <= 90.0:
            raise ValueError(f"широта вне диапазона: {self.latitude}")
        if not -180.0 <= self.longitude <= 180.0:
            raise ValueError(f"долгота вне диапазона: {self.longitude}")


@dataclass(frozen=True)
class PlanetPosition:
    """Положение тела в карте."""

    body: Body
    longitude: float
    latitude: float
    distance: float
    speed: float
    houses: Mapping[str, int]
    primary_system: str
    dignity: str

    @property
    def sign(self) -> SignPosition:
        return to_sign(self.longitude)

    @property
    def house(self) -> int:
        return self.houses[self.primary_system]

    @property
    def retrograde(self) -> bool:
        return self.speed < 0.0

    @property
    def stationary(self) -> bool:
        """Планета близка к стоянию: суточный ход меньше одной минуты дуги."""
        return abs(self.speed) < 1.0 / 60.0

    def describe(self) -> str:
        mark = " R" if self.retrograde else ""
        return (
            f"{self.body.name:16s} {format_longitude(self.longitude):22s}"
            f"{mark:2s}  дом {self.house:2d}  {self.speed:+8.4f}°/сут"
        )


@dataclass(frozen=True)
class Chart:
    """Готовая натальная карта."""

    moment: timeutil.Moment
    place: Place
    angles: angles_mod.Angles
    houses: Mapping[str, houses_mod.Houses]
    primary_system: str
    positions: Mapping[str, PlanetPosition]
    aspects: Tuple[aspects_mod.AspectHit, ...]
    angle_aspects: Tuple[aspects_mod.AspectHit, ...]
    dispositors: rulers_mod.DispositorTree
    patterns: Tuple[patterns_mod.PatternHit, ...]
    stelliums: Tuple[patterns_mod.Stellium, ...]
    antiscia: Tuple[patterns_mod.AntisciaHit, ...]
    dignities: Mapping[str, rulers_mod.EssentialDignities]
    ruler_scheme: str
    ephemeris: str
    diurnal: Optional[bool] = None
    lilith_model: str = nodes_mod.LILITH_SWISS

    @property
    def primary_houses(self) -> houses_mod.Houses:
        return self.houses[self.primary_system]

    @property
    def chart_ruler(self) -> str:
        """Управитель карты — управитель знака Асцендента."""
        return rulers_mod.ruler_of(to_sign(self.angles.asc).sign_index, self.ruler_scheme)

    def position(self, key: str) -> PlanetPosition:
        return self.positions[key]

    def digest(self, salt: Optional[str] = None) -> str:
        """Устойчивый идентификатор карты без раскрытия исходных данных.

        Считается от момента в UTC и координат. Пространство дат и мест
        мало, поэтому без секретной соли такой хеш перебирается за минуты
        и персональными данными быть не перестаёт. Соль берётся из
        переменной окружения ASTRO_HASH_SALT; если её нет, хеш всё равно
        вернётся, но полагаться на него как на обезличивание нельзя.
        """
        secret = salt if salt is not None else os.environ.get(SALT_ENV, "")
        payload = "|".join(
            [
                secret,
                self.moment.utc.strftime("%Y-%m-%dT%H:%M:%S"),
                f"{self.place.latitude:.6f}",
                f"{self.place.longitude:.6f}",
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self, include_birth_data: bool = False, salt: Optional[str] = None) -> dict:
        """Словарь с результатом расчёта.

        По умолчанию дата и место рождения в выдачу не попадают: остаются
        только градусы и идентификатор карты. Исходные данные добавляются
        лишь по явному запросу.
        """
        data = {
            "id": self.digest(salt),
            "ephemeris": self.ephemeris,
            "house_system": self.primary_system,
            "ruler_scheme": self.ruler_scheme,
            "angles": {
                "asc": self.angles.asc,
                "mc": self.angles.mc,
                "desc": self.angles.desc,
                "ic": self.angles.ic,
                "vertex": self.angles.vertex,
                "east_point": self.angles.east_point,
                "obliquity": self.angles.obliquity,
                "ramc": self.angles.ramc,
            },
            "houses": {
                name: list(h.cusps) for name, h in self.houses.items()
            },
            "positions": {
                key: {
                    "name": p.body.name,
                    "longitude": p.longitude,
                    "latitude": p.latitude,
                    "distance_au": None if p.distance != p.distance else p.distance,
                    "speed": p.speed,
                    "retrograde": p.retrograde,
                    "sign": p.sign.sign,
                    "sign_index": p.sign.sign_index,
                    "degree_in_sign": p.sign.degree_in_sign,
                    "formatted": format_longitude(p.longitude),
                    "houses": dict(p.houses),
                    "dignity": p.dignity,
                }
                for key, p in self.positions.items()
            },
            "aspects": [
                {
                    "a": hit.body_a,
                    "b": hit.body_b,
                    "aspect": hit.aspect.key,
                    "angle": hit.aspect.angle,
                    "orb": hit.orb,
                    "limit": hit.limit,
                    "applying": hit.applying,
                    "strength": hit.strength,
                }
                for hit in self.aspects
            ],
            "angle_aspects": [
                {
                    "a": hit.body_a,
                    "b": hit.body_b,
                    "aspect": hit.aspect.key,
                    "orb": hit.orb,
                }
                for hit in self.angle_aspects
            ],
            "dispositors": {
                "immediate": dict(self.dispositors.dispositor),
                "cycles": [list(c) for c in self.dispositors.cycles],
                "final": list(self.dispositors.final_dispositors),
                "mutual_receptions": [list(p) for p in self.dispositors.mutual_receptions],
            },
            "patterns": [
                {
                    "key": hit.key,
                    "name": hit.name,
                    "bodies": list(hit.bodies),
                    "worst_orb": hit.worst_orb,
                }
                for hit in self.patterns
            ],
            "stelliums": [
                {
                    "bodies": list(item.bodies),
                    "sign_index": item.sign_index,
                    "by_conjunction": item.by_conjunction,
                }
                for item in self.stelliums
            ],
            "antiscia": [
                {"a": hit.body_a, "b": hit.body_b, "kind": hit.kind, "orb": hit.orb}
                for hit in self.antiscia
            ],
            "dignities": {
                key: {
                    "state": item.state,
                    "own": list(item.own),
                    "ruler": item.ruler,
                    "triplicity": item.triplicity,
                    "term": item.term,
                    "decan": item.decan,
                    "peregrine": item.peregrine,
                }
                for key, item in self.dignities.items()
            },
            "chart_ruler": self.chart_ruler,
            "diurnal": self.diurnal,
            "lilith_model": self.lilith_model,
        }
        if include_birth_data:
            data["birth"] = {
                "utc": self.moment.utc.isoformat(),
                "local": self.moment.local.isoformat(),
                "zone": self.moment.zone,
                "offset_hours": self.moment.offset_hours,
                "latitude": self.place.latitude,
                "longitude": self.place.longitude,
                "place": self.place.name,
            }
        return data


def compute(
    local_time: datetime,
    place: Place,
    zone: Optional[str] = None,
    utc_offset_hours: Optional[float] = None,
    fold: int = 0,
    body_keys: Optional[Tuple[str, ...]] = None,
    house_systems: Sequence[str] = (houses_mod.WHOLE_SIGN, houses_mod.PLACIDUS),
    primary_system: Optional[str] = None,
    house_fallback: Optional[str] = None,
    aspect_set: Optional[Sequence[aspects_mod.Aspect]] = None,
    orb_policy: aspects_mod.OrbPolicy = aspects_mod.DEFAULT_ORBS,
    ruler_scheme: str = rulers_mod.TRADITIONAL,
    lilith_model: str = nodes_mod.LILITH_SWISS,
    antiscia_orb: float = 1.0,
    ephemeris: Optional[Ephemeris] = None,
) -> Chart:
    """Считает натальную карту на местное гражданское время."""
    moment = timeutil.resolve(
        local_time,
        place.latitude,
        place.longitude,
        zone=zone,
        utc_offset_hours=utc_offset_hours,
        fold=fold,
    )
    return compute_at(
        moment,
        place,
        body_keys=body_keys,
        house_systems=house_systems,
        primary_system=primary_system,
        house_fallback=house_fallback,
        aspect_set=aspect_set,
        orb_policy=orb_policy,
        ruler_scheme=ruler_scheme,
        lilith_model=lilith_model,
        antiscia_orb=antiscia_orb,
        ephemeris=ephemeris,
    )


def compute_at(
    moment: timeutil.Moment,
    place: Place,
    body_keys: Optional[Tuple[str, ...]] = None,
    house_systems: Sequence[str] = (houses_mod.WHOLE_SIGN, houses_mod.PLACIDUS),
    primary_system: Optional[str] = None,
    house_fallback: Optional[str] = None,
    aspect_set: Optional[Sequence[aspects_mod.Aspect]] = None,
    orb_policy: aspects_mod.OrbPolicy = aspects_mod.DEFAULT_ORBS,
    ruler_scheme: str = rulers_mod.TRADITIONAL,
    lilith_model: str = nodes_mod.LILITH_SWISS,
    antiscia_orb: float = 1.0,
    ephemeris: Optional[Ephemeris] = None,
) -> Chart:
    """Считает карту на уже разрешённый момент времени."""
    eph = ephemeris if ephemeris is not None else load_ephemeris()
    t = moment.t

    selected = bodies_mod.resolve(body_keys)
    if body_keys is None:
        # Необязательные тела входят в карту, только если для них есть файл
        # эфемериды: отсутствие Хирона не должно ронять расчёт.
        selected = selected + tuple(
            body for body in bodies_mod.OPTIONAL_BODIES if eph.has(body)
        )
    raw: Dict[str, RawPosition] = {}
    for body in selected:
        if body.kind == "lot":
            continue  # считается ниже, после углов
        if nodes_mod.is_lunar_point(body):
            raw[body.key] = nodes_mod.position(body, eph, t, lilith_model)
        else:
            raw[body.key] = eph.position(body, t)

    chart_angles = angles_mod.compute(t, place.latitude, place.longitude)

    # Секта нужна и жребиям, и триплицитетам, поэтому считается всегда, как
    # только в карте есть Солнце.
    diurnal = None
    if bodies_mod.SUN.key in raw:
        diurnal = lots_mod.is_diurnal(raw[bodies_mod.SUN.key].longitude, chart_angles.asc)

    # Жребии зависят от Асцендента, поэтому считаются после углов.
    if bodies_mod.PART_OF_FORTUNE in selected:
        if bodies_mod.SUN.key not in raw or bodies_mod.MOON.key not in raw:
            raise ValueError("для Части Фортуны нужны Солнце и Луна в составе карты")
        sun_longitude = raw[bodies_mod.SUN.key].longitude
        moon_longitude = raw[bodies_mod.MOON.key].longitude
        raw[bodies_mod.PART_OF_FORTUNE.key] = RawPosition(
            longitude=lots_mod.part_of_fortune(
                chart_angles.asc, sun_longitude, moon_longitude, diurnal
            ),
            latitude=0.0,
            distance=float("nan"),
            # Жребий движется вместе с Асцендентом, то есть примерно градус
            # в четыре минуты. Такая скорость не описывает движение среди
            # знаков, и схождение аспектов по ней считать бессмысленно,
            # поэтому здесь она нулевая.
            speed=0.0,
        )

    if not house_systems:
        raise ValueError("нужна хотя бы одна система домов")
    built: Dict[str, houses_mod.Houses] = {}
    for system in house_systems:
        built[system] = houses_mod.build(
            system, chart_angles, place.latitude, fallback=house_fallback
        )
    primary = primary_system if primary_system is not None else house_systems[0]
    if primary not in built:
        raise ValueError(f"основная система домов не рассчитана: {primary!r}")

    positions: Dict[str, PlanetPosition] = {}
    for body in selected:
        item = raw[body.key]
        sign_index = to_sign(item.longitude).sign_index
        positions[body.key] = PlanetPosition(
            body=body,
            longitude=item.longitude,
            latitude=item.latitude,
            distance=item.distance,
            speed=item.speed,
            houses={name: h.house_of(item.longitude) for name, h in built.items()},
            primary_system=primary,
            dignity=rulers_mod.dignity(body.key, sign_index, ruler_scheme),
        )

    chosen_aspects = tuple(aspect_set) if aspect_set is not None else aspects_mod.MAJOR
    hits = aspects_mod.find_all(
        positions, aspects=chosen_aspects, policy=orb_policy,
        order=[b.key for b in selected],
    )

    angle_targets = {"asc": chart_angles.asc, "mc": chart_angles.mc}
    angle_hits = []
    for body in selected:
        item = raw[body.key]
        angle_hits.extend(
            aspects_mod.to_angles(
                item.longitude, item.speed, body.key, angle_targets,
                aspects=chosen_aspects, policy=orb_policy,
            )
        )
    angle_hits.sort(key=lambda h: h.orb)

    dispositors = rulers_mod.build_dispositors(
        {key: to_sign(p.longitude).sign_index for key, p in positions.items()},
        scheme=ruler_scheme,
        bodies=[b.key for b in selected],
    )

    figures = patterns_mod.find_patterns(hits)
    stelliums = patterns_mod.find_stelliums(positions, hits)
    antiscia = patterns_mod.find_antiscia(
        positions, orb=antiscia_orb, order=[b.key for b in selected]
    )

    # Достоинства определены для тел, а не для расчётных точек: у узлов,
    # Лилит и жребиев нет ни обители, ни экзальтации.
    dignities = {}
    if diurnal is not None:
        dignities = {
            key: rulers_mod.essential_dignities(
                key, position.longitude, diurnal, ruler_scheme
            )
            for key, position in positions.items()
            if position.body.kind in ("planet", "luminary", "asteroid")
        }

    return Chart(
        moment=moment,
        place=place,
        angles=chart_angles,
        houses=built,
        primary_system=primary,
        positions=positions,
        aspects=hits,
        angle_aspects=tuple(angle_hits),
        dispositors=dispositors,
        patterns=figures,
        stelliums=stelliums,
        antiscia=antiscia,
        dignities=dignities,
        ruler_scheme=ruler_scheme,
        ephemeris=eph.name,
        diurnal=diurnal,
        lilith_model=lilith_model,
    )
