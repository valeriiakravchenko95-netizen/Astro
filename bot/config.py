"""Настройки бота из переменных окружения."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

TOKEN_ENV = "TELEGRAM_BOT_TOKEN"


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
        token = os.environ.get(TOKEN_ENV, "").strip()
        if not token:
            raise ConfigError(
                f"не задан {TOKEN_ENV}. Получите токен у @BotFather и укажите его "
                f"в окружении: export {TOKEN_ENV}=..."
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
