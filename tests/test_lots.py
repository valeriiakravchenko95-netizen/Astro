"""Жребии: Часть Фортуны и определение секты."""

import pytest

from astro import lots
from astro.zodiac import norm360


def test_sun_above_the_horizon_makes_the_chart_diurnal():
    ascendant = 0.0     # Асцендент в 0° Овна, Десцендент в 0° Весов
    assert lots.is_diurnal(200.0, ascendant)    # между DSC и ASC — верхняя половина
    assert not lots.is_diurnal(20.0, ascendant)  # только что взошло — первый дом, ещё внизу


def test_sect_boundary_sits_on_the_angles():
    ascendant = 100.0
    assert not lots.is_diurnal(ascendant + 0.01, ascendant)
    assert lots.is_diurnal(ascendant - 0.01, ascendant)


def test_day_and_night_formulas_are_mirrored():
    ascendant, sun, moon = 197.6, 60.0, 330.8
    day = lots.part_of_fortune(ascendant, sun, moon, diurnal=True)
    night = lots.part_of_fortune(ascendant, sun, moon, diurnal=False)
    assert day == pytest.approx(norm360(ascendant + moon - sun))
    assert night == pytest.approx(norm360(ascendant + sun - moon))
    # оба жребия равноудалены от Асцендента в разные стороны
    assert norm360(day - ascendant) == pytest.approx(norm360(ascendant - night))


def test_fortune_coincides_with_ascendant_at_new_moon():
    """В новолуние Солнце и Луна совпадают, и жребий садится на Асцендент."""
    for diurnal in (True, False):
        assert lots.part_of_fortune(197.6, 45.0, 45.0, diurnal) == pytest.approx(197.6)


def test_fortune_is_computed_in_the_chart(eph):
    from datetime import datetime

    from astro.chart import Place, compute

    chart = compute(datetime(1987, 7, 14, 11, 25), Place(50.4501, 30.5234), ephemeris=eph)
    fortune = chart.positions["part_of_fortune"]
    expected = lots.part_of_fortune(
        chart.angles.asc,
        chart.positions["sun"].longitude,
        chart.positions["moon"].longitude,
        chart.diurnal,
    )
    assert fortune.longitude == pytest.approx(expected)
    assert fortune.latitude == 0.0
    assert fortune.speed == 0.0
    assert chart.diurnal in (True, False)


def test_fortune_needs_the_luminaries(eph):
    from datetime import datetime

    from astro.chart import Place, compute

    with pytest.raises(ValueError):
        compute(datetime(1987, 7, 14, 11, 25), Place(50.4501, 30.5234), ephemeris=eph,
                body_keys=("mars", "part_of_fortune"))


def test_south_node_is_opposite_the_north(eph):
    from astro import bodies, nodes

    t = eph.ts.utc(1995, 5, 21, 13, 10)
    north = nodes.position(bodies.TRUE_NODE, eph, t).longitude
    south = nodes.position(bodies.SOUTH_NODE, eph, t).longitude
    assert norm360(south - north) == pytest.approx(180.0)
