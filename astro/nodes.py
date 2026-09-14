"""Лунные узлы и Лилит.

Три точки считаются не из ядра эфемерид, а из орбиты Луны:

* средний Узел и средняя Лилит — по полиномам лунной теории (Meeus,
  "Astronomical Algorithms", гл. 47);
* истинный Узел — из мгновенного (оскулирующего) вектора состояния Луны.

Средние элементы — это сглаженная орбита, поэтому значения совпадают со
Swiss Ephemeris не до секунды: расхождение по узлу порядка секунд дуги,
по Лилит — до нескольких минут дуги, потому что разные программы берут
разные редакции лунной теории. Истинный Узел воспроизводится точно, он
определяется геометрией, а не выбором полинома.
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

from .bodies import Body, MEAN_LILITH, MEAN_NODE, SOUTH_NODE, TRUE_NODE
from .ephemeris import Ephemeris, RawPosition
from .zodiac import norm360

#: Юлианская дата эпохи J2000.0 в шкале TT.
J2000 = 2451545.0

_SPEED_STEP = 1.0 / 24.0  # сутки


def _centuries(jd_tt: float) -> float:
    """Юлианские столетия от J2000.

    Приведение к float здесь не косметика: время приходит из Skyfield в
    виде numpy-скаляра, и без него numpy-типы расходятся по всем полиномам
    и всплывают уже на сериализации результата.
    """
    return (float(jd_tt) - J2000) / 36525.0


def mean_node_longitude(jd_tt: float) -> float:
    """Долгота среднего восходящего Узла, градусы (Meeus 47.7)."""
    t = _centuries(jd_tt)
    omega = (
        125.0445479
        - 1934.1362891 * t
        + 0.0020754 * t * t
        + t ** 3 / 467441.0
        - t ** 4 / 60616000.0
    )
    return norm360(omega)


#: Модели средней Лилит.
LILITH_MEEUS = "meeus"
LILITH_SWISS = "swiss"
LILITH_MODELS = (LILITH_MEEUS, LILITH_SWISS)

#: Постоянная поправка ряда, угловые секунды.
_APOGEE_CONSTANT = 0.7174

#: Периодические поправки к простому полиному апогея: множители при
#: D, M, M', F и амплитуды при синусе и косинусе аргумента, в угловых
#: секундах. Главный член — чистый синус аргумента 2(F − M'), то есть
#: удвоенной разности долгот узла и перигея, с амплитудой почти 7 угловых
#: минут; остальные на два порядка меньше.
_APOGEE_TERMS = (
    (0, 0, -2, 2, -416.4319, 0.0010),
    (-1, -1, 0, 1, 3.8266, 16.7607),
    (0, -2, 0, 0, -1.1850, 0.5750),
    (0, -1, -2, 2, 0.1522, 0.3719),
    (-2, -2, 0, 0, -0.2047, 0.0989),
    (-2, -2, 0, 2, 0.1936, -0.0914),
    (0, -1, 0, 0, -0.1293, -0.0085),
    (-2, -2, 1, 1, 0.0321, -0.0669),
    (0, 0, -1, 0, -0.0711, -0.0001),
    (0, -3, 0, 0, -0.0465, 0.0225),
)


def lunar_arguments(jd_tt: float) -> Tuple[float, float, float, float]:
    """Средние аргументы лунной теории в радианах: D, M, M', F (Meeus 47.2–47.5)."""
    t = _centuries(jd_tt)
    elongation = (
        297.8501921 + 445267.1114034 * t - 0.0018819 * t ** 2
        + t ** 3 / 545868.0 - t ** 4 / 113065000.0
    )
    solar_anomaly = (
        357.5291092 + 35999.0502909 * t - 0.0001536 * t ** 2 + t ** 3 / 24490000.0
    )
    lunar_anomaly = (
        134.9633964 + 477198.8675055 * t + 0.0087414 * t ** 2
        + t ** 3 / 69699.0 - t ** 4 / 14712000.0
    )
    latitude_argument = (
        93.2720950 + 483202.0175233 * t - 0.0036539 * t ** 2
        - t ** 3 / 3526000.0 + t ** 4 / 863310000.0
    )
    return (
        math.radians(elongation),
        math.radians(solar_anomaly),
        math.radians(lunar_anomaly),
        math.radians(latitude_argument),
    )


def _polynomial_apogee(jd_tt: float) -> float:
    """Апогей по простому полиному: средняя долгота минус средняя аномалия."""
    t = _centuries(jd_tt)
    mean_longitude = (
        218.3164477
        + 481267.88123421 * t
        - 0.0015786 * t * t
        + t ** 3 / 538841.0
        - t ** 4 / 65194000.0
    )
    mean_anomaly = (
        134.9633964
        + 477198.8675055 * t
        + 0.0087414 * t * t
        + t ** 3 / 69699.0
        - t ** 4 / 14712000.0
    )
    return mean_longitude - mean_anomaly + 180.0


def mean_lilith_longitude(jd_tt: float, model: str = LILITH_SWISS) -> float:
    """Долгота средней Лилит — среднего апогея лунной орбиты, градусы.

    Основа у обеих моделей одна: долгота перигея как разность средней
    долготы Луны и её средней аномалии (Meeus 47.1 и 47.4), развёрнутая на
    полуоборот.

    ``meeus`` оставляет этот полином как есть. ``swiss`` добавляет ряд
    периодических поправок и совпадает со средним апогеем Swiss Ephemeris
    и построенных на нём программ — расхождение около 0.6″ на интервале
    1850–2150 и до 2.5″ за его пределами. Разница между моделями доходит
    до 7 угловых минут, так что выбор здесь не косметический.

    Ряд поправок получен разложением расхождения по средним аргументам
    лунной теории. Это числовые коэффициенты физической величины, кода
    Swiss Ephemeris в них нет, и самой библиотеки среди зависимостей тоже.
    """
    if model not in LILITH_MODELS:
        raise ValueError(f"неизвестная модель Лилит: {model!r}")

    longitude = _polynomial_apogee(jd_tt)
    if model == LILITH_MEEUS:
        return norm360(longitude)

    elongation, solar, lunar, latitude = lunar_arguments(jd_tt)
    correction = _APOGEE_CONSTANT
    for factor_d, factor_m, factor_mp, factor_f, sine, cosine in _APOGEE_TERMS:
        argument = (
            factor_d * elongation
            + factor_m * solar
            + factor_mp * lunar
            + factor_f * latitude
        )
        correction += sine * math.sin(argument) + cosine * math.cos(argument)
    return norm360(longitude + correction / 3600.0)


def true_node_longitude(eph: Ephemeris, t) -> float:
    """Долгота истинного (оскулирующего) восходящего Узла, градусы.

    Узел — пересечение мгновенной плоскости орбиты Луны с эклиптикой.
    Нормаль к плоскости орбиты — момент импульса h = r × v; линия узлов
    перпендикулярна и ей, и оси эклиптики, откуда Ω = atan2(h_x, −h_y).
    """
    r, v = eph.moon_state(t)
    hx = r[1] * v[2] - r[2] * v[1]
    hy = r[2] * v[0] - r[0] * v[2]
    return norm360(math.degrees(math.atan2(hx, -hy)))


def _numeric_speed(fn, eph: Ephemeris, t) -> float:
    """Скорость расчётной точки по долготе, градусов в сутки."""
    h = _SPEED_STEP
    t_minus = eph.ts.tt_jd(t.tt - h)
    t_plus = eph.ts.tt_jd(t.tt + h)
    delta = (fn(eph, t_plus) - fn(eph, t_minus) + 180.0) % 360.0 - 180.0
    return float(delta / (2.0 * h))


def _mean_node(eph: Ephemeris, t) -> float:
    return mean_node_longitude(t.tt)


def _mean_lilith(eph: Ephemeris, t, model: str = LILITH_SWISS) -> float:
    return mean_lilith_longitude(t.tt, model)


def _south_node(eph: Ephemeris, t) -> float:
    return norm360(true_node_longitude(eph, t) + 180.0)


_POINTS = {
    MEAN_NODE.key: _mean_node,
    TRUE_NODE.key: true_node_longitude,
    SOUTH_NODE.key: _south_node,
    MEAN_LILITH.key: _mean_lilith,
}


def is_lunar_point(body: Body) -> bool:
    """Считается ли тело из орбиты Луны, а не из ядра эфемерид."""
    return body.key in _POINTS


def position(
    body: Body, eph: Ephemeris, t, lilith_model: str = LILITH_SWISS
) -> RawPosition:
    """Положение расчётной точки: долгота, скорость, нулевая широта.

    Широта у всех этих точек равна нулю по определению: узлы лежат на
    эклиптике, а средняя Лилит — это долгота апогея, спроецированная на
    эклиптику.
    """
    fn = _POINTS[body.key]
    if body.key == MEAN_LILITH.key:
        fn = lambda e, time: _mean_lilith(e, time, lilith_model)  # noqa: E731
    longitude = fn(eph, t)
    speed = _numeric_speed(fn, eph, t)
    return RawPosition(longitude, 0.0, float("nan"), speed)


def south_node(longitude: float) -> float:
    """Долгота нисходящего Узла — противоположная точка."""
    return norm360(longitude + 180.0)


def node_pair(eph: Ephemeris, t, true: bool = True) -> Tuple[float, float]:
    """Пара (северный, южный) Узел."""
    north = true_node_longitude(eph, t) if true else mean_node_longitude(t.tt)
    return north, south_node(north)
