"""События неба: станции, аспекты между планетами, входы в знаки, лунации.

Это то, о чём говорят «сейчас в небе»: Уран развернулся, Сатурн сошёлся с
Нептуном, Плутон вошёл в Водолей. События ищутся численно — по смене
знака у нужной величины, — а затем момент уточняется делением отрезка,
поэтому даты выходят с точностью до минут.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from . import aspects as aspects_mod
from . import bodies as bodies_mod
from . import nodes as nodes_mod
from .zodiac import norm180, norm360, to_sign

#: Тела, у которых бывают станции.
STATION_BODIES = (
    "mercury", "venus", "mars", "jupiter", "saturn", "uranus", "neptune", "pluto",
)

#: Пары, чьи схождения обычно и обсуждают. Быстрые пары дают десятки
#: событий в год и тонут в шуме, поэтому Луна сюда не входит вовсе.
ASPECT_PAIRS = (
    ("jupiter", "saturn"), ("jupiter", "uranus"), ("jupiter", "neptune"),
    ("jupiter", "pluto"), ("saturn", "uranus"), ("saturn", "neptune"),
    ("saturn", "pluto"), ("uranus", "neptune"), ("uranus", "pluto"),
    ("neptune", "pluto"), ("mars", "saturn"), ("mars", "uranus"),
    ("mars", "pluto"), ("venus", "jupiter"), ("venus", "saturn"),
)

#: Медленные тела, у которых вход в знак — событие сам по себе.
INGRESS_BODIES = ("jupiter", "saturn", "uranus", "neptune", "pluto", "true_node")

#: Аспекты, схождение по которым считается событием.
EVENT_ASPECTS = ("conjunction", "opposition", "square", "trine", "sextile")

#: Широта Луны, ниже которой лунация становится затмением. Величины
#: приблизительные: точный расчёт требует размеров тени, а для календаря
#: достаточно знать, что затмение в этот день есть.
SOLAR_ECLIPSE_LATITUDE = 1.4
LUNAR_ECLIPSE_LATITUDE = 1.0


@dataclass(frozen=True)
class SkyEvent:
    """Событие в небе."""

    kind: str                 # station | aspect | ingress | lunation
    jd: float                 # момент в шкале TT
    title: str                # как назвать по-русски
    bodies: Tuple[str, ...]
    longitude: float          # градус, вокруг которого всё происходит
    detail: Dict[str, object]

    @property
    def sign(self) -> int:
        return to_sign(self.longitude).sign_index

    def key(self) -> str:
        """Устойчивый ключ события — по нему подбирается трактовка."""
        if self.kind == "station":
            return f"station.{self.bodies[0]}.{self.detail['direction']}"
        if self.kind == "aspect":
            return f"aspect.{'.'.join(self.bodies)}.{self.detail['aspect']}"
        if self.kind == "ingress":
            return f"ingress.{self.bodies[0]}.{self.sign}"
        return f"lunation.{self.detail['phase']}" + (
            f".{self.detail['eclipse']}" if self.detail.get("eclipse") else ""
        )


def _refine(function: Callable[[float], float], low: float, high: float,
            iterations: int = 60) -> float:
    """Уточняет момент смены знака делением отрезка."""
    value_low = function(low)
    for _ in range(iterations):
        middle = 0.5 * (low + high)
        value_middle = function(middle)
        if value_low * value_middle <= 0:
            high = middle
        else:
            low, value_low = middle, value_middle
    return 0.5 * (low + high)


def _scan(function: Callable[[float], float], jd_start: float, jd_end: float,
          step: float, max_jump: float = 90.0) -> Iterable[float]:
    """Находит все смены знака на интервале.

    Смена знака бывает двух видов, и различать их обязательно. Настоящий
    корень — функция плавно прошла через ноль. Ложный — функция разорвалась
    на границе круга, перескочив с +180 на −180: так, при прохождении Марса
    мимо Плутона отклонение от любого угла скачком меняет знак, и без
    проверки в календарь попадают соединение, квадрат, трин и секстиль
    одной и той же минутой. Отличаются они величиной скачка.
    """
    previous_jd = jd_start
    previous = function(jd_start)
    jd = jd_start + step
    while jd <= jd_end:
        current = function(jd)
        if previous == 0.0:
            yield previous_jd
        elif previous * current < 0 and abs(current - previous) < max_jump:
            yield _refine(function, previous_jd, jd)
        previous_jd, previous = jd, current
        jd += step
    return


def _longitude(eph, key: str, jd: float) -> float:
    body = bodies_mod.get(key)
    t = eph.ts.tt_jd(jd)
    if nodes_mod.is_lunar_point(body):
        return nodes_mod.position(body, eph, t).longitude
    return eph.ecliptic(body, t)[0]


def find_stations(eph, jd_start: float, jd_end: float,
                  keys: Sequence[str] = STATION_BODIES) -> List[SkyEvent]:
    """Моменты, когда планета останавливается и меняет направление."""
    events: List[SkyEvent] = []
    for key in keys:
        body = bodies_mod.get(key)
        speed = lambda jd, b=body: eph.longitude_speed(b, eph.ts.tt_jd(jd))  # noqa: E731
        # Шаг подбирается так, чтобы не проскочить петлю: у Меркурия она
        # длится недели, у внешних планет — месяцы.
        step = 1.0 if key in ("mercury", "venus", "mars") else 3.0
        for jd in _scan(speed, jd_start, jd_end, step):
            after = speed(jd + step)
            direction = "retrograde" if after < 0 else "direct"
            longitude = _longitude(eph, key, jd)
            events.append(SkyEvent(
                kind="station", jd=jd,
                title=f"{body.name} {'уходит в ретроград' if direction == 'retrograde' else 'выходит из ретрограда'}",
                bodies=(key,), longitude=longitude,
                detail={"direction": direction},
            ))
    return events


def find_aspects(eph, jd_start: float, jd_end: float,
                 pairs: Sequence[Tuple[str, str]] = ASPECT_PAIRS,
                 aspect_keys: Sequence[str] = EVENT_ASPECTS) -> List[SkyEvent]:
    """Моменты точных аспектов между планетами."""
    events: List[SkyEvent] = []
    for first, second in pairs:
        body_a = bodies_mod.get(first)
        body_b = bodies_mod.get(second)
        for aspect_key in aspect_keys:
            aspect = aspects_mod.BY_KEY[aspect_key]

            def difference(jd, a=first, b=second, angle=aspect.angle):
                delta = norm180(_longitude(eph, a, jd) - _longitude(eph, b, jd))
                target = angle if delta >= 0 else -angle
                return norm180(delta - target)

            # Шаг в пять суток: за него даже Марс не проскакивает аспект,
            # а разворот пары ловится сменой знака отклонения.
            for jd in _scan(difference, jd_start, jd_end, 5.0):
                longitude = _longitude(eph, first, jd)
                events.append(SkyEvent(
                    kind="aspect", jd=jd,
                    title=f"{body_a.name} {aspect.name.lower()} {body_b.name}",
                    bodies=(first, second), longitude=longitude,
                    detail={
                        "aspect": aspect_key,
                        "longitude_b": _longitude(eph, second, jd),
                    },
                ))
    return events


def find_ingresses(eph, jd_start: float, jd_end: float,
                   keys: Sequence[str] = INGRESS_BODIES) -> List[SkyEvent]:
    """Моменты входа планеты в новый знак."""
    events: List[SkyEvent] = []
    for key in keys:
        body = bodies_mod.get(key)
        step = 2.0
        previous_sign = to_sign(_longitude(eph, key, jd_start)).sign_index
        jd = jd_start + step
        while jd <= jd_end:
            sign = to_sign(_longitude(eph, key, jd)).sign_index
            if sign != previous_sign:
                boundary = sign * 30.0

                def offset(moment, b=boundary, k=key):
                    return norm180(_longitude(eph, k, moment) - b)

                exact = _refine(offset, jd - step, jd)
                events.append(SkyEvent(
                    kind="ingress", jd=exact,
                    title=f"{body.name} входит в знак {to_sign(boundary).sign}",
                    bodies=(key,), longitude=boundary,
                    detail={"from_sign": previous_sign, "to_sign": sign},
                ))
                previous_sign = sign
            jd += step
    return events


def find_lunations(eph, jd_start: float, jd_end: float) -> List[SkyEvent]:
    """Новолуния и полнолуния, с пометкой затмений."""
    sun = bodies_mod.SUN
    moon = bodies_mod.MOON

    def elongation(jd):
        t = eph.ts.tt_jd(jd)
        return norm180(eph.ecliptic(moon, t)[0] - eph.ecliptic(sun, t)[0])

    def opposition(jd):
        return norm180(elongation(jd) - 180.0)

    events: List[SkyEvent] = []
    for phase, function, name in (
        ("new", elongation, "Новолуние"),
        ("full", opposition, "Полнолуние"),
    ):
        for jd in _scan(function, jd_start, jd_end, 2.0):
            t = eph.ts.tt_jd(jd)
            longitude, latitude, _ = eph.ecliptic(moon, t)
            limit = SOLAR_ECLIPSE_LATITUDE if phase == "new" else LUNAR_ECLIPSE_LATITUDE
            eclipse = None
            if abs(latitude) <= limit:
                eclipse = "solar" if phase == "new" else "lunar"
            title = name
            if eclipse:
                title = "Солнечное затмение" if eclipse == "solar" else "Лунное затмение"
            events.append(SkyEvent(
                kind="lunation", jd=jd, title=title,
                bodies=("moon", "sun"),
                longitude=eph.ecliptic(sun, t)[0] if phase == "new" else longitude,
                detail={"phase": phase, "eclipse": eclipse,
                        "moon_latitude": latitude},
            ))
    return events


def collect(eph, jd_start: float, jd_end: float,
            kinds: Optional[Sequence[str]] = None) -> List[SkyEvent]:
    """Все события на интервале, по возрастанию даты."""
    wanted = set(kinds or ("station", "aspect", "ingress", "lunation"))
    events: List[SkyEvent] = []
    if "station" in wanted:
        events.extend(find_stations(eph, jd_start, jd_end))
    if "aspect" in wanted:
        events.extend(find_aspects(eph, jd_start, jd_end))
    if "ingress" in wanted:
        events.extend(find_ingresses(eph, jd_start, jd_end))
    if "lunation" in wanted:
        events.extend(find_lunations(eph, jd_start, jd_end))
    events.sort(key=lambda event: event.jd)
    return events
