"""Запуск бота: python3 -m bot"""

from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from astro.ephemeris import EphemerisNotFound, load_ephemeris

from . import handlers
from .config import Config, ConfigError


async def run() -> None:
    config = Config.from_env()
    ephemeris = load_ephemeris(config.ephemeris_path)
    logging.info("эфемериды: %s", ephemeris.name)

    handlers.setup(config, ephemeris)

    bot = Bot(
        token=config.token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_router(handlers.router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dispatcher.start_polling(bot)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        asyncio.run(run())
    except (ConfigError, EphemerisNotFound) as error:
        print(str(error), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
