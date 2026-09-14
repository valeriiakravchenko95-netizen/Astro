"""Настройки бота из переменных окружения."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

TOKEN_ENV = "TELEGRAM_BOT_TOKEN"

#: Файл с настройками рядом с проектом. Читается в переменные окружения,
#: если они ещё не заданы, — так удобнее запускать вручную, а на сервере
#: по-прежнему можно задать всё через окружение, и файл ничего не перебьёт.
ENV_FILE = ".env"


def load_env_file(path: Optional[str] = None) -> None:
    """Подхватывает переменные из .env, не затирая уже заданные.

    Формат простой: строки вида ``КЛЮЧ=значение``, решётка начинает
    комментарий, кавычки вокруг значения снимаются. Внешней библиотеки
    ради пятнадцати строк разбора здесь нет.
    """
    if path is None:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(root, ENV_FILE)
    if not os.path.isfile(path):
        return

    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("\"'")
            if key and key not in os.environ:
                os.environ[key] = value


class ConfigError(RuntimeError):
    """Бот не настроен."""


@dataclass(frozen=True)
class Config:
    """Что нужно боту для работы."""

    token: str
    ephemeris_path: Optional[str] = None
    house_system: str = "placidus"
    ruler_scheme: str = "traditional"
    lilith_model: str = "swiss"
    minor_aspects: bool = False
    #: Время, на которое считается карта, если оно неизвестно.
    unknown_time_hour: int = 12

    @classmethod
    def from_env(cls) -> "Config":
        load_env_file()
        token = os.environ.get(TOKEN_ENV, "").strip()
        if not token:
            raise ConfigError(
                f"не задан {TOKEN_ENV}.\n\n"
                "Бота нужно сперва завести в Telegram: напишите @BotFather, "
                "команда /newbot, дальше он спросит имя и адрес бота и выдаст "
                "токен.\n\n"
                f"Токен положите в файл {ENV_FILE} рядом с проектом:\n"
                f"    {TOKEN_ENV}=123456:ABC-DEF...\n"
                f"либо задайте в окружении: export {TOKEN_ENV}=..."
            )
        return cls(
            token=token,
            ephemeris_path=os.environ.get("ASTRO_EPHEMERIS") or None,
            house_system=os.environ.get("ASTRO_HOUSE_SYSTEM", "placidus"),
            ruler_scheme=os.environ.get("ASTRO_RULERS", "traditional"),
            lilith_model=os.environ.get("ASTRO_LILITH", "swiss"),
            minor_aspects=os.environ.get("ASTRO_MINOR_ASPECTS", "").lower()
            in ("1", "true", "yes", "да"),
        )
