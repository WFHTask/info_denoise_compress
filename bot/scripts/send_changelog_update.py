#!/usr/bin/env python3
"""
Send CHANGELOG Update Notification

This script parses the latest version from CHANGELOG.md and sends it to all
subscribed users. It's designed to be called by GitHub Actions when CHANGELOG.md
is updated.

Usage:
    python scripts/send_changelog_update.py [--dry-run]

Arguments:
    --dry-run    Don't send messages, just show what would be sent
"""

import asyncio
import os
import re
import sys
import logging
import argparse
from typing import Any, Dict, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError

from config import TELEGRAM_BOT_TOKEN, DATA_DIR
from utils.json_storage import (
    get_subscribed_users,
    get_user_language,
    get_system_config,
    set_system_config,
)
from locales.ui_strings import get_ui_locale
from services.gemini_provider import GeminiProvider

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Path to CHANGELOG.md
# In Docker: mounted at /app/CHANGELOG.md
# In dev: relative to bot directory (../CHANGELOG.md)
_script_dir = os.path.dirname(os.path.abspath(__file__))
_bot_dir = os.path.dirname(_script_dir)
CHANGELOG_PATH = os.path.join(_bot_dir, "CHANGELOG.md")  # /app/CHANGELOG.md in Docker

# Cache for translated content
_translation_cache: Dict[str, str] = {}


def parse_latest_changelog() -> Optional[Dict[str, str]]:
    """
    Parse the latest version entry from CHANGELOG.md.
    
    Only extracts user-facing content under "### 本次更新" section.
    Skips technical details like "### 技术改进", "### 测试验证", etc.
    
    Returns:
        Dict with 'version', 'date', and 'content', or None if parsing fails
    """
    try:
        with open(CHANGELOG_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        logger.error(f"CHANGELOG.md not found at {CHANGELOG_PATH}")
        return None
    
    # Pattern to match version headers like "## v1.6.3 - 2026年1月30日"
    # or "## v1.6.3 - January 30, 2026"
    version_pattern = r'^## (v[\d.]+) - (.+?)$'
    
    # Find all version sections
    lines = content.split('\n')
    start_idx = None
    end_idx = None
    version = None
    date = None
    
    for i, line in enumerate(lines):
        match = re.match(version_pattern, line.strip())
        if match:
            if start_idx is None:
                # Found the first (latest) version
                start_idx = i
                version = match.group(1)
                date = match.group(2)
            else:
                # Found the next version, mark end of current section
                end_idx = i
                break
    
    if start_idx is None:
        logger.error("No version entry found in CHANGELOG.md")
        return None
    
    # Extract content between this version and the next (or end of file)
    if end_idx is None:
        section_lines = lines[start_idx + 1:]
    else:
        section_lines = lines[start_idx + 1:end_idx]
    
    # Only extract "### 本次更新" section (user-facing content)
    # Skip technical sections like "### 技术改进", "### 测试验证", "### 运营须知"
    user_content_lines = []
    in_user_section = False
    
    # Sections to include (user-facing)
    include_sections = ['本次更新', '新功能', '改进', '修复']
    # Sections to skip (technical/internal)
    skip_sections = ['技术改进', '测试验证', '运营须知', '技术细节', '开发说明']
    
    for line in section_lines:
        stripped = line.strip()
        
        # Check if entering a new ### section
        if stripped.startswith('### '):
            section_name = stripped[4:].strip()
            
            # IMPORTANT: Check skip sections FIRST (e.g., "技术改进" contains "改进")
            if any(name in section_name for name in skip_sections):
                in_user_section = False
                continue
            elif any(name in section_name for name in include_sections):
                in_user_section = True
                # Don't include the "### 本次更新" header itself
                continue
            else:
                # Unknown section, skip by default
                in_user_section = False
                continue
        
        # Collect lines if in user section
        if in_user_section:
            user_content_lines.append(line)
    
    # Clean up
    user_content = '\n'.join(user_content_lines).strip()
    
    # Remove leading/trailing "---" separators
    if user_content.startswith('---'):
        user_content = user_content[3:].strip()
    if user_content.endswith('---'):
        user_content = user_content[:-3].strip()
    
    # If no user content found, fall back to full section (minus code blocks)
    if not user_content:
        full_content = '\n'.join(section_lines).strip()
        # Remove code blocks (test output, etc.)
        full_content = re.sub(r'```[\s\S]*?```', '', full_content)
        user_content = full_content.strip()
    
    return {
        'version': version,
        'date': date,
        'content': user_content
    }


async def translate_changelog(content: str, target_lang: str) -> str:
    """
    Translate CHANGELOG content to target language using Gemini.
    
    Uses caching to avoid redundant API calls for the same language.
    
    Args:
        content: Original content (in Chinese)
        target_lang: Target language code (en, ja, ko)
        
    Returns:
        Translated content
    """
    # Chinese doesn't need translation
    if target_lang == 'zh':
        return content
    
    # Check cache
    cache_key = f"{target_lang}:{hash(content)}"
    if cache_key in _translation_cache:
        logger.info(f"Using cached translation for {target_lang}")
        return _translation_cache[cache_key]
    
    # Map language codes to full names for the prompt
    lang_names = {
        'en': 'English',
        'ja': 'Japanese',
        'ko': 'Korean'
    }
    
    target_name = lang_names.get(target_lang, 'English')
    
    prompt = f"""Translate the following product update notes from Chinese to {target_name}.

Keep the formatting (markdown, bullet points, emojis) intact.
Keep technical terms and version numbers unchanged.
Translate naturally for the target audience, not word-by-word.

---

{content}

---

Provide only the translated text, no explanations."""

    try:
        provider = GeminiProvider()
        response = await provider.generate_text(
            prompt=prompt,
            temperature=0.3,
            max_tokens=4096
        )
        translated = response.content.strip()
        
        # Cache the result
        _translation_cache[cache_key] = translated
        logger.info(f"Translated changelog to {target_lang} ({len(translated)} chars)")
        
        return translated
        
    except Exception as e:
        logger.error(f"Translation to {target_lang} failed: {e}")
        # Return original content as fallback
        return content


def create_unsubscribe_keyboard(lang: str = "zh") -> InlineKeyboardMarkup:
    """Create keyboard with unsubscribe button."""
    ui = get_ui_locale(lang)
    keyboard = [[
        InlineKeyboardButton(
            ui["btn_unsubscribe_updates"],
            callback_data="unsubscribe_updates"
        )
    ]]
    return InlineKeyboardMarkup(keyboard)


async def send_update_to_user(
    bot: Bot,
    telegram_id: str,
    changelog: Dict[str, str],
    dry_run: bool = False
) -> bool:
    """
    Send changelog update to a single user.
    
    Args:
        bot: Telegram Bot instance
        telegram_id: User's Telegram ID
        changelog: Parsed changelog dict
        dry_run: If True, don't actually send
        
    Returns:
        True if successful (or dry_run), False otherwise
    """
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)
    
    # Translate if needed
    content = await translate_changelog(changelog['content'], lang)
    
    # Build message
    message = f"**{ui['update_notification_title']}** ({changelog['version']})\n\n"
    message += content
    
    # Truncate if too long (Telegram limit is 4096 chars)
    if len(message) > 4000:
        message = message[:3950] + "\n\n... (内容已截断)"
    
    keyboard = create_unsubscribe_keyboard(lang)
    
    if dry_run:
        logger.info(f"[DRY RUN] Would send to {telegram_id} ({lang}):\n{message[:200]}...")
        return True
    
    try:
        await bot.send_message(
            chat_id=telegram_id,
            text=message,
            parse_mode='Markdown',
            reply_markup=keyboard
        )
        logger.info(f"Sent update to {telegram_id} ({lang})")
        return True
        
    except TelegramError as e:
        logger.error(f"Failed to send to {telegram_id}: {e}")
        return False


async def send_latest_changelog_update(
    dry_run: bool = False,
    skip_if_not_changed: bool = True,
    persist_on_success: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Parse latest changelog and notify subscribed users.

    Args:
        dry_run: If True, do not actually send messages
        skip_if_not_changed: If True, skip when latest version == last_notified_version
        persist_on_success: If True, update last_notified_version after full success

    Returns:
        Summary dict when parsing succeeds, None when parsing fails.
    """
    # Parse changelog
    changelog = parse_latest_changelog()
    if not changelog:
        logger.error("Failed to parse CHANGELOG.md")
        return None

    version = changelog.get("version", "")
    last_notified_version = get_system_config("last_notified_version", "")
    if skip_if_not_changed and version and version == last_notified_version:
        logger.info(
            f"Skip notification: latest version {version} already notified "
            f"(last_notified_version={last_notified_version})"
        )
        return {
            "version": version,
            "date": changelog.get("date", ""),
            "skipped": True,
            "reason": "already_notified",
            "success_count": 0,
            "fail_count": 0,
            "total_users": 0,
        }

    logger.info(f"Parsed changelog: {changelog['version']} ({changelog['date']})")
    logger.info(f"Content preview: {changelog['content'][:200]}...")
    
    # Get subscribed users
    users = get_subscribed_users()
    if not users:
        logger.warning("No subscribed users found")
        return {
            "version": version,
            "date": changelog.get("date", ""),
            "skipped": False,
            "reason": "no_users",
            "success_count": 0,
            "fail_count": 0,
            "total_users": 0,
        }
    
    logger.info(f"Found {len(users)} subscribed users")
    
    # Initialize bot
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    
    # Pre-translate for all languages to populate cache
    languages = set(get_user_language(str(u.get('telegram_id'))) for u in users)
    logger.info(f"Languages to translate: {languages}")
    
    for lang in languages:
        if lang != 'zh':
            await translate_changelog(changelog['content'], lang)
    
    # Send to all users
    success_count = 0
    fail_count = 0
    
    for user in users:
        telegram_id = str(user.get('telegram_id'))
        if not telegram_id:
            continue
        
        # Rate limiting: 25 messages per second max
        await asyncio.sleep(0.05)
        
        success = await send_update_to_user(bot, telegram_id, changelog, dry_run)
        if success:
            success_count += 1
        else:
            fail_count += 1
    
    logger.info(f"Finished: {success_count} sent, {fail_count} failed")

    if fail_count == 0 and (not dry_run) and persist_on_success:
        set_ok = set_system_config("last_notified_version", version)
        if set_ok:
            logger.info(f"Updated last_notified_version to {version}")
        else:
            logger.warning(f"Failed to persist last_notified_version={version}")

    return {
        "version": version,
        "date": changelog.get("date", ""),
        "skipped": False,
        "reason": "",
        "success_count": success_count,
        "fail_count": fail_count,
        "total_users": len(users),
    }


async def main(dry_run: bool = False, force: bool = False):
    """Main function to send changelog updates."""
    result = await send_latest_changelog_update(
        dry_run=dry_run,
        skip_if_not_changed=not force,
        persist_on_success=True,
    )

    if result is None:
        sys.exit(1)

    if result.get("fail_count", 0) > 0:
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send CHANGELOG update notifications")
    parser.add_argument('--dry-run', action='store_true', help="Don't send messages, just preview")
    parser.add_argument('--force', action='store_true', help="Force send even if version already notified")
    args = parser.parse_args()

    asyncio.run(main(dry_run=args.dry_run, force=args.force))
