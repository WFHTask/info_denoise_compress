"""
JSON Storage Utilities

Handles all file-based data storage operations.
Uses JSON files for users, profiles, feedback, and content.
"""
import json
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path

from config import (
    DATA_DIR,
    USERS_FILE,
    PROFILES_DIR,
    FEEDBACK_DIR,
    DAILY_STATS_DIR,
    RAW_CONTENT_DIR,
    USER_SOURCES_DIR,
    PREFETCH_CACHE_DIR,
    EVENTS_DIR,
    DEFAULT_USER_SOURCES,
    RAW_CONTENT_RETENTION_DAYS,
    DAILY_STATS_RETENTION_DAYS,
    FEEDBACK_RETENTION_DAYS,
    EVENTS_RETENTION_DAYS,
)

logger = logging.getLogger(__name__)


def _ensure_dir(path: str) -> None:
    """Ensure directory exists."""
    Path(path).mkdir(parents=True, exist_ok=True)


def _read_json(file_path: str) -> Dict[str, Any]:
    """
    Read JSON file with retry logic.

    No file locking needed - atomic writes guarantee consistency.
    Retries handle transient permission issues on Windows.
    """
    import time

    max_retries = 5
    retry_delay = 0.05  # 50ms

    for attempt in range(max_retries):
        try:
            if not os.path.exists(file_path):
                return {}

            with open(file_path, "r", encoding="utf-8") as f:
                raw = f.read()
            # Empty or whitespace-only file: treat as empty object (avoid JSONDecodeError)
            if not raw.strip():
                return {}
            return json.loads(raw)

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in {file_path}: {e}")
            return {}
        except (PermissionError, OSError) as e:
            # Retry on Windows permission errors
            if attempt < max_retries - 1:
                logger.debug(f"File locked, retrying ({attempt+1}/{max_retries}): {file_path}")
                time.sleep(retry_delay)
                retry_delay *= 1.5  # Gentle backoff
                continue
            else:
                logger.error(f"Error reading {file_path} after {max_retries} retries: {e}")
                return {}
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
            return {}

    return {}


def _write_json(file_path: str, data: Dict[str, Any]) -> bool:
    """
    Write JSON file using atomic write with retry logic.

    Uses temp file + atomic rename to avoid file lock issues on Windows.
    This is more reliable than msvcrt.locking().
    """
    import time
    import tempfile

    max_retries = 5  # Increased retries for atomic write
    retry_delay = 0.05  # 50ms

    for attempt in range(max_retries):
        temp_fd = None
        temp_path = None
        try:
            _ensure_dir(os.path.dirname(file_path))

            # Write to temporary file in same directory (same filesystem)
            dir_path = os.path.dirname(file_path) or '.'
            temp_fd, temp_path = tempfile.mkstemp(
                dir=dir_path,
                prefix='.tmp_',
                suffix='.json',
                text=True
            )

            # Write JSON to temp file
            with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                temp_fd = None  # Prevent double close
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())

            # Atomic replace (os.replace is atomic on both Windows and Unix)
            os.replace(temp_path, file_path)
            temp_path = None  # Prevent cleanup of successful file
            return True

        except (PermissionError, OSError) as e:
            # Retry on Windows file lock errors
            if attempt < max_retries - 1:
                logger.debug(f"File locked for write, retrying ({attempt+1}/{max_retries}): {file_path}")
                time.sleep(retry_delay)
                retry_delay *= 1.5  # Gentle backoff
                continue
            else:
                logger.error(f"Error writing {file_path} after {max_retries} retries: {e}")
                return False
        except Exception as e:
            logger.error(f"Error writing {file_path}: {e}")
            return False
        finally:
            # Cleanup on failure
            if temp_fd is not None:
                try:
                    os.close(temp_fd)
                except:
                    pass
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except:
                    pass

    return False


# ============ User Management ============

def get_users() -> List[Dict[str, Any]]:
    """Get all users."""
    data = _read_json(USERS_FILE)
    return data.get("users", [])


def get_user(telegram_id: str) -> Optional[Dict[str, Any]]:
    """Get user by Telegram ID."""
    users = get_users()
    for user in users:
        if user.get("telegram_id") == telegram_id:
            return user
    return None


def create_user(
    telegram_id: str,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    language: str = "zh"
) -> Dict[str, Any]:
    """Create a new user.
    
    Args:
        telegram_id: Telegram user ID
        username: Telegram username
        first_name: User's first name
        language: User's language code (from Telegram language_code)
    """
    data = _read_json(USERS_FILE)
    if "users" not in data:
        data["users"] = []

    # Check if user already exists
    for user in data["users"]:
        if user.get("telegram_id") == telegram_id:
            return user

    # Create new user
    user = {
        "id": f"user_{len(data['users']) + 1:03d}",
        "telegram_id": telegram_id,
        "username": username,
        "first_name": first_name,
        "language": language,
        "created": datetime.now().isoformat(),
        "last_active": datetime.now().isoformat(),
    }

    data["users"].append(user)
    _write_json(USERS_FILE, data)

    logger.info(f"Created user: {user['id']} (telegram_id: {telegram_id}, language: {language})")
    return user


def update_user_activity(telegram_id: str) -> None:
    """Update user's last activity timestamp."""
    data = _read_json(USERS_FILE)
    for user in data.get("users", []):
        if user.get("telegram_id") == telegram_id:
            user["last_active"] = datetime.now().isoformat()
            _write_json(USERS_FILE, data)
            break


def pause_user_service(telegram_id: str) -> bool:
    """Pause a user's digest service due to inactivity."""
    data = _read_json(USERS_FILE)
    for user in data.get("users", []):
        if user.get("telegram_id") == telegram_id:
            user["service_paused"] = True
            user["paused_at"] = datetime.now().isoformat()
            result = _write_json(USERS_FILE, data)
            if result:
                logger.info(f"Paused service for user {telegram_id}")
            return result
    return False


def resume_user_service(telegram_id: str) -> bool:
    """Resume a user's paused digest service (user clicked 'resume')."""
    data = _read_json(USERS_FILE)
    for user in data.get("users", []):
        if user.get("telegram_id") == telegram_id:
            user["service_paused"] = False
            user["paused_at"] = None
            user["pause_notified"] = False
            user["last_active"] = datetime.now().isoformat()
            result = _write_json(USERS_FILE, data)
            if result:
                logger.info(f"Resumed service for user {telegram_id}")
            return result
    return False


def is_user_paused(telegram_id: str) -> bool:
    """Check if a user's service is paused."""
    user = get_user(telegram_id)
    if not user:
        return False
    return user.get("service_paused", False)


def mark_pause_notified(telegram_id: str) -> bool:
    """Mark that the pause notification has been sent to the user."""
    data = _read_json(USERS_FILE)
    for user in data.get("users", []):
        if user.get("telegram_id") == telegram_id:
            user["pause_notified"] = True
            return _write_json(USERS_FILE, data)
    return False


def get_inactive_users(inactive_days: int) -> list:
    """Get users who have been inactive for more than inactive_days.

    Returns list of user dicts that:
    - Are NOT already paused
    - Have last_active older than inactive_days ago
    """
    users = get_users()
    cutoff = datetime.now() - timedelta(days=inactive_days)
    inactive = []
    for user in users:
        if user.get("service_paused"):
            continue
        last_active_str = user.get("last_active") or user.get("created")
        if not last_active_str:
            continue
        try:
            last_active = datetime.fromisoformat(last_active_str)
            if last_active < cutoff:
                inactive.append(user)
        except (ValueError, TypeError):
            continue
    return inactive


def get_user_language(telegram_id: str) -> str:
    """Get user's language setting.
    
    Args:
        telegram_id: Telegram user ID
        
    Returns:
        Language code (e.g., "zh", "en", "ja", "ko"), defaults to "zh"
    """
    user = get_user(telegram_id)
    if not user:
        return "zh"
    return user.get("language", "zh")


# ============ Update Subscription Management ============

def get_user_subscribe_updates(telegram_id: str) -> bool:
    """Get user's update subscription status.
    
    Args:
        telegram_id: Telegram user ID
        
    Returns:
        True if user is subscribed to system updates (default True)
    """
    user = get_user(telegram_id)
    if not user:
        return True
    return user.get("subscribe_updates", True)


def set_user_subscribe_updates(telegram_id: str, subscribed: bool) -> bool:
    """Set user's update subscription status.
    
    Args:
        telegram_id: Telegram user ID
        subscribed: True to subscribe, False to unsubscribe
        
    Returns:
        True if successful
    """
    data = _read_json(USERS_FILE)
    for user in data.get("users", []):
        if user.get("telegram_id") == telegram_id:
            user["subscribe_updates"] = subscribed
            result = _write_json(USERS_FILE, data)
            if result:
                logger.info(f"Updated subscribe_updates for {telegram_id}: {subscribed}")
            return result
    return False


def set_onboarding_paid_redeem_available(telegram_id: str) -> bool:
    """Set onboarding-paid-redeem available for user (after completing onboarding)."""
    data = _read_json(USERS_FILE)
    for user in data.get("users", []):
        if user.get("telegram_id") == telegram_id:
            user["onboarding_paid_redeem_available"] = True
            result = _write_json(USERS_FILE, data)
            if result:
                logger.info(f"Set onboarding_paid_redeem_available for {telegram_id}")
            return result
    return False


def consume_onboarding_redeem(telegram_id: str) -> bool:
    """Consume the one-time paid feature redeem (e.g. after adding first custom source)."""
    data = _read_json(USERS_FILE)
    for user in data.get("users", []):
        if user.get("telegram_id") == telegram_id:
            if not user.get("onboarding_paid_redeem_available"):
                return False
            user["onboarding_paid_redeem_available"] = False
            result = _write_json(USERS_FILE, data)
            if result:
                logger.info(f"Consumed onboarding_paid_redeem for {telegram_id}")
            return result
    return False


def get_subscribed_users() -> List[Dict[str, Any]]:
    """Get all users who are subscribed to system updates.
    
    Returns:
        List of user dictionaries who have subscribe_updates=True (or not set, defaulting to True)
    """
    users = get_users()
    return [u for u in users if u.get("subscribe_updates", True)]


def update_user_language(telegram_id: str, language: str) -> bool:
    """Update user's language setting.
    
    Args:
        telegram_id: Telegram user ID
        language: Language code (e.g., "zh", "en", "ja", "ko")
        
    Returns:
        True if successful, False otherwise
    """
    data = _read_json(USERS_FILE)
    for user in data.get("users", []):
        if user.get("telegram_id") == telegram_id:
            user["language"] = language
            _write_json(USERS_FILE, data)
            logger.info(f"Updated language for {telegram_id}: {language}")
            return True
    return False


def get_user_setting(telegram_id: str, key: str, default: Any = None) -> Any:
    """Get a user setting value."""
    user = get_user(telegram_id)
    if not user:
        return default
    return user.get("settings", {}).get(key, default)


def set_user_setting(telegram_id: str, key: str, value: Any) -> bool:
    """Set a user setting value."""
    data = _read_json(USERS_FILE)
    for user in data.get("users", []):
        if user.get("telegram_id") == telegram_id:
            if "settings" not in user:
                user["settings"] = {}
            user["settings"][key] = value
            return _write_json(USERS_FILE, data)
    return False


def get_user_last_push_time(telegram_id: str) -> Optional[str]:
    """
    获取用户上次推送时间。
    
    Returns:
        ISO 格式的时间字符串，如果没有记录则返回 None
    """
    user = get_user(telegram_id)
    if not user:
        return None
    return user.get("last_push_time")


def set_user_last_push_time(telegram_id: str, push_time: Optional[str] = None) -> bool:
    """
    记录用户本次推送时间。
    
    Args:
        telegram_id: 用户 Telegram ID
        push_time: ISO 格式的时间字符串，默认为当前时间
    
    Returns:
        是否保存成功
    """
    if not push_time:
        push_time = datetime.now().isoformat()
    
    data = _read_json(USERS_FILE)
    for user in data.get("users", []):
        if user.get("telegram_id") == telegram_id:
            user["last_push_time"] = push_time
            return _write_json(USERS_FILE, data)
    return False


# ============ User Profile Management ============

def get_user_profile(telegram_id: str) -> Optional[str]:
    """Get user's natural language profile."""
    user = get_user(telegram_id)
    if not user:
        return None

    profile_path = os.path.join(PROFILES_DIR, f"{user['id']}.txt")
    if not os.path.exists(profile_path):
        return None

    try:
        with open(profile_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error reading profile for {telegram_id}: {e}")
        return None


def save_user_profile(telegram_id: str, profile: str, user_id: Optional[str] = None) -> bool:
    """Save user's natural language profile.

    Args:
        telegram_id: User's Telegram ID
        profile: Profile content
        user_id: Optional user ID (avoids file lock race condition)
    """
    if not user_id:
        user = get_user(telegram_id)
        if not user:
            logger.error(f"Cannot save profile: user {telegram_id} not found")
            return False
        user_id = user['id']

    _ensure_dir(PROFILES_DIR)
    profile_path = os.path.join(PROFILES_DIR, f"{user_id}.txt")

    try:
        with open(profile_path, "w", encoding="utf-8") as f:
            f.write(profile)
        logger.info(f"Saved profile for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error saving profile for {telegram_id}: {e}")
        return False


# ============ Feedback Management ============

def save_feedback(
    telegram_id: str,
    overall_rating: str,
    reason_selected: Optional[List[str]] = None,
    reason_text: Optional[str] = None,
    item_feedbacks: Optional[List[Dict[str, str]]] = None
) -> bool:
    """Save user feedback for a day."""
    user = get_user(telegram_id)
    if not user:
        return False

    today = datetime.now().strftime("%Y-%m-%d")
    feedback_path = os.path.join(FEEDBACK_DIR, f"{today}.json")

    data = _read_json(feedback_path)
    if "date" not in data:
        data["date"] = today
        data["feedbacks"] = []

    feedback = {
        "user_id": user["id"],
        "telegram_id": telegram_id,
        "time": datetime.now().strftime("%H:%M"),
        "overall": overall_rating,
        "reason_selected": reason_selected or [],
        "reason_text": reason_text,
        "item_feedbacks": item_feedbacks or [],
    }

    data["feedbacks"].append(feedback)
    return _write_json(feedback_path, data)


def get_user_feedbacks(telegram_id: str, days: int = 7) -> List[Dict[str, Any]]:
    """Get user's feedback history for the past N days."""
    user = get_user(telegram_id)
    if not user:
        return []

    feedbacks = []
    from datetime import timedelta

    for i in range(days):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        feedback_path = os.path.join(FEEDBACK_DIR, f"{date}.json")

        data = _read_json(feedback_path)
        for feedback in data.get("feedbacks", []):
            if feedback.get("user_id") == user["id"]:
                feedback["date"] = date
                feedbacks.append(feedback)

    return feedbacks


def get_feedback_reason_stats(days: int = 7) -> Dict[str, int]:
    """
    统计负面反馈原因分布。
    
    遍历指定天数内的反馈数据，提取 overall="negative" 的反馈中的 reason_selected，
    返回各原因的计数。
    
    Args:
        days: 统计的天数（默认 7 天）
        
    Returns:
        原因 -> 次数 的映射，按次数降序排列
    """
    reason_counts: Dict[str, int] = {}
    
    for i in range(days):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        feedback_path = os.path.join(FEEDBACK_DIR, f"{date}.json")
        
        data = _read_json(feedback_path)
        for feedback in data.get("feedbacks", []):
            # 只统计负面反馈
            if feedback.get("overall") == "negative":
                # 统计 reason_selected 中的原因
                for reason in feedback.get("reason_selected", []):
                    if reason:
                        reason_counts[reason] = reason_counts.get(reason, 0) + 1
                
                # 如果有自定义原因文本，也统计
                reason_text = feedback.get("reason_text")
                if reason_text:
                    # 自定义原因归类为"其他"
                    reason_counts["其他"] = reason_counts.get("其他", 0) + 1
    
    return reason_counts


# ============ Daily Stats Management ============

def save_daily_stats(
    date: str,
    sources_monitored: int,
    raw_items_scanned: int,
    user_stats: Dict[str, Dict[str, Any]]
) -> bool:
    """Save daily statistics."""
    stats_path = os.path.join(DAILY_STATS_DIR, f"{date}.json")

    data = {
        "date": date,
        "sources_monitored": sources_monitored,
        "raw_items_scanned": raw_items_scanned,
        "users": user_stats,
    }

    return _write_json(stats_path, data)


def get_daily_stats(date: Optional[str] = None) -> Dict[str, Any]:
    """Get daily statistics."""
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    stats_path = os.path.join(DAILY_STATS_DIR, f"{date}.json")
    return _read_json(stats_path)


# ============ Raw Content Management ============

def save_raw_content(date: str, items: List[Dict[str, Any]]) -> bool:
    """Save raw fetched content for a day."""
    content_path = os.path.join(RAW_CONTENT_DIR, f"{date}.json")

    data = {
        "date": date,
        "fetched_at": datetime.now().isoformat(),
        "count": len(items),
        "items": items,
    }

    return _write_json(content_path, data)


def get_raw_content(date: Optional[str] = None) -> Dict[str, Any]:
    """Get raw content for a day."""
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    content_path = os.path.join(RAW_CONTENT_DIR, f"{date}.json")
    return _read_json(content_path)


# ============ User Sources Management ============
# 
# 设计原则：
# 1. 默认源（DEFAULT_USER_SOURCES）：全局配置，修改后所有用户即时生效
# 2. 用户自定义源（custom_sources）：用户单独添加的源
# 3. 最终源 = 默认源 + 用户自定义源（合并）
#


def _source_key(category: str, name: str) -> str:
    """Unique key for a source (used in disabled list)."""
    return f"{category}:{name}"


def get_disabled_sources_set(telegram_id: str) -> set:
    """Get set of disabled source keys for the user. Keys are 'category:name'."""
    user = get_user(telegram_id)
    if not user:
        return set()
    _ensure_dir(USER_SOURCES_DIR)
    sources_path = os.path.join(USER_SOURCES_DIR, f"{user['id']}.json")
    if not os.path.exists(sources_path):
        return set()
    data = _read_json(sources_path)
    return set(data.get("disabled", []))


def set_source_enabled(telegram_id: str, category: str, name: str, enabled: bool) -> bool:
    """Enable or disable a source. Disabled sources are not fetched for digest."""
    user = get_user(telegram_id)
    if not user:
        return False
    _ensure_dir(USER_SOURCES_DIR)
    sources_path = os.path.join(USER_SOURCES_DIR, f"{user['id']}.json")
    data = _read_json(sources_path) if os.path.exists(sources_path) else {}
    disabled = list(data.get("disabled", []))
    key = _source_key(category, name)
    if enabled:
        if key in disabled:
            disabled.remove(key)
    else:
        if key not in disabled:
            disabled.append(key)
    data["disabled"] = disabled
    data.setdefault("user_id", user["id"])
    data.setdefault("telegram_id", telegram_id)
    data["updated"] = datetime.now().isoformat()
    if "custom_sources" not in data:
        data["custom_sources"] = data.get("custom_sources", {})
    result = _write_json(sources_path, data)
    if result:
        logger.info(f"Source {category}/{name} enabled={enabled} for user {user['id']}")
    return result


def get_user_sources(telegram_id: str, include_disabled: bool = True) -> Dict[str, Dict[str, str]]:
    """Get user's RSS source configuration.
    
    Returns merged sources: DEFAULT_USER_SOURCES + user's custom sources.
    Default sources always apply globally; user custom sources are additive.
    
    When include_disabled=False, disabled sources are excluded (for fetching digest).
    """
    import copy
    
    # Start with default sources (always included)
    merged = copy.deepcopy(DEFAULT_USER_SOURCES)
    
    user = get_user(telegram_id)
    if not user:
        return merged

    _ensure_dir(USER_SOURCES_DIR)
    sources_path = os.path.join(USER_SOURCES_DIR, f"{user['id']}.json")

    if not os.path.exists(sources_path):
        return merged

    data = _read_json(sources_path)
    custom_sources = data.get("custom_sources", {})
    
    # Merge custom sources into defaults
    for category, sources in custom_sources.items():
        if category not in merged:
            merged[category] = {}
        merged[category].update(sources)
    
    if not include_disabled:
        disabled = set(data.get("disabled", []))
        for category in list(merged.keys()):
            for name in list(merged.get(category, {}).keys()):
                if _source_key(category, name) in disabled:
                    del merged[category][name]
            if not merged.get(category):
                del merged[category]
    
    return merged


def get_user_custom_sources(telegram_id: str) -> Dict[str, Dict[str, str]]:
    """Get only user's custom (non-default) sources."""
    user = get_user(telegram_id)
    if not user:
        return {}

    _ensure_dir(USER_SOURCES_DIR)
    sources_path = os.path.join(USER_SOURCES_DIR, f"{user['id']}.json")

    if not os.path.exists(sources_path):
        return {}

    data = _read_json(sources_path)
    return data.get("custom_sources", {})


def save_user_sources(telegram_id: str, sources: Dict[str, Dict[str, str]]) -> bool:
    """Save user's custom RSS source configuration.
    
    Note: This saves ALL sources passed in. For the new architecture,
    use save_user_custom_sources() to save only custom sources.
    This function is kept for backward compatibility during migration.
    """
    user = get_user(telegram_id)
    if not user:
        logger.error(f"Cannot save sources: user {telegram_id} not found")
        return False

    _ensure_dir(USER_SOURCES_DIR)
    sources_path = os.path.join(USER_SOURCES_DIR, f"{user['id']}.json")

    # Extract custom sources (sources not in defaults)
    custom_sources = {}
    for category, cat_sources in sources.items():
        default_cat = DEFAULT_USER_SOURCES.get(category, {})
        custom_cat = {}
        for name, url in cat_sources.items():
            # Keep if not in defaults OR has different URL
            if name not in default_cat or (url and url != default_cat.get(name)):
                custom_cat[name] = url
        if custom_cat:
            custom_sources[category] = custom_cat

    # Preserve disabled list when saving
    existing = _read_json(sources_path) if os.path.exists(sources_path) else {}
    data = {
        "user_id": user["id"],
        "telegram_id": telegram_id,
        "updated": datetime.now().isoformat(),
        "custom_sources": custom_sources,
        "disabled": existing.get("disabled", []),
    }

    result = _write_json(sources_path, data)
    if result:
        logger.info(f"Saved custom sources for user {user['id']}: {len(custom_sources)} categories")
    return result


def add_user_source(telegram_id: str, category: str, name: str, url: str) -> bool:
    """Add a custom source to user's configuration.
    Enforces custom_sources_max limit; consumes onboarding redeem when free user adds first source.
    """
    custom = get_user_custom_sources(telegram_id)
    count_before = sum(len(v) for v in custom.values())
    is_new = name not in custom.get(category, {})

    try:
        from utils.permissions import get_user_plan, get_feature_limit
        limit = get_feature_limit(telegram_id, "custom_sources_max")
        if limit is not None and count_before >= limit:
            logger.info(f"User {telegram_id} custom source limit reached ({count_before} >= {limit})")
            return False
    except Exception:
        pass

    if category not in custom:
        custom[category] = {}

    custom[category][name] = url

    # Rebuild full sources for save (which will extract custom again)
    full_sources = get_user_sources(telegram_id)
    full_sources.setdefault(category, {})[name] = url
    ok = save_user_sources(telegram_id, full_sources)
    if not ok:
        return False

    # Consume onboarding one-time redeem when free user adds their first custom source
    if is_new and count_before == 0:
        try:
            from utils.permissions import get_user_plan
            user = get_user(telegram_id)
            if (
                user
                and get_user_plan(telegram_id) == "free"
                and user.get("onboarding_paid_redeem_available")
            ):
                consume_onboarding_redeem(telegram_id)
        except Exception:
            pass
    return True


def remove_user_source(telegram_id: str, category: str, name: str) -> bool:
    """Remove a source from user's configuration.
    
    Note: Cannot remove default sources. Only custom sources can be removed.
    """
    # Check if it's a default source
    if category in DEFAULT_USER_SOURCES and name in DEFAULT_USER_SOURCES[category]:
        logger.warning(f"Cannot remove default source: {category}/{name}")
        return False
    
    custom = get_user_custom_sources(telegram_id)

    if category in custom and name in custom[category]:
        del custom[category][name]
        # Clean up empty categories
        if not custom[category]:
            del custom[category]
        
        # Rebuild and save
        full_sources = get_user_sources(telegram_id)
        if category in full_sources and name in full_sources[category]:
            del full_sources[category][name]
        return save_user_sources(telegram_id, full_sources)
    return False


# ============ Per-User Raw Content ============

def save_user_raw_content(
    telegram_id: str,
    date: str,
    items: List[Dict[str, Any]],
    user_id: Optional[str] = None
) -> bool:
    """Save raw fetched content for a user on a specific day.

    Args:
        telegram_id: User's Telegram ID
        date: Date string (YYYY-MM-DD)
        items: Raw content items
        user_id: Optional user ID (avoids file lock race condition)
    """
    if not user_id:
        user = get_user(telegram_id)
        if not user:
            return False
        user_id = user["id"]

    user_content_dir = os.path.join(RAW_CONTENT_DIR, user_id)
    _ensure_dir(user_content_dir)
    content_path = os.path.join(user_content_dir, f"{date}.json")

    data = {
        "date": date,
        "user_id": user_id,
        "fetched_at": datetime.now().isoformat(),
        "count": len(items),
        "items": items,
    }

    return _write_json(content_path, data)


def get_user_raw_content(telegram_id: str, date: Optional[str] = None) -> Dict[str, Any]:
    """Get raw content for a user on a specific day."""
    user = get_user(telegram_id)
    if not user:
        return {}

    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    user_content_dir = os.path.join(RAW_CONTENT_DIR, user["id"])
    content_path = os.path.join(user_content_dir, f"{date}.json")
    return _read_json(content_path)


# ============ Per-User Daily Stats ============

def save_user_daily_stats(
    telegram_id: str,
    date: str,
    sources_monitored: int,
    raw_items_scanned: int,
    items_sent: int,
    status: str = "success",
    filtered_items: Optional[List[Dict[str, Any]]] = None,
    user_id: Optional[str] = None
) -> bool:
    """Save daily statistics for a specific user.

    Args:
        telegram_id: User's Telegram ID
        date: Date string (YYYY-MM-DD)
        sources_monitored: Number of sources monitored
        raw_items_scanned: Number of raw items scanned
        items_sent: Number of items sent
        status: Status string (default "success")
        filtered_items: Filtered items list (optional)
        user_id: Optional user ID (avoids file lock race condition)
    """
    if not user_id:
        user = get_user(telegram_id)
        if not user:
            return False
        user_id = user["id"]

    user_stats_dir = os.path.join(DAILY_STATS_DIR, user_id)
    _ensure_dir(user_stats_dir)
    stats_path = os.path.join(user_stats_dir, f"{date}.json")

    data = {
        "date": date,
        "user_id": user_id,
        "sources_monitored": sources_monitored,
        "raw_items_scanned": raw_items_scanned,
        "items_sent": items_sent,
        "status": status,
    }

    # Save filtered items for re-viewing the digest
    if filtered_items is not None:
        data["filtered_items"] = filtered_items

    return _write_json(stats_path, data)


def get_user_daily_stats(telegram_id: str, date: Optional[str] = None) -> Dict[str, Any]:
    """Get daily statistics for a specific user."""
    user = get_user(telegram_id)
    if not user:
        return {}

    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    user_stats_dir = os.path.join(DAILY_STATS_DIR, user["id"])
    stats_path = os.path.join(user_stats_dir, f"{date}.json")
    return _read_json(stats_path)


# ============ Data Cleanup ============

def _cleanup_old_files_in_dir(directory: str, retention_days: int) -> int:
    """
    Delete files older than retention_days in a directory.

    清理指定目录中超过保留天数的文件。
    支持 {date}.json 格式的文件名。

    Returns:
        Number of files deleted
    """
    if not os.path.exists(directory):
        return 0

    deleted_count = 0
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    cutoff_str = cutoff_date.strftime("%Y-%m-%d")

    try:
        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)

            # Skip directories (handle user subdirectories separately)
            if os.path.isdir(filepath):
                continue

            # Extract date from filename (format: {date}.json)
            if filename.endswith(".json"):
                date_part = filename.replace(".json", "")
                try:
                    # Validate date format
                    datetime.strptime(date_part, "%Y-%m-%d")
                    if date_part < cutoff_str:
                        os.remove(filepath)
                        deleted_count += 1
                        logger.debug(f"Deleted old file: {filepath}")
                except ValueError:
                    # Not a date-formatted file, skip
                    continue
    except Exception as e:
        logger.error(f"Error cleaning up {directory}: {e}")

    return deleted_count


def cleanup_old_data() -> Dict[str, int]:
    """
    Clean up old data files based on retention settings.

    根据配置的保留天数清理过期数据：
    - raw_content: RAW_CONTENT_RETENTION_DAYS (默认7天)
    - daily_stats: DAILY_STATS_RETENTION_DAYS (默认30天)
    - feedback: FEEDBACK_RETENTION_DAYS (默认30天)

    Returns:
        Dict with cleanup counts for each category
    """
    results = {
        "raw_content": 0,
        "daily_stats": 0,
        "feedback": 0,
    }

    # Clean feedback directory
    results["feedback"] = _cleanup_old_files_in_dir(
        FEEDBACK_DIR, FEEDBACK_RETENTION_DAYS
    )

    # Clean raw_content - handle per-user subdirectories
    if os.path.exists(RAW_CONTENT_DIR):
        root_level_cleaned = False
        for item in os.listdir(RAW_CONTENT_DIR):
            item_path = os.path.join(RAW_CONTENT_DIR, item)
            if os.path.isdir(item_path):
                # User subdirectory
                results["raw_content"] += _cleanup_old_files_in_dir(
                    item_path, RAW_CONTENT_RETENTION_DAYS
                )
            elif item.endswith(".json") and not root_level_cleaned:
                # Legacy global files - only process root level once
                results["raw_content"] += _cleanup_old_files_in_dir(
                    RAW_CONTENT_DIR, RAW_CONTENT_RETENTION_DAYS
                )
                root_level_cleaned = True

    # Clean daily_stats - handle per-user subdirectories
    if os.path.exists(DAILY_STATS_DIR):
        root_level_cleaned = False
        for item in os.listdir(DAILY_STATS_DIR):
            item_path = os.path.join(DAILY_STATS_DIR, item)
            if os.path.isdir(item_path):
                # User subdirectory
                results["daily_stats"] += _cleanup_old_files_in_dir(
                    item_path, DAILY_STATS_RETENTION_DAYS
                )
            elif item.endswith(".json") and not root_level_cleaned:
                # Legacy global files - only process root level once
                results["daily_stats"] += _cleanup_old_files_in_dir(
                    DAILY_STATS_DIR, DAILY_STATS_RETENTION_DAYS
                )
                root_level_cleaned = True

    total = sum(results.values())
    if total > 0:
        logger.info(
            f"Data cleanup complete: {results['raw_content']} raw_content, "
            f"{results['daily_stats']} daily_stats, {results['feedback']} feedback files deleted"
        )

    return results


# ============ Prefetch Cache Management ============

def get_prefetch_cache(date: Optional[str] = None) -> Dict[str, Any]:
    """
    获取指定日期的预抓取缓存。

    Args:
        date: 日期字符串 (YYYY-MM-DD)，默认为今天

    Returns:
        缓存数据字典，包含 seen_ids 和 items
    """
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    _ensure_dir(PREFETCH_CACHE_DIR)
    cache_path = os.path.join(PREFETCH_CACHE_DIR, f"{date}.json")

    data = _read_json(cache_path)
    if not data:
        # 初始化空缓存
        data = {
            "date": date,
            "seen_ids": [],
            "items": [],
            "fetch_count": 0,
            "last_fetch": None,
        }

    return data


def save_prefetch_cache(
    items: List[Dict[str, Any]],
    date: Optional[str] = None
) -> Dict[str, int]:
    """
    保存预抓取的内容到缓存，自动去重。

    Args:
        items: 新抓取的内容列表
        date: 日期字符串 (YYYY-MM-DD)，默认为今天

    Returns:
        统计信息 {"new_items": N, "total_items": M, "duplicates": D}
    """
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    # 读取现有缓存
    cache = get_prefetch_cache(date)
    seen_ids = set(cache.get("seen_ids", []))
    existing_items = cache.get("items", [])

    # 去重添加新内容
    new_count = 0
    duplicate_count = 0

    for item in items:
        item_id = item.get("id")
        if item_id and item_id not in seen_ids:
            seen_ids.add(item_id)
            existing_items.append(item)
            new_count += 1
        else:
            duplicate_count += 1

    # 更新缓存
    cache["seen_ids"] = list(seen_ids)
    cache["items"] = existing_items
    cache["fetch_count"] = cache.get("fetch_count", 0) + 1
    cache["last_fetch"] = datetime.now().isoformat()

    # 保存
    _ensure_dir(PREFETCH_CACHE_DIR)
    cache_path = os.path.join(PREFETCH_CACHE_DIR, f"{date}.json")
    _write_json(cache_path, cache)

    stats = {
        "new_items": new_count,
        "total_items": len(existing_items),
        "duplicates": duplicate_count,
    }

    logger.info(
        f"Prefetch cache updated: +{new_count} new, {duplicate_count} duplicates, "
        f"{len(existing_items)} total items"
    )

    return stats


def get_prefetch_items(date: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    获取指定日期的所有预抓取内容（已去重）。

    Args:
        date: 日期字符串 (YYYY-MM-DD)，默认为今天

    Returns:
        内容列表
    """
    cache = get_prefetch_cache(date)
    return cache.get("items", [])


def clear_prefetch_cache(date: Optional[str] = None) -> bool:
    """
    清除指定日期的预抓取缓存。

    Args:
        date: 日期字符串 (YYYY-MM-DD)，默认为今天

    Returns:
        是否成功
    """
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    cache_path = os.path.join(PREFETCH_CACHE_DIR, f"{date}.json")

    try:
        if os.path.exists(cache_path):
            os.remove(cache_path)
            logger.info(f"Cleared prefetch cache for {date}")
        return True
    except Exception as e:
        logger.error(f"Error clearing prefetch cache: {e}")
        return False


def cleanup_prefetch_cache(retention_days: int = 2) -> int:
    """
    清理过期的预抓取缓存（默认保留 2 天）。

    Args:
        retention_days: 保留天数

    Returns:
        删除的文件数
    """
    return _cleanup_old_files_in_dir(PREFETCH_CACHE_DIR, retention_days)


# ============ Whitelist Management ============

def get_whitelist() -> List[int]:
    """Get whitelisted user IDs."""
    from config import WHITELIST_FILE
    
    data = _read_json(WHITELIST_FILE)
    return data.get("whitelisted_ids", [])


def add_to_whitelist(telegram_id: int) -> bool:
    """Add user to whitelist."""
    from config import WHITELIST_FILE
    
    data = _read_json(WHITELIST_FILE)
    if "whitelisted_ids" not in data:
        data["whitelisted_ids"] = []
        
    if telegram_id not in data["whitelisted_ids"]:
        data["whitelisted_ids"].append(telegram_id)
        return _write_json(WHITELIST_FILE, data)
    
    return True


def remove_from_whitelist(telegram_id: int) -> bool:
    """Remove user from whitelist."""
    from config import WHITELIST_FILE
    
    data = _read_json(WHITELIST_FILE)
    if "whitelisted_ids" not in data:
        return False
        
    if telegram_id in data["whitelisted_ids"]:
        data["whitelisted_ids"].remove(telegram_id)
        return _write_json(WHITELIST_FILE, data)
        
    return False

# ============ Whitelist Settings ============

def get_whitelist_enabled() -> bool:
    """Get whitelist enabled status. Reads from settings file or defaults to env config."""
    from config import WHITELIST_SETTINGS_FILE, WHITELIST_ENABLED_DEFAULT
    
    data = _read_json(WHITELIST_SETTINGS_FILE)
    if "enabled" in data:
        return data["enabled"]
    return WHITELIST_ENABLED_DEFAULT


def set_whitelist_enabled(enabled: bool) -> bool:
    """Set whitelist enabled status. Saves to settings file."""
    from config import WHITELIST_SETTINGS_FILE
    
    data = _read_json(WHITELIST_SETTINGS_FILE)
    data["enabled"] = enabled
    return _write_json(WHITELIST_SETTINGS_FILE, data)


def is_whitelisted(telegram_id: int) -> bool:
    """Check if user is whitelisted (considering whitelist enabled status)."""
    from config import ADMIN_TELEGRAM_IDS
    
    # Admins are always allowed
    if str(telegram_id) in ADMIN_TELEGRAM_IDS:
        return True
    
    # If whitelist is disabled, everyone is allowed
    if not get_whitelist_enabled():
        return True
        
    # Check whitelist
    whitelist = get_whitelist()
    return telegram_id in whitelist


# ============ User Events Tracking (埋点) ============

def track_event(
    telegram_id: str,
    event_type: str,
    data: Optional[Dict[str, Any]] = None
) -> bool:
    """
    记录用户行为事件（埋点）
    
    Args:
        telegram_id: 用户 Telegram ID
        event_type: 事件类型，如 'feedback_positive', 'settings_changed' 等
        data: 事件附加数据（可选）
    
    Returns:
        是否记录成功
    
    事件类型说明:
        - digest_read: 用户点击查看摘要详情
        - feedback_positive: 正面反馈（点赞）
        - feedback_negative: 负面反馈（踩）
        - settings_changed: 设置变更
        - source_added: 添加信息源
        - source_removed: 删除信息源
        - chat_command: 使用命令
        - session_start: 会话开始（每日首次互动）
    """
    _ensure_dir(EVENTS_DIR)
    
    # 按月分文件，格式: events_2026-01.jsonl
    month_str = datetime.now().strftime("%Y-%m")
    events_file = os.path.join(EVENTS_DIR, f"events_{month_str}.jsonl")
    
    event = {
        "ts": datetime.now().isoformat(),
        "uid": telegram_id,
        "event": event_type,
    }
    
    if data:
        event["data"] = data
    
    try:
        # 追加写入 JSONL（每行一条 JSON）
        with open(events_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
        return True
    except Exception as e:
        logger.error(f"Failed to track event for {telegram_id}: {e}")
        return False


def get_user_events(
    telegram_id: str,
    days: int = 30,
    event_types: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    获取指定用户的事件记录
    
    Args:
        telegram_id: 用户 Telegram ID
        days: 获取最近多少天的事件
        event_types: 过滤特定事件类型（可选）
    
    Returns:
        事件列表
    """
    events = []
    cutoff_date = datetime.now() - timedelta(days=days)
    
    # 扫描相关月份的文件
    for filename in os.listdir(EVENTS_DIR) if os.path.exists(EVENTS_DIR) else []:
        if not filename.startswith("events_") or not filename.endswith(".jsonl"):
            continue
        
        filepath = os.path.join(EVENTS_DIR, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        event = json.loads(line)
                        # 过滤用户
                        if event.get("uid") != telegram_id:
                            continue
                        # 过滤时间
                        event_time = datetime.fromisoformat(event.get("ts", ""))
                        if event_time < cutoff_date:
                            continue
                        # 过滤事件类型
                        if event_types and event.get("event") not in event_types:
                            continue
                        events.append(event)
                    except (json.JSONDecodeError, ValueError):
                        continue
        except Exception as e:
            logger.error(f"Error reading events file {filename}: {e}")
    
    # 按时间排序
    events.sort(key=lambda x: x.get("ts", ""))
    return events


def get_events_summary(days: int = 7) -> Dict[str, Any]:
    """
    获取事件汇总统计（运营报表用）
    
    Args:
        days: 统计最近多少天
    
    Returns:
        汇总数据，包含：
        - active_users: 活跃的注册用户数（仅统计在users.json中存在的用户）
        - total_event_users: 有事件的所有用户数（包含已删除/未注册用户）
    """
    cutoff_date = datetime.now() - timedelta(days=days)
    
    # 获取所有注册用户的telegram_id集合
    registered_users = get_users()
    registered_user_ids = {str(u.get("telegram_id")) for u in registered_users}
    
    # 统计数据
    event_counts: Dict[str, int] = {}
    user_events: Dict[str, int] = {}  # 所有有事件的用户
    registered_user_events: Dict[str, int] = {}  # 仅注册用户
    daily_counts: Dict[str, int] = {}
    
    for filename in os.listdir(EVENTS_DIR) if os.path.exists(EVENTS_DIR) else []:
        if not filename.startswith("events_") or not filename.endswith(".jsonl"):
            continue
        
        filepath = os.path.join(EVENTS_DIR, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        event = json.loads(line)
                        event_time = datetime.fromisoformat(event.get("ts", ""))
                        if event_time < cutoff_date:
                            continue
                        
                        # 按事件类型统计
                        event_type = event.get("event", "unknown")
                        event_counts[event_type] = event_counts.get(event_type, 0) + 1
                        
                        # 按用户统计（所有用户）
                        uid = event.get("uid", "unknown")
                        user_events[uid] = user_events.get(uid, 0) + 1
                        
                        # 仅统计注册用户的活跃
                        if uid in registered_user_ids:
                            registered_user_events[uid] = registered_user_events.get(uid, 0) + 1
                        
                        # 按日期统计
                        date_str = event_time.strftime("%Y-%m-%d")
                        daily_counts[date_str] = daily_counts.get(date_str, 0) + 1
                        
                    except (json.JSONDecodeError, ValueError):
                        continue
        except Exception as e:
            logger.error(f"Error reading events file {filename}: {e}")
    
    return {
        "period_days": days,
        "total_events": sum(event_counts.values()),
        "active_users": len(registered_user_events),  # 仅注册用户中的活跃数
        "total_event_users": len(user_events),  # 所有有事件的用户（含已删除/未注册）
        "event_counts": event_counts,
        "daily_counts": daily_counts,
        "top_users": sorted(registered_user_events.items(), key=lambda x: -x[1])[:10],  # 仅展示注册用户
    }


def cleanup_old_events() -> int:
    """
    清理过期的事件文件
    
    Returns:
        删除的文件数
    """
    if not os.path.exists(EVENTS_DIR):
        return 0
    
    deleted = 0
    cutoff_date = datetime.now() - timedelta(days=EVENTS_RETENTION_DAYS)
    cutoff_month = cutoff_date.strftime("%Y-%m")
    
    for filename in os.listdir(EVENTS_DIR):
        if not filename.startswith("events_") or not filename.endswith(".jsonl"):
            continue
        
        # 从文件名提取月份: events_2026-01.jsonl -> 2026-01
        try:
            file_month = filename.replace("events_", "").replace(".jsonl", "")
            if file_month < cutoff_month:
                filepath = os.path.join(EVENTS_DIR, filename)
                os.remove(filepath)
                deleted += 1
                logger.info(f"Deleted old events file: {filename}")
        except Exception as e:
            logger.error(f"Error deleting events file {filename}: {e}")
    
    return deleted


# ─── Item URL Persistent Storage ───────────────────────────────────────

ITEM_URLS_FILE = os.path.join(DATA_DIR, "item_urls.json")


def save_item_urls(url_map: Dict[str, str]) -> bool:
    """
    Merge new item_id->url mappings into the persistent file.
    Keeps only the last 3 days of entries to avoid unbounded growth.
    """
    try:
        existing = _read_json(ITEM_URLS_FILE)
        now = datetime.now().isoformat()
        
        for item_id, url in url_map.items():
            existing[item_id] = {"url": url, "ts": now}
        
        cutoff = (datetime.now() - timedelta(days=3)).isoformat()
        pruned = {k: v for k, v in existing.items() if v.get("ts", "") >= cutoff}
        
        return _write_json(ITEM_URLS_FILE, pruned)
    except Exception as e:
        logger.error(f"Error saving item URLs: {e}")
        return False


def get_item_url(item_id: str) -> str:
    """Look up a persisted item URL by item_id."""
    try:
        data = _read_json(ITEM_URLS_FILE)
        entry = data.get(item_id, {})
        if isinstance(entry, dict):
            return entry.get("url", "")
        elif isinstance(entry, str):
            return entry
        return ""
    except Exception as e:
        logger.error(f"Error reading item URL for {item_id}: {e}")
        return ""


# ─── System Config (platform-level settings) ───────────────────────────

SYSTEM_CONFIG_FILE = os.path.join(DATA_DIR, "system_config.json")


def get_system_config(key: str, default=None):
    """Read a platform-level config value (e.g. CTA text)."""
    data = _read_json(SYSTEM_CONFIG_FILE)
    return data.get(key, default)


def set_system_config(key: str, value) -> bool:
    """Write a platform-level config value."""
    data = _read_json(SYSTEM_CONFIG_FILE)
    data[key] = value
    return _write_json(SYSTEM_CONFIG_FILE, data)
