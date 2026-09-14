"""Эфемериды малых тел: интерполяция состояний и подключение к карте.

Настоящего Хирона в тестах нет — вместо него берётся Юпитер из ядра DE,
прогоняется через тот же конвейер (выборка состояний, запись, чтение,
интерполяция) и сверяется с прямым расчётом. Юпитер движется быстрее
Хирона, поэтому полученная точность для Хирона будет только лучше.
"""

import os
import sys

import numpy as np
import pytest
from skyfield.framelib import ecliptic_frame

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from astro import bodies, smallbody  # noqa: E402

STEP_DAYS = 16.0
JD_START = 2433282.5  # 1950-01-01
NODES = 900


@pytest.fixture(scope="module")
def jupiter_table(eph, tmp_path_factory):
    """Юпитер, пропущенный через формат малых тел."""
    jupiter = eph.kernel[5]
    states = []
    for step in range(NODES):
        position = jupiter.at(eph.ts.tdb_jd(JD_START + STEP_DAYS * step))
        states.append(
            np.concatenate([position.position.km, position.velocity.km_per_s * 86400.0])
        )
    path = str(tmp_path_factory.mktemp("small") / "probe.npz")
    smallbody.save(path, target=5, center=0, jd_start=JD_START,
                   step_days=STEP_DAYS, states=np.array(states), name="probe")
    return smallbody.load(path)


def test_interpolated_longitude_matches_the_kernel(eph, jupiter_table):
    """Долгота из таблицы совпадает с долготой из ядра DE."""
    earth, jupiter = eph.kernel[399], eph.kernel[5]
    worst = 0.0
    for jd in np.linspace(JD_START + 50, jupiter_table.jd_end - 50, 200):
        t = eph.ts.tdb_jd(jd)
        reference = earth.at(t).observe(jupiter).apparent().frame_latlon(ecliptic_frame)
        candidate = earth.at(t).observe(jupiter_table).apparent().frame_latlon(ecliptic_frame)
        difference = abs(
            (reference[1].degrees - candidate[1].degrees + 180.0) % 360.0 - 180.0
        )
        worst = max(worst, difference * 3600.0)
    assert worst < 0.001, f"расхождение {worst:.6f} угловой секунды"


def test_interpolation_is_exact_at_the_nodes(eph, jupiter_table):
    """В узлах сетки интерполяция обязана возвращать исходное состояние."""
    jupiter = eph.kernel[5]
    for step in (0, 1, 17, NODES - 1):
        jd = JD_START + STEP_DAYS * step
        t = eph.ts.tdb_jd(jd)
        expected = jupiter.at(t).position.km
        got = jupiter_table.at(t).position.km
        assert np.allclose(got, expected, atol=1e-6)


def test_velocity_is_consistent_with_position(eph, jupiter_table):
    """Скорость из интерполяции сходится с численной производной положения."""
    jd = JD_START + STEP_DAYS * 100 + 3.7
    h = 0.01
    velocity = jupiter_table.at(eph.ts.tdb_jd(jd)).velocity.km_per_s * 86400.0
    forward = jupiter_table.at(eph.ts.tdb_jd(jd + h)).position.km
    backward = jupiter_table.at(eph.ts.tdb_jd(jd - h)).position.km
    numeric = (forward - backward) / (2 * h)
    assert np.allclose(velocity, numeric, rtol=1e-6)


def test_request_outside_coverage_is_refused(eph, jupiter_table):
    with pytest.raises(smallbody.SmallBodyError):
        jupiter_table.at(eph.ts.tdb_jd(JD_START - 10.0))
    with pytest.raises(smallbody.SmallBodyError):
        jupiter_table.at(eph.ts.tdb_jd(jupiter_table.jd_end + 10.0))


def test_broken_table_is_rejected(tmp_path):
    path = str(tmp_path / "broken.npz")
    with pytest.raises(smallbody.SmallBodyError):
        smallbody.save(path, target=1, center=0, jd_start=0.0, step_days=1.0,
                       states=np.zeros((5, 3)))
    smallbody.save(path, target=1, center=0, jd_start=0.0, step_days=1.0,
                   states=np.zeros((1, 6)))
    with pytest.raises(smallbody.SmallBodyError):
        smallbody.load(path)
    with pytest.raises(smallbody.SmallBodyError):
        smallbody.load(str(tmp_path / "нет-такого.npz"))


def test_missing_chiron_does_not_break_the_chart(eph):
    """Без файла эфемериды Хирон просто не попадает в карту."""
    from datetime import datetime

    from astro.chart import Place, compute

    if eph.has(bodies.CHIRON):
        pytest.skip("файл Хирона присутствует, случай отсутствия не проверить")
    chart = compute(datetime(1987, 7, 14, 11, 25), Place(50.4501, 30.5234), ephemeris=eph)
    assert "chiron" not in chart.positions
    assert len(chart.positions) >= 14


def test_chiron_joins_the_chart_when_its_file_exists(eph, jupiter_table, monkeypatch):
    """С файлом эфемериды Хирон появляется в составе карты и получает дом."""
    from datetime import datetime

    from astro.chart import Place, compute

    monkeypatch.setitem(eph._cache, "chiron", jupiter_table)
    chart = compute(datetime(1987, 7, 14, 11, 25), Place(50.4501, 30.5234), ephemeris=eph)
    assert "chiron" in chart.positions
    chiron = chart.positions["chiron"]
    assert 1 <= chiron.house <= 12
    assert chiron.distance > 0
    eph._cache.pop("chiron", None)


def test_horizons_csv_is_parsed(tmp_path):
    """Разбор ответа Horizons на образце его формата."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "scripts"))
    import fetch_chiron

    sample = """
*******************************************************************************
JDTDB, Calendar Date (TDB), X, Y, Z, VX, VY, VZ,
$$SOE
2451544.500000000, A.D. 2000-Jan-01 00:00:00.0000,  1.2E+09,  2.3E+09, -4.5E+08,  1.5E+00, -2.5E+00,  3.5E-01,
2451560.500000000, A.D. 2000-Jan-17 00:00:00.0000,  1.3E+09,  2.4E+09, -4.6E+08,  1.6E+00, -2.6E+00,  3.6E-01,
$$EOE
*******************************************************************************
"""
    times, states = fetch_chiron.parse_vectors(sample)
    assert times.tolist() == [2451544.5, 2451560.5]
    assert states[0][0] == pytest.approx(1.2e9)
    # скорость переведена из километров в секунду в километры в сутки
    assert states[0][3] == pytest.approx(1.5 * 86400.0)
    fetch_chiron.check_uniform(times, 16.0)
    with pytest.raises(SystemExit):
        fetch_chiron.check_uniform(times, 8.0)


def test_horizons_error_reply_is_reported(tmp_path):
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "scripts"))
    import fetch_chiron

    with pytest.raises(SystemExit):
        fetch_chiron.parse_vectors("No matches found.")
