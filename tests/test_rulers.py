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


# --- Триплицитеты, термы, деканы -------------------------------------------


def test_triplicity_rulers_follow_the_sect():
    # Огонь: днём Солнце, ночью Юпитер
    assert rulers.triplicity_ruler(0, diurnal=True) == "sun"
    assert rulers.triplicity_ruler(0, diurnal=False) == "jupiter"
    # Вода по Дорофею: днём Венера, ночью Марс
    assert rulers.triplicity_ruler(3, diurnal=True) == "venus"
    assert rulers.triplicity_ruler(3, diurnal=False) == "mars"


def test_ptolemy_gives_water_to_mars_in_both_sects():
    assert rulers.triplicity_ruler(3, True, rulers.PTOLEMY) == "mars"
    assert rulers.triplicity_ruler(3, False, rulers.PTOLEMY) == "mars"
    assert rulers.triplicity_rulers(0, rulers.PTOLEMY)[2] is None


def test_signs_of_one_element_share_triplicity_rulers():
    for element_start in range(4):
        signs = [element_start + 4 * step for step in range(3)]
        rulers_seen = {rulers.triplicity_rulers(sign) for sign in signs}
        assert len(rulers_seen) == 1


def test_unknown_triplicity_scheme_rejected():
    with pytest.raises(ValueError):
        rulers.triplicity_rulers(0, "выдуманная")


def test_every_sign_is_covered_by_exactly_thirty_degrees_of_terms():
    for sign_index, rows in rulers.EGYPTIAN_TERMS.items():
        assert rows[-1][1] == 30, sign_index
        boundaries = [boundary for _, boundary in rows]
        assert boundaries == sorted(boundaries), sign_index


def test_terms_divide_the_whole_circle():
    """Египетские термы: Венера 82°, Юпитер 79°, Меркурий 76°, Марс 66°, Сатурн 57°."""
    totals = {}
    for rows in rulers.EGYPTIAN_TERMS.values():
        previous = 0
        for ruler, boundary in rows:
            totals[ruler] = totals.get(ruler, 0) + boundary - previous
            previous = boundary
    assert totals == {"venus": 82, "jupiter": 79, "mercury": 76, "mars": 66, "saturn": 57}
    assert sum(totals.values()) == 360


@pytest.mark.parametrize("longitude,expected", [
    (0.0, "jupiter"), (5.99, "jupiter"), (6.0, "venus"),
    (19.99, "mercury"), (20.0, "mars"), (29.99, "saturn"),
])
def test_term_ruler_at_boundaries(longitude, expected):
    assert rulers.term_ruler(longitude) == expected


def test_term_bounds():
    assert rulers.term_bounds(3.0) == (0.0, 6.0)
    assert rulers.term_bounds(21.0) == (20.0, 25.0)


def test_chaldean_decans_start_from_mars_in_aries():
    assert [rulers.decan_ruler(d) for d in (5, 15, 25)] == ["mars", "sun", "venus"]
    assert [rulers.decan_ruler(30 + d) for d in (5, 15, 25)] == ["mercury", "moon", "saturn"]


def test_chaldean_decans_cycle_through_all_seven():
    seen = [rulers.decan_ruler(10 * step + 5) for step in range(36)]
    assert set(seen) == set(rulers.CHALDEAN_ORDER)
    assert seen[0] == seen[7]  # ряд из семи планет повторяется


def test_triplicity_decans_stay_within_the_element():
    """Деканы знака достаются управителям знаков той же стихии."""
    assert [rulers.decan_ruler(d, rulers.TRIPLICITY_DECANS) for d in (5, 15, 25)] == [
        "mars", "sun", "jupiter"  # Овен, Лев, Стрелец
    ]


def test_unknown_decan_scheme_rejected():
    with pytest.raises(ValueError):
        rulers.decan_ruler(5.0, "выдуманная")


def test_essential_dignities_collects_all_five():
    # Солнце в 4°30' Овна: экзальтация и дневной триплицитет Огня
    item = rulers.essential_dignities("sun", 4.5, diurnal=True)
    assert item.state == "exaltation"
    assert set(item.own) == {"exaltation", "triplicity"}
    assert item.ruler == "mars"
    assert item.term == "jupiter"
    assert item.decan == "mars"
    assert not item.peregrine


def test_body_without_major_dignity_is_not_automatically_peregrine():
    """Терм или декан спасают тело от перегринности.

    Меркурий в 15° Овна не имеет там ни обители, ни экзальтации, ни ущерба,
    но 12–20° Овна — его собственный терм.
    """
    item = rulers.essential_dignities("mercury", 15.0, diurnal=True)
    assert item.state == "peregrine"      # ни обители, ни экзальтации
    assert item.own == ("term",)
    assert not item.peregrine             # но перегрином он не является


def test_truly_peregrine_body():
    """Луна в 5° Близнецов не занимает ни одного из пяти достоинств."""
    item = rulers.essential_dignities("moon", 65.0, diurnal=True)
    assert item.state == "peregrine"
    assert item.own == ()
    assert item.peregrine


def test_exaltation_ruler_of_sign():
    assert rulers.exaltation_ruler_of(0) == "sun"
    assert rulers.exaltation_ruler_of(2) is None  # в Близнецах никто не экзальтирует
