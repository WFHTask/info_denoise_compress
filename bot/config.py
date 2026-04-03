"""
Web3 Daily Digest - Configuration Management
"""
import os
import json
import logging
from dotenv import load_dotenv

# Load environment: .env.test takes priority over .env (for development/testing)
test_env_path = os.path.join(os.path.dirname(__file__), '.env.test')
env_path = os.path.join(os.path.dirname(__file__), '.env')

if os.path.exists(test_env_path):
    load_dotenv(test_env_path, override=True)
    print("⚠️  Loaded .env.test (TEST MODE)")
elif os.path.exists(env_path):
    load_dotenv(env_path, override=True)
else:
    load_dotenv(override=True)

logger = logging.getLogger(__name__)

# ============ LLM Provider Chain (Multi-Provider Fallback) ============
# LLM_PROVIDERS: comma-separated provider chain, e.g. "gemini,kimi,openai"
# Each provider needs its own {NAME}_API_KEY, {NAME}_MODEL, {NAME}_API_URL
# Provider types: "gemini" uses Gemini API; all others use OpenAI-compatible API
#
# Example .env:
#   LLM_PROVIDERS=gemini,kimi,openai
#   GEMINI_API_KEY=xxx
#   GEMINI_MODEL=gemini-3-flash-preview
#   KIMI_API_KEY=xxx
#   KIMI_MODEL=moonshot-v1-8k
#   KIMI_API_URL=https://api.moonshot.cn/v1/chat/completions
#   OPENAI_API_KEY=xxx
#   OPENAI_MODEL=gpt-4o

import sys

_raw_providers = os.getenv("LLM_PROVIDERS", "").strip()
if not _raw_providers:
    _raw_providers = os.getenv("LLM", "gemini").strip()

GEMINI_THINKING_LEVEL = os.getenv("GEMINI_THINKING_LEVEL", "HIGH")

LLM_CHAIN: list = []

for _name in _raw_providers.split(","):
    _name = _name.strip().lower()
    if not _name:
        continue

    _prefix = _name.upper()
    _api_key = os.getenv(f"{_prefix}_API_KEY", "")
    _model = os.getenv(f"{_prefix}_MODEL", "")
    _api_url = os.getenv(f"{_prefix}_API_URL", "")

    if not _api_key:
        logger.warning(f"⚠️ {_prefix}_API_KEY not set, skipping provider '{_name}'")
        continue

    if _name == "gemini":
        if not _model:
            _model = "gemini-3-flash-preview"
        _base = _api_url.rstrip("/") if _api_url else ""
        if _base:
            if "/v1beta/models/" in _base or ":generateContent" in _base:
                _resolved_url = _base
            else:
                _resolved_url = f"{_base}/v1beta/models/{_model}:generateContent"
        else:
            _resolved_url = f"https://generativelanguage.googleapis.com/v1beta/models/{_model}:generateContent"

        LLM_CHAIN.append({
            "name": _name,
            "type": "gemini",
            "api_key": _api_key,
            "model": _model,
            "api_url": _resolved_url,
        })
        logger.info(f"✨ LLM chain [{len(LLM_CHAIN)}]: Gemini ({_model})")
    else:
        if not _model:
            _model = "gpt-4o" if _name == "openai" else _name
        _resolved_url = _api_url or "https://api.openai.com/v1/chat/completions"

        LLM_CHAIN.append({
            "name": _name,
            "type": "openai",
            "api_key": _api_key,
            "model": _model,
            "api_url": _resolved_url,
        })
        logger.info(f"🤖 LLM chain [{len(LLM_CHAIN)}]: {_name} ({_model})")

if not LLM_CHAIN:
    logger.error("❌ No valid LLM provider configured! Check LLM_PROVIDERS and API keys in .env")
    sys.exit(1)

LLM_PROVIDER = LLM_CHAIN[0]["name"]

# Backward-compatible variables (used by some legacy code paths)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
GEMINI_API_URL = next((p["api_url"] for p in LLM_CHAIN if p["type"] == "gemini"), "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
OPENAI_API_URL = os.getenv("OPENAI_API_URL", "")

# Telegram Bot
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# Push Schedule (Beijing Time)
def _parse_int_env(key: str, default: int) -> int:
    """Parse an integer environment variable with fallback."""
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default

PUSH_HOUR = _parse_int_env("PUSH_HOUR", 9)
PUSH_MINUTE = _parse_int_env("PUSH_MINUTE", 0)

# ============ Push Strategy Configuration ============
# 推送策略配置

# 推送模式: "fixed_time" (固定时间推送所有用户) / "user_interval" (按用户注册时间循环)
PUSH_MODE = os.getenv("PUSH_MODE", "user_interval")

# 用户间隔模式的周期（小时），默认24小时（Free 用户）
PUSH_INTERVAL_HOURS = _parse_int_env("PUSH_INTERVAL_HOURS", 24)

# Pro 用户推送间隔（小时），默认1小时（24小时及时实时推送）
PUSH_INTERVAL_PRO_HOURS = _parse_int_env("PUSH_INTERVAL_PRO_HOURS", 1)

# 静默时段（北京时间），此时段内不推送，延迟到静默结束后
PUSH_QUIET_START = _parse_int_env("PUSH_QUIET_START", 0)   # 00:00 开始静默
PUSH_QUIET_END = _parse_int_env("PUSH_QUIET_END", 7)       # 07:00 结束静默

# 检查频率（分钟），用于 user_interval 模式，每隔多少分钟检查一次到期用户
PUSH_CHECK_INTERVAL = _parse_int_env("PUSH_CHECK_INTERVAL", 30)

# 暂停推送开关（调试用）- 设置为 true 可暂停所有定时推送
PAUSE_PUSH = os.getenv("PAUSE_PUSH", "").lower() in ("true", "1", "yes")

# Chat Context Days - 聊天上下文天数 (0=仅今天, 1=+昨天, etc.)
CHAT_CONTEXT_DAYS = _parse_int_env("CHAT_CONTEXT_DAYS", 1)

# Data Directory
DATA_DIR = os.getenv("DATA_DIR", "./data")

# Security Configuration
# Support multiple admins (comma-separated)
_admin_ids_str = os.getenv("ADMIN_TELEGRAM_IDS", "") or os.getenv("ADMIN_TELEGRAM_ID", "")
ADMIN_TELEGRAM_IDS = [id.strip() for id in _admin_ids_str.split(",") if id.strip()]

# Rate Limiting Configuration (防止高频交互攻击)
# 每用户每分钟最大交互次数，设为 0 表示禁用频率限制
RATE_LIMIT_PER_MINUTE = _parse_int_env("RATE_LIMIT_PER_MINUTE", 30)

# Legacy single admin (for backward compatibility)
ADMIN_TELEGRAM_ID = ADMIN_TELEGRAM_IDS[0] if ADMIN_TELEGRAM_IDS else ""

# Whitelist settings
WHITELIST_FILE = os.path.join(DATA_DIR, "whitelist.json")
WHITELIST_SETTINGS_FILE = os.path.join(DATA_DIR, "whitelist_settings.json")
WHITELIST_ENABLED_DEFAULT = os.getenv("WHITELIST_ENABLED", "true").lower() == "true"

# Logging Configuration
LOG_ROTATE_DAYS = _parse_int_env("LOG_ROTATE_DAYS", 1)  # 每几天轮转一次日志
LOG_BACKUP_COUNT = _parse_int_env("LOG_BACKUP_COUNT", 30)  # 最多保留多少个备份

# Data Retention Configuration (days)
# 数据保留天数配置
RAW_CONTENT_RETENTION_DAYS = _parse_int_env("RAW_CONTENT_RETENTION_DAYS", 7)  # 原始内容保留天数
DAILY_STATS_RETENTION_DAYS = _parse_int_env("DAILY_STATS_RETENTION_DAYS", 30)  # 每日统计保留天数
FEEDBACK_RETENTION_DAYS = _parse_int_env("FEEDBACK_RETENTION_DAYS", 30)  # 反馈记录保留天数
EVENTS_RETENTION_DAYS = _parse_int_env("EVENTS_RETENTION_DAYS", 90)  # 用户行为事件保留天数

# Events Directory (用户行为埋点)
EVENTS_DIR = os.path.join(DATA_DIR, "events")

# Digest Configuration
# 简报配置
MAX_DIGEST_ITEMS = _parse_int_env("MAX_DIGEST_ITEMS", 20)  # 每日精选输出条数

# Translation Configuration
# 翻译配置 - 低温度值确保翻译输出稳定不发散
def _parse_float_env(key: str, default: float) -> float:
    """Parse a float environment variable with fallback."""
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        return default

TRANSLATION_TEMPERATURE = _parse_float_env("TRANSLATION_TEMPERATURE", 0.1)

# Two-stage filtering configuration (v2.1)
# 两阶段筛选配置
BATCH_SIZE = _parse_int_env("BATCH_SIZE", 100)  # 每批处理的新闻数量
# Stage 1 粗筛比例：自动计算，确保候选池 = 最终输出的 3-5 倍
# 例如：BATCH_SIZE=100, MAX_DIGEST_ITEMS=20 → STAGE1_RATIO=0.10 (每批选10条)
STAGE1_RATIO = min(0.15, max(0.05, MAX_DIGEST_ITEMS / BATCH_SIZE * 0.5))

# Concurrency Configuration
# 并发配置
CONCURRENT_USERS = _parse_int_env("CONCURRENT_USERS", 10)  # 并发处理用户数（1-50，建议10）

# Prefetch Configuration
# 预抓取配置（解决 RSS.app 只返回最近内容的问题）
PREFETCH_INTERVAL_HOURS = _parse_int_env("PREFETCH_INTERVAL_HOURS", 2)  # 预抓取间隔（小时）
PREFETCH_START_HOUR = _parse_int_env("PREFETCH_START_HOUR", 1)  # 预抓取开始时间（小时，北京时间）

# ============ Twitter RSS Configuration ============
# Twitter-to-RSS 转换服务配置
# 支持: rsshub (默认) | nitter | custom
# RSSHub: 可使用公共实例或自托管 (https://docs.rsshub.app)
# Nitter: 使用 Nitter 实例 (不稳定)
# Custom: 自定义 URL 模板，{username} 会被替换为用户名
TWITTER_RSS_SERVICE = os.getenv("TWITTER_RSS_SERVICE", "rsshub").lower().strip()
TWITTER_RSS_BASE_URL = os.getenv("TWITTER_RSS_BASE_URL", "").rstrip("/")

# Auto-configure based on service
if not TWITTER_RSS_BASE_URL:
    if TWITTER_RSS_SERVICE == "nitter":
        TWITTER_RSS_BASE_URL = "https://nitter.privacydev.net"
    else:
        # Default to RSSHub public instance
        TWITTER_RSS_BASE_URL = "https://rsshub.liumingye.cn"

# Paths
USERS_FILE = os.path.join(DATA_DIR, "users.json")
PROFILES_DIR = os.path.join(DATA_DIR, "profiles")
FEEDBACK_DIR = os.path.join(DATA_DIR, "feedback")
DAILY_STATS_DIR = os.path.join(DATA_DIR, "daily_stats")
RAW_CONTENT_DIR = os.path.join(DATA_DIR, "raw_content")
USER_SOURCES_DIR = os.path.join(DATA_DIR, "user_sources")  # Per-user source configs
PREFETCH_CACHE_DIR = os.path.join(DATA_DIR, "prefetch_cache")  # 预抓取缓存目录
USER_MESSAGES_DIR = os.path.join(DATA_DIR, "user_messages")  # 私聊文本消息存档
USER_TEXT_REPLY_LIMIT = _parse_int_env("USER_TEXT_REPLY_LIMIT", 10)
USER_TEXT_MAX_LENGTH = _parse_int_env("USER_TEXT_MAX_LENGTH", 500)


# ============ Default Sources Configuration ============

# Hardcoded default sources (used if env not set)
_DEFAULT_SOURCES = {
    "twitter": {
        # These are bundled Twitter feeds from RSS.app
        # The actual feeds are aggregated through these URLs:
        # 1. https://rss.app/feeds/G6dip9YSp1NzQMls.xml
        # 2. https://rss.app/feeds/HVg722x6SI7tChWQ.xml
        "Twitter Bundle 1": "https://rss.app/feeds/G6dip9YSp1NzQMls.xml",
        "Twitter Bundle 2": "https://rss.app/feeds/HVg722x6SI7tChWQ.xml",
    },
    "websites": {
        # Web3 news sites with verified RSS feeds
        "Cointelegraph": "https://cointelegraph.com/rss",
        "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "The Block Beats": "https://api.theblockbeats.news/v1/open-api/home-xml",  # Fixed: using API endpoint
        # Additional sites from Excel with verified RSS
        "TechFlow Post": "https://techflowpost.substack.com/feed",  # Alternative: https://techflowpost.mirror.xyz/feed/atom
        "DeFi Rate": "https://defirate.com/feed",
        "Prediction News": "https://predictionnews.com/rss/",
        "Event Horizon": "https://nexteventhorizon.substack.com/feed",
        "un.Block (吴说)": "https://unblock256.substack.com/feed",  # wublock123.com's newsletter
        # Note: Sites without RSS feeds (verified by testing):
        # - Odaily: Returns HTML instead of RSS
        # - ChainFeeds: 404 error
        # - Foresight News: WAF protection page
        # - https://www.me.news/news (no RSS)
        # - https://www.chaincatcher.com/news (404 on RSS endpoint)
        # - https://www.panewslab.com/ (no RSS)
        # - Telegram channels cannot be added as RSS
    }
}


def _is_full_rss_url(url: str) -> bool:
    """Check if a string is a full RSS URL (not just a domain)."""
    if not url:
        return False
    url_lower = url.lower()
    # Full URL patterns
    if url_lower.startswith("http://") or url_lower.startswith("https://"):
        # Check if it's more than just a domain (has path or specific endpoints)
        from urllib.parse import urlparse
        parsed = urlparse(url)
        # If path is empty or just "/", it's likely a domain needing detection
        if parsed.path and parsed.path != "/" and len(parsed.path) > 1:
            return True
        # If has common RSS path indicators
        if any(x in url_lower for x in ["/rss", "/feed", "/atom", ".xml", "/api/"]):
            return True
        return False
    return False


def _parse_sources_env() -> dict:
    """
    Parse default sources from environment variables.

    Supports multiple formats:
    1. JSON format: DEFAULT_SOURCES='{"twitter": {"@user": "url"}, "websites": {"name": "url"}}'
    2. Simple format (comma-separated):
       DEFAULT_TWITTER_SOURCES='@VitalikButerin,@lookonchain,@whale_alert'
       DEFAULT_WEBSITE_SOURCES='The Block|https://theblock.co/rss.xml,CoinDesk|https://coindesk.com/rss'
    3. Auto-detect format (domain only, RSS will be auto-detected at startup):
       DEFAULT_WEBSITE_SOURCES='Cointelegraph|cointelegraph.com,CoinDesk|coindesk.com'
       DEFAULT_WEBSITE_SOURCES='theblock.co,coindesk.com' (name = domain)

    Returns:
        Dict with twitter and websites sources
        URL can be:
        - Full RSS URL: use directly
        - Domain only: marked with "AUTO:" prefix for later detection
        - Empty: will attempt auto-detection
    """
    # Try JSON format first
    json_sources = os.getenv("DEFAULT_SOURCES", "")
    if json_sources:
        try:
            parsed = json.loads(json_sources)
            if isinstance(parsed, dict):
                return {
                    "twitter": parsed.get("twitter", {}),
                    "websites": parsed.get("websites", {})
                }
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse DEFAULT_SOURCES JSON: {e}")

    # Try simple format
    result = {"twitter": {}, "websites": {}}

    # Parse Twitter sources: @user1,@user2 or @user1|rss_url,@user2|rss_url
    twitter_env = os.getenv("DEFAULT_TWITTER_SOURCES", "")
    if twitter_env:
        for item in twitter_env.split(","):
            item = item.strip()
            if not item:
                continue
            if "|" in item:
                parts = item.split("|", 1)
                handle = parts[0].strip()
                url = parts[1].strip()
            else:
                handle = item
                url = ""
            # Ensure @ prefix
            if not handle.startswith("@"):
                handle = f"@{handle}"
            result["twitter"][handle] = url

    # Parse website sources with auto-detection support
    # Formats:
    #   Name|https://xxx/rss.xml  -> full URL, use directly
    #   Name|domain.com           -> domain only, mark for auto-detection
    #   domain.com                -> name=domain, mark for auto-detection
    website_env = os.getenv("DEFAULT_WEBSITE_SOURCES", "")
    if website_env:
        for item in website_env.split(","):
            item = item.strip()
            if not item:
                continue
            if "|" in item:
                parts = item.split("|", 1)
                name = parts[0].strip()
                url_or_domain = parts[1].strip()
            else:
                # No "|" - treat as domain, name = domain
                name = item
                url_or_domain = item
            
            # Determine if it's a full RSS URL or needs auto-detection
            if _is_full_rss_url(url_or_domain):
                # Full RSS URL, use directly
                result["websites"][name] = url_or_domain
            else:
                # Domain only or incomplete URL, mark for auto-detection
                # Store domain with AUTO: prefix for later resolution
                domain = url_or_domain.replace("https://", "").replace("http://", "").replace("www.", "").rstrip("/")
                result["websites"][name] = f"AUTO:{domain}"

    # If nothing from env, return None to use hardcoded defaults
    if not result["twitter"] and not result["websites"]:
        return None

    return result


# ============ Feature Flags (Sprint1 新功能开关，默认全部关闭) ============
FEATURE_SOURCE_HEALTH = os.getenv("FEATURE_SOURCE_HEALTH", "false").lower() == "true"
FEATURE_PAYMENT = os.getenv("FEATURE_PAYMENT", "false").lower() == "true"
FEATURE_GROUP_CHAT = os.getenv("FEATURE_GROUP_CHAT", "false").lower() == "true"

# ============ Source Health Configuration ============
SOURCE_HEALTH_DIR = os.path.join(DATA_DIR, "source_health")

# ============ Payment Configuration ============
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN", "")
PLAN_CONFIG_FILE = os.path.join(DATA_DIR, "plan_config.json")

# ============ Group Chat Configuration ============
GROUP_CONFIGS_DIR = os.path.join(DATA_DIR, "group_configs")

# ============ Noise Prefix Configuration (T2: 简报视觉重构) ============
# RSS 内容中常见的噪音前缀，抓取后自动清除
NOISE_PREFIXES = [
    "blockbeats 消息，",
    "BlockBeats 消息，",
    "转发 ",
    "深潮 TechFlow 消息，",
    "Odaily 星球日报讯，",
    "金色财经报道，",
    "PANews ",
]
# Support additional prefixes from environment
_extra_prefixes = os.getenv("NOISE_PREFIXES", "")
if _extra_prefixes:
    NOISE_PREFIXES.extend([p.strip() for p in _extra_prefixes.split(",") if p.strip()])

# Load default sources: env > hardcoded defaults
_env_sources = _parse_sources_env()
DEFAULT_USER_SOURCES = _env_sources if _env_sources else _DEFAULT_SOURCES


async def resolve_default_sources_rss() -> None:
    """
    Resolve RSS URLs for sources marked with AUTO: prefix.
    Called at bot startup to auto-detect RSS feeds for configured domains.
    
    This allows .env to use simple domain format:
        DEFAULT_WEBSITE_SOURCES=Cointelegraph|cointelegraph.com,CoinDesk|coindesk.com
    Instead of requiring full RSS URLs.
    """
    global DEFAULT_USER_SOURCES
    
    from services.rss_fetcher import auto_detect_rss
    
    websites = DEFAULT_USER_SOURCES.get("websites", {})
    updated = False
    
    for name, url in list(websites.items()):
        if url.startswith("AUTO:"):
            domain = url[5:]  # Remove "AUTO:" prefix
            logger.info(f"Auto-detecting RSS for {name} ({domain})...")
            
            try:
                result = await auto_detect_rss(domain)
                if result.get("found"):
                    websites[name] = result["url"]
                    logger.info(f"  ✓ Found RSS: {result['url']}")
                    updated = True
                else:
                    logger.warning(f"  ✗ No RSS found for {name} ({domain}): {result.get('error')}")
                    # Keep the AUTO: prefix so it can be retried later
            except Exception as e:
                logger.error(f"  ✗ Error detecting RSS for {name}: {e}")
    
    if updated:
        DEFAULT_USER_SOURCES["websites"] = websites
        logger.info("Default sources updated with auto-detected RSS URLs")
