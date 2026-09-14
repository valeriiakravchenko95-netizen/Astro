"""Клавиатуры бота."""

from __future__ import annotations

from typing import List, Sequence

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from . import texts
from .places import Place

#: Разделы карты, доступные кнопками под основным сообщением.
SECTIONS = (
    ("houses", "Углы и дома"),
    ("aspects", "Аспекты"),
    ("dignities", "Достоинства"),
    ("patterns", "Фигуры и антисы"),
    ("dispositors", "Диспозиторы"),
)


def start() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=texts.START_BUTTON)]],
        resize_keyboard=True,
    )


def unknown_time() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=texts.UNKNOWN_TIME_BUTTON)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def remove() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def place_choice(places: Sequence[Place]) -> InlineKeyboardMarkup:
    """Кнопки выбора места; в callback_data идёт только номер варианта."""
    rows: List[List[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text=place.label(), callback_data=f"place:{index}")]
        for index, place in enumerate(places)
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def sections(available: Sequence[str]) -> InlineKeyboardMarkup:
    """Кнопки разделов — только те, для которых есть содержимое."""
    buttons = [
        InlineKeyboardButton(text=title, callback_data=f"section:{key}")
        for key, title in SECTIONS
        if key in available
    ]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(inline_keyboard=rows)
