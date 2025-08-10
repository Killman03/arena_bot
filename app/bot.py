from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from .config import settings
from .handlers import setup_routers
from .logging_config import setup_logging
from .db.session import SessionLocal, create_all
from .utils.scheduler import AppScheduler
from .middlewares import InteractionLoggingMiddleware


async def main() -> None:
    logger = setup_logging()
    logger.info("Starting Gladiator Arena Life Bot")

    # Ensure tables for local run (prefer Alembic for production)
    await create_all()

    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()
    dp.message.middleware(InteractionLoggingMiddleware())
    dp.include_router(setup_routers())

    scheduler = AppScheduler(bot=bot, session_factory=SessionLocal)
    scheduler.start()

    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.getLogger(__name__).info("Bot stopped")


