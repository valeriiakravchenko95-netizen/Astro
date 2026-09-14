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
from typing import Tuple

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


def mean_lilith_longitude(jd_tt: float) -> float:
    """Долгота средней Лилит — среднего апогея лунной орбиты, градусы.

    Апогей = средняя долгота Луны минус средняя аномалия плюс 180°
    (Meeus 47.1 и 47.4): разность даёт долготу перигея, полуоборот
    переводит её в апогей.
    """
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
    return norm360(mean_longitude - mean_anomaly + 180.0)


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
    return delta / (2.0 * h)


def _mean_node(eph: Ephemeris, t) -> float:
    return mean_node_longitude(t.tt)


def _mean_lilith(eph: Ephemeris, t) -> float:
    return mean_lilith_longitude(t.tt)


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


def position(body: Body, eph: Ephemeris, t) -> RawPosition:
    """Положение расчётной точки: долгота, скорость, нулевая широта.

    Широта у всех трёх точек равна нулю по определению: узел лежит на
    эклиптике, а средняя Лилит — это долгота апогея, спроецированная на
    эклиптику.
    """
    fn = _POINTS[body.key]
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
