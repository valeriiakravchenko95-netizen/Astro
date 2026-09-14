"""Позиции тел, проверенные против независимых величин.

Здесь нет сверки «число к числу» с чужой программой: проверяется физика,
которую можно измерить отдельно от нашего кода, — моменты равноденствий,
длина тропического года и синодического месяца, период обращения узла, а
также перекрёстный расчёт через skyfield.almanac, который ищет сезоны
своим собственным трактом.
"""

from datetime import datetime

import pytest
from skyfield import almanac

from astro import bodies, nodes
from astro.zodiac import norm180

#: Опубликованные моменты равноденствий и солнцестояний, UTC.
PUBLISHED_SEASONS = [
    (2000, 0.0, datetime(2000, 3, 20, 7, 35)),
    (2024, 0.0, datetime(2024, 3, 20, 3, 6)),
    (2024, 90.0, datetime(2024, 6, 20, 20, 51)),
    (2024, 180.0, datetime(2024, 9, 22, 12, 44)),
    (2024, 270.0, datetime(2024, 12, 21, 9, 21)),
]


def _solve_longitude(eph, body, target, guess_tt, span=3.0):
    """Момент (в TT), когда долгота тела равна target."""
    def residual(tt):
        longitude, _, _ = eph.ecliptic(body, eph.ts.tt_jd(tt))
        return norm180(longitude - target)

    low, high = guess_tt - span, guess_tt + span
    f_low = residual(low)
    for _ in range(200):
        middle = 0.5 * (low + high)
        f_middle = residual(middle)
        if f_low * f_middle <= 0:
            high = middle
        else:
            low, f_low = middle, f_middle
        if high - low < 1e-11:
            break
    return 0.5 * (low + high)


@pytest.mark.parametrize("year,target,published", PUBLISHED_SEASONS)
def test_seasons_match_published_tables(eph, year, target, published):
    """Солнце приходит в 0°, 90°, 180° и 270° в опубликованные моменты.

    Это проверяет главное — что долгота считается в видимых геоцентрических
    координатах истинной эклиптики даты. Ошибка в системе координат сдвинула
    бы моменты на минуты и часы. Допуск в минуту покрывает округление таблиц
    и разницу редакций эфемерид.
    """
    month = {0.0: 3, 90.0: 6, 180.0: 9, 270.0: 12}[target]
    guess = eph.ts.utc(year, month, 21).tt
    found = eph.ts.tt_jd(_solve_longitude(eph, bodies.SUN, target, guess, span=5.0))
    delta_seconds = abs((found.utc_datetime().replace(tzinfo=None) - published).total_seconds())
    assert delta_seconds < 60.0


def test_seasons_match_skyfield_almanac(eph):
    """Перекрёстная проверка: skyfield.almanac ищет сезоны своим путём."""
    start, end = eph.ts.utc(2023, 1, 1), eph.ts.utc(2025, 1, 1)
    times, events = almanac.find_discrete(start, end, almanac.seasons(eph.kernel))
    assert len(times) == 8
    for time, event in zip(times, events):
        mine = _solve_longitude(eph, bodies.SUN, event * 90.0, time.tt)
        assert abs(mine - time.tt) * 86400 < 1.0  # секунда времени


def test_tropical_year_length(eph):
    """От равноденствия до равноденствия — тропический год, 365.2422 суток."""
    first = _solve_longitude(eph, bodies.SUN, 0.0, eph.ts.utc(2020, 3, 20).tt, span=5.0)
    last = _solve_longitude(eph, bodies.SUN, 0.0, eph.ts.utc(2024, 3, 20).tt, span=5.0)
    assert (last - first) / 4.0 == pytest.approx(365.2422, abs=0.01)


def test_synodic_month_length(eph):
    """Средний промежуток между новолуниями — 29.5306 суток."""
    def elongation(tt):
        t = eph.ts.tt_jd(tt)
        sun, _, _ = eph.ecliptic(bodies.SUN, t)
        moon, _, _ = eph.ecliptic(bodies.MOON, t)
        return norm180(moon - sun)

    def new_moon_near(guess):
        low, high = guess - 2.0, guess + 2.0
        f_low = elongation(low)
        for _ in range(200):
            middle = 0.5 * (low + high)
            f_middle = elongation(middle)
            if f_low * f_middle <= 0:
                high = middle
            else:
                low, f_low = middle, f_middle
            if high - low < 1e-10:
                break
        return 0.5 * (low + high)

    first = new_moon_near(eph.ts.utc(2024, 1, 11).tt)
    thirteenth = new_moon_near(first + 13 * 29.53)
    assert (thirteenth - first) / 13.0 == pytest.approx(29.5306, abs=0.02)


def test_mean_node_period(eph):
    """Средний Узел обходит зодиак за 18.6 года, двигаясь назад."""
    speed = nodes.position(bodies.MEAN_NODE, eph, eph.ts.utc(2024, 1, 1)).speed
    assert speed < 0
    assert 360.0 / abs(speed) / 365.25 == pytest.approx(18.6, abs=0.05)


def test_true_node_stays_near_mean_node(eph):
    """Истинный Узел колеблется вокруг среднего в пределах примерно 1.7°."""
    worst = 0.0
    for month in range(1, 13):
        t = eph.ts.utc(2024, month, 1)
        difference = abs(norm180(
            nodes.true_node_longitude(eph, t) - nodes.mean_node_longitude(t.tt)
        ))
        worst = max(worst, difference)
    assert 0.5 < worst < 1.8


def test_mean_lilith_matches_known_apogee_at_j2000(eph):
    """Долгота среднего апогея Луны на эпоху J2000 — 263.353°."""
    assert nodes.mean_lilith_longitude(2451545.0) == pytest.approx(263.3532, abs=0.001)


def test_mean_node_matches_known_value_at_j2000(eph):
    assert nodes.mean_node_longitude(2451545.0) == pytest.approx(125.0445, abs=0.0005)


def test_lunar_points_have_zero_latitude(eph):
    t = eph.ts.utc(1987, 7, 14, 7, 25)
    for body in bodies.LUNAR_POINTS:
        assert nodes.position(body, eph, t).latitude == 0.0


def test_retrograde_flag_follows_speed(eph):
    """Меркурий пятится примерно три раза в году, суммарно около 60 суток."""
    days = 0
    switches = 0
    previous = None
    for day in range(365):
        t = eph.ts.tt_jd(eph.ts.utc(2024, 1, 1).tt + day)
        retrograde = eph.position(bodies.MERCURY, t).retrograde
        days += retrograde
        if previous is not None and retrograde != previous:
            switches += 1
        previous = retrograde
    assert 50 <= days <= 80
    assert switches in (5, 6, 7)  # три петли за год, по две смены на петлю


def test_outer_planets_move_slowly(eph):
    """Суточный ход планет лежит в известных пределах."""
    t = eph.ts.utc(2024, 6, 1)
    limits = {
        bodies.MOON: (11.0, 15.5), bodies.SUN: (0.95, 1.02),
        bodies.JUPITER: (0.0, 0.25), bodies.PLUTO: (0.0, 0.04),
    }
    for body, (low, high) in limits.items():
        speed = abs(eph.position(body, t).speed)
        assert low <= speed <= high, body.name
