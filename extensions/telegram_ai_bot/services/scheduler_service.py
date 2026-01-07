import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from core import config, db
from core.formatting import escape_markdown_v2
from services import data_service, llm_service, rss_service

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone=config.TIMEZONE)


def _generate_default_times(count: int) -> list[str]:
    count = max(1, min(count, 6))
    if count == 1:
        return ["09:00"]
    start = 9
    end = 21
    step = (end - start) / (count - 1)
    hours = [int(round(start + i * step)) for i in range(count)]
    times = [f"{h:02d}:00" for h in hours]
    return sorted(dict.fromkeys(times))


def _parse_time(value: str) -> tuple[int, int] | None:
    if not isinstance(value, str) or len(value) != 5 or value[2] != ":":
        return None
    try:
        hour = int(value[:2])
        minute = int(value[3:])
    except ValueError:
        return None
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return hour, minute
    return None


def _normalize_times(cfg: dict) -> list[str]:
    times = []
    raw_times = cfg.get("brief_times")
    if isinstance(raw_times, list):
        for item in raw_times:
            if _parse_time(item):
                times.append(item)

    times = sorted(dict.fromkeys(times))
    if times:
        count = cfg.get("brief_count")
        if isinstance(count, int) and count > 0 and len(times) > count:
            return times[:count]
        return times

    count = cfg.get("brief_count")
    if isinstance(count, int) and count > 0:
        return _generate_default_times(count)

    daily_time = cfg.get("daily_time") or config.DAILY_BRIEF_TIME
    if _parse_time(daily_time):
        return [daily_time]

    return ["09:00"]


def get_brief_times(cfg: dict) -> list[str]:
    return _normalize_times(cfg)


def _job_id(user_id: int, time_str: str) -> str:
    return f"brief:{user_id}:{time_str}"


def _remove_user_jobs(user_id: int):
    prefix = f"brief:{user_id}:"
    for job in scheduler.get_jobs():
        if job.id.startswith(prefix):
            scheduler.remove_job(job.id)


async def schedule_user_brief(bot: Bot, user_id: int, cfg: dict):
    _remove_user_jobs(user_id)
    times = _normalize_times(cfg)
    for time_str in times:
        parsed = _parse_time(time_str)
        if not parsed:
            continue
        hour, minute = parsed
        scheduler.add_job(
            send_brief_for_user,
            "cron",
            hour=hour,
            minute=minute,
            args=[bot, user_id],
            id=_job_id(user_id, time_str),
            replace_existing=True,
        )
    logger.info("Scheduled %d brief job(s) for user %s: %s", len(times), user_id, ", ".join(times))


async def refresh_user_schedule(bot: Bot, user_id: int):
    cfg = await db.get_config(user_id)
    await schedule_user_brief(bot, user_id, cfg)


async def start_scheduler(bot: Bot):
    user_ids = await db.get_all_user_ids()
    for user_id in user_ids:
        cfg = await db.get_config(user_id)
        await schedule_user_brief(bot, user_id, cfg)
    scheduler.start()
    logger.info("Scheduler started for %d user(s)", len(user_ids))


async def send_brief_for_user(bot: Bot, user_id: int):
    try:
        logger.info("Generating brief for user %s", user_id)
        cfg = await db.get_config(user_id)

        events = await data_service.get_todays_news(limit=100)

        user_sources = await db.get_user_sources(user_id)
        if user_sources:
            source_urls = [s["url"] for s in user_sources]
            rss_items = await rss_service.get_user_rss_items(source_urls)
            for item in rss_items:
                item["platform_id"] = "RSS"
                item["rank"] = 0
                item["is_subscribed"] = True
                events.append(item)

        if not events:
            return

        filtered_events, stats = data_service.filter_news(events, cfg)
        if not filtered_events:
            return

        brief_text, err = await llm_service.generate_brief(
            filtered_events,
            cfg,
            api_key=cfg.get("api_key"),
        )

        if err:
            logger.error("Brief generation error for %s: %s", user_id, err)
            return

        stats_info = escape_markdown_v2(
            f"🔍 扫描: {stats['total']} | ✅ 保留: {stats['kept']} | 🗑️ 过滤: {stats['dropped']}\n"
        )
        stats_text = f"🕒 *{escape_markdown_v2('智能简报定时推送')}*\n{stats_info}"

        final_text = f"{stats_text}\n{brief_text}"

        await bot.send_message(user_id, final_text, parse_mode="MarkdownV2")

    except Exception as e:
        logger.exception("Error sending brief to %s: %s", user_id, e)
