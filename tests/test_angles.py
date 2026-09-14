"""Углы карты, проверенные через горизонтальные координаты.

Асцендент, MC и Вертекс определяются геометрически: точка на горизонте,
точка на меридиане, точка на главном вертикале. Здесь найденные долготы
переводятся обратно в высоту и азимут другим путём — если формула
ошибочна, точка не окажется там, где должна.
"""

import math

import pytest

from astro import angles

PLACES = [
    ("Москва", 55.7558, 37.6173, (2024, 3, 20, 3, 6)),
    ("Киев", 50.4501, 30.5234, (1987, 7, 14, 7, 25)),
    ("Сингапур", 1.3521, 103.8198, (2001, 12, 31, 23, 59)),
    ("Буэнос-Айрес", -34.6037, -58.3816, (1966, 2, 2, 6, 0)),
    ("Кейптаун", -33.9249, 18.4241, (1995, 9, 9, 18, 30)),
    ("Мурманск", 68.9585, 33.0827, (2010, 5, 5, 4, 0)),
]


def horizontal(longitude, obliquity, latitude, ramc):
    """Долгота точки эклиптики → высота, азимут (от севера через восток), часовой угол."""
    declination = math.radians(angles.ecliptic_declination(longitude, obliquity))
    right_ascension = angles.ecliptic_right_ascension(longitude, obliquity)
    hour_angle = math.radians((ramc - right_ascension + 180.0) % 360.0 - 180.0)
    phi = math.radians(latitude)
    altitude = math.asin(
        math.sin(phi) * math.sin(declination)
        + math.cos(phi) * math.cos(declination) * math.cos(hour_angle)
    )
    azimuth = math.atan2(
        -math.cos(declination) * math.sin(hour_angle),
        math.sin(declination) * math.cos(phi)
        - math.cos(declination) * math.sin(phi) * math.cos(hour_angle),
    )
    return math.degrees(altitude), math.degrees(azimuth) % 360.0, math.degrees(hour_angle)


@pytest.mark.parametrize("name,latitude,longitude,when", PLACES)
def test_ascendant_lies_on_eastern_horizon(ts, name, latitude, longitude, when):
    chart = angles.compute(ts.utc(*when), latitude, longitude)
    altitude, azimuth, _ = horizontal(chart.asc, chart.obliquity, latitude, chart.ramc)
    assert altitude == pytest.approx(0.0, abs=1e-9), name
    assert 0.0 < azimuth < 180.0, name


@pytest.mark.parametrize("name,latitude,longitude,when", PLACES)
def test_midheaven_lies_on_meridian(ts, name, latitude, longitude, when):
    chart = angles.compute(ts.utc(*when), latitude, longitude)
    _, _, hour_angle = horizontal(chart.mc, chart.obliquity, latitude, chart.ramc)
    assert hour_angle == pytest.approx(0.0, abs=1e-9), name


@pytest.mark.parametrize("name,latitude,longitude,when", PLACES)
def test_vertex_lies_on_western_prime_vertical(ts, name, latitude, longitude, when):
    """Вертекс — западная точка главного вертикала, азимут ровно 270°."""
    chart = angles.compute(ts.utc(*when), latitude, longitude)
    _, azimuth, _ = horizontal(chart.vertex, chart.obliquity, latitude, chart.ramc)
    assert abs(((azimuth - 270.0 + 180.0) % 360.0) - 180.0) < 1e-6, name


def test_obliquity_is_true_obliquity_of_date(ts):
    """Истинный наклон эклиптики в 2024 году: 23.4387°, средний — 23.4361°."""
    value = angles.true_obliquity(ts.utc(2024, 3, 20, 3, 6))
    assert value == pytest.approx(23.4387, abs=0.0005)


def test_east_point_equals_ascendant_at_equator(ts):
    chart = angles.compute(ts.utc(2024, 3, 20, 3, 6), 0.0, 0.0)
    assert chart.east_point == pytest.approx(chart.asc, abs=1e-9)


def test_opposite_angles(ts):
    chart = angles.compute(ts.utc(2024, 3, 20, 3, 6), 55.0, 37.0)
    assert (chart.desc - chart.asc) % 360.0 == pytest.approx(180.0)
    assert (chart.ic - chart.mc) % 360.0 == pytest.approx(180.0)


def test_ramc_tracks_sidereal_time(ts):
    """RAMC — местное звёздное время: за сутки полный оборот с небольшим опережением."""
    t0 = ts.utc(2024, 6, 1, 0, 0)
    t1 = ts.tt_jd(t0.tt + 1.0)
    advance = (angles.ramc(t1, 37.0) - angles.ramc(t0, 37.0)) % 360.0
    assert advance == pytest.approx(0.9856 * 1.0, abs=0.01)
