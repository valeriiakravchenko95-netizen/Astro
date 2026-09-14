"""Управители, достоинства и цепочки диспозиторов."""

import pytest

from astro import rulers


def test_traditional_and_modern_schemes_differ_only_in_three_signs():
    traditional = rulers.rulers(rulers.TRADITIONAL)
    modern = rulers.rulers(rulers.MODERN)
    differing = {i for i in range(12) if traditional[i] != modern[i]}
    assert differing == {7, 10, 11}  # Скорпион, Водолей, Рыбы


def test_every_classical_planet_rules_two_signs_except_luminaries():
    for body in ("mercury", "venus", "mars", "jupiter", "saturn"):
        assert len(rulers.signs_ruled_by(body)) == 2
    for body in ("sun", "moon"):
        assert len(rulers.signs_ruled_by(body)) == 1


@pytest.mark.parametrize("body,sign_index,expected", [
    ("sun", 4, "domicile"),      # Лев
    ("sun", 10, "detriment"),    # Водолей
    ("sun", 0, "exaltation"),    # Овен
    ("sun", 6, "fall"),          # Весы
    ("moon", 3, "domicile"),     # Рак
    ("moon", 1, "exaltation"),   # Телец
    ("saturn", 6, "exaltation"), # Весы
    ("saturn", 0, "fall"),       # Овен
    ("mars", 3, "fall"),         # Рак
    ("venus", 5, "fall"),        # Дева: напротив экзальтации в Рыбах
    ("venus", 2, "peregrine"),   # Близнецы: без достоинства и без ущерба
])
def test_dignities(body, sign_index, expected):
    assert rulers.dignity(body, sign_index) == expected


def test_co_ruler_only_in_modern_scheme():
    assert rulers.co_ruler_of(7, rulers.MODERN) == "mars"
    assert rulers.co_ruler_of(7, rulers.TRADITIONAL) is None


def test_chain_ends_at_planet_in_its_own_sign():
    # Солнце в Деве -> Меркурий в Весах -> Венера в Тельце -> Венера
    tree = rulers.build_dispositors({"sun": 5, "mercury": 6, "venus": 1})
    assert tree.dispositor["sun"] == "mercury"
    assert tree.final_dispositors == ("venus",)
    assert tree.chain_of("sun") == ("mercury",)
    assert tree.terminal["sun"] == ("venus",)


def test_mutual_reception_forms_a_ring_of_two():
    # Марс в Весах и Венера в Овне управляют знаками друг друга
    tree = rulers.build_dispositors({"mars": 6, "venus": 0})
    assert tree.mutual_receptions == (("mars", "venus"),)
    assert tree.final_dispositors == ()


def test_longer_ring_is_detected_once():
    # Солнце в Раке -> Луна в Овне -> Марс во Льве -> Солнце
    tree = rulers.build_dispositors({"sun": 3, "moon": 0, "mars": 4})
    assert len(tree.cycles) == 1
    assert set(tree.cycles[0]) == {"sun", "moon", "mars"}
    assert tree.final_dispositors == ()


def test_chain_breaks_when_ruler_is_absent_from_the_chart():
    tree = rulers.build_dispositors({"sun": 7, "pluto": 0}, rulers.MODERN)
    assert tree.dispositor["pluto"] is None  # Марса в карте нет
    assert tree.terminal["sun"] is None
    assert "?" in rulers.describe_chain("sun", tree)


def test_chain_description_is_readable():
    tree = rulers.build_dispositors({"sun": 5, "mercury": 6, "venus": 1})
    assert rulers.describe_chain("venus", tree) == "venus в своей обители"
    assert "финальный диспозитор" in rulers.describe_chain("sun", tree)
    names = {"sun": "Солнце", "mercury": "Меркурий", "venus": "Венера"}
    assert "Солнце" in rulers.describe_chain("sun", tree, names)


def test_unknown_scheme_rejected():
    with pytest.raises(ValueError):
        rulers.rulers("выдуманная")
