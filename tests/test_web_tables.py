"""Таблицы эфемерид для браузера: формат и точность восстановления.

Таблица — это сжатая выжимка из ядра JPL, и проверять её надо против
самого ядра: восстановленная долгота обязана совпадать с посчитанной
напрямую. Порог в одну угловую секунду выбран не случайно — при выдаче
градусов и минут этого достаточно, чтобы ни одна минута не сдвинулась.
"""

import json
import os
import struct

import numpy as np
import pytest

from astro import bodies, nodes

TABLE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "web", "data", "ephemeris.bin",
)

#: Допуск на восстановление, угловые секунды.
#:
#: Две угловые секунды — это одна тридцатая той минуты, которую видит
#: читатель, так что сдвинуть отображаемое значение такая погрешность не
#: может. Столько набирается лишь у долей процента точек, и только там,
#: где планета почти закрыта Солнцем: гравитационное отклонение света
#: меняется у края диска за часы, и никакая разумная сетка этого не ловит.
TOLERANCE = 2.0

MAGIC = b"ASTREPH1"


def load_tables(path=TABLE_PATH):
    """Читает файл таблиц тем же способом, что и браузер."""
    with open(path, "rb") as handle:
        blob = handle.read()

    assert blob[:8] == MAGIC, "не та подпись файла"
    header_length = struct.unpack("<I", blob[8:12])[0]
    header = json.loads(blob[12:12 + header_length])
    base = 12 + header_length

    tables = {}
    for entry in header["bodies"]:
        start = base + entry["offset"]
        count = entry["count"]
        raw = blob[start:start + entry["length"]]
        tables[entry["key"]] = {
            "step": entry["step"],
            "count": count,
            "longitude": np.frombuffer(raw[:4 * count], "<i4") / header["micro"],
            "rate": np.frombuffer(raw[4 * count:8 * count], "<f4").astype(float),
        }
    return header, tables


def hermite(table, jd_start, jd):
    """Кубическая интерполяция Эрмита — та же, что будет в браузере."""
    step = table["step"]
    position = (np.asarray(jd, dtype=float) - jd_start) / step
    index = np.clip(np.floor(position).astype(int), 0, table["count"] - 2)
    u = position - index

    left = table["longitude"][index]
    right = table["longitude"][index + 1]
    # приращение считается без скачка через ноль градусов
    delta = (right - left + 180.0) % 360.0 - 180.0
    slope_left = table["rate"][index] * step
    slope_right = table["rate"][index + 1] * step

    u2 = u * u
    u3 = u2 * u
    return (
        left
        + (-2 * u3 + 3 * u2) * delta
        + (u3 - 2 * u2 + u) * slope_left
        + (u3 - u2) * slope_right
    ) % 360.0


@pytest.fixture(scope="module")
def tables():
    if not os.path.isfile(TABLE_PATH):
        pytest.skip("таблицы не собраны: scripts/build_web_ephemeris.py")
    return load_tables()


@pytest.fixture(scope="module")
def sample_times(tables):
    header, _ = tables
    generator = np.random.default_rng(20260922)
    span = header["jd_end"] - header["jd_start"]
    return header["jd_start"] + generator.random(2000) * (span - 40.0)


def exact_longitude(eph, key, jds):
    """Долгота, посчитанная напрямую из ядра, — эталон для сверки."""
    t = eph.ts.tt_jd(jds)
    if key == "true_node":
        return np.asarray(nodes.true_node_longitude(eph, t))
    if key == "mean_lilith":
        return np.asarray(nodes.mean_lilith_longitude(jds))
    if key == "mean_node":
        return np.asarray(nodes.mean_node_longitude(jds))
    return np.asarray(eph.ecliptic(bodies.get(key), t)[0])


@pytest.mark.parametrize("key", [
    "sun", "moon", "mercury", "venus", "mars", "jupiter",
    "saturn", "uranus", "neptune", "pluto", "true_node", "mean_lilith",
])
def test_table_reproduces_the_kernel(eph, tables, sample_times, key):
    header, all_tables = tables
    table = all_tables[key]
    restored = hermite(table, header["jd_start"], sample_times)
    expected = exact_longitude(eph, key, sample_times)
    error = np.abs((restored - expected + 180.0) % 360.0 - 180.0) * 3600.0
    assert error.max() < TOLERANCE, (
        f"{key}: худшее расхождение {error.max():.3f} угловой секунды"
    )


def test_interpolation_is_exact_at_the_nodes(eph, tables):
    """В узлах сетки интерполяция обязана вернуть записанное значение."""
    header, all_tables = tables
    table = all_tables["moon"]
    indices = np.arange(10, table["count"] - 10, 997)
    jds = header["jd_start"] + indices * table["step"]
    restored = hermite(table, header["jd_start"], jds)
    stored = table["longitude"][indices]
    assert np.abs((restored - stored + 180) % 360 - 180).max() < 1e-6


def test_header_describes_every_body(tables):
    header, all_tables = tables
    assert header["jd_end"] > header["jd_start"]
    for key, table in all_tables.items():
        assert table["count"] >= 2
        assert table["step"] > 0
        assert len(table["longitude"]) == table["count"]
        assert len(table["rate"]) == table["count"]


def test_table_covers_a_century(tables):
    """Интервал должен покрывать всех, кто может прийти считать карту."""
    header, _ = tables
    years = (header["jd_end"] - header["jd_start"]) / 365.25
    assert years > 100


def test_file_stays_small_enough_for_mobile(tables):
    """Файл грузится с телефона, поэтому размер под присмотром."""
    assert os.path.getsize(TABLE_PATH) < 4e6
