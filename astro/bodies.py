"""Каталог небесных тел и расчётных точек."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class Body:
    """Описание точки карты.

    ``targets`` — идентификаторы NAIF в порядке предпочтения. Для Меркурия
    и Венеры в ядрах JPL есть и центр планеты (199/299), и барицентр
    системы (1/2); они совпадают, потому что спутников нет. Для внешних
    планет доступен только барицентр системы, и это стандартная практика
    астрологических эфемерид: смещение барицентра от центра планеты
    меньше секунды дуги в геоцентрической проекции.
    """

    key: str
    name: str
    glyph: str
    targets: Tuple[int, ...] = ()
    kind: str = "planet"  # planet | luminary | point


SUN = Body("sun", "Солнце", "☉", (10,), kind="luminary")
MOON = Body("moon", "Луна", "☽", (301,), kind="luminary")
MERCURY = Body("mercury", "Меркурий", "☿", (199, 1))
VENUS = Body("venus", "Венера", "♀", (299, 2))
MARS = Body("mars", "Марс", "♂", (499, 4))
JUPITER = Body("jupiter", "Юпитер", "♃", (5,))
SATURN = Body("saturn", "Сатурн", "♄", (6,))
URANUS = Body("uranus", "Уран", "♅", (7,))
NEPTUNE = Body("neptune", "Нептун", "♆", (8,))
PLUTO = Body("pluto", "Плутон", "♇", (9,))

# Расчётные точки — считаются не из ядра, а из орбиты Луны.
MEAN_NODE = Body("mean_node", "Средний Узел", "☊", kind="point")
TRUE_NODE = Body("true_node", "Истинный Узел", "☊", kind="point")
MEAN_LILITH = Body("mean_lilith", "Лилит (средняя)", "⚸", kind="point")

#: Семь видимых планет традиционной астрологии.
CLASSICAL = (SUN, MOON, MERCURY, VENUS, MARS, JUPITER, SATURN)

#: Тела, читаемые напрямую из эфемерид.
EPHEMERIS_BODIES = CLASSICAL + (URANUS, NEPTUNE, PLUTO)

#: Расчётные точки лунной орбиты.
LUNAR_POINTS = (MEAN_NODE, TRUE_NODE, MEAN_LILITH)

#: Состав карты по умолчанию: истинный Узел, без среднего.
DEFAULT_BODIES = EPHEMERIS_BODIES + (TRUE_NODE, MEAN_LILITH)

ALL_BODIES = EPHEMERIS_BODIES + LUNAR_POINTS

BY_KEY = {b.key: b for b in ALL_BODIES}


def get(key: str) -> Body:
    """Находит тело по ключу."""
    try:
        return BY_KEY[key]
    except KeyError:
        raise KeyError(f"неизвестное тело: {key!r}") from None


def resolve(keys: Optional[Tuple[str, ...]]) -> Tuple[Body, ...]:
    """Превращает список ключей в список тел (None — состав по умолчанию)."""
    if keys is None:
        return DEFAULT_BODIES
    return tuple(get(k) for k in keys)
