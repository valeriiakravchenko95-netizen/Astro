"""Хендлеры диалога.

Данные рождения живут в состоянии диалога только до расчёта. Сразу после
него состояние очищается и вместо них сохраняются готовые тексты разделов
и идентификатор карты — так в памяти процесса не остаётся ни даты, ни
места, а листать разделы всё равно можно.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, Optional

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from astro import houses as houses_mod
from astro.chart import Chart, Place as ChartPlace, compute
from astro.timeutil import TimeZoneError

from . import keyboards, render, texts
from .config import Config
from .parsing import ParseError, parse_date, parse_optional_time
from .places import Place, parse_coordinates, search
from .states import ChartDialog

router = Router()
logger = logging.getLogger(__name__)

#: Конфигурация и эфемериды подставляются при запуске.
_runtime: Dict[str, object] = {}


def setup(config: Config, ephemeris) -> None:
    _runtime["config"] = config
    _runtime["ephemeris"] = ephemeris


def _config() -> Config:
    return _runtime["config"]


@router.message(CommandStart())
async def on_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(texts.START, reply_markup=keyboards.start())


@router.message(Command("help"))
async def on_help(message: Message) -> None:
    await message.answer(texts.HELP)


@router.message(Command("cancel"))
async def on_cancel(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        await message.answer(texts.NOTHING_TO_CANCEL)
        return
    await state.clear()
    await message.answer(texts.CANCELLED, reply_markup=keyboards.remove())


@router.message(Command("chart"))
@router.message(F.text == texts.START_BUTTON)
async def on_chart(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(ChartDialog.waiting_date)
    await message.answer(texts.ASK_DATE, reply_markup=keyboards.remove())


@router.message(ChartDialog.waiting_date, F.text)
async def on_date(message: Message, state: FSMContext) -> None:
    try:
        value = parse_date(message.text)
    except ParseError:
        await message.answer(texts.BAD_DATE)
        return
    await state.update_data(date=value.isoformat())
    await state.set_state(ChartDialog.waiting_time)
    await message.answer(texts.ASK_TIME, reply_markup=keyboards.unknown_time())


@router.message(ChartDialog.waiting_time, F.text)
async def on_time(message: Message, state: FSMContext) -> None:
    text = message.text
    if text == texts.UNKNOWN_TIME_BUTTON:
        text = "не знаю"
    try:
        value = parse_optional_time(text)
    except ParseError:
        await message.answer(texts.BAD_TIME)
        return
    await state.update_data(time=value.isoformat() if value else None)
    await state.set_state(ChartDialog.waiting_place)
    await message.answer(texts.ASK_PLACE, reply_markup=keyboards.remove())


@router.message(ChartDialog.waiting_place, F.location)
async def on_location(message: Message, state: FSMContext) -> None:
    place = Place(
        name="координаты",
        country="",
        latitude=message.location.latitude,
        longitude=message.location.longitude,
        population=0,
    )
    await _calculate(message, state, place)


@router.message(ChartDialog.waiting_place, F.text)
async def on_place(message: Message, state: FSMContext) -> None:
    coordinates = parse_coordinates(message.text)
    if coordinates is not None:
        latitude, longitude = coordinates
        place = Place("координаты", "", latitude, longitude, 0)
        await _calculate(message, state, place)
        return

    found = search(message.text)
    if not found:
        await message.answer(texts.PLACE_NOT_FOUND)
        return
    if len(found) == 1:
        await _calculate(message, state, found[0])
        return

    await state.update_data(
        places=[
            [place.name, place.country, place.latitude, place.longitude, place.population]
            for place in found
        ]
    )
    await state.set_state(ChartDialog.choosing_place)
    await message.answer(
        texts.CHOOSE_PLACE, reply_markup=keyboards.place_choice(found)
    )


@router.callback_query(ChartDialog.choosing_place, F.data.startswith("place:"))
async def on_place_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    raw = data.get("places") or []
    index = int(callback.data.split(":", 1)[1])
    if index >= len(raw):
        await callback.message.answer(texts.SESSION_LOST)
        await state.clear()
        return
    name, country, latitude, longitude, population = raw[index]
    place = Place(name, country, latitude, longitude, population)
    await _calculate(callback.message, state, place)


@router.callback_query(F.data.startswith("section:"))
async def on_section(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    sections = data.get("sections")
    if not sections:
        await callback.message.answer(texts.SESSION_LOST)
        return
    key = callback.data.split(":", 1)[1]
    text = sections.get(key)
    if not text:
        await callback.message.answer(texts.SESSION_LOST)
        return
    for part in render.split(text):
        await callback.message.answer(part)


async def _calculate(message: Message, state: FSMContext, place: Place) -> None:
    data = await state.get_data()
    if not data.get("date"):
        await message.answer(texts.SESSION_LOST)
        await state.clear()
        return

    config = _config()
    birth_date = datetime.fromisoformat(data["date"]).date()
    raw_time = data.get("time")
    exact_time = raw_time is not None
    if exact_time:
        hour, minute = (int(part) for part in raw_time.split(":")[:2])
    else:
        hour, minute = config.unknown_time_hour, 0

    await message.answer(texts.CALCULATING)

    try:
        chart = compute(
            datetime(birth_date.year, birth_date.month, birth_date.day, hour, minute),
            ChartPlace(place.latitude, place.longitude, place.short()),
            house_systems=(config.house_system, houses_mod.WHOLE_SIGN),
            primary_system=config.house_system,
            house_fallback=houses_mod.WHOLE_SIGN,
            ruler_scheme=config.ruler_scheme,
            lilith_model=config.lilith_model,
            ephemeris=_runtime.get("ephemeris"),
        )
    except (TimeZoneError, ValueError) as error:
        # Сообщение об ошибке не содержит введённых данных: логируем только
        # тип отказа, чтобы в журнал не попали дата и место.
        logger.warning("расчёт не удался: %s", type(error).__name__)
        await message.answer(texts.ERROR.format(reason=error))
        await state.clear()
        return

    sections = _sections(chart, exact_time)
    header = render.header(chart, place.short() if place.population else None, exact_time)
    body = sections.pop("positions")

    # Всё, что касается рождения, стирается прямо здесь: дальше живут
    # только готовые тексты и идентификатор карты.
    await state.clear()
    await state.set_state(ChartDialog.showing_chart)
    await state.update_data(sections=sections, chart_id=chart.digest())

    for part in render.split(f"{header}\n\n{body}"):
        await message.answer(part, reply_markup=keyboards.remove())
    await message.answer(
        "Что показать дальше?", reply_markup=keyboards.sections(list(sections))
    )


def _sections(chart: Chart, exact_time: bool) -> Dict[str, str]:
    """Готовит тексты разделов.

    Без точного времени дома и углы не выдаются вовсе: показывать их —
    значит выдавать за расчёт то, что определяется минутами рождения.
    """
    sections = {"positions": render.positions(chart, with_houses=exact_time)}
    if exact_time:
        houses_text = render.angles_and_houses(chart)
        angle_text = render.angle_aspects(chart)
        sections["houses"] = f"{houses_text}\n\n{angle_text}" if angle_text else houses_text
    for key, text in (
        ("aspects", render.aspects(chart)),
        ("dignities", render.dignities(chart)),
        ("patterns", render.patterns(chart)),
        ("dispositors", render.dispositors(chart)),
    ):
        if text:
            sections[key] = text
    return sections
