"""Бот: разбор ввода, поиск места, диалог и обращение с данными рождения.

Telegram здесь не участвует — сообщения подменены простыми объектами,
которые запоминают отправленный текст. Проверяется логика диалога, а не
транспорт.
"""

import os
import sys
from dataclasses import dataclass, field
from datetime import date, time
from typing import Any, List, Optional

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram.fsm.context import FSMContext  # noqa: E402
from aiogram.fsm.storage.base import StorageKey  # noqa: E402
from aiogram.fsm.storage.memory import MemoryStorage  # noqa: E402

from bot import handlers, keyboards, render, texts  # noqa: E402
from bot.config import Config, ConfigError  # noqa: E402
from bot.parsing import ParseError, parse_date, parse_optional_time, parse_time  # noqa: E402
from bot.places import Place, normalize, parse_coordinates, search  # noqa: E402
from bot.states import ChartDialog  # noqa: E402


# --- Разбор ввода ----------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("21.05.1995", date(1995, 5, 21)),
    ("1995-05-21", date(1995, 5, 21)),
    ("21/05/1995", date(1995, 5, 21)),
    ("  21 05 1995 ", date(1995, 5, 21)),
])
def test_parse_date(text, expected):
    assert parse_date(text) == expected


@pytest.mark.parametrize("text", ["21.05.95", "вчера", "32.05.1995", "05.21.1995", ""])
def test_bad_dates_are_refused(text):
    """Двузначный год не принимается: 95 может быть и 1995, и 2095."""
    with pytest.raises(ParseError):
        parse_date(text)


@pytest.mark.parametrize("year", [1700, 2200])
def test_dates_outside_the_ephemeris_range_are_refused(year):
    with pytest.raises(ParseError):
        parse_date(f"21.05.{year}")


@pytest.mark.parametrize("text,expected", [
    ("16:10", time(16, 10)), ("16.10", time(16, 10)),
    ("9:05", time(9, 5)), ("16", time(16, 0)),
])
def test_parse_time(text, expected):
    assert parse_time(text) == expected


@pytest.mark.parametrize("text", ["25:00", "полдень", "16:99", ""])
def test_bad_times_are_refused(text):
    with pytest.raises(ParseError):
        parse_time(text)


@pytest.mark.parametrize("text", ["не знаю", "НЕ ЗНАЮ", "неизвестно", "?", "-"])
def test_unknown_time_is_recognised(text):
    assert parse_optional_time(text) is None


# --- Поиск места -----------------------------------------------------------

def test_city_search_is_case_and_script_insensitive():
    for query in ("Донецк", "донецк", "Donetsk"):
        found = search(query)
        assert found, query
        assert found[0].name == "Donetsk"


def test_larger_city_comes_first():
    """У одинаковых названий первым идёт тот, который вероятнее имелся в виду."""
    found = search("Донецк")
    assert len(found) >= 2
    assert found[0].population > found[1].population
    assert found[0].country == "UA"


def test_search_by_prefix():
    found = search("Мариу")
    assert any(place.name == "Mariupol" for place in found)


def test_search_normalizes_separators():
    assert normalize("Санкт-Петербург") == normalize("санкт петербург")
    assert search("Санкт-Петербург")[0].name == "Saint Petersburg"


def test_unknown_place_gives_nothing():
    assert search("нетакогогородавообще") == []
    assert search("") == []


@pytest.mark.parametrize("text,expected", [
    ("48.02, 37.80", (48.02, 37.80)),
    ("48.02 37.80", (48.02, 37.80)),
    ("-33.9, 18.4", (-33.9, 18.4)),
])
def test_parse_coordinates(text, expected):
    assert parse_coordinates(text) == expected


@pytest.mark.parametrize("text", ["48.02", "чепуха", "95.0, 37.0", "48.0, 200.0"])
def test_bad_coordinates_are_refused(text):
    assert parse_coordinates(text) is None


# --- Оформление ------------------------------------------------------------

def test_long_text_is_split_into_messages_and_pre_is_closed():
    body = "\n".join(f"строка номер {i}" for i in range(400))
    text = f"<b>Заголовок</b>\n<pre>{body}</pre>"
    parts = render.split(text, limit=1000)
    assert len(parts) > 1
    for part in parts:
        assert len(part) <= 1200
        assert part.count("<pre>") == part.count("</pre>")


def test_short_text_is_not_split():
    assert render.split("коротко") == ["коротко"]


# --- Конфигурация ----------------------------------------------------------

def test_config_requires_a_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    with pytest.raises(ConfigError):
        Config.from_env()


def test_env_file_is_read(tmp_path, monkeypatch):
    from bot.config import load_env_file

    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("ASTRO_RULERS", raising=False)
    path = tmp_path / ".env"
    path.write_text(
        "# комментарий\n"
        "TELEGRAM_BOT_TOKEN=\"из-файла\"\n"
        "\n"
        "ASTRO_RULERS = modern\n"
        "мусор без равно\n",
        encoding="utf-8",
    )
    load_env_file(str(path))
    assert os.environ["TELEGRAM_BOT_TOKEN"] == "из-файла"
    assert os.environ["ASTRO_RULERS"] == "modern"


def test_env_file_does_not_override_the_environment(tmp_path, monkeypatch):
    """На сервере настройки задают окружением, и файл не должен их перебивать."""
    from bot.config import load_env_file

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "из-окружения")
    path = tmp_path / ".env"
    path.write_text("TELEGRAM_BOT_TOKEN=из-файла\n", encoding="utf-8")
    load_env_file(str(path))
    assert os.environ["TELEGRAM_BOT_TOKEN"] == "из-окружения"


def test_missing_env_file_is_not_an_error(tmp_path):
    from bot.config import load_env_file

    load_env_file(str(tmp_path / "нет-такого"))


def test_config_error_explains_how_to_get_a_token(monkeypatch, tmp_path):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ConfigError) as error:
        Config.from_env()
    assert "@BotFather" in str(error.value)


def test_config_reads_the_environment(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret")
    monkeypatch.setenv("ASTRO_HOUSE_SYSTEM", "whole_sign")
    config = Config.from_env()
    assert config.token == "secret"
    assert config.house_system == "whole_sign"


# --- Диалог ----------------------------------------------------------------

@dataclass
class FakeMessage:
    """Подставное сообщение: запоминает, что бот ответил."""

    text: Optional[str] = None
    location: Any = None
    sent: List[str] = field(default_factory=list)
    markups: List[Any] = field(default_factory=list)

    async def answer(self, text, reply_markup=None, **kwargs):
        self.sent.append(text)
        self.markups.append(reply_markup)
        return self


@dataclass
class FakeCallback:
    data: str
    message: FakeMessage

    async def answer(self, *args, **kwargs):
        return None


@pytest.fixture
def state():
    storage = MemoryStorage()
    return FSMContext(
        storage=storage,
        key=StorageKey(bot_id=1, chat_id=1, user_id=1),
    )


@pytest.fixture(autouse=True)
def runtime(eph):
    handlers.setup(Config(token="test"), eph)


async def walk_dialog(state, date_text, time_text, place_text):
    """Проводит диалог до расчёта и возвращает последнее сообщение."""
    message = FakeMessage(text="/chart")
    await handlers.on_chart(message, state)

    message = FakeMessage(text=date_text)
    await handlers.on_date(message, state)

    message = FakeMessage(text=time_text)
    await handlers.on_time(message, state)

    message = FakeMessage(text=place_text)
    await handlers.on_place(message, state)
    return message


@pytest.mark.asyncio
async def test_dialog_asks_for_each_field_in_turn(state):
    message = FakeMessage(text="/chart")
    await handlers.on_chart(message, state)
    assert await state.get_state() == ChartDialog.waiting_date

    message = FakeMessage(text="21.05.1995")
    await handlers.on_date(message, state)
    assert await state.get_state() == ChartDialog.waiting_time

    message = FakeMessage(text="16:10")
    await handlers.on_time(message, state)
    assert await state.get_state() == ChartDialog.waiting_place


@pytest.mark.asyncio
async def test_bad_input_does_not_advance_the_dialog(state):
    await handlers.on_chart(FakeMessage(), state)
    message = FakeMessage(text="вчера")
    await handlers.on_date(message, state)
    assert await state.get_state() == ChartDialog.waiting_date
    assert texts.BAD_DATE in message.sent


@pytest.mark.asyncio
async def test_ambiguous_place_offers_a_choice(state):
    await handlers.on_chart(FakeMessage(), state)
    await handlers.on_date(FakeMessage(text="21.05.1995"), state)
    await handlers.on_time(FakeMessage(text="16:10"), state)
    message = FakeMessage(text="Донецк")
    await handlers.on_place(message, state)
    assert await state.get_state() == ChartDialog.choosing_place
    assert texts.CHOOSE_PLACE in message.sent


@pytest.mark.asyncio
async def test_unknown_place_is_reported(state):
    await handlers.on_chart(FakeMessage(), state)
    await handlers.on_date(FakeMessage(text="21.05.1995"), state)
    await handlers.on_time(FakeMessage(text="16:10"), state)
    message = FakeMessage(text="нетакогогорода")
    await handlers.on_place(message, state)
    assert texts.PLACE_NOT_FOUND in message.sent
    assert await state.get_state() == ChartDialog.waiting_place


@pytest.mark.asyncio
async def test_chart_is_produced_from_coordinates(state):
    message = await walk_dialog(state, "21.05.1995", "16:10", "48.023, 37.802")
    output = "\n".join(message.sent)
    assert "ПОЛОЖЕНИЯ" in output
    assert "Солнце" in output
    assert await state.get_state() == ChartDialog.showing_chart


@pytest.mark.asyncio
async def test_birth_data_is_erased_after_the_calculation(state):
    """Главное требование: после расчёта дата и место не остаются в памяти."""
    await walk_dialog(state, "21.05.1995", "16:10", "48.023, 37.802")
    data = await state.get_data()
    assert "date" not in data and "time" not in data and "places" not in data
    assert set(data) <= {"sections", "chart_id"}
    stored = repr(data)
    assert "1995" not in stored
    assert "48.02" not in stored and "37.80" not in stored


@pytest.mark.asyncio
async def test_chart_identifier_is_kept_for_the_session(state):
    await walk_dialog(state, "21.05.1995", "16:10", "48.023, 37.802")
    data = await state.get_data()
    assert len(data["chart_id"]) == 64  # SHA-256 в шестнадцатеричном виде


@pytest.mark.asyncio
async def test_unknown_time_hides_houses_and_warns(state):
    message = await walk_dialog(state, "21.05.1995", texts.UNKNOWN_TIME_BUTTON,
                                "48.023, 37.802")
    output = "\n".join(message.sent)
    assert "Время рождения неизвестно" in output
    data = await state.get_data()
    assert "houses" not in data["sections"]


@pytest.mark.asyncio
async def test_known_time_keeps_houses(state):
    await walk_dialog(state, "21.05.1995", "16:10", "48.023, 37.802")
    data = await state.get_data()
    assert "houses" in data["sections"]
    assert "ASC" in data["sections"]["houses"]


@pytest.mark.asyncio
async def test_sections_can_be_requested_afterwards(state):
    await walk_dialog(state, "21.05.1995", "16:10", "48.023, 37.802")
    message = FakeMessage()
    await handlers.on_section(FakeCallback("section:aspects", message), state)
    assert any("АСПЕКТЫ" in text for text in message.sent)


@pytest.mark.asyncio
async def test_section_request_without_a_chart_says_so(state):
    message = FakeMessage()
    await handlers.on_section(FakeCallback("section:aspects", message), state)
    assert texts.SESSION_LOST in message.sent


@pytest.mark.asyncio
async def test_cancel_clears_everything(state):
    await handlers.on_chart(FakeMessage(), state)
    await handlers.on_date(FakeMessage(text="21.05.1995"), state)
    message = FakeMessage()
    await handlers.on_cancel(message, state)
    assert await state.get_state() is None
    assert await state.get_data() == {}
    assert texts.CANCELLED in message.sent


@pytest.mark.asyncio
async def test_choosing_a_place_produces_the_chart(state):
    await handlers.on_chart(FakeMessage(), state)
    await handlers.on_date(FakeMessage(text="21.05.1995"), state)
    await handlers.on_time(FakeMessage(text="16:10"), state)
    await handlers.on_place(FakeMessage(text="Донецк"), state)

    message = FakeMessage()
    await handlers.on_place_chosen(FakeCallback("place:0", message), state)
    assert any("ПОЛОЖЕНИЯ" in text for text in message.sent)
    data = await state.get_data()
    assert "places" not in data


@pytest.mark.asyncio
async def test_only_available_sections_get_buttons(state):
    await walk_dialog(state, "21.05.1995", texts.UNKNOWN_TIME_BUTTON, "48.023, 37.802")
    data = await state.get_data()
    markup = keyboards.sections(list(data["sections"]))
    offered = {
        button.callback_data.split(":", 1)[1]
        for row in markup.inline_keyboard for button in row
    }
    assert "houses" not in offered
    assert "aspects" in offered
