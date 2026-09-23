"""Транзиты и события неба."""

from datetime import datetime

import pytest

from astro import sky, transits
from astro.chart import Place, compute


@pytest.fixture(scope="module")
def chart(eph):
    return compute(datetime(1995, 5, 21, 16, 10), Place(48.023, 37.80224),
                   ephemeris=eph, primary_system="placidus")


def test_transit_finds_conjunction_with_a_natal_body(chart):
    """Градус, поставленный на натальное Солнце, обязан его найти."""
    sun = chart.positions["sun"].longitude
    report = transits.examine(chart, sun + 0.5, "проба")
    hit = next(h for h in report.hits if h.natal == "sun")
    assert hit.aspect.key == "conjunction"
    assert hit.orb == pytest.approx(0.5, abs=1e-9)
    assert not hit.exact


def test_exact_contact_is_marked(chart):
    sun = chart.positions["sun"].longitude
    report = transits.examine(chart, sun + 0.1, "проба")
    assert next(h for h in report.hits if h.natal == "sun").exact


def test_transit_outside_the_orb_is_not_reported(chart):
    sun = chart.positions["sun"].longitude
    report = transits.examine(chart, sun + 5.0, "проба")
    assert not any(h.natal == "sun" for h in report.hits)


def test_house_of_the_transit_degree(chart):
    """Градус попадает в тот дом, который его содержит."""
    for house in range(1, 13):
        middle = chart.primary_houses.cusp(house) + chart.primary_houses.widths()[house - 1] / 2
        report = transits.examine(chart, middle, "проба")
        assert report.house == house


def test_cusp_contact_is_found(chart):
    cusp = chart.primary_houses.cusp(10)
    report = transits.examine(chart, cusp + 0.5, "проба")
    assert any(h.natal_kind == "cusp" and h.natal.endswith("10") for h in report.hits)


def test_ruled_houses_cover_all_twelve(chart):
    mapping = transits.ruled_houses(chart)
    covered = sorted(house for houses in mapping.values() for house in houses)
    assert covered == list(range(1, 13))


def test_touched_houses_include_those_ruled_by_hit_bodies(chart):
    """Задета планета — задеты и дома, которыми она управляет."""
    mapping = transits.ruled_houses(chart)
    body = next(key for key, houses in mapping.items() if houses and key in chart.positions)
    report = transits.examine(chart, chart.positions[body].longitude, "проба")
    for house in mapping[body]:
        assert house in report.houses_touched


def test_without_exact_time_houses_are_not_invented(eph):
    """Без времени рождения дома и углы не показываются вовсе."""
    rough = compute(datetime(1995, 5, 21, 12, 0), Place(48.023, 37.80224),
                    ephemeris=eph, exact_time=False)
    report = transits.examine(rough, rough.angles.asc, "проба")
    assert report.house is None
    assert not any(h.natal_kind in ("angle", "cusp") for h in report.hits)


# --- события неба ----------------------------------------------------------

def test_station_is_found_where_speed_changes_sign(eph):
    """Уран развернулся на попятное 10 сентября 2026 года."""
    start = eph.ts.utc(2026, 8, 1).tt
    end = eph.ts.utc(2026, 10, 1).tt
    events = sky.find_stations(eph, start, end, keys=("uranus",))
    assert len(events) == 1
    event = events[0]
    assert event.detail["direction"] == "retrograde"
    assert eph.ts.tt_jd(event.jd).utc_strftime("%Y-%m-%d") == "2026-09-10"
    assert event.key() == "station.uranus.retrograde"


def test_speed_really_changes_sign_at_the_station(eph):
    from astro import bodies

    events = sky.find_stations(eph, eph.ts.utc(2026, 8, 1).tt,
                               eph.ts.utc(2026, 10, 1).tt, keys=("uranus",))
    jd = events[0].jd
    before = eph.longitude_speed(bodies.get("uranus"), eph.ts.tt_jd(jd - 2))
    after = eph.longitude_speed(bodies.get("uranus"), eph.ts.tt_jd(jd + 2))
    assert before > 0 > after


def test_aspect_search_does_not_invent_aspects_at_the_circle_boundary(eph):
    """Проход Марса мимо Плутона не должен давать пяти аспектов разом.

    Отклонение от любого угла на границе круга скачком меняет знак, и без
    проверки на разрыв в календарь попадали соединение, квадрат, трин и
    секстиль одной и той же минутой.
    """
    events = sky.find_aspects(
        eph, eph.ts.utc(2026, 9, 25).tt, eph.ts.utc(2026, 10, 10).tt,
        pairs=(("mars", "pluto"),),
    )
    assert len(events) == 1
    assert events[0].detail["aspect"] == "opposition"


def test_aspect_is_exact_at_the_found_moment(eph):
    from astro.zodiac import norm180

    events = sky.find_aspects(
        eph, eph.ts.utc(2026, 9, 25).tt, eph.ts.utc(2026, 10, 10).tt,
        pairs=(("mars", "pluto"),),
    )
    jd = events[0].jd
    mars = sky._longitude(eph, "mars", jd)
    pluto = sky._longitude(eph, "pluto", jd)
    assert abs(abs(norm180(mars - pluto)) - 180) < 1e-4


def test_ingress_lands_on_a_sign_boundary(eph):
    events = sky.find_ingresses(eph, eph.ts.utc(2026, 1, 1).tt,
                                eph.ts.utc(2027, 1, 1).tt, keys=("saturn",))
    for event in events:
        assert event.longitude % 30 == pytest.approx(0.0, abs=1e-6)
        actual = sky._longitude(eph, "saturn", event.jd)
        assert abs(((actual - event.longitude + 180) % 360) - 180) < 1e-4


def test_lunations_alternate_and_keep_the_synodic_month(eph):
    events = sky.find_lunations(eph, eph.ts.utc(2026, 1, 1).tt,
                                eph.ts.utc(2026, 7, 1).tt)
    new_moons = sorted(e.jd for e in events if e.detail["phase"] == "new")
    gaps = [b - a for a, b in zip(new_moons, new_moons[1:])]
    assert all(28.0 < gap < 31.0 for gap in gaps)


def test_eclipse_is_marked_only_near_the_nodes(eph):
    events = sky.find_lunations(eph, eph.ts.utc(2026, 1, 1).tt,
                                eph.ts.utc(2027, 1, 1).tt)
    for event in events:
        latitude = abs(event.detail["moon_latitude"])
        if event.detail["eclipse"]:
            assert latitude <= sky.SOLAR_ECLIPSE_LATITUDE
    assert any(e.detail["eclipse"] for e in events), "за год должно быть затмение"


def test_event_keys_are_stable(eph):
    events = sky.collect(eph, eph.ts.utc(2026, 9, 1).tt, eph.ts.utc(2026, 10, 1).tt)
    keys = [event.key() for event in events]
    assert "station.uranus.retrograde" in keys
    assert all(key and " " not in key for key in keys)
