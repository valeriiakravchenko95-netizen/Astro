"""Аспекты, орбисы, схождение и расхождение."""

from dataclasses import dataclass

import pytest

from astro import aspects


@dataclass
class Fake:
    longitude: float
    speed: float


def test_exact_aspects_are_found():
    for aspect in aspects.MAJOR:
        hit = aspects.find_between("mars", 10.0, 0.5, "saturn", 10.0 + aspect.angle, 0.1)
        assert hit is not None and hit.aspect.key == aspect.key
        assert hit.orb == pytest.approx(0.0, abs=1e-12)
        assert hit.strength == pytest.approx(1.0)


def test_aspect_beyond_orb_is_not_reported():
    hit = aspects.find_between("mars", 0.0, 0.5, "saturn", 100.0, 0.1)
    assert hit is None


def test_luminaries_get_wider_orb():
    policy = aspects.DEFAULT_ORBS
    assert policy.limit("sun", "mars", aspects.CONJUNCTION) == pytest.approx(10.0)
    assert policy.limit("mars", "saturn", aspects.CONJUNCTION) == pytest.approx(8.0)
    assert policy.limit("sun", "moon", aspects.CONJUNCTION) == pytest.approx(10.0)


def test_combine_modes():
    summed = aspects.OrbPolicy(combine="sum")
    averaged = aspects.OrbPolicy(combine="mean")
    assert summed.limit("sun", "moon", aspects.CONJUNCTION) == pytest.approx(12.0)
    assert averaged.limit("sun", "moon", aspects.CONJUNCTION) == pytest.approx(10.0)
    with pytest.raises(ValueError):
        aspects.OrbPolicy(combine="что-нибудь").limit("sun", "moon", aspects.CONJUNCTION)


def test_orbs_can_be_overridden():
    narrow = aspects.DEFAULT_ORBS.with_orbs(square=1.0)
    assert narrow.limit("mars", "saturn", aspects.SQUARE) == pytest.approx(1.0)
    assert aspects.find_between("mars", 0.0, 0.5, "saturn", 92.0, 0.1, policy=narrow) is None
    assert aspects.find_between("mars", 0.0, 0.5, "saturn", 92.0, 0.1) is not None
    with pytest.raises(KeyError):
        aspects.DEFAULT_ORBS.with_orbs(несуществующий=1.0)


def test_custom_policy_via_override():
    policy = aspects.OrbPolicy(override=lambda a, b, aspect: 0.5)
    assert aspects.find_between("mars", 0.0, 0.5, "saturn", 91.0, 0.1, policy=policy) is None
    assert aspects.find_between("mars", 0.0, 0.5, "saturn", 90.3, 0.1, policy=policy) is not None


def test_applying_when_faster_body_approaches():
    """Луна в 85° идёт к квадрату с Солнцем в 0° — аспект сходится."""
    hit = aspects.find_between("moon", 85.0, 13.0, "sun", 0.0, 1.0)
    assert hit.aspect.key == "square" and hit.applying


def test_separating_when_faster_body_has_passed():
    hit = aspects.find_between("moon", 95.0, 13.0, "sun", 0.0, 1.0)
    assert hit.aspect.key == "square" and not hit.applying


def test_direction_follows_relative_speed_not_absolute():
    """Аспект сходится, когда разность долгот идёт к точному углу.

    Марс уже прошёл квадрат к Сатурну на 5°. Пока Марс движется вперёд,
    аспект расходится; развернувшись в попятное движение, Марс идёт к
    точному квадрату обратно.
    """
    forward = aspects.find_between("mars", 95.0, 0.5, "saturn", 0.0, 0.03)
    backward = aspects.find_between("mars", 95.0, -0.5, "saturn", 0.0, 0.03)
    assert forward.aspect.key == "square" and not forward.applying
    assert backward.aspect.key == "square" and backward.applying


def test_slower_body_can_be_the_one_catching_up():
    """Солнце быстрее Марса, поэтому квадрат позади Марса всё равно сходится."""
    hit = aspects.find_between("mars", 95.0, 0.5, "sun", 0.0, 1.0)
    assert hit.aspect.key == "square" and hit.applying


def test_closest_aspect_wins_when_two_fit():
    """Соединение и полусекстиль могут перекрыться — берётся более точный."""
    hit = aspects.find_between(
        "sun", 0.0, 1.0, "mars", 9.5, 0.5, aspects=aspects.ALL_ASPECTS
    )
    assert hit.aspect.key == "conjunction"


def test_find_all_covers_each_pair_once_and_sorts_by_orb():
    positions = {
        "sun": Fake(0.0, 1.0), "moon": Fake(90.5, 13.0),
        "mars": Fake(180.2, 0.5), "venus": Fake(45.0, 1.2),
    }
    hits = aspects.find_all(positions)
    pairs = {frozenset((h.body_a, h.body_b)) for h in hits}
    assert len(pairs) == len(hits)
    assert [h.orb for h in hits] == sorted(h.orb for h in hits)


def test_aspects_to_angles_do_not_claim_direction():
    hits = aspects.to_angles(10.0, 1.0, "sun", {"asc": 10.5, "mc": 100.7})
    assert hits and all(not h.applying for h in hits)
    assert {h.body_b for h in hits} == {"asc", "mc"}
    by_angle = {h.body_b: h for h in hits}
    assert by_angle["asc"].aspect.key == "conjunction"
    assert by_angle["mc"].aspect.key == "square"


def test_opposition_orb_measured_across_the_circle():
    hit = aspects.find_between("sun", 359.0, 1.0, "mars", 178.0, 0.5)
    assert hit.aspect.key == "opposition"
    assert hit.orb == pytest.approx(1.0)
