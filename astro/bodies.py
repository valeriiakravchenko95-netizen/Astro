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
    kind: str = "planet"  # planet | luminary | point | lot | asteroid
    #: Короткое имя для узких экранов; по умолчанию совпадает с полным.
    short_name: str = ""
    #: Порог стоянки в градусах за сутки. Задаётся отдельно для каждого
    #: тела, потому что одна общая величина бессмысленна: минута дуги в
    #: сутки для Меркурия — почти остановка, а для Урана обычный ход.
    #: Ноль означает, что тело не бывает попятным и не имеет стоянок.
    stationary_limit: float = 0.0

    def __post_init__(self) -> None:
        if not self.short_name:
            object.__setattr__(self, "short_name", self.name)


SUN = Body("sun", "Солнце", "☉", (10,), kind="luminary")
MOON = Body("moon", "Луна", "☽", (301,), kind="luminary")
MERCURY = Body("mercury", "Меркурий", "☿", (199, 1), stationary_limit=0.03)
VENUS = Body("venus", "Венера", "♀", (299, 2), stationary_limit=0.012)
MARS = Body("mars", "Марс", "♂", (499, 4), stationary_limit=0.008)
JUPITER = Body("jupiter", "Юпитер", "♃", (5,), stationary_limit=0.003)
SATURN = Body("saturn", "Сатурн", "♄", (6,), stationary_limit=0.0016)
URANUS = Body("uranus", "Уран", "♅", (7,), stationary_limit=0.0008)
NEPTUNE = Body("neptune", "Нептун", "♆", (8,), stationary_limit=0.0006)
PLUTO = Body("pluto", "Плутон", "♇", (9,), stationary_limit=0.0005)

# Малые тела в ядрах DE отсутствуют и читаются из отдельных файлов,
# которые готовит scripts/fetch_chiron.py. Код NAIF нумерованного
# астероида — это 2000000 плюс его номер.
CHIRON = Body("chiron", "Хирон", "\u26b7", (2002060,), kind="asteroid", stationary_limit=0.0008)

# Расчётные точки — считаются не из ядра, а из орбиты Луны.
MEAN_NODE = Body("mean_node", "Средний Узел", "☊", kind="point", short_name="Ср. Узел")
TRUE_NODE = Body("true_node", "Истинный Узел", "☊", kind="point", short_name="Сев. Узел", stationary_limit=0.001)
MEAN_LILITH = Body("mean_lilith", "Лилит (средняя)", "⚸", kind="point", short_name="Лилит")
SOUTH_NODE = Body("south_node", "Нисходящий Узел", "\u260b", kind="point", short_name="Юж. Узел", stationary_limit=0.001)

# Жребий Фортуны считается из углов карты, а не из положения тел,
# поэтому стоит особняком: без Асцендента его не существует.
PART_OF_FORTUNE = Body("part_of_fortune", "Часть Фортуны", "\u2297", kind="lot", short_name="Фортуна")

#: Семь видимых планет традиционной астрологии.
CLASSICAL = (SUN, MOON, MERCURY, VENUS, MARS, JUPITER, SATURN)

#: Тела, читаемые напрямую из эфемерид.
EPHEMERIS_BODIES = CLASSICAL + (URANUS, NEPTUNE, PLUTO)

#: Расчётные точки лунной орбиты.
LUNAR_POINTS = (MEAN_NODE, TRUE_NODE, SOUTH_NODE, MEAN_LILITH)

#: Жребии — считаются от углов карты.
LOTS = (PART_OF_FORTUNE,)

#: Тела, которые попадают в карту только если для них есть файл эфемериды.
OPTIONAL_BODIES = (CHIRON,)

#: Состав карты по умолчанию: истинный Узел, без среднего.
DEFAULT_BODIES = EPHEMERIS_BODIES + (
    TRUE_NODE, SOUTH_NODE, MEAN_LILITH, PART_OF_FORTUNE,
)

ALL_BODIES = EPHEMERIS_BODIES + LUNAR_POINTS + LOTS + OPTIONAL_BODIES

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
