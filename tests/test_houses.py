"""Дома: целые знаки и Плацидус.

Плацидус проверяется по своему определению, но измеренному независимо:
куспид должен делить реальный суточный путь точки в заданной пропорции.
Моменты восхода и кульминации ищутся численно по высоте, которую считает
Skyfield собственным трактом.
"""

import math

import numpy as np
import pytest
from skyfield.api import Star, wgs84
from skyfield.framelib import ecliptic_frame

from astro import angles, houses
from astro.zodiac import norm360

PLACES = [
    ("Киев", 50.4501, 30.5234, (1987, 7, 14, 7, 25)),
    ("Москва", 55.7558, 37.6173, (2024, 3, 20, 3, 6)),
    ("Сингапур", 1.3521, 103.8198, (2001, 12, 31, 23, 59)),
    ("Буэнос-Айрес", -34.6037, -58.3816, (1966, 2, 2, 6, 0)),
    ("Рейкьявик", 64.1466, -21.9426, (1999, 11, 11, 14, 0)),
]

#: дом → (доля суточной дуги, лежит ли дуга над горизонтом)
PLACIDUS_FRACTIONS = {11: (1 / 3, True), 12: (2 / 3, True), 2: (2 / 3, False), 3: (1 / 3, False)}


def _star_at(longitude, t):
    """Точка эклиптики как неподвижный объект в ICRS."""
    lam = math.radians(longitude)
    vector = ecliptic_frame.rotation_at(t).T @ np.array([math.cos(lam), math.sin(lam), 0.0])
    declination = math.degrees(math.asin(vector[2]))
    right_ascension = math.degrees(math.atan2(vector[1], vector[0])) % 360.0
    return Star(ra_hours=right_ascension / 15.0, dec_degrees=declination)


def _find_root(f, low, high):
    f_low = f(low)
    for _ in range(120):
        middle = 0.5 * (low + high)
        f_middle = f(middle)
        if f_low * f_middle <= 0:
            high = middle
        else:
            low, f_low = middle, f_middle
    return 0.5 * (low + high)


def _find_extremum(f, low, high, maximum):
    ratio = (math.sqrt(5.0) - 1.0) / 2.0
    c, d = high - ratio * (high - low), low + ratio * (high - low)
    for _ in range(120):
        better = f(c) > f(d) if maximum else f(c) < f(d)
        if better:
            high, d = d, c
        else:
            low, c = c, d
        c, d = high - ratio * (high - low), low + ratio * (high - low)
    return 0.5 * (low + high)


@pytest.mark.parametrize("name,latitude,longitude,when", PLACES)
def test_placidus_cusps_split_the_real_diurnal_arc(eph, name, latitude, longitude, when):
    t = eph.ts.utc(*when)
    chart = angles.compute(t, latitude, longitude)
    built = houses.placidus(chart, latitude)
    observer = eph.kernel[399] + wgs84.latlon(latitude, longitude)

    for house, (fraction, diurnal) in PLACIDUS_FRACTIONS.items():
        star = _star_at(built.cusp(house), t)

        def altitude(tt):
            alt, _, _ = observer.at(eph.ts.tt_jd(tt)).observe(star).apparent().altaz()
            return alt.degrees

        now = t.tt
        if diurnal:
            rise = _find_root(altitude, now - 0.5, now)
            culmination = _find_extremum(altitude, now, now + 0.5, maximum=True)
            travelled = (now - rise) / (culmination - rise)
            expected = 1.0 - fraction
        else:
            lower = _find_extremum(altitude, now - 0.5, now, maximum=False)
            rise = _find_root(altitude, now, now + 0.5)
            travelled = (now - lower) / (rise - lower)
            expected = fraction
        # допуск покрывает аберрацию, которую Skyfield включает в высоту,
        # а геометрическое определение куспида — нет
        assert travelled == pytest.approx(expected, abs=3e-4), f"{name}, дом {house}"


@pytest.mark.parametrize("name,latitude,longitude,when", PLACES)
def test_placidus_opposite_cusps_are_opposite(eph, name, latitude, longitude, when):
    chart = angles.compute(eph.ts.utc(*when), latitude, longitude)
    built = houses.placidus(chart, latitude)
    for house in range(1, 7):
        difference = (built.cusp(house + 6) - built.cusp(house)) % 360.0
        assert difference == pytest.approx(180.0, abs=1e-9), f"{name}, дом {house}"


@pytest.mark.parametrize("name,latitude,longitude,when", PLACES)
def test_cusps_go_in_order_and_cover_the_circle(eph, name, latitude, longitude, when):
    chart = angles.compute(eph.ts.utc(*when), latitude, longitude)
    for system in (houses.PLACIDUS, houses.WHOLE_SIGN, houses.PORPHYRY):
        built = houses.build(system, chart, latitude)
        widths = built.widths()
        assert sum(widths) == pytest.approx(360.0, abs=1e-9), f"{name}, {system}"
        assert all(width > 0 for width in widths), f"{name}, {system}"


@pytest.mark.parametrize("name,latitude,longitude,when", PLACES)
def test_house_lookup_agrees_with_cusps(eph, name, latitude, longitude, when):
    chart = angles.compute(eph.ts.utc(*when), latitude, longitude)
    built = houses.placidus(chart, latitude)
    for house in range(1, 13):
        assert built.house_of(built.cusp(house)) == house
        middle = norm360(built.cusp(house) + built.widths()[house - 1] / 2.0)
        assert built.house_of(middle) == house


def test_angles_sit_on_their_cusps(eph):
    chart = angles.compute(eph.ts.utc(1987, 7, 14, 7, 25), 50.4501, 30.5234)
    built = houses.placidus(chart, 50.4501)
    assert built.cusp(1) == pytest.approx(chart.asc)
    assert built.cusp(10) == pytest.approx(chart.mc)
    assert built.cusp(7) == pytest.approx(chart.desc)
    assert built.cusp(4) == pytest.approx(chart.ic)


def test_whole_sign_starts_at_the_ascendant_sign(eph):
    chart = angles.compute(eph.ts.utc(1987, 7, 14, 7, 25), 50.4501, 30.5234)
    built = houses.whole_sign(chart.asc)
    assert built.cusp(1) == pytest.approx(math.floor(chart.asc / 30.0) * 30.0)
    assert all(cusp % 30.0 == pytest.approx(0.0) for cusp in built.cusps)
    assert built.house_of(chart.asc) == 1


def test_placidus_is_refused_beyond_the_polar_circle(eph):
    """За полярным кругом система не определена, и это должно быть сказано."""
    chart = angles.compute(eph.ts.utc(2010, 6, 21, 12, 0), 78.2232, 15.6267)  # Лонгйир
    with pytest.raises(houses.CircumpolarError):
        houses.placidus(chart, 78.2232)


def test_fallback_replaces_undefined_system(eph):
    chart = angles.compute(eph.ts.utc(2010, 6, 21, 12, 0), 78.2232, 15.6267)
    built = houses.build(houses.PLACIDUS, chart, 78.2232, fallback=houses.WHOLE_SIGN)
    assert built.system == houses.WHOLE_SIGN
    with pytest.raises(houses.CircumpolarError):
        houses.build(houses.PLACIDUS, chart, 78.2232)


def test_porphyry_thirds_each_quadrant(eph):
    chart = angles.compute(eph.ts.utc(1987, 7, 14, 7, 25), 50.4501, 30.5234)
    built = houses.porphyry(chart.asc, chart.mc)
    widths = built.widths()
    assert widths[0] == pytest.approx(widths[1]) == pytest.approx(widths[2])
    assert widths[9] == pytest.approx(widths[10]) == pytest.approx(widths[11])
