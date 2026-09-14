"""Разбор даты и времени, введённых человеком."""

from __future__ import annotations

import re
from datetime import date, time
from typing import Optional

_DATE_PATTERNS = (
    "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%Y.%m.%d", "%d %m %Y",
)
_TIME_PATTERNS = ("%H:%M", "%H.%M", "%H %M", "%H:%M:%S")

#: Разумные границы: ядро считает по эфемеридам, покрывающим эти годы.
MIN_YEAR = 1850
MAX_YEAR = 2150


class ParseError(ValueError):
    """Введённое значение не разобрать."""


def parse_date(text: str) -> date:
    """Разбирает дату рождения.

    Двузначный год не принимается намеренно: «05» может значить и 1905,
    и 2005, и угадывать здесь нельзя — ошибка сместит всю карту.
    """
    from datetime import datetime

    cleaned = " ".join(text.strip().split())
    for pattern in _DATE_PATTERNS:
        try:
            value = datetime.strptime(cleaned, pattern).date()
        except ValueError:
            continue
        if not MIN_YEAR <= value.year <= MAX_YEAR:
            raise ParseError(
                f"год {value.year} вне диапазона {MIN_YEAR}–{MAX_YEAR}"
            )
        return value
    raise ParseError("не разобрать дату")


def parse_time(text: str) -> time:
    """Разбирает время рождения."""
    from datetime import datetime

    cleaned = " ".join(text.strip().split())
    # «16 10» и «1610» встречаются в документах, но вторая запись
    # неоднозначна, поэтому принимается только с разделителем
    if re.fullmatch(r"\d{1,2}", cleaned):
        hour = int(cleaned)
        if 0 <= hour <= 23:
            return time(hour, 0)
        raise ParseError("час вне диапазона 0–23")
    for pattern in _TIME_PATTERNS:
        try:
            return datetime.strptime(cleaned, pattern).time()
        except ValueError:
            continue
    raise ParseError("не разобрать время")


def parse_optional_time(text: str) -> Optional[time]:
    """Возвращает None, если человек сказал, что времени не знает."""
    lowered = text.strip().lower()
    if lowered in ("не знаю", "незнаю", "неизвестно", "-", "?", "не помню"):
        return None
    return parse_time(text)
