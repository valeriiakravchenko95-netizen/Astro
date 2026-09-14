"""Аспектные фигуры, стеллиумы и контакты по антисам."""

from dataclasses import dataclass

import pytest

from astro import aspects, patterns
from astro.zodiac import antiscion, contra_antiscion


@dataclass
class Point:
    longitude: float
    speed: float = 1.0


def figures(longitudes, aspect_set=aspects.MAJOR, **kwargs):
    positions = {key: Point(value) for key, value in longitudes.items()}
    hits = aspects.find_all(positions, aspects=aspect_set)
    return patterns.find_patterns(hits, **kwargs)


def keys_of(found):
    return {hit.key for hit in found}


def test_grand_trine():
    found = figures({"a": 0.0, "b": 120.0, "c": 240.0})
    assert keys_of(found) == {"grand_trine"}
    assert found[0].members == {"a", "b", "c"}


def test_t_square():
    found = figures({"a": 0.0, "b": 180.0, "c": 90.0})
    assert keys_of(found) == {"t_square"}


def test_grand_cross_absorbs_its_t_squares():
    found = figures({"a": 0.0, "b": 90.0, "c": 180.0, "d": 270.0})
    assert keys_of(found) == {"grand_cross"}


def test_kite_absorbs_its_grand_trine():
    found = figures({"a": 0.0, "b": 120.0, "c": 240.0, "d": 180.0})
    assert keys_of(found) == {"kite"}


def test_subpatterns_can_be_requested():
    found = figures({"a": 0.0, "b": 120.0, "c": 240.0, "d": 180.0},
                    include_subpatterns=True)
    assert "grand_trine" in keys_of(found)
    assert "kite" in keys_of(found)


def test_yod_needs_minor_aspects():
    longitudes = {"a": 0.0, "b": 60.0, "c": 210.0}
    assert keys_of(figures(longitudes, aspects.MAJOR)) == set()
    assert keys_of(figures(longitudes, aspects.ALL_ASPECTS)) == {"yod"}


def test_minor_trine():
    found = figures({"a": 0.0, "b": 60.0, "c": 120.0})
    assert keys_of(found) == {"minor_trine"}


def test_mystic_rectangle():
    found = figures({"a": 0.0, "b": 60.0, "c": 180.0, "d": 240.0})
    assert "mystic_rectangle" in keys_of(found)


def test_pattern_not_reported_when_an_edge_is_out_of_orb():
    """Достаточно одному аспекту выйти из орбиса — фигуры нет."""
    assert keys_of(figures({"a": 0.0, "b": 120.0, "c": 240.0})) == {"grand_trine"}
    assert keys_of(figures({"a": 0.0, "b": 120.0, "c": 252.0})) == set()


def test_orbs_are_reported_per_edge():
    found = figures({"a": 0.0, "b": 121.0, "c": 240.0})
    hit = found[0]
    assert len(hit.orbs) == len(hit.spec.edges)
    assert hit.worst_orb == pytest.approx(1.0)
    assert hit.mean_orb <= hit.worst_orb


def test_node_pair_does_not_manufacture_a_t_square():
    """Узлы всегда в оппозиции, и это не повод считать фигуру."""
    longitudes = {"true_node": 0.0, "south_node": 180.0, "venus": 90.0}
    assert keys_of(figures(longitudes)) == set()
    assert keys_of(figures(longitudes, excluded=frozenset())) == {"t_square"}


def test_stellium_by_conjunction_and_by_sign():
    positions = {
        "sun": Point(10.0), "mercury": Point(14.0), "venus": Point(18.0),
        "mars": Point(200.0),
    }
    hits = aspects.find_all(positions)
    found = patterns.find_stelliums(positions, hits)
    by_conjunction = [item for item in found if item.by_conjunction]
    by_sign = [item for item in found if not item.by_conjunction]
    assert by_conjunction and by_conjunction[0].bodies == ("mercury", "sun", "venus")
    assert by_sign and by_sign[0].sign_index == 0


def test_stellium_needs_enough_members():
    positions = {"sun": Point(10.0), "mercury": Point(14.0)}
    hits = aspects.find_all(positions)
    assert patterns.find_stelliums(positions, hits) == ()


def test_antiscion_reflects_across_the_solstice_axis():
    assert antiscion(40.0) == pytest.approx(140.0)   # 10° Тельца → 20° Льва
    assert antiscion(90.0) == pytest.approx(90.0)    # 0° Рака неподвижна
    assert antiscion(270.0) == pytest.approx(270.0)  # 0° Козерога тоже
    assert antiscion(antiscion(123.0)) == pytest.approx(123.0)


def test_contra_antiscion_reflects_across_the_equinox_axis():
    assert contra_antiscion(0.0) == pytest.approx(0.0)
    assert contra_antiscion(30.0) == pytest.approx(330.0)
    assert contra_antiscion(contra_antiscion(77.0)) == pytest.approx(77.0)


def test_antiscia_contacts_are_found_within_orb():
    positions = {"sun": Point(40.0), "mars": Point(140.4), "venus": Point(320.2)}
    found = patterns.find_antiscia(positions, orb=1.0)
    kinds = {(hit.body_a, hit.body_b, hit.kind) for hit in found}
    assert ("sun", "mars", "antiscion") in kinds
    assert ("sun", "venus", "contra_antiscion") in kinds


def test_antiscia_respect_the_orb():
    positions = {"sun": Point(40.0), "mars": Point(143.0)}
    assert patterns.find_antiscia(positions, orb=1.0) == ()
    assert patterns.find_antiscia(positions, orb=3.5) != ()
