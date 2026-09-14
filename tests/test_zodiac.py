"""Знаки и форматирование градусов."""

import pytest

from astro.zodiac import (
    norm180, norm360, separation, to_sign, format_longitude, format_signed_arc,
)


@pytest.mark.parametrize("value,expected", [
    (0.0, 0.0), (360.0, 0.0), (-1.0, 359.0), (725.0, 5.0),
])
def test_norm360(value, expected):
    assert norm360(value) == pytest.approx(expected)


@pytest.mark.parametrize("value,expected", [
    (0.0, 0.0), (180.0, 180.0), (181.0, -179.0), (-180.0, 180.0), (359.0, -1.0),
])
def test_norm180(value, expected):
    assert norm180(value) == pytest.approx(expected)


def test_separation_is_shortest_arc():
    assert separation(359.0, 2.0) == pytest.approx(3.0)
    assert separation(10.0, 190.0) == pytest.approx(180.0)


@pytest.mark.parametrize("longitude,sign,degree", [
    (0.0, "Овен", 0), (29.99, "Овен", 29), (30.0, "Телец", 0),
    (123.456, "Лев", 3), (359.9, "Рыбы", 29),
])
def test_to_sign(longitude, sign, degree):
    position = to_sign(longitude)
    assert position.sign == sign
    assert position.degree == degree


def test_rounding_does_not_produce_sixty_seconds():
    """29°59'59.6" округляется в следующий знак, а не в 59'60"."""
    text = format_longitude(30.0 - 0.4 / 3600.0)
    assert "60" not in text
    assert text.startswith("00°00'00\"")
    assert "Телец" in text


def test_element_and_modality():
    assert to_sign(5.0).element == "Огонь"       # Овен
    assert to_sign(35.0).element == "Земля"      # Телец
    assert to_sign(5.0).modality == "Кардинальный"
    assert to_sign(125.0).modality == "Фиксированный"  # Лев


def test_format_signed_arc():
    assert format_signed_arc(-2.25) == "-2°15'00\""
    assert format_signed_arc(1.5).startswith("+1°30")
