"""
Web3 Daily Digest - Telegram Bot Entry Point

Main application file that initializes the bot, sets up handlers,
and configures scheduled tasks for daily digest delivery.

Reference: python-telegram-bot v22.x with built-in JobQueue
"""
import asyncio
import logging
from logging.handlers import TimedRotatingFileHandler
import os
import sys
import signal
import atexit
from datetime import time, datetime, timedelta
from typing import Dict, Any
from zoneinfo import ZoneInfo

from telegram import (
    BotCommand,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import (
    TELEGRAM_BOT_TOKEN, PUSH_HOUR, PUSH_MINUTE, DATA_DIR,
    LOG_ROTATE_DAYS, LOG_BACKUP_COUNT, MAX_DIGEST_ITEMS, CONCURRENT_USERS,
    PREFETCH_INTERVAL_HOURS, PREFETCH_START_HOUR, ADMIN_TELEGRAM_IDS,
    PUSH_MODE, PUSH_INTERVAL_HOURS, PUSH_INTERVAL_PRO_HOURS,
    PUSH_QUIET_START, PUSH_QUIET_END, PUSH_CHECK_INTERVAL
)
from services.digest_processor import process_single_user
from utils.telegram_utils import safe_answer_callback_query
from utils.json_storage import get_user_language
from locales.ui_strings import get_ui_locale
from handlers.start import get_start_handler, get_start_callbacks
from handlers.feedback import get_feedback_handlers
from handlers.settings import get_settings_handler, get_settings_callbacks
from handlers.sources import get_sources_handler, get_sources_callbacks
from handlers.admin import get_admin_handlers
from handlers.payment import get_payment_handlers
from handlers.group import get_group_handler, get_group_callbacks
from services.rate_limiter import get_rate_limiter


# ============ Logging Configuration ============

# Create logs directory
LOGS_DIR = os.path.join(DATA_DIR, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)


class HeartbeatFilter(logging.Filter):
    """Filter out noisy heartbeat/polling log messages."""

    # Patterns to filter out
    NOISE_PATTERNS = [
        "HTTP Request: POST https://api.telegram.org/bot",
        "getUpdates",
        "Got response",
        "Entering:",
        "Exiting:",
        "No updates to fetch",
        "Network loop",
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        for pattern in self.NOISE_PATTERNS:
            if pattern in msg:
                return False
        return True


log_formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Console handler (with heartbeat filter)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_formatter)
console_handler.addFilter(HeartbeatFilter())

# Timed rotating file handler: rotate every N days, keep 30 backups
# 按天轮转日志，LOG_ROTATE_DAYS 控制几天轮转一次，LOG_BACKUP_COUNT 控制保留数量
file_handler = TimedRotatingFileHandler(
    os.path.join(LOGS_DIR, "bot.log"),
    when="D",                        # 按天
    interval=LOG_ROTATE_DAYS,        # 每 N 天轮转
    backupCount=LOG_BACKUP_COUNT,    # 保留 N 个备份（默认30天）
    encoding="utf-8"
)
file_handler.setFormatter(log_formatter)
file_handler.addFilter(HeartbeatFilter())

logging.basicConfig(
    level=logging.INFO,
    handlers=[console_handler, file_handler]
)

# Reduce noise from third-party libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Force reload environment variables and update config
from dotenv import load_dotenv
import config

env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_path):
    load_dotenv(env_path, override=True)
    logger.info(f"Force reloaded .env from {env_path}")

# Update config variable (support multiple admins)
_admin_ids_str = os.getenv("ADMIN_TELEGRAM_IDS", "") or os.getenv("ADMIN_TELEGRAM_ID", "")
config.ADMIN_TELEGRAM_IDS = [id.strip() for id in _admin_ids_str.split(",") if id.strip()]
config.ADMIN_TELEGRAM_ID = config.ADMIN_TELEGRAM_IDS[0] if config.ADMIN_TELEGRAM_IDS else ""
logger.info(f"Admin IDs configured: {len(config.ADMIN_TELEGRAM_IDS)} admin(s)")


async def daily_digest_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Scheduled job to generate and send daily digest.
    In fixed_time mode: pushes Free users only (Pro users get hourly push via pro_realtime_job).
    Uses concurrent processing for better performance with pre-fetching optimization.
    """
    from utils.json_storage import get_users, get_user_sources
    from utils.permissions import check_feature
    from services.rss_fetcher import fetch_all_sources

    logger.info("Starting daily digest generation...")

    today = datetime.now().strftime("%Y-%m-%d")

    try:
        # Get all users
        all_users = get_users()
        if not all_users:
            logger.warning("No users registered, skipping digest")
            return

        # In fixed_time: Free only (Pro gets hourly push via pro_realtime_job)
        if PUSH_MODE == "fixed_time":
            users = [u for u in all_users if u.get("telegram_id") and not check_feature(u["telegram_id"], "priority_push")]
            if not users:
                logger.info("No Free users due for daily digest")
                return
        else:
            users = all_users

        # ===== Pre-fetch optimization: Collect all unique sources =====
        logger.info("Collecting all user sources...")
        all_sources = {}  # {category: {name: url}}

        for user in users:
            telegram_id = user.get("telegram_id")
            if not telegram_id:
                continue

            user_sources = get_user_sources(telegram_id)
            # Merge into global sources dict
            for category, sources in user_sources.items():
                if category not in all_sources:
                    all_sources[category] = {}
                for name, url in sources.items():
                    if url and name not in all_sources[category]:
                        all_sources[category][name] = url

        # Count unique sources
        unique_sources_count = sum(len(sources) for sources in all_sources.values())
        logger.info(f"Found {unique_sources_count} unique RSS sources across {len(users)} users")

        # Batch fetch all sources once (shared by all users)
        logger.info("Pre-fetching all RSS sources...")
        global_raw_content = await fetch_all_sources(
            hours_back=24,
            sources=all_sources
        )
        logger.info(f"Pre-fetched {len(global_raw_content)} total items")
        # ===== Pre-fetch complete =====

        logger.info(f"Processing {len(users)} users with concurrency={CONCURRENT_USERS}")

        # Concurrent processing with semaphore to limit concurrency
        semaphore = asyncio.Semaphore(CONCURRENT_USERS)

        async def process_with_limit(user):
            async with semaphore:
                # Pass global data to avoid duplicate fetching
                return await process_single_user(context, user, today, global_raw_content)

        # Process all users concurrently
        results = await asyncio.gather(
            *[process_with_limit(user) for user in users],
            return_exceptions=True  # Single user failure doesn't affect others
        )

        # Collect statistics
        success_count = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "success")
        error_count = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "error")
        skipped_count = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "skipped")
        exception_count = sum(1 for r in results if isinstance(r, Exception))

        logger.info(
            f"Daily digest complete: {success_count} success, {error_count} errors, "
            f"{skipped_count} skipped, {exception_count} exceptions"
        )

        # Log any exceptions that occurred
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"User {users[i].get('telegram_id')} raised exception: {result}")

    except Exception as e:
        logger.error(f"Daily digest job failed: {e}", exc_info=True)


async def interval_digest_check_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Scheduled job for user_interval mode: check which users are due for push.
    Pro users: push every PUSH_INTERVAL_PRO_HOURS (default 1h, 24h timely real-time).
    Free users: push every PUSH_INTERVAL_HOURS (default 24h, once per day).
    Respects quiet hours (PUSH_QUIET_START to PUSH_QUIET_END).
    """
    from config import PAUSE_PUSH
    from utils.json_storage import get_users, get_user_sources
    from utils.permissions import check_feature

    # Check if push is paused (for debugging)
    if PAUSE_PUSH:
        logger.info("Push paused (PAUSE_PUSH=true), skipping interval check")
        return

    beijing_tz = ZoneInfo("Asia/Shanghai")
    now = datetime.now(beijing_tz)
    current_hour = now.hour

    # Check if we're in quiet hours
    if PUSH_QUIET_START <= current_hour < PUSH_QUIET_END:
        logger.debug(f"In quiet hours ({PUSH_QUIET_START}:00-{PUSH_QUIET_END}:00), skipping interval check")
        return

    logger.info("Running interval digest check...")

    today = datetime.now().strftime("%Y-%m-%d")

    def parse_datetime(dt_str: str) -> datetime:
        """Parse ISO format datetime string."""
        # Handle ISO format with or without microseconds
        dt_str = dt_str.replace("Z", "+00:00")
        if "+" not in dt_str and "T" in dt_str:
            # No timezone, assume Beijing time
            dt = datetime.fromisoformat(dt_str)
            dt = dt.replace(tzinfo=beijing_tz)
        else:
            dt = datetime.fromisoformat(dt_str)
        return dt

    try:
        # Get all users
        users = get_users()
        if not users:
            logger.debug("No users registered, skipping interval check")
            return

        # Find users who are due for push (Pro: shorter interval, Free: 24h)
        due_users = []

        for user in users:
            telegram_id = user.get("telegram_id")
            if not telegram_id:
                continue

            # CRITICAL: 推送间隔判定 — 不可使用 check_feature()
            # check_feature() 在 FEATURE_PAYMENT=false 时对所有人返回 True，
            # 会导致全员被当作 Pro (1h间隔) 高频推送。
            # 事故记录: 2026-02-23, 2026-03-05。守卫测试: test_critical_guards.py
            from config import FEATURE_PAYMENT
            if FEATURE_PAYMENT:
                is_pro = check_feature(telegram_id, "priority_push")
            else:
                from utils.permissions import get_user_plan
                is_pro = get_user_plan(str(telegram_id)) == "pro"

            custom = user.get("settings", {}).get("push_interval_hours")
            if custom is not None and isinstance(custom, (int, float)) and is_pro:
                interval_hours = max(1, min(24, int(custom)))
            elif is_pro:
                interval_hours = PUSH_INTERVAL_PRO_HOURS
            else:
                interval_hours = PUSH_INTERVAL_HOURS
            interval_seconds = interval_hours * 3600

            # Get last push time
            last_push_str = user.get("last_push_time")
            created_str = user.get("created")

            if last_push_str:
                try:
                    last_push = parse_datetime(last_push_str)
                    time_since_push = (now - last_push).total_seconds()
                    if time_since_push >= interval_seconds:
                        due_users.append(user)
                except Exception as e:
                    logger.warning(f"Failed to parse last_push_time for {telegram_id}: {e}")
            elif created_str:
                try:
                    created = parse_datetime(created_str)
                    time_since_created = (now - created).total_seconds()
                    if time_since_created >= interval_seconds:
                        due_users.append(user)
                except Exception as e:
                    logger.warning(f"Failed to parse created time for {telegram_id}: {e}")

        if not due_users:
            logger.info("No users due for push this interval")
            return

        logger.info(f"Found {len(due_users)} users due for push")

        # Collect all sources from due users
        all_sources = {}
        for user in due_users:
            telegram_id = user.get("telegram_id")
            user_sources = get_user_sources(telegram_id)
            for category, sources in user_sources.items():
                if category not in all_sources:
                    all_sources[category] = {}
                for name, url in sources.items():
                    if url and name not in all_sources[category]:
                        all_sources[category][name] = url

        # Pre-fetch all sources
        from services.rss_fetcher import fetch_all_sources
        logger.info(f"Pre-fetching sources for {len(due_users)} due users...")
        global_raw_content = await fetch_all_sources(
            hours_back=24,
            sources=all_sources
        )
        logger.info(f"Pre-fetched {len(global_raw_content)} items")

        # Process due users with concurrency limit
        semaphore = asyncio.Semaphore(CONCURRENT_USERS)

        async def process_with_limit(user):
            async with semaphore:
                return await process_single_user(context, user, today, global_raw_content)

        results = await asyncio.gather(
            *[process_with_limit(user) for user in due_users],
            return_exceptions=True
        )

        # Collect statistics
        success_count = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "success")
        error_count = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "error")
        exception_count = sum(1 for r in results if isinstance(r, Exception))

        logger.info(
            f"Interval digest complete: {success_count} success, {error_count} errors, {exception_count} exceptions"
        )

    except Exception as e:
        logger.error(f"Interval digest check failed: {e}", exc_info=True)


async def pro_realtime_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Scheduled job for fixed_time mode: push Pro users every PUSH_INTERVAL_PRO_HOURS.
    Pro users get 24-hour timely real-time push; runs every hour.
    Respects quiet hours.
    """
    from config import PAUSE_PUSH, PUSH_QUIET_START, PUSH_QUIET_END
    from utils.json_storage import get_users, get_user_sources
    from utils.permissions import check_feature
    from services.rss_fetcher import fetch_all_sources

    if PUSH_MODE != "fixed_time":
        return
    if PAUSE_PUSH:
        return

    beijing_tz = ZoneInfo("Asia/Shanghai")
    now = datetime.now(beijing_tz)
    if PUSH_QUIET_START <= now.hour < PUSH_QUIET_END:
        return

    today = datetime.now().strftime("%Y-%m-%d")

    def parse_datetime(dt_str: str) -> datetime:
        dt_str = dt_str.replace("Z", "+00:00")
        if "+" not in dt_str and "T" in dt_str:
            dt = datetime.fromisoformat(dt_str)
            return dt.replace(tzinfo=beijing_tz)
        return datetime.fromisoformat(dt_str)

    try:
        users = get_users()
        if not users:
            return
        due_users = []
        for user in users:
            telegram_id = user.get("telegram_id")
            if not telegram_id or not check_feature(telegram_id, "priority_push"):
                continue
            custom = user.get("settings", {}).get("push_interval_hours")
            if custom is not None and isinstance(custom, (int, float)):
                interval_hours = max(1, min(24, int(custom)))
            else:
                interval_hours = PUSH_INTERVAL_PRO_HOURS
            interval_seconds = interval_hours * 3600
            last_push_str = user.get("last_push_time")
            created_str = user.get("created")
            ref_str = last_push_str or created_str
            if not ref_str:
                due_users.append(user)
                continue
            try:
                ref_dt = parse_datetime(ref_str)
                if (now - ref_dt).total_seconds() >= interval_seconds:
                    due_users.append(user)
            except Exception:
                pass
        if not due_users:
            return
        logger.info(f"Pro realtime: pushing {len(due_users)} Pro users")
        all_sources = {}
        for u in due_users:
            for cat, srcs in get_user_sources(u.get("telegram_id") or "").items():
                if cat not in all_sources:
                    all_sources[cat] = {}
                for name, url in (srcs or {}).items():
                    if url and name not in all_sources[cat]:
                        all_sources[cat][name] = url
        global_raw_content = await fetch_all_sources(hours_back=24, sources=all_sources)
        semaphore = asyncio.Semaphore(CONCURRENT_USERS)

        async def process_with_limit(user):
            async with semaphore:
                return await process_single_user(context, user, today, global_raw_content)

        await asyncio.gather(*[process_with_limit(u) for u in due_users], return_exceptions=True)
    except Exception as e:
        logger.error(f"Pro realtime job failed: {e}", exc_info=True)


async def test_fetch_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin-only /test command - manually trigger digest for testing."""
    from utils.json_storage import get_user, get_user_sources
    from services.rss_fetcher import fetch_all_sources
    from handlers.admin import is_admin
    
    user = update.effective_user
    telegram_id = str(user.id)
    
    # Admin check
    if not is_admin(user.id):
        await update.message.reply_text("此命令仅限管理员使用。")
        return
    
    today = datetime.now().strftime("%Y-%m-%d")

    await update.message.reply_text("正在为你生成简报...")

    try:
        # Get current user's data
        user_data = get_user(telegram_id)
        if not user_data:
            await update.message.reply_text("未找到你的用户数据，请先完成 /start 设置。")
            return
        
        # Fetch sources for this user only
        user_sources = get_user_sources(telegram_id)
        if not user_sources:
            await update.message.reply_text("你还没有配置信息源，请使用 /sources 添加。")
            return
        
        # Add sources to user_data for process_single_user
        user_data["sources"] = user_sources
        
        logger.info(f"Test command: Processing user {telegram_id}")
        
        # Fetch RSS content for this user
        raw_content = await fetch_all_sources(
            hours_back=24,
            sources=user_sources
        )
        logger.info(f"Test command: Fetched {len(raw_content)} items for user {telegram_id}")
        
        # Process single user
        result = await process_single_user(context, user_data, today, raw_content)
        
        if result.get("status") == "success":
            await update.message.reply_text("简报已发送！")
        elif result.get("status") == "skipped":
            await update.message.reply_text(f"跳过: {result.get('reason', '未知原因')}")
        else:
            await update.message.reply_text(f"处理失败: {result.get('error', '未知错误')[:100]}")
            
    except Exception as e:
        logger.error(f"Test fetch failed for user {telegram_id}: {e}", exc_info=True)
        await update.message.reply_text(f"抓取失败: {str(e)[:100]}")


async def test_profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin-only /testprofile command - manually trigger profile update from feedback."""
    from services.profile_updater import update_all_user_profiles
    from handlers.admin import is_admin

    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("此命令仅限管理员使用。")
        return

    await update.message.reply_text("正在更新用户画像...")

    try:
        await update_all_user_profiles()
        await update.message.reply_text("画像更新完成。")
    except Exception as e:
        logger.error(f"Test profile update failed: {e}")
        await update.message.reply_text(f"更新失败: {str(e)[:100]}")


async def test_prefetch_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin-only /testprefetch command - manually trigger prefetch and show stats."""
    from services.rss_fetcher import prefetch_all_user_sources
    from utils.json_storage import get_prefetch_cache
    from datetime import datetime
    from handlers.admin import is_admin

    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("此命令仅限管理员使用。")
        return

    await update.message.reply_text("🔄 正在执行预抓取测试...")

    try:
        # 执行预抓取
        stats = await prefetch_all_user_sources()

        # 获取缓存状态
        today = datetime.now().strftime("%Y-%m-%d")
        cache = get_prefetch_cache(today)

        result_text = f"""✅ 预抓取测试完成

📊 本次抓取统计：
• 用户数: {stats.get('users_count', 0)}
• 信息源数: {stats.get('sources_count', 0)}
• 新增条目: {stats.get('new_items', 0)}
• 重复跳过: {stats.get('duplicates', 0)}

📦 当日缓存状态：
• 累计条目: {len(cache.get('items', []))}
• 去重 ID 数: {len(cache.get('seen_ids', []))}
• 抓取次数: {cache.get('fetch_count', 0)}
• 最后抓取: {cache.get('last_fetch', 'N/A')[:19] if cache.get('last_fetch') else 'N/A'}

💡 提示：
• 如果"新增条目"为 0 且"重复跳过"有数值，说明去重正常工作
• 多次执行此命令，观察"累计条目"是否增加（有新推文时）"""

        await update.message.reply_text(result_text)

    except Exception as e:
        logger.error(f"Test prefetch failed: {e}", exc_info=True)
        await update.message.reply_text(f"❌ 预抓取失败: {str(e)[:200]}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    telegram_id = str(update.effective_user.id)
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)
    
    keyboard = [
        [
            InlineKeyboardButton(ui["back_to_main"], callback_data="back_to_start"),
            InlineKeyboardButton(ui["menu_preferences"], callback_data="update_preferences"),
        ],
        [InlineKeyboardButton(ui["menu_sources"], callback_data="manage_sources")],
        [InlineKeyboardButton(
            ui.get("help_group_setup", "Group Push Guidelines"),
            callback_data="group_setup_guide"
        )],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    help_text = f"""{ui['help_title']}
{ui['divider']}

{ui['help_commands']}
{ui['help_start']}
{ui['help_settings']}
{ui['help_sources']}
{ui['help_stats']}
{ui['help_help']}

{ui['divider']}

{ui['help_features']}

{ui['help_digest_title']}
{ui['help_digest_desc']}

{ui['help_settings_title']}
{ui['help_settings_desc']}

{ui['help_sources_title']}
{ui['help_sources_desc']}

{ui['help_stats_title']}
{ui['help_stats_desc']}

{ui['help_feedback_title']}
{ui['help_feedback_desc']}

{ui['divider']}

{ui['help_footer']}"""

    await update.message.reply_text(help_text, reply_markup=reply_markup)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /stats command - show user statistics."""
    from services.profile_updater import analyze_feedback_trends
    from utils.json_storage import get_user

    def _translate_trend(trend: str) -> str:
        """Translate trend text to Chinese."""
        translations = {
            "improving": "improving",
            "declining": "declining",
            "stable": "stable",
            "no_data": "no_data",
        }
        return translations.get(trend, trend.replace('_', ' '))

    user = update.effective_user
    telegram_id = str(user.id)
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)

    db_user = get_user(telegram_id)
    if not db_user:
        await update.message.reply_text(ui.get("not_registered", "Please use /start to begin."))
        return

    # Get feedback trends
    trends = await analyze_feedback_trends(telegram_id, days=30)

    # Translate trend
    trend_key = f"stats_trend_{_translate_trend(trends['trend'])}"
    trend_text = ui.get(trend_key, trends['trend'])

    stats_text = f"""{ui.get('stats_your_stats', 'Your Statistics')}
{ui['divider']}

{ui.get('stats_registered', 'Registered')}: {db_user.get('created', 'Unknown')[:10]}

{ui.get('stats_last_30_days', 'Last 30 days')}
  {ui.get('stats_total_feedbacks', 'Feedbacks')}: {trends['total_feedbacks']}
  {ui.get('stats_positive', 'Positive')}: {trends['positive_count']}
  {ui.get('stats_negative', 'Negative')}: {trends['negative_count']}
  {ui.get('stats_satisfaction', 'Satisfaction')}: {trends['positive_rate']:.0%}
  {ui.get('stats_trend', 'Trend')}: {trend_text}
{f"  {ui.get('stats_issues', 'Issues')}: {', '.join(trends['common_issues'][:2])}" if trends['common_issues'] else ""}

{ui['divider']}

{ui.get('settings_use_settings', 'Use /settings to adjust preferences.')}"""

    keyboard = [
        [
            InlineKeyboardButton(ui.get("settings_update", "Update Preferences"), callback_data="settings_update"),
            InlineKeyboardButton(ui.get("menu_main", "Main Menu"), callback_data="back_to_start"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(stats_text, reply_markup=reply_markup)


async def post_init(application: Application) -> None:
    """Post-initialization callback to set up scheduled jobs and bot commands."""
    # Auto-detect RSS for sources configured with domain only (AUTO: prefix)
    from config import resolve_default_sources_rss
    await resolve_default_sources_rss()
    
    # Set bot commands menu for private chats and groups separately.
    # This exposes /setup in groups without cluttering private chat menus.
    private_commands_zh = [
        BotCommand("start", "主菜单"),
        BotCommand("help", "帮助信息"),
        BotCommand("settings", "偏好设置"),
        BotCommand("sources", "信息源管理"),
        BotCommand("stats", "查看统计"),
    ]
    await application.bot.set_my_commands(private_commands_zh)  # Default fallback
    await application.bot.set_my_commands(private_commands_zh, scope=BotCommandScopeAllPrivateChats())
    await application.bot.set_my_commands(private_commands_zh, scope=BotCommandScopeAllPrivateChats(), language_code="zh")

    private_commands_en = [
        BotCommand("start", "Main Menu"),
        BotCommand("help", "Help"),
        BotCommand("settings", "Preferences"),
        BotCommand("sources", "Sources"),
        BotCommand("stats", "Statistics"),
    ]
    await application.bot.set_my_commands(private_commands_en, scope=BotCommandScopeAllPrivateChats(), language_code="en")

    private_commands_ja = [
        BotCommand("start", "メインメニュー"),
        BotCommand("help", "ヘルプ"),
        BotCommand("settings", "設定"),
        BotCommand("sources", "情報源"),
        BotCommand("stats", "統計"),
    ]
    await application.bot.set_my_commands(private_commands_ja, scope=BotCommandScopeAllPrivateChats(), language_code="ja")

    private_commands_ko = [
        BotCommand("start", "메인 메뉴"),
        BotCommand("help", "도움말"),
        BotCommand("settings", "설정"),
        BotCommand("sources", "소스"),
        BotCommand("stats", "통계"),
    ]
    await application.bot.set_my_commands(private_commands_ko, scope=BotCommandScopeAllPrivateChats(), language_code="ko")

    group_commands_zh = [
        BotCommand("setup", "配置群推送"),
        BotCommand("help", "帮助信息"),
        BotCommand("cancel", "取消当前操作"),
    ]
    await application.bot.set_my_commands(group_commands_zh, scope=BotCommandScopeAllGroupChats())
    await application.bot.set_my_commands(group_commands_zh, scope=BotCommandScopeAllGroupChats(), language_code="zh")

    group_commands_en = [
        BotCommand("setup", "Configure group push"),
        BotCommand("help", "Help"),
        BotCommand("cancel", "Cancel current action"),
    ]
    await application.bot.set_my_commands(group_commands_en, scope=BotCommandScopeAllGroupChats(), language_code="en")

    group_commands_ja = [
        BotCommand("setup", "グループ配信を設定"),
        BotCommand("help", "ヘルプ"),
        BotCommand("cancel", "現在の操作をキャンセル"),
    ]
    await application.bot.set_my_commands(group_commands_ja, scope=BotCommandScopeAllGroupChats(), language_code="ja")

    group_commands_ko = [
        BotCommand("setup", "그룹 푸시 설정"),
        BotCommand("help", "도움말"),
        BotCommand("cancel", "현재 작업 취소"),
    ]
    await application.bot.set_my_commands(group_commands_ko, scope=BotCommandScopeAllGroupChats(), language_code="ko")

    logger.info("Bot commands menu set for private/group chats in zh/en/ja/ko")

    # Get timezone for Beijing
    beijing_tz = ZoneInfo("Asia/Shanghai")

    # Schedule digest based on PUSH_MODE
    if PUSH_MODE == "fixed_time":
        # Fixed time mode: push all users at the same time
        push_time = time(hour=PUSH_HOUR, minute=PUSH_MINUTE, tzinfo=beijing_tz)

        application.job_queue.run_daily(
            callback=daily_digest_job,
            time=push_time,
            name="daily_digest"
        )

        logger.info(f"Scheduled daily digest at {PUSH_HOUR:02d}:{PUSH_MINUTE:02d} Beijing Time (fixed_time, Free only)")

        # Pro users: hourly real-time push
        application.job_queue.run_repeating(
            callback=pro_realtime_job,
            interval=3600,
            first=120,
            name="pro_realtime"
        )
        logger.info(f"Pro realtime: every {PUSH_INTERVAL_PRO_HOURS}h for Pro users")

        # Run profile updates 30 minutes before daily digest push
        profile_update_hour = PUSH_HOUR if PUSH_MINUTE >= 30 else (PUSH_HOUR - 1) % 24
        profile_update_minute = (PUSH_MINUTE - 30) % 60
        profile_update_time = time(hour=profile_update_hour, minute=profile_update_minute, tzinfo=beijing_tz)
        application.job_queue.run_daily(
            callback=profile_update_job,
            time=profile_update_time,
            name="profile_update"
        )
        logger.info(f"Scheduled profile update at {profile_update_hour:02d}:{profile_update_minute:02d} Beijing Time")

    else:
        # User interval mode: check every PUSH_CHECK_INTERVAL minutes for due users
        application.job_queue.run_repeating(
            callback=interval_digest_check_job,
            interval=PUSH_CHECK_INTERVAL * 60,  # Convert minutes to seconds
            first=60,  # Start 60 seconds after boot
            name="interval_digest_check"
        )

        logger.info(
            f"Scheduled interval digest check every {PUSH_CHECK_INTERVAL} minutes "
            f"(user_interval mode, {PUSH_INTERVAL_HOURS}h cycle, "
            f"quiet hours {PUSH_QUIET_START:02d}:00-{PUSH_QUIET_END:02d}:00)"
        )

        # Profile updates run every 6 hours in interval mode
        for update_hour in [2, 8, 14, 20]:
            profile_update_time = time(hour=update_hour, minute=30, tzinfo=beijing_tz)
            application.job_queue.run_daily(
                callback=profile_update_job,
                time=profile_update_time,
                name=f"profile_update_{update_hour:02d}"
            )
        logger.info("Scheduled profile updates at 02:30, 08:30, 14:30, 20:30 Beijing Time")

    # Run data cleanup at 00:30 daily
    # 每日 00:30 清理过期数据文件
    cleanup_time = time(hour=0, minute=30, tzinfo=beijing_tz)
    application.job_queue.run_daily(
        callback=data_cleanup_job,
        time=cleanup_time,
        name="data_cleanup"
    )

    logger.info("Scheduled data cleanup at 00:30 Beijing Time")

    # T7: Group digest push — check every hour if any group is due for push
    from config import FEATURE_GROUP_CHAT
    if FEATURE_GROUP_CHAT:
        application.job_queue.run_repeating(
            callback=group_digest_push_job,
            interval=3600,  # Check every hour
            first=120,  # Start 2 minutes after boot
            name="group_digest_push"
        )
        logger.info("Scheduled group digest push job (hourly check)")

    # Schedule prefetch jobs (if enabled)
    # 预抓取任务：每隔 PREFETCH_INTERVAL_HOURS 小时执行一次
    if PREFETCH_INTERVAL_HOURS > 0:
        # 计算预抓取时间点
        prefetch_times = []
        hour = PREFETCH_START_HOUR
        while hour < 24:
            prefetch_times.append(hour)
            hour += PREFETCH_INTERVAL_HOURS

        # 为每个时间点创建定时任务
        for i, prefetch_hour in enumerate(prefetch_times):
            prefetch_time = time(hour=prefetch_hour, minute=0, tzinfo=beijing_tz)
            application.job_queue.run_daily(
                callback=prefetch_job,
                time=prefetch_time,
                name=f"prefetch_{prefetch_hour:02d}"
            )

        # Only add pre-push prefetch in fixed_time mode
        if PUSH_MODE == "fixed_time":
            pre_push_hour = (PUSH_HOUR - 1) % 24 if PUSH_HOUR > 0 else 23
            pre_push_time = time(hour=pre_push_hour, minute=30, tzinfo=beijing_tz)
            application.job_queue.run_daily(
                callback=prefetch_job,
                time=pre_push_time,
                name="prefetch_pre_push"
            )
            logger.info(
                f"Scheduled prefetch jobs at hours: {prefetch_times} + {pre_push_hour:02d}:30 (pre-push) Beijing Time"
            )
        else:
            logger.info(f"Scheduled prefetch jobs at hours: {prefetch_times} Beijing Time")

        # 启动时立即执行一次预抓取（异步）
        application.job_queue.run_once(
            callback=prefetch_job,
            when=10,  # 10 秒后执行
            name="prefetch_startup"
        )
        logger.info("Scheduled startup prefetch in 10 seconds")
    else:
        logger.info("Prefetch disabled (PREFETCH_INTERVAL_HOURS=0)")

    # Startup changelog notification check (async, non-blocking startup)
    application.job_queue.run_once(
        callback=startup_changelog_notify_job,
        when=15,  # Execute shortly after boot
        name="startup_changelog_notify",
    )
    logger.info("Scheduled startup changelog notification check in 15 seconds")


async def startup_changelog_notify_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Check latest CHANGELOG version and notify subscribers on startup if version changed.
    """
    from scripts.send_changelog_update import parse_latest_changelog, send_latest_changelog_update
    from utils.json_storage import get_system_config, set_system_config

    logger.info("Running startup changelog notification check...")

    try:
        latest = parse_latest_changelog()
        if not latest or not latest.get("version"):
            logger.warning("Startup changelog check skipped: latest version not found")
            return

        latest_version = latest["version"]
        last_notified_version = get_system_config("last_notified_version", "")

        if latest_version == last_notified_version:
            logger.info(f"No new changelog version to notify: {latest_version}")
            return

        logger.info(
            f"New changelog detected on startup: latest={latest_version}, "
            f"last_notified={last_notified_version or 'none'}"
        )

        result = await send_latest_changelog_update(dry_run=False)
        if not result:
            logger.error("Startup changelog notification failed: send result is empty")
            return

        if result.get("fail_count", 0) > 0:
            logger.warning(
                "Startup changelog notification had failures: "
                f"{result.get('success_count', 0)} sent, {result.get('fail_count', 0)} failed. "
                "Version marker will not be updated for retry on next startup."
            )
            return

        set_ok = set_system_config("last_notified_version", latest_version)
        if set_ok:
            logger.info(f"Updated last_notified_version to {latest_version}")
        else:
            logger.warning(f"Failed to persist last_notified_version={latest_version}")

    except Exception as e:
        logger.error(f"Startup changelog notification check failed: {e}", exc_info=True)


async def profile_update_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Scheduled job to update user profiles based on feedback."""
    from services.profile_updater import update_all_user_profiles

    logger.info("Running scheduled profile update...")
    try:
        await update_all_user_profiles()
        logger.info("Profile update complete")
    except Exception as e:
        logger.error(f"Profile update failed: {e}")


async def data_cleanup_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Scheduled job to clean up old data files.

    每日定时清理过期数据：
    - raw_content: 保留 RAW_CONTENT_RETENTION_DAYS 天
    - daily_stats: 保留 DAILY_STATS_RETENTION_DAYS 天
    - feedback: 保留 FEEDBACK_RETENTION_DAYS 天
    - prefetch_cache: 保留 2 天
    """
    from utils.json_storage import cleanup_old_data, cleanup_prefetch_cache

    logger.info("Running scheduled data cleanup...")
    try:
        results = cleanup_old_data()
        # 清理预抓取缓存（保留 2 天）
        prefetch_deleted = cleanup_prefetch_cache(retention_days=2)
        results["prefetch_cache"] = prefetch_deleted

        total = sum(results.values())
        if total > 0:
            logger.info(
                f"Data cleanup complete: deleted {results['raw_content']} raw_content, "
                f"{results['daily_stats']} daily_stats, {results['feedback']} feedback, "
                f"{results['prefetch_cache']} prefetch_cache files"
            )
        else:
            logger.info("Data cleanup complete: no expired files to delete")
    except Exception as e:
        logger.error(f"Data cleanup failed: {e}")


async def prefetch_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    定时预抓取任务。

    每隔 PREFETCH_INTERVAL_HOURS 小时执行一次，
    抓取所有用户的 RSS 源并保存到缓存（自动去重）。

    解决 RSS.app 只返回最近 25 条内容的问题。
    """
    from services.rss_fetcher import prefetch_all_user_sources

    logger.info("Running scheduled prefetch job...")
    try:
        stats = await prefetch_all_user_sources()
        logger.info(
            f"Prefetch job complete: {stats.get('new_items', 0)} new items, "
            f"{stats.get('total_items', 0)} total cached from {stats.get('sources_count', 0)} sources"
        )
    except Exception as e:
        logger.error(f"Prefetch job failed: {e}", exc_info=True)


async def group_digest_push_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    T7: Scheduled job to push daily digest to configured groups.
    Checks each group's push_hour and sends public digest if it's time.
    """
    from handlers.group import get_all_group_configs
    from services.rss_fetcher import fetch_all_sources
    from services.digest_processor import generate_group_digest
    from services.report_generator import split_report_for_telegram

    beijing_tz = ZoneInfo("Asia/Shanghai")
    current_hour = datetime.now(beijing_tz).hour

    try:
        configs = get_all_group_configs()
        if not configs:
            return

        for group_config in configs:
            push_hour = group_config.get("push_hour", 9)
            if current_hour != push_hour:
                continue

            group_id = group_config.get("group_id")
            if not group_id:
                continue

            # Check if already pushed today
            today = datetime.now().strftime("%Y-%m-%d")
            last_push = group_config.get("last_push_date")
            if last_push == today:
                continue

            try:
                # Generate and send group digest
                profile = group_config.get("profile", "Web3 general news")
                language = group_config.get("language", "zh")

                # Fetch public sources
                raw_content = await fetch_all_sources(hours_back=24)
                if not raw_content:
                    continue

                digest_text = await generate_group_digest(raw_content, profile, language)

                # Read admin-configured CTA (falls back to default)
                from utils.json_storage import get_system_config
                from handlers.admin import DEFAULT_CTA_TEXT
                cta_text = get_system_config("group_cta_text", DEFAULT_CTA_TEXT)
                footer = (
                    "\n\n━━━━━━━━━━━━━━━━━━━━━\n"
                    f"{cta_text}\n"
                    "━━━━━━━━━━━━━━━━━━━━━"
                )

                digest_chunks = split_report_for_telegram(digest_text, max_length=3900)
                if digest_chunks:
                    digest_chunks[-1] = digest_chunks[-1] + footer
                else:
                    digest_chunks = [footer.strip()]

                for chunk in digest_chunks:
                    await context.bot.send_message(
                        chat_id=group_id,
                        text=chunk,
                        parse_mode="HTML",
                        disable_web_page_preview=True,
                    )

                # Update last push date
                from handlers.group import save_group_config
                group_config["last_push_date"] = today
                save_group_config(group_id, group_config)

                logger.info(f"Group digest pushed to {group_id}")

            except Exception as e:
                logger.error(f"Failed to push digest to group {group_id}: {e}")

    except Exception as e:
        logger.error(f"Group digest push job failed: {e}", exc_info=True)


async def rate_limit_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    全局频率限制中间件。
    
    在所有其他 handler 之前执行，检查用户是否超过频率限制。
    如果被限制，抛出 ApplicationHandlerStop 阻止后续处理。
    """
    from telegram.ext import ApplicationHandlerStop
    
    user = update.effective_user
    if not user:
        return  # 没有用户信息，继续处理
    
    user_id = str(user.id)
    limiter = get_rate_limiter()
    
    is_limited, reason = limiter.is_rate_limited(user_id)
    if is_limited:
        # 被限制，发送提示并阻止后续处理
        logger.warning(f"Rate limited user {user_id}: {reason}")
        if update.callback_query:
            await safe_answer_callback_query(update.callback_query, f"⚠️ {reason}", show_alert=True)
        elif update.message:
            await update.message.reply_text(f"⚠️ {reason}")
        raise ApplicationHandlerStop()  # 阻止后续 handler
    
    # 记录请求，继续后续处理
    limiter.record_request(user_id)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors in the bot — always notify the user so they don't get stuck."""
    logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)

    if not isinstance(update, Update):
        return

    # Determine user language for localized error message
    try:
        user = update.effective_user
        telegram_id = str(user.id) if user else None
        lang = get_user_language(telegram_id) if telegram_id else "en"
        ui = get_ui_locale(lang)
    except Exception:
        ui = {}

    error_text = ui.get("global_error", (
        "⚠️ 操作失败，请稍后重试。\n"
        "Operation failed. Please try again later."
    ))

    keyboard = [[
        InlineKeyboardButton(
            ui.get("menu_main", "主菜单 / Main Menu"),
            callback_data="back_to_start",
        )
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        if update.callback_query:
            await safe_answer_callback_query(
                update.callback_query, "⚠️ Error", show_alert=False
            )
            await update.callback_query.message.reply_text(
                error_text, reply_markup=reply_markup
            )
        elif update.message:
            await update.message.reply_text(
                error_text, reply_markup=reply_markup
            )
        elif update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=error_text,
                reply_markup=reply_markup,
            )
    except Exception as notify_err:
        logger.warning(f"Failed to notify user about error: {notify_err}")


async def handle_unmatched_private_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Save unhandled private text messages and reply with guidance (rate-limited)."""
    from config import USER_MESSAGES_DIR, USER_TEXT_REPLY_LIMIT, USER_TEXT_MAX_LENGTH
    user = update.effective_user
    if not user:
        return
    telegram_id = str(user.id)
    raw_text = update.message.text or ""
    text = raw_text[:USER_TEXT_MAX_LENGTH]
    now = datetime.now()

    # Always save (text only, truncated to max length)
    os.makedirs(USER_MESSAGES_DIR, exist_ok=True)
    date_str = now.strftime("%Y-%m-%d")
    filepath = os.path.join(USER_MESSAGES_DIR, f"{date_str}.jsonl")
    import json as _json
    entry = {
        "telegram_id": telegram_id,
        "username": user.username,
        "first_name": user.first_name,
        "text": text,
        "truncated": len(raw_text) > USER_TEXT_MAX_LENGTH,
        "timestamp": now.isoformat(),
    }
    try:
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(_json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.error(f"Failed to save user message: {e}")

    logger.info(f"Saved private text from {telegram_id}: {text[:80]}")

    # Rate-limited reply
    counter_key = f"text_reply_{telegram_id}_{date_str}"
    count = context.bot_data.get(counter_key, 0)
    if count >= USER_TEXT_REPLY_LIMIT:
        return

    context.bot_data[counter_key] = count + 1

    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)
    guide = ui.get("unmatched_text_guide", (
        "📝 已收到你的消息。\n\n"
        "如需操作，请使用以下命令：\n"
        "  /start    — 主菜单\n"
        "  /settings — 偏好设置\n"
        "  /sources  — 信息源管理\n"
        "  /help     — 帮助"
    ))
    keyboard = [[
        InlineKeyboardButton(ui.get("menu_main", "主菜单"), callback_data="back_to_start"),
        InlineKeyboardButton(ui.get("settings_title", "设置"), callback_data="update_preferences"),
    ]]
    await update.message.reply_text(guide, reply_markup=InlineKeyboardMarkup(keyboard))


async def noop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle noop callback for already-feedback items."""
    query = update.callback_query
    user = query.from_user
    telegram_id = str(user.id) if user else "0"
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)
    await safe_answer_callback_query(query, ui.get("feedback_already", "Already submitted"), show_alert=False)


async def show_help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle show_help callback from unknown message handler."""
    query = update.callback_query
    await safe_answer_callback_query(query)

    user = query.from_user
    telegram_id = str(user.id) if user else "0"
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)

    keyboard = [
        [
            InlineKeyboardButton(ui.get("menu_main", "Main Menu"), callback_data="back_to_start"),
            InlineKeyboardButton(ui.get("settings_title", "Settings"), callback_data="update_preferences"),
        ],
        [InlineKeyboardButton(ui.get("sources_title", "Sources"), callback_data="manage_sources")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    help_text = f"""{ui.get('help_title', 'Help')}
{ui['divider']}

{ui.get('help_commands', 'Commands:')}
{ui.get('help_start', '  /start     Main menu')}
{ui.get('help_settings', '  /settings  Preferences')}
{ui.get('help_sources', '  /sources   Manage sources')}
{ui.get('help_stats', '  /stats     View statistics')}
{ui.get('help_help', '  /help      Help')}

{ui['divider']}

{ui.get('help_features', 'Features:')}

{ui.get('help_digest_title', 'Daily Digest')}
{ui.get('help_digest_desc', '  Auto-pushed daily.')}

{ui.get('help_settings_title', 'Preferences (/settings)')}
{ui.get('help_settings_desc', '  Update your interests.')}

{ui.get('help_sources_title', 'Sources (/sources)')}
{ui.get('help_sources_desc', '  Manage your sources.')}

{ui.get('help_stats_title', 'Statistics (/stats)')}
{ui.get('help_stats_desc', '  View your feedback history.')}

{ui.get('help_feedback_title', 'Feedback')}
{ui.get('help_feedback_desc', '  Use buttons to provide feedback.')}

{'─' * 24}

有问题？使用上方命令或主菜单操作。"""

    await query.edit_message_text(help_text, reply_markup=reply_markup)


def main() -> None:
    """Main function to run the bot."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set. Please check your .env file.")
        sys.exit(1)

    # Build application
    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Add handlers
    
    # 0. Global rate limiter (Priority: Highest - runs before all other handlers)
    from telegram.ext import TypeHandler
    application.add_handler(TypeHandler(Update, rate_limit_middleware), group=-1)
    logger.info("Rate limiter middleware registered")
    
    # 1. Admin handlers (Priority: High - handle admin commands first)
    for handler in get_admin_handlers():
        application.add_handler(handler)
    logger.info("Admin handlers registered")

    # 2. Start/onboarding conversation handler
    application.add_handler(get_start_handler())

    # Start menu callbacks
    for callback in get_start_callbacks():
        application.add_handler(callback)

    # Settings handler
    application.add_handler(get_settings_handler())
    for callback in get_settings_callbacks():
        application.add_handler(callback)

    # Sources handler
    application.add_handler(get_sources_handler())
    for callback in get_sources_callbacks():
        application.add_handler(callback)

    # Feedback handlers
    feedback_conv, item_handler, unsubscribe_handler = get_feedback_handlers()
    application.add_handler(feedback_conv)
    application.add_handler(item_handler)
    application.add_handler(unsubscribe_handler)

    # Command handlers
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("test", test_fetch_command))
    application.add_handler(CommandHandler("testprofile", test_profile_command))
    application.add_handler(CommandHandler("testprefetch", test_prefetch_command))
    application.add_handler(CommandHandler("stats", stats_command))

    # Payment handlers (T5)
    for handler in get_payment_handlers():
        application.add_handler(handler)
    logger.info("Payment handlers registered")

    # Group chat handlers (T7)
    group_handler = get_group_handler()
    if group_handler:
        application.add_handler(group_handler)
    for callback in get_group_callbacks():
        application.add_handler(callback)
    logger.info("Group chat handlers registered")

    # Group setup guide callback (private chat)
    async def group_setup_guide_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show group setup guide when clicked from help menu."""
        query = update.callback_query
        await query.answer()
        from handlers.group import setup_command
        # Create a fake update with message for setup_command
        # The setup_command will detect private chat and show the guide
        guide_text = (
            "📋 群组推送配置指南\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📌 如何将 Bot 添加到群组：\n\n"
            "1️⃣ 打开你的 Telegram 群组\n"
            "2️⃣ 点击群组名称 → 「添加成员」\n"
            "3️⃣ 搜索 @learnfi_bot 并添加\n"
            "4️⃣ 将 Bot 设为「管理员」（需要发消息权限）\n"
            "5️⃣ 在群组中发送 /setup 开始配置\n\n"
            "⚙️ 配置流程：\n"
            "• 描述群组关注的 Web3 方向（如 DeFi、Layer2）\n"
            "• 选择每日推送时间\n"
            "• 选择推送语言\n\n"
            "配置完成后，Bot 每天定时在群里推送 Web3 简报 📰\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "Setup Guide for Groups\n\n"
            "1. Open your Telegram group\n"
            "2. Tap group name → Add Members\n"
            "3. Search @learnfi_bot and add\n"
            "4. Make Bot an Admin (needs send messages)\n"
            "5. Send /setup in the group to configure"
        )
        await query.edit_message_text(
            guide_text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("« 返回帮助 / Back to Help", callback_data="show_help")]
            ])
        )

    application.add_handler(CallbackQueryHandler(group_setup_guide_callback, pattern="^group_setup_guide$"))

    # Callback for help from unknown message
    application.add_handler(CallbackQueryHandler(show_help_callback, pattern="^show_help$"))
    application.add_handler(CallbackQueryHandler(noop_callback, pattern="^noop$"))

    # Catch-all: save unhandled private text messages as user behavior data
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
        handle_unmatched_private_text
    ))
    logger.info("Private text catch-all handler registered")

    # Error handler
    application.add_error_handler(error_handler)

    # Register shutdown handler to save shutdown log
    # 服务关闭时保存 shutdown 日志
    def on_shutdown():
        shutdown_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        shutdown_log_path = os.path.join(LOGS_DIR, f"bot.log.shutdown.{shutdown_time}")
        try:
            # Copy current log to shutdown file
            current_log_path = os.path.join(LOGS_DIR, "bot.log")
            if os.path.exists(current_log_path):
                import shutil
                shutil.copy2(current_log_path, shutdown_log_path)
                logger.info(f"Shutdown log saved to {shutdown_log_path}")
        except Exception as e:
            logger.error(f"Failed to save shutdown log: {e}")
        logger.info("Bot shutting down...")

    atexit.register(on_shutdown)

    # Start the bot
    logger.info(f"Admin IDs: {len(ADMIN_TELEGRAM_IDS)} configured")
    logger.info("Starting Web3 Daily Digest Bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
