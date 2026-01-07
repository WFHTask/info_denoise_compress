import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession

from core.logging_setup import setup_logging

setup_logging()

logger = logging.getLogger(__name__)

from core import config, runtime
from core.db import init_db
from handlers import admin, basic, natural_language, rss as rss_handler
from services.rss_service import rss_fetcher_loop
from services import scheduler_service


def create_bot() -> Bot:
    if config.PROXY_URL:
        session = AiohttpSession(proxy=config.PROXY_URL)
        return Bot(token=config.BOT_TOKEN, session=session)
    return Bot(token=config.BOT_TOKEN)


async def main():
    if not config.BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")

    await init_db()

    bot = create_bot()
    dp = Dispatcher()

    dp.include_router(rss_handler.router)
    dp.include_router(basic.router)
    dp.include_router(admin.router)
    dp.include_router(natural_language.create_router(dp, lambda: bot.id))

    asyncio.create_task(rss_fetcher_loop())
    await scheduler_service.start_scheduler(bot)

    me = await bot.me()
    runtime.BOT_USERNAME = me.username
    logger.info("Bot started: @%s", runtime.BOT_USERNAME)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

