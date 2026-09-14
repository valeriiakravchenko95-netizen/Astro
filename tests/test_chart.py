"""Сборка карты целиком и правила выдачи результата."""

from datetime import datetime

import pytest

from astro import houses as houses_mod
from astro.chart import Place, compute
from astro.zodiac import to_sign

KYIV = (datetime(1987, 7, 14, 11, 25), Place(50.4501, 30.5234, "Киев"))


@pytest.fixture(scope="module")
def chart(eph):
    moment, place = KYIV
    return compute(moment, place, ephemeris=eph, primary_system=houses_mod.PLACIDUS)


def test_chart_has_all_default_bodies(chart):
    expected = {
        "sun", "moon", "mercury", "venus", "mars", "jupiter",
        "saturn", "uranus", "neptune", "pluto",
        "true_node", "south_node", "mean_lilith", "part_of_fortune",
    }
    assert set(chart.positions) == expected


def test_both_house_systems_are_built(chart):
    assert set(chart.houses) == {houses_mod.WHOLE_SIGN, houses_mod.PLACIDUS}
    assert chart.primary_system == houses_mod.PLACIDUS


def test_planet_house_matches_the_cusps_of_each_system(chart):
    for position in chart.positions.values():
        for system, houses in chart.houses.items():
            assert position.houses[system] == houses.house_of(position.longitude)


def test_whole_sign_house_follows_from_the_sign(chart):
    """В целых знаках дом планеты определяется только знаком Асцендента."""
    ascendant_sign = to_sign(chart.angles.asc).sign_index
    for position in chart.positions.values():
        expected = (to_sign(position.longitude).sign_index - ascendant_sign) % 12 + 1
        assert position.houses[houses_mod.WHOLE_SIGN] == expected


def test_chart_ruler_is_the_ruler_of_the_ascendant_sign(chart):
    from astro.rulers import ruler_of
    assert chart.chart_ruler == ruler_of(to_sign(chart.angles.asc).sign_index, "traditional")


def test_dispositors_cover_every_body(chart):
    assert set(chart.dispositors.dispositor) == set(chart.positions)


def test_every_value_in_json_is_a_plain_type(chart):
    """Числа Skyfield приходят из numpy, наружу они так попадать не должны."""
    import json

    def walk(value, path):
        if isinstance(value, dict):
            for key, item in value.items():
                walk(item, f"{path}.{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f"{path}[{index}]")
        elif value is not None:
            assert type(value).__module__ == "builtins", f"{path}: {type(value)}"

    data = chart.to_dict(include_birth_data=True)
    walk(data, "root")
    json.dumps(data, ensure_ascii=False)


def test_json_hides_birth_data_by_default(chart):
    data = chart.to_dict()
    assert "birth" not in data
    assert set(data) >= {"id", "positions", "houses", "aspects", "angles", "dispositors"}
    text = repr(data)
    assert "1987" not in text and "50.45" not in text and "30.52" not in text


def test_json_includes_birth_data_on_request(chart):
    data = chart.to_dict(include_birth_data=True)
    assert data["birth"]["zone"] == "Europe/Kyiv"
    assert data["birth"]["offset_hours"] == pytest.approx(4.0)


def test_identifier_depends_on_salt_and_on_the_data(eph):
    moment, place = KYIV
    chart = compute(moment, place, ephemeris=eph)
    other = compute(datetime(1987, 7, 14, 11, 26), place, ephemeris=eph)
    assert chart.digest("соль") != chart.digest("другая соль")
    assert chart.digest("соль") == chart.digest("соль")
    assert chart.digest("соль") != other.digest("соль")


def test_node_distance_is_reported_as_absent(chart):
    """У расчётных точек нет расстояния, и в JSON оно не выдумывается."""
    assert chart.to_dict()["positions"]["true_node"]["distance_au"] is None
    assert chart.to_dict()["positions"]["sun"]["distance_au"] > 0


def test_manual_offset_changes_the_chart(eph):
    moment, place = KYIV
    default = compute(moment, place, ephemeris=eph)
    shifted = compute(moment, place, utc_offset_hours=3.0, ephemeris=eph)
    assert abs(default.angles.asc - shifted.angles.asc) > 10.0


def test_polar_birth_needs_a_fallback(eph):
    place = Place(78.2232, 15.6267, "Лонгйир")
    with pytest.raises(houses_mod.CircumpolarError):
        compute(datetime(2010, 6, 21, 12, 0), place, ephemeris=eph,
                house_systems=(houses_mod.PLACIDUS,))
    chart = compute(datetime(2010, 6, 21, 12, 0), place, ephemeris=eph,
                    house_systems=(houses_mod.PLACIDUS,),
                    house_fallback=houses_mod.WHOLE_SIGN)
    assert chart.primary_houses.system == houses_mod.WHOLE_SIGN


def test_place_validates_coordinates():
    with pytest.raises(ValueError):
        Place(91.0, 0.0)
    with pytest.raises(ValueError):
        Place(0.0, 181.0)


def test_cli_renders_and_emits_json(capsys, eph):
    from astro.cli import main
    assert main(["1987-07-14 11:25", "50.4501", "30.5234", "--place", "Киев"]) == 0
    text = capsys.readouterr().out
    assert "ПОЛОЖЕНИЯ" in text and "ДОМА" in text and "АСПЕКТЫ" in text

    assert main(["1987-07-14 11:25", "50.4501", "30.5234", "--json"]) == 0
    import json
    data = json.loads(capsys.readouterr().out)
    assert data["positions"]["sun"]["sign"] == "Рак"
    assert "birth" not in data
