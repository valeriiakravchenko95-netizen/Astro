"""Системы домов: целые знаки и Плацидус.

Реализованы две системы, заказанные для ядра:

* **Целые знаки** (whole sign) — первый дом занимает весь знак Асцендента,
  дальше по знаку на дом. Куспиды всегда в 0° знака.
* **Плацидус** — деление суточного пути точки эклиптики на три равные
  части по времени. Система нелинейная, куспиды ищутся итеративно и за
  полярным кругом не существуют вовсе.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Optional, Tuple

from .angles import (
    Angles,
    ecliptic_declination,
    longitude_from_right_ascension,
)
from .zodiac import norm180, norm360

WHOLE_SIGN = "whole_sign"
PLACIDUS = "placidus"
PORPHYRY = "porphyry"

SYSTEM_NAMES = {
    WHOLE_SIGN: "Целые знаки",
    PLACIDUS: "Плацидус",
    PORPHYRY: "Порфирий",
}


class HouseError(ValueError):
    """Дома не могут быть построены для заданных условий."""


class CircumpolarError(HouseError):
    """Точка эклиптики не восходит и не заходит — Плацидус не определён.

    Возникает за полярным кругом (|широта| > 90° − ε): часть эклиптики
    становится незаходящей, у неё нет полусуточной дуги, а значит нет и
    того пути, который Плацидус делит на три части.
    """


@dataclass(frozen=True)
class Houses:
    """Двенадцать куспидов в порядке домов, cusps[0] — куспид первого дома."""

    system: str
    cusps: Tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.cusps) != 12:
            raise ValueError("нужно ровно 12 куспидов")

    @property
    def system_name(self) -> str:
        return SYSTEM_NAMES.get(self.system, self.system)

    def cusp(self, house: int) -> float:
        """Долгота куспида дома 1..12."""
        if not 1 <= house <= 12:
            raise ValueError(f"дом вне диапазона 1..12: {house}")
        return self.cusps[house - 1]

    def house_of(self, longitude: float) -> int:
        """Номер дома, в котором лежит долгота.

        Дом — дуга от своего куспида (включительно) до следующего.
        """
        lon = norm360(longitude)
        for i in range(12):
            start = self.cusps[i]
            width = norm360(self.cusps[(i + 1) % 12] - start)
            if width == 0.0:
                width = 360.0
            if norm360(lon - start) < width:
                return i + 1
        return 12  # недостижимо: дуги покрывают круг целиком

    def widths(self) -> Tuple[float, ...]:
        """Протяжённость каждого дома в градусах."""
        return tuple(
            norm360(self.cusps[(i + 1) % 12] - self.cusps[i]) for i in range(12)
        )


def whole_sign(asc: float) -> Houses:
    """Дома целых знаков: первый дом — знак Асцендента целиком."""
    start = math.floor(norm360(asc) / 30.0) * 30.0
    return Houses(WHOLE_SIGN, tuple(norm360(start + 30.0 * i) for i in range(12)))


def porphyry(asc: float, mc: float) -> Houses:
    """Дома Порфирия: каждый квадрант делится на три равные дуги.

    Здесь она нужна как корректный запасной вариант там, где Плацидус
    математически не существует: Порфирий определён на любой широте.
    """
    desc = norm360(asc + 180.0)
    ic = norm360(mc + 180.0)
    # По зодиаку дома идут ASC -> IC -> DESC -> MC -> ASC, и каждый из
    # четырёх отрезков делится на три. Противоположные квадранты равны,
    # поэтому достаточно двух величин.
    step_asc_ic = norm360(ic - asc) / 3.0   # дома 1, 2, 3 и зеркальные 7, 8, 9
    step_ic_desc = norm360(desc - ic) / 3.0  # дома 4, 5, 6 и зеркальные 10, 11, 12
    cusps = [
        asc,
        norm360(asc + step_asc_ic),
        norm360(asc + 2 * step_asc_ic),
        ic,
        norm360(ic + step_ic_desc),
        norm360(ic + 2 * step_ic_desc),
        desc,
        norm360(desc + step_asc_ic),
        norm360(desc + 2 * step_asc_ic),
        mc,
        norm360(mc + step_ic_desc),
        norm360(mc + 2 * step_ic_desc),
    ]
    return Houses(PORPHYRY, tuple(cusps))


#: Спецификация промежуточных куспидов Плацидуса:
#: номер дома → (доля дуги, дневная ли дуга, начальное приближение в RA).
_PLACIDUS_SPEC = {
    11: (1.0 / 3.0, True, 30.0),
    12: (2.0 / 3.0, True, 60.0),
    2: (2.0 / 3.0, False, 120.0),
    3: (1.0 / 3.0, False, 150.0),
}

_MAX_ITERATIONS = 60
_TOLERANCE = 1e-10  # градусов, примерно 4e-7 угловой секунды


def _semiarc(declination: float, latitude: float) -> float:
    """Полусуточная дуга точки со склонением δ на широте φ, градусы.

    cos(SD) = −tg φ · tg δ. Если модуль правой части больше единицы,
    точка не пересекает горизонт: она либо незаходящая, либо невосходящая.
    """
    cos_sd = -math.tan(math.radians(latitude)) * math.tan(math.radians(declination))
    if cos_sd > 1.0 or cos_sd < -1.0:
        raise CircumpolarError(
            "точка эклиптики не пересекает горизонт на широте "
            f"{latitude:.4f}°: Плацидус здесь не определён"
        )
    return math.degrees(math.acos(cos_sd))


def _placidus_cusp(
    house: int, ramc: float, obliquity: float, latitude: float
) -> float:
    """Ищет один промежуточный куспид Плацидуса итерациями.

    Куспид — точка эклиптики, прошедшая заданную долю своего суточного
    пути. Доля задана, но и полусуточная дуга, и положение точки зависят
    от её склонения, которое само зависит от искомой долготы. Уравнение
    решается простыми итерациями: по текущей оценке долготы считается
    склонение, по нему — дуга, по дуге — часовой угол и новое прямое
    восхождение, из которого получается уточнённая долгота.
    """
    fraction, is_diurnal, initial_offset = _PLACIDUS_SPEC[house]
    longitude = longitude_from_right_ascension(ramc + initial_offset, obliquity)

    damping = 1.0
    for attempt in range(3):
        candidate = longitude
        for _ in range(_MAX_ITERATIONS):
            declination = ecliptic_declination(candidate, obliquity)
            semidiurnal = _semiarc(declination, latitude)
            if is_diurnal:
                hour_angle = -fraction * semidiurnal
            else:
                seminocturnal = 180.0 - semidiurnal
                hour_angle = -(180.0 - fraction * seminocturnal)
            updated = longitude_from_right_ascension(ramc - hour_angle, obliquity)
            step = norm180(updated - candidate)
            candidate = norm360(candidate + damping * step)
            if abs(step) < _TOLERANCE:
                return candidate
        damping *= 0.5  # итерация разошлась — повторяем медленнее

    raise HouseError(
        f"куспид {house} дома не сошёлся на широте {latitude:.4f}°"
    )


def placidus(angles: Angles, latitude: float) -> Houses:
    """Дома Плацидуса.

    Куспиды 10 и 1 — это MC и ASC, куспиды 11, 12, 2 и 3 ищутся
    итеративно, оставшиеся шесть — противоположные точки.
    """
    if abs(latitude) >= 90.0 - angles.obliquity:
        raise CircumpolarError(
            f"широта {latitude:.4f}° лежит за полярным кругом: "
            "система Плацидуса там не определена"
        )

    cusp11 = _placidus_cusp(11, angles.ramc, angles.obliquity, latitude)
    cusp12 = _placidus_cusp(12, angles.ramc, angles.obliquity, latitude)
    cusp2 = _placidus_cusp(2, angles.ramc, angles.obliquity, latitude)
    cusp3 = _placidus_cusp(3, angles.ramc, angles.obliquity, latitude)

    cusps = (
        angles.asc,
        cusp2,
        cusp3,
        angles.ic,
        norm360(cusp11 + 180.0),
        norm360(cusp12 + 180.0),
        angles.desc,
        norm360(cusp2 + 180.0),
        norm360(cusp3 + 180.0),
        angles.mc,
        cusp11,
        cusp12,
    )
    return Houses(PLACIDUS, cusps)


def build(
    system: str,
    angles: Angles,
    latitude: float,
    fallback: Optional[str] = None,
) -> Houses:
    """Строит дома выбранной системы.

    ``fallback`` задаёт систему, на которую разрешено переключиться, если
    запрошенная не определена для этой широты. По умолчанию фолбэка нет:
    молча подменять систему домов хуже, чем сказать об этом.
    """
    builders: dict[str, Callable[[], Houses]] = {
        WHOLE_SIGN: lambda: whole_sign(angles.asc),
        PLACIDUS: lambda: placidus(angles, latitude),
        PORPHYRY: lambda: porphyry(angles.asc, angles.mc),
    }
    if system not in builders:
        raise ValueError(f"неизвестная система домов: {system!r}")
    try:
        return builders[system]()
    except HouseError:
        if fallback is None or fallback == system:
            raise
        return builders[fallback]()
