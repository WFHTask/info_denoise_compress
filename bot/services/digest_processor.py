"""
Digest Processor - Handles single user digest generation

This module is separated to avoid circular imports between main.py and handlers/start.py
"""

import logging
import html
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from telegram.ext import ContextTypes
from config import MAX_DIGEST_ITEMS
from utils.telegram_utils import send_message_safe

logger = logging.getLogger(__name__)


async def process_single_user(
    context: ContextTypes.DEFAULT_TYPE,
    user: Dict[str, Any],
    today: str,
    global_raw_content: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Process digest generation and sending for a single user.

    Args:
        context: Telegram context
        user: User dict with telegram_id
        today: Date string (YYYY-MM-DD)
        global_raw_content: Pre-fetched global RSS data (optional)
                           If provided, will filter from this instead of fetching

    Returns:
        Dict with status info: {"user": telegram_id, "status": "success|error", ...}
    """
    from services.rss_fetcher import fetch_user_sources, get_user_source_list
    from services.content_filter import filter_and_translate_for_user, get_ai_summary, translate_text, translate_content, get_user_target_language
    from services.report_generator import (
        generate_empty_report,
        detect_user_language,
        prepare_digest_messages,
        get_translation_language,
        get_locale,
    )
    from utils.json_storage import (
        get_user_profile,
        save_user_raw_content,
        save_user_daily_stats,
        get_prefetch_items,
        get_user_last_push_time,
        set_user_last_push_time,
    )
    from handlers.feedback import create_feedback_keyboard, create_item_feedback_keyboard

    telegram_id = user.get("telegram_id")
    user_id = user.get("id")  # Extract user_id to avoid race condition
    if not telegram_id:
        return {"user": None, "status": "skipped", "reason": "no telegram_id"}

    # 记录本次推送开始时间（用于更新 last_push_time）
    current_push_time = datetime.now()

    try:
        # 1. Fetch content from this user's sources
        user_sources = get_user_source_list(telegram_id)
        sources_count = sum(len(s) for s in user_sources.values())

        # 获取用户订阅的源名称集合
        user_source_names = set()
        for category_sources in user_sources.values():
            user_source_names.update(category_sources)

        # ===== 获取上次推送时间，用于过滤新内容 =====
        last_push_time_str = get_user_last_push_time(telegram_id)
        if last_push_time_str:
            try:
                last_push_time = datetime.fromisoformat(last_push_time_str)
                logger.info(f"User {telegram_id}: Last push time: {last_push_time_str}")
            except ValueError:
                # 解析失败，默认为 24 小时前
                last_push_time = current_push_time - timedelta(hours=24)
                logger.warning(f"User {telegram_id}: Invalid last_push_time, using 24h ago")
        else:
            # 新用户或首次推送，默认筛选过去 24 小时
            last_push_time = current_push_time - timedelta(hours=24)
            logger.info(f"User {telegram_id}: First push, using 24h window")

        # ===== 数据获取优先级：预抓取缓存 > 传入的全局数据 > 实时抓取 =====

        # 尝试从预抓取缓存获取（包含多次抓取累积的去重数据）
        # 合并今天和昨天的缓存，确保不遗漏跨天数据
        yesterday = (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
        
        prefetch_items_today = get_prefetch_items(today)
        prefetch_items_yesterday = get_prefetch_items(yesterday)
        
        # 合并并去重（以 id 为准）
        seen_ids = set()
        prefetch_items = []
        
        for item in prefetch_items_today + prefetch_items_yesterday:
            item_id = item.get("id")
            if item_id and item_id not in seen_ids:
                seen_ids.add(item_id)
                prefetch_items.append(item)

        if prefetch_items:
            # 从预抓取缓存中过滤：1) 用户订阅的源 2) 上次推送之后的新内容
            raw_content_before_filter = len(prefetch_items)
            raw_content = []
            
            for item in prefetch_items:
                # 检查是否是用户订阅的源
                if item.get("source") not in user_source_names:
                    continue
                
                # 检查是否是上次推送之后的新内容
                published_str = item.get("published")
                if published_str:
                    try:
                        published = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
                        # 转换为 naive datetime 进行比较（去掉时区信息）
                        if published.tzinfo:
                            published = published.replace(tzinfo=None)
                        if published <= last_push_time.replace(tzinfo=None):
                            continue  # 跳过上次推送之前的旧内容
                    except (ValueError, TypeError):
                        pass  # 解析失败的保留
                
                raw_content.append(item)
            
            filtered_out = raw_content_before_filter - len(raw_content)
            logger.info(
                f"User {telegram_id}: Got {len(raw_content)} NEW items from cache "
                f"(total cached: {raw_content_before_filter}, filtered out {filtered_out} old items)"
            )

        elif global_raw_content is not None:
            # 从传入的全局数据中过滤（兼容旧逻辑）
            raw_content = []
            for item in global_raw_content:
                if item.get("source") not in user_source_names:
                    continue
                # 时间过滤
                published_str = item.get("published")
                if published_str:
                    try:
                        published = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
                        if published.tzinfo:
                            published = published.replace(tzinfo=None)
                        if published <= last_push_time.replace(tzinfo=None):
                            continue
                    except (ValueError, TypeError):
                        pass
                raw_content.append(item)
            logger.info(f"User {telegram_id}: Filtered {len(raw_content)} NEW items from global data")

        else:
            # Fallback: 实时抓取（用于 /test 命令或首次推送）
            raw_content = await fetch_user_sources(telegram_id, hours_back=24)
            logger.info(f"User {telegram_id}: Fetched {len(raw_content)} items "
                       f"from {sources_count} sources (realtime)")

        # ===== 数据获取完成 =====

        # Save raw content for this user
        save_user_raw_content(telegram_id, today, raw_content, user_id=user_id)

        # Get user profile for language detection
        profile = get_user_profile(telegram_id) or ""
        user_lang = detect_user_language(profile)

        # 2. Filter content for user (filtering only, no translation)
        filtered_items = await filter_and_translate_for_user(
            telegram_id=telegram_id,
            raw_content=raw_content,
            max_items=MAX_DIGEST_ITEMS
        )

        chat_id = int(telegram_id)
        report_id = f"{today}_{telegram_id}"

        if filtered_items:
            # Generate AI summary (in English - all AI processing uses English)
            ai_summary = await get_ai_summary(filtered_items, profile)
            
            # === Final output translation ===
            # Get translation target language from user_lang code
            target_language = get_translation_language(user_lang)
            
            # Translate content to user's language (handles all cases including mixed content)
            filtered_items = await translate_content(filtered_items, target_language)
            ai_summary = await translate_text(ai_summary, target_language)

            # Prepare messages: header + individual items
            header, item_messages = prepare_digest_messages(
                filtered_items=filtered_items,
                ai_summary=ai_summary,
                sources_count=sources_count,
                raw_count=len(raw_content),
                lang=user_lang
            )

            # Send header message
            await send_message_safe(context,
                chat_id=chat_id,
                text=header,
                parse_mode="HTML",
                disable_web_page_preview=True
            )

            # Get locale for feedback buttons
            locale = get_locale(user_lang)

            # Send each item with feedback buttons
            # Store item_id -> item_url mapping for click tracking
            if "item_urls" not in context.bot_data:
                context.bot_data["item_urls"] = {}
            
            _batch_urls = {}
            
            for item_msg, item_id, item_url in item_messages:
                # Section headers don't get feedback buttons
                if item_id.startswith("section_"):
                    await send_message_safe(context,
                        chat_id=chat_id,
                        text=item_msg,
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    )
                else:
                    # Store URL mapping for later retrieval in click handler
                    if item_url:
                        context.bot_data["item_urls"][item_id] = item_url
                        _batch_urls[item_id] = item_url
                    
                    # Pass item_url for "查看原文" button
                    item_keyboard = create_item_feedback_keyboard(item_id, item_url=item_url, lang=user_lang)
                    await send_message_safe(context,
                        chat_id=chat_id,
                        text=item_msg,
                        reply_markup=item_keyboard,
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    )

            # Persist item URLs to file (survives bot restart)
            if _batch_urls:
                from utils.json_storage import save_item_urls
                save_item_urls(_batch_urls)

            # Send final feedback message
            final_keyboard = create_feedback_keyboard(report_id)
            locale_prompt = locale.get("helpful_prompt", "Was this helpful?")
            await send_message_safe(context,
                chat_id=chat_id,
                text=f"{'─' * 28}\n{locale_prompt}",
                reply_markup=final_keyboard
            )

        else:
            # No content - send empty report
            report = generate_empty_report(lang=user_lang)
            await send_message_safe(context,
                chat_id=chat_id,
                text=report,
                parse_mode="HTML",
                disable_web_page_preview=True
            )

        # 3. Save per-user daily stats
        save_user_daily_stats(
            telegram_id=telegram_id,
            date=today,
            sources_monitored=sources_count,
            raw_items_scanned=len(raw_content),
            items_sent=len(filtered_items),
            status="success",
            filtered_items=filtered_items,
            user_id=user_id
        )

        # 4. 更新用户的上次推送时间（用于下次过滤新内容）
        set_user_last_push_time(telegram_id, current_push_time.isoformat())

        logger.info(f"Sent digest to {telegram_id}: {len(filtered_items)} items")
        return {
            "user": telegram_id,
            "status": "success",
            "items_sent": len(filtered_items)
        }

    except Exception as e:
        logger.error(f"Failed to send digest to {telegram_id}: {e}")
        err_msg = str(e).lower()
        if "blocked by the user" in err_msg or "user is deactivated" in err_msg:
            set_user_last_push_time(telegram_id, current_push_time.isoformat())
            logger.info(f"User {telegram_id} blocked/deactivated, updated last_push_time to avoid frequent retries")
        save_user_daily_stats(
            telegram_id=telegram_id,
            date=today,
            sources_monitored=0,
            raw_items_scanned=0,
            items_sent=0,
            status=f"error: {str(e)[:50]}",
            user_id=user_id
        )
        return {
            "user": telegram_id,
            "status": "error",
            "error": str(e)[:100]
        }


async def generate_group_digest(
    raw_content: List[Dict[str, Any]],
    profile: str,
    language: str
) -> str:
    """
    Generate a group digest using AI filtering and summary.

    Output is Telegram HTML format and keeps original links in each item.
    """
    from services.llm_factory import call_llm_json
    from services.content_filter import get_ai_summary, translate_content, translate_text, smart_truncate
    from services.report_generator import (
        get_locale,
        get_category_names,
        DIVIDER_HEAVY,
        DIVIDER_LIGHT,
        SEPARATOR_LENGTH,
    )
    from config import MAX_DIGEST_ITEMS

    locale_lang = language if language in ("zh", "en", "ja", "ko") else "en"
    locale = get_locale(locale_lang)
    category_names = get_category_names(locale_lang)
    date_str = datetime.now().strftime("%Y-%m-%d")

    if not raw_content:
        return (
            f"<b>{locale['title']}</b>\n"
            f"{date_str}\n"
            f"{DIVIDER_HEAVY * SEPARATOR_LENGTH}\n\n"
            f"{locale['no_content']}"
        )

    index_map: Dict[int, Dict[str, Any]] = {}
    content_for_ai: List[Dict[str, Any]] = []

    for i, item in enumerate(raw_content, 1):
        index_map[i] = item
        title = (item.get("title") or "").strip()
        summary = (item.get("summary") or "").strip()
        merged_text = f"{title} | {summary}" if summary and summary not in title else (title or summary)
        content_for_ai.append({
            "n": i,
            "src": item.get("source", "Unknown"),
            "t": smart_truncate(merged_text, 300),
        })

    system_instruction = (
        "You are a Web3 group digest editor.\n"
        "Given a group profile and content list, select high-value items only.\n"
        "Return JSON object only with keys: must_read, macro_insights, recommended, other.\n"
        "Each item format: {\"n\": <index>, \"r\": <short recommendation reason>}.\n"
        "Rules:\n"
        "- put market/protocol critical updates into must_read\n"
        "- put trend/context information into macro_insights\n"
        "- put profile-matching updates into recommended\n"
        "- keep less-important leftovers in other\n"
        f"- total selected count in [6, {MAX_DIGEST_ITEMS}] when possible\n"
    )
    prompt = (
        f"Group profile:\n{profile or 'General Web3 news'}\n\n"
        f"Output language code target: {language}\n\n"
        f"Content items ({len(content_for_ai)}):\n"
        f"{json.dumps(content_for_ai, ensure_ascii=False)}\n\n"
        "Return valid JSON only."
    )

    filtered_result, _model = await call_llm_json(
        prompt=prompt,
        system_instruction=system_instruction,
        context="group-digest-filter",
    )

    selected_items: List[Dict[str, Any]] = []
    if isinstance(filtered_result, dict):
        for section in ["must_read", "macro_insights", "recommended", "other"]:
            for ai_item in filtered_result.get(section, []):
                n = ai_item.get("n")
                if not n or n not in index_map:
                    continue
                original = index_map[n]
                selected_items.append({
                    "id": original.get("id", f"group_item_{n}"),
                    "title": original.get("title", "Untitled"),
                    "summary": smart_truncate(original.get("summary", "") or "", 220),
                    "source": original.get("source", "Unknown"),
                    "link": original.get("link", ""),
                    "section": section,
                    "reason": ai_item.get("r", ""),
                    "author": original.get("author", ""),
                })

    # Fallback when AI output is unavailable or malformed
    if not selected_items:
        selected_items = [
            {
                "id": item.get("id", f"group_fallback_{idx}"),
                "title": item.get("title", "Untitled"),
                "summary": smart_truncate(item.get("summary", "") or "", 220),
                "source": item.get("source", "Unknown"),
                "link": item.get("link", ""),
                "section": "other",
                "reason": "Fallback: AI unavailable",
                "author": item.get("author", ""),
            }
            for idx, item in enumerate(raw_content[:MAX_DIGEST_ITEMS], 1)
        ]

    # Keep stable order and remove duplicates by link/title
    deduped_items: List[Dict[str, Any]] = []
    seen_keys = set()
    for item in selected_items:
        dedup_key = (item.get("link") or "").strip() or (item.get("title") or "").strip().lower()
        if not dedup_key or dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)
        deduped_items.append(item)
    selected_items = deduped_items[:MAX_DIGEST_ITEMS]

    ai_summary = await get_ai_summary(selected_items, profile or "General Web3 news")

    # Final translation for output
    target_lang_map = {
        "zh": "Chinese",
        "en": "English",
        "ja": "Japanese",
        "ko": "Korean",
    }
    target_language = target_lang_map.get(locale_lang, "English")
    if target_language != "English":
        selected_items = await translate_content(selected_items, target_language)
        ai_summary = await translate_text(ai_summary, target_language)

    grouped: Dict[str, List[Dict[str, Any]]] = {
        "must_read": [],
        "macro_insights": [],
        "recommended": [],
        "other": [],
    }
    for item in selected_items:
        section = item.get("section", "other")
        if section not in grouped:
            section = "other"
        grouped[section].append(item)

    lines = [
        f"<b>{locale['title']}</b>",
        date_str,
        DIVIDER_HEAVY * SEPARATOR_LENGTH,
        "",
        html.escape(ai_summary),
        "",
        DIVIDER_LIGHT * SEPARATOR_LENGTH,
        "",
    ]

    for section in ["must_read", "macro_insights", "recommended", "other"]:
        items = grouped.get(section, [])
        if not items:
            continue
        section_name = category_names.get(section, section)
        lines.append(f"<b>{section_name}</b>")
        lines.append("")

        for item in items:
            title = html.escape(item.get("title", "Untitled"))
            summary = html.escape(item.get("summary", "") or "")
            source = html.escape(item.get("source", "") or "")
            link = (item.get("link", "") or "").strip()

            if link:
                safe_link = html.escape(link, quote=True)
                lines.append(f'• <a href="{safe_link}">{title}</a>')
            else:
                lines.append(f"• {title}")

            if summary:
                lines.append(f"  {summary}")
            if source:
                lines.append(f"  <i>{source}</i>")
            lines.append("")

    return "\n".join(lines).strip()
