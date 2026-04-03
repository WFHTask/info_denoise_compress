"""
Telegram Bot Sources Handler

Handles /sources command for users to view and manage information sources.
Allows viewing current sources and suggesting new ones.

Reference: python-telegram-bot v22.x (Exa verified 2025-01-12)
"""
import html
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from services.rss_fetcher import get_user_source_list
from utils.telegram_utils import safe_answer_callback_query
from utils.permissions import require_plan
from utils.json_storage import (
    get_user,
    add_user_source,
    remove_user_source,
    get_user_language,
    get_disabled_sources_set,
    set_source_enabled,
    track_event,
    update_user_activity,
)
from locales.ui_strings import get_ui_locale

logger = logging.getLogger(__name__)

# Conversation states
AWAITING_SOURCE_SUGGESTION, AWAITING_TWITTER_ADD, AWAITING_WEBSITE_ADD, AWAITING_BULK_IMPORT = range(4)


async def sources_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /sources command - show sources menu."""
    user = update.effective_user
    telegram_id = str(user.id)

    db_user = get_user(telegram_id)
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)
    
    if not db_user:
        await update.message.reply_text(ui["not_registered"])
        return

    keyboard = [
        [
            InlineKeyboardButton(ui["sources_twitter"], callback_data="sources_twitter"),
            InlineKeyboardButton(ui["sources_websites"], callback_data="sources_websites"),
        ],
        [InlineKeyboardButton(ui["sources_bulk_import"], callback_data="sources_bulk_import")],
        [InlineKeyboardButton(ui["sources_suggest"], callback_data="sources_suggest")],
        [InlineKeyboardButton(ui["back"], callback_data="back_to_start")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Get source counts and enabled/disabled for this user
    sources = get_user_source_list(telegram_id)
    disabled = get_disabled_sources_set(telegram_id)
    twitter_list = sources.get("twitter", [])
    website_list = sources.get("websites", [])

    def _stats_suffix(category: str, names: list) -> str:
        off = sum(1 for n in names if f"{category}:{n}" in disabled)
        on_count = len(names) - off
        return " " + ui["sources_stats_suffix"].format(enabled=on_count, disabled=off)

    twitter_line = f"  • {ui['sources_twitter_count'].format(count=len(twitter_list))}{_stats_suffix('twitter', twitter_list)}"
    website_line = f"  • {ui['sources_website_count'].format(count=len(website_list))}{_stats_suffix('websites', website_list)}"

    await update.message.reply_text(
        f"{ui['sources_title']}\n"
        f"{ui['divider']}\n\n"
        f"{ui['sources_current']}\n"
        f"{twitter_line}\n"
        f"{website_line}\n\n"
        f"{ui['sources_choose_category']}",
        reply_markup=reply_markup
    )


async def view_twitter_sources(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show list of monitored Twitter accounts with enable/disable toggle per source."""
    query = update.callback_query
    await safe_answer_callback_query(query)

    telegram_id = str(query.from_user.id)
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)
    
    sources = get_user_source_list(telegram_id)
    twitter_sources = sources.get("twitter", [])
    disabled = get_disabled_sources_set(telegram_id)

    if twitter_sources:
        lines = [
            f"{ui['twitter_title']}\n"
            f"{ui['divider']}\n"
        ]
        for i, source in enumerate(twitter_sources, 1):
            key = f"twitter:{source}"
            if key in disabled:
                lines.append(f"  🔴 {i}. {source} [{ui['source_disabled']}]")
            else:
                lines.append(f"  🟢 {i}. {source} [{ui['source_enabled']}]")
        lines.append(f"\n{ui['twitter_total'].format(count=len(twitter_sources))}")
        text = "\n".join(lines)
    else:
        text = (
            f"{ui['twitter_title']}\n"
            f"{ui['divider']}\n\n"
            f"{ui['twitter_empty']}"
        )

    keyboard = []
    if twitter_sources:
        for idx, source in enumerate(twitter_sources):
            key = f"twitter:{source}"
            if key in disabled:
                keyboard.append([
                    InlineKeyboardButton(
                        f"✅ {source} → {ui['btn_enable_source']}",
                        callback_data=f"src_tg_tw_{idx}",
                    )
                ])
            else:
                keyboard.append([
                    InlineKeyboardButton(
                        f"⏸ {source} → {ui['btn_disable_source']}",
                        callback_data=f"src_tg_tw_{idx}",
                    )
                ])
    keyboard.append([InlineKeyboardButton(ui["twitter_add"], callback_data="sources_add_twitter")])
    if twitter_sources:
        keyboard.append([InlineKeyboardButton(ui["twitter_delete"], callback_data="sources_del_twitter")])
    keyboard.append([InlineKeyboardButton(ui["back"], callback_data="sources_back")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup)


async def view_website_sources(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show list of monitored website RSS feeds with enable/disable toggle per source."""
    query = update.callback_query
    await safe_answer_callback_query(query)

    telegram_id = str(query.from_user.id)
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)
    sources = get_user_source_list(telegram_id)
    website_sources = sources.get("websites", [])
    disabled = get_disabled_sources_set(telegram_id)

    if website_sources:
        lines = [
            f"{ui.get('website_title', 'Website Sources')}\n"
            f"{ui['divider']}\n"
        ]
        for i, source in enumerate(website_sources, 1):
            key = f"websites:{source}"
            if key in disabled:
                lines.append(f"  🔴 {i}. {source} [{ui['source_disabled']}]")
            else:
                lines.append(f"  🟢 {i}. {source} [{ui['source_enabled']}]")
        lines.append(f"\n{ui.get('website_total', '{count} websites').format(count=len(website_sources))}")
        text = "\n".join(lines)
    else:
        text = (
            f"{ui.get('website_title', 'Website Sources')}\n"
            f"{ui['divider']}\n\n"
            f"{ui.get('website_empty', 'No website sources configured.')}"
        )

    keyboard = []
    if website_sources:
        for idx, source in enumerate(website_sources):
            key = f"websites:{source}"
            if key in disabled:
                keyboard.append([
                    InlineKeyboardButton(
                        f"✅ {source} → {ui['btn_enable_source']}",
                        callback_data=f"src_tg_web_{idx}",
                    )
                ])
            else:
                keyboard.append([
                    InlineKeyboardButton(
                        f"⏸ {source} → {ui['btn_disable_source']}",
                        callback_data=f"src_tg_web_{idx}",
                    )
                ])
    keyboard.append([InlineKeyboardButton(ui.get("website_add", "Add Website"), callback_data="sources_add_website")])
    if website_sources:
        keyboard.append([InlineKeyboardButton(ui.get("website_delete", "Delete Website"), callback_data="sources_del_website")])
    keyboard.append([InlineKeyboardButton(ui.get("back", "Back"), callback_data="sources_back")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup)


async def start_source_suggestion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the source suggestion conversation."""
    from utils.conv_manager import activate_conv
    activate_conv(context, "sources")

    query = update.callback_query
    await safe_answer_callback_query(query)

    telegram_id = str(query.from_user.id)
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)

    await query.edit_message_text(
        f"{ui.get('suggest_title', 'Suggest Sources')}\n"
        f"{ui['divider']}\n\n"
        f"{ui.get('suggest_prompt', 'Tell us sources you want to follow.')}\n\n"
        f"{ui.get('suggest_examples', 'Examples: @DefiLlama, defillama.com')}\n\n"
        f"{ui.get('settings_input_or_cancel', 'Enter or /cancel:')}"
    )

    return AWAITING_SOURCE_SUGGESTION


@require_plan("custom_sources")
async def start_add_twitter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start adding a Twitter RSS feed (Pro or one-time onboarding redeem)."""
    from utils.conv_manager import activate_conv
    activate_conv(context, "sources")

    query = update.callback_query
    await safe_answer_callback_query(query)

    telegram_id = str(query.from_user.id)
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)

    keyboard = [
        [InlineKeyboardButton(ui["btn_view_tutorial"], callback_data="twitter_tutorial")],
        [InlineKeyboardButton(ui["cancel"], callback_data="sources_twitter")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"{ui['twitter_add_title']}\n"
        f"{ui['divider']}\n\n"
        f"{ui.get('twitter_add_intro_rss_only', ui['twitter_add_intro'])}\n\n"
        f"{ui.get('twitter_add_method_title', '')}\n"
        f"{ui.get('twitter_add_method_desc', '')}\n\n"
        f"{ui['divider']}\n\n"
        f"{ui.get('twitter_input_prompt_rss_only', ui['twitter_input_prompt'])}",
        reply_markup=reply_markup,
        disable_web_page_preview=True
    )

    return AWAITING_TWITTER_ADD


async def show_twitter_tutorial(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show Twitter RSS tutorial. Returns AWAITING_TWITTER_ADD to stay in conversation."""
    query = update.callback_query
    await safe_answer_callback_query(query)

    telegram_id = str(query.from_user.id)
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)

    keyboard = [
        [InlineKeyboardButton(ui["btn_back_to_add"], callback_data="sources_add_twitter")],
        [InlineKeyboardButton(ui["cancel"], callback_data="sources_twitter")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"{ui['twitter_tutorial_title']}\n"
        f"{ui['divider']}\n\n"
        f"{ui['twitter_tutorial_step1']}\n\n"
        f"{ui['twitter_tutorial_step2']}\n\n"
        f"{ui['twitter_tutorial_step3']}\n\n"
        f"{ui['twitter_tutorial_step4']}\n\n"
        f"{ui['twitter_tutorial_step5']}\n\n"
        f"{ui['divider']}\n"
        f"{ui['twitter_tutorial_tip']}\n\n"
        f"{ui['twitter_tutorial_future']}\n\n"
        f"👇 {ui.get('twitter_paste_hint', '获取到 RSS 地址后，直接粘贴到此聊天窗口发送即可。')}",
        reply_markup=reply_markup,
        disable_web_page_preview=True
    )
    return AWAITING_TWITTER_ADD


async def handle_twitter_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle Twitter source addition - RSS URL only (e.g. from rss.app)."""
    from utils.conv_manager import is_active_conv
    if not is_active_conv(context, "sources"):
        logger.info("Sources text handler yielding - another conversation is active")
        telegram_id = str(update.effective_user.id)
        lang = get_user_language(telegram_id)
        ui = get_ui_locale(lang)
        await update.message.reply_text(ui.get("source_action_interrupted", "⚠️ Source action interrupted. Please click the add button again."))
        return ConversationHandler.END

    from services.rss_fetcher import validate_rss_url

    telegram_id = str(update.effective_user.id)
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)
    user_input = update.message.text.strip()

    feed_title = None
    feed_url = None
    entries_count = 0

    if user_input.startswith("http"):
        # --- Only support: paste RSS URL (e.g. from rss.app) ---
        validation = await validate_rss_url(user_input)

        if not validation["valid"]:
            keyboard = [
                [InlineKeyboardButton(ui["btn_view_tutorial"], callback_data="twitter_tutorial")],
                [InlineKeyboardButton(ui["btn_retry"], callback_data="sources_add_twitter")],
                [InlineKeyboardButton(ui["back"], callback_data="sources_twitter")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"{ui['twitter_add_failed']}\n"
                f"{ui['divider']}\n\n"
                f"{html.escape(validation['error'])}\n\n"
                f"{ui['twitter_check_retry']}",
                reply_markup=reply_markup
            )
            return ConversationHandler.END

        feed_title = validation.get("title", "Twitter List RSS")
        feed_url = user_input
        entries_count = validation.get("entries_count", 0)

    else:
        # --- Invalid input format ---
        keyboard = [
            [InlineKeyboardButton(ui["btn_view_tutorial"], callback_data="twitter_tutorial")],
            [InlineKeyboardButton(ui["btn_retry"], callback_data="sources_add_twitter")],
            [InlineKeyboardButton(ui["back"], callback_data="sources_twitter")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"{ui['twitter_format_error']}\n"
            f"{ui['divider']}\n\n"
            f"{ui.get('twitter_format_hint_rss_only', '请粘贴 RSS 链接（如 rss.app 生成）。')}",
            reply_markup=reply_markup
        )
        return ConversationHandler.END

    # --- Add to user's sources ---
    success = add_user_source(telegram_id, "twitter", feed_title, feed_url)

    keyboard = [
        [InlineKeyboardButton(ui["btn_add_more"], callback_data="sources_add_twitter")],
        [InlineKeyboardButton(ui["back"], callback_data="sources_twitter")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if success:
        track_event(telegram_id, "source_added", {"category": "twitter", "name": feed_title, "url": feed_url})
        update_user_activity(telegram_id)

        await update.message.reply_text(
            f"{ui['twitter_add_success']}\n"
            f"{ui['divider']}\n\n"
            f"{ui['twitter_added'].format(title=html.escape(feed_title))}\n"
            f"{ui['twitter_entries_count'].format(count=entries_count)}\n\n"
            f"{ui['twitter_next_digest']}",
            reply_markup=reply_markup
        )
        logger.info(f"Added Twitter source for user {telegram_id}: {feed_title} ({feed_url})")
    else:
        await update.message.reply_text(
            f"{ui['twitter_add_failed']}\n"
            f"{ui['divider']}\n\n"
            f"{ui['twitter_save_failed']}",
            reply_markup=reply_markup
        )
        logger.warning(f"Failed to add Twitter source for user {telegram_id}: {feed_url}")

    return ConversationHandler.END


@require_plan("custom_sources")
async def start_add_website(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start adding a website RSS feed (Pro or one-time onboarding redeem)."""
    from utils.conv_manager import activate_conv
    activate_conv(context, "sources")

    query = update.callback_query
    await safe_answer_callback_query(query)

    await query.edit_message_text(
        f"添加网站 RSS\n"
        f"{'─' * 24}\n\n"
        "方式一：只输入域名（自动探测）\n"
        "  theblock.co\n"
        "  decrypt.co\n\n"
        "方式二：指定名称和地址\n"
        "  The Block | https://theblock.co/rss.xml\n\n"
        "请输入或 /cancel 取消："
    )

    return AWAITING_WEBSITE_ADD


async def handle_website_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle website RSS feed addition."""
    from utils.conv_manager import is_active_conv
    if not is_active_conv(context, "sources"):
        return ConversationHandler.END

    from services.rss_fetcher import validate_url, auto_detect_rss

    telegram_id = str(update.effective_user.id)
    user_input = update.message.text.strip()

    # Parse input: "Name | URL" or just URL/domain
    if "|" in user_input:
        parts = user_input.split("|", 1)
        name = parts[0].strip()
        url = parts[1].strip()
    else:
        # Try to extract name from URL/domain
        url = user_input
        try:
            from urllib.parse import urlparse
            if url.startswith("http"):
                parsed = urlparse(url)
                name = parsed.netloc.replace("www.", "").split(".")[0].title()
            else:
                name = url.replace("www.", "").split(".")[0].title()
        except Exception:
            name = "Custom Source"

    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)

    keyboard = [
        [InlineKeyboardButton(ui.get("sources_add_more", "Add More"), callback_data="sources_add_website")],
        [InlineKeyboardButton(ui.get("back", "Back"), callback_data="sources_websites")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # If URL provided, validate it directly
    if url.startswith("http"):
        validation = await validate_url(url)
        if not validation["valid"]:
            await update.message.reply_text(
                f"{ui.get('website_add_failed', 'Failed to add')}\n"
                f"{ui['divider']}\n\n"
                f"{html.escape(validation['error'])}\n\n"
                f"{ui.get('website_check_retry', 'Please check and retry.')}",
                reply_markup=reply_markup
            )
            return ConversationHandler.END
        final_url = url
    else:
        # No full URL - try to auto-detect RSS from domain
        detection = await auto_detect_rss(url)
        if not detection["found"]:
            await update.message.reply_text(
                f"{ui.get('website_add_failed', 'Failed to add')}\n"
                f"{ui['divider']}\n\n"
                f"{html.escape(detection['error'])}\n\n"
                f"{ui.get('website_check_retry', 'Please check and retry.')}",
                reply_markup=reply_markup
            )
            return ConversationHandler.END
        final_url = detection["url"]

    # Add to user's sources
    success = add_user_source(telegram_id, "websites", name, final_url)

    if success:
        # 埋点：添加信息源 + 更新活跃时间
        track_event(telegram_id, "source_added", {"category": "websites", "name": name})
        update_user_activity(telegram_id)
        
        added_msg = ui.get('website_added', '✅ Added {title}').format(title=html.escape(name))
        await update.message.reply_text(
            f"{added_msg}\n"
            f"{ui['divider']}\n\n"
            f"RSS: {html.escape(final_url)}",
            reply_markup=reply_markup
        )
        logger.info(f"Added website source for user {telegram_id}: {name} - {final_url}")
    else:
        await update.message.reply_text(
            f"添加失败\n"
            f"{'─' * 24}\n\n"
            "保存失败，请重试。",
            reply_markup=reply_markup
        )
        logger.warning(f"Failed to add website source for user {telegram_id}: {name}")

    return ConversationHandler.END


async def handle_source_suggestion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle user's source suggestion."""
    from utils.conv_manager import is_active_conv
    if not is_active_conv(context, "sources"):
        return ConversationHandler.END

    user = update.effective_user
    telegram_id = str(user.id)
    suggestion = update.message.text

    # In a real implementation, this would be saved to a review queue
    # For MVP, we just acknowledge and log

    logger.info(f"Source suggestion from {telegram_id}: {suggestion}")

    await update.message.reply_text(
        f"已收到推荐\n"
        f"{'─' * 24}\n\n"
        f"{suggestion}\n\n"
        "我们会审核这个信息源。\n"
        "如果通过审核，将添加到监控列表。\n\n"
        "使用 /sources 查看当前信息源。"
    )

    return ConversationHandler.END


@require_plan("custom_sources")
async def start_bulk_import(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start bulk source import conversation (Pro or one-time onboarding redeem)."""
    from utils.conv_manager import activate_conv
    activate_conv(context, "sources")

    query = update.callback_query
    await safe_answer_callback_query(query)

    telegram_id = str(query.from_user.id)
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)
    title = ui.get("bulk_import_title", "Bulk Import Sources")
    body = ui.get("bulk_import_body", "Enter multiple sources, one per line.")
    prompt = ui.get("bulk_import_prompt", "Send content or /cancel:")
    divider = ui.get("divider", "─" * 24)

    await query.edit_message_text(
        f"{title}\n{divider}\n\n{body}\n\n{prompt}"
    )

    return AWAITING_BULK_IMPORT


async def handle_bulk_import(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle bulk source import."""
    from utils.conv_manager import is_active_conv
    if not is_active_conv(context, "sources"):
        return ConversationHandler.END

    from services.rss_fetcher import validate_rss_url, validate_url, auto_detect_rss

    telegram_id = str(update.effective_user.id)
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)
    user_input = update.message.text.strip()
    lines = user_input.split("\n")

    success_count = 0
    fail_count = 0
    results = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Determine category based on @ symbol
        if line.startswith("@") or ("|" in line and line.split("|")[0].strip().startswith("@")):
            category = "twitter"
        else:
            category = "websites"

        # Parse name and URL
        if "|" in line:
            parts = line.split("|", 1)
            name = parts[0].strip()
            url = parts[1].strip()
        else:
            name = line
            url = ""

        # Process based on category
        if category == "twitter":
            # Twitter: only support RSS URL (no @handle → auto-convert)
            url = url.strip() if url else ""
            if not url or not url.startswith("http"):
                fail_count += 1
                results.append(f"  - {name}: {ui.get('bulk_import_twitter_rss_required', 'Twitter requires RSS URL (format: name|RSS URL)')}")
                continue
            url_validation = await validate_rss_url(url)
            if not url_validation["valid"]:
                fail_count += 1
                results.append(f"  - {name}: {url_validation.get('error', ui.get('bulk_import_rss_invalid', 'Invalid RSS'))[:40]}")
                continue
            name = url_validation.get("title", name or "Twitter List RSS")
        else:
            # Website
            if url.startswith("http"):
                validation = await validate_url(url)
                if not validation["valid"]:
                    fail_count += 1
                    results.append(f"  - {name}: {validation['error'][:30]}")
                    continue
            elif not url:
                # Try auto-detect
                detection = await auto_detect_rss(name)
                if detection["found"]:
                    url = detection["url"]
                    name = name.replace("www.", "").split(".")[0].title()
                else:
                    fail_count += 1
                    results.append(f"  - {name}: {ui.get('bulk_import_rss_not_found', 'RSS not found')}")
                    continue

        # Add to user's sources
        success = add_user_source(telegram_id, category, name, url)
        if success:
            # 埋点：批量添加信息源 + 更新活跃时间
            track_event(telegram_id, "source_added", {"category": category, "name": name, "bulk": True})
            update_user_activity(telegram_id)
            success_count += 1
            results.append(f"  + {name}")
        else:
            fail_count += 1
            fail_msg = ui.get("bulk_import_line_fail", "Save failed")
            results.append(f"  - {name}: {fail_msg}")

    result_title = ui.get("bulk_import_result", "Bulk Import Results")
    success_line = ui.get("bulk_import_success_count", "Success: {count}").format(count=success_count)
    failed_line = ui.get("bulk_import_failed_count", "Failed: {count}").format(count=fail_count)
    detail_label = ui.get("bulk_import_detail", "Details:")
    more_label = ui.get("bulk_import_more", "... and {n} more").format(n=len(results) - 15)
    btn_continue = ui.get("bulk_import_btn_continue", "Continue Import")
    btn_back = ui.get("bulk_import_btn_back", "Back")
    divider = ui.get("divider", "─" * 24)

    keyboard = [
        [InlineKeyboardButton(btn_continue, callback_data="sources_bulk_import")],
        [InlineKeyboardButton(btn_back, callback_data="sources_back")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    status_text = "\n".join(results[:15])
    if len(results) > 15:
        status_text += f"\n  {more_label}"

    await update.message.reply_text(
        f"{result_title}\n{divider}\n\n{success_line}\n{failed_line}\n\n{detail_label}\n{status_text}",
        reply_markup=reply_markup
    )

    logger.info(f"Bulk import for user {telegram_id}: {success_count} success, {fail_count} failed")
    return ConversationHandler.END


async def show_delete_twitter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show Twitter sources with delete buttons."""
    query = update.callback_query
    await safe_answer_callback_query(query)

    telegram_id = str(query.from_user.id)
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)
    sources = get_user_source_list(telegram_id)
    twitter_sources = sources.get("twitter", [])

    if not twitter_sources:
        await query.edit_message_text(
            ui.get("sources_twitter_empty", "No Twitter sources to delete."),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(ui.get("back", "Back"), callback_data="sources_twitter")]
            ])
        )
        return

    text = (
        f"{ui.get('sources_delete_twitter', 'Delete Twitter Sources')}\n"
        f"{ui['divider']}\n\n"
        f"{ui.get('delete_select_prompt', 'Click to delete:')}\n"
    )

    # Create a button for each source
    keyboard = []
    for source in twitter_sources:
        keyboard.append([InlineKeyboardButton(f"❌ {source}", callback_data=f"del_tw_{source}")])
    keyboard.append([InlineKeyboardButton(ui.get("cancel", "Cancel"), callback_data="sources_twitter")])

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def show_delete_website(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show website sources with delete buttons."""
    query = update.callback_query
    await safe_answer_callback_query(query)

    telegram_id = str(query.from_user.id)
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)
    sources = get_user_source_list(telegram_id)
    website_sources = sources.get("websites", [])

    if not website_sources:
        await query.edit_message_text(
            ui.get("sources_website_empty", "No website sources to delete."),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(ui.get("back", "Back"), callback_data="sources_websites")]
            ])
        )
        return

    text = (
        f"{ui.get('sources_delete_website', 'Delete Website Sources')}\n"
        f"{ui['divider']}\n\n"
        f"{ui.get('delete_select_prompt', 'Click to delete:')}\n"
    )

    # Create a button for each source
    keyboard = []
    for source in website_sources:
        keyboard.append([InlineKeyboardButton(f"❌ {source}", callback_data=f"del_web_{source}")])
    keyboard.append([InlineKeyboardButton(ui.get("cancel", "Cancel"), callback_data="sources_websites")])

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_delete_twitter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle Twitter source deletion."""
    query = update.callback_query
    await safe_answer_callback_query(query)

    telegram_id = str(query.from_user.id)
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)
    source_name = query.data.replace("del_tw_", "")

    success = remove_user_source(telegram_id, "twitter", source_name)

    if success:
        # 埋点：删除信息源 + 更新活跃时间
        track_event(telegram_id, "source_removed", {"category": "twitter", "name": source_name})
        update_user_activity(telegram_id)
        
        logger.info(f"Deleted Twitter source for user {telegram_id}: {source_name}")
        await query.edit_message_text(
            ui.get('delete_success', '🗑️ Deleted {name}').format(name=source_name),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(ui.get("sources_continue_delete", "Continue Delete"), callback_data="sources_del_twitter")],
                [InlineKeyboardButton(ui.get("back", "Back"), callback_data="sources_twitter")],
            ])
        )
    else:
        await query.edit_message_text(
            f"{ui.get('delete_failed', 'Delete failed. Please retry.')}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(ui.get("back", "Back"), callback_data="sources_twitter")]
            ])
        )


async def handle_delete_website(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle website source deletion."""
    query = update.callback_query
    await safe_answer_callback_query(query)

    telegram_id = str(query.from_user.id)
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)
    source_name = query.data.replace("del_web_", "")

    success = remove_user_source(telegram_id, "websites", source_name)

    if success:
        # 埋点：删除信息源 + 更新活跃时间
        track_event(telegram_id, "source_removed", {"category": "websites", "name": source_name})
        update_user_activity(telegram_id)
        
        logger.info(f"Deleted website source for user {telegram_id}: {source_name}")
        await query.edit_message_text(
            ui.get('delete_success', '🗑️ Deleted {name}').format(name=source_name),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(ui.get("sources_continue_delete", "Continue Delete"), callback_data="sources_del_website")],
                [InlineKeyboardButton(ui.get("back", "Back"), callback_data="sources_websites")],
            ])
        )
    else:
        await query.edit_message_text(
            f"{ui.get('delete_failed', 'Delete failed. Please retry.')}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(ui.get("back", "Back"), callback_data="sources_websites")]
            ])
        )


async def handle_source_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggle enable/disable for one source. Refreshes the list view after."""
    query = update.callback_query
    await safe_answer_callback_query(query)

    telegram_id = str(query.from_user.id)
    # callback_data: src_tg_tw_0 or src_tg_web_1
    parts = query.data.split("_")
    if len(parts) != 4 or parts[0] != "src" or parts[1] != "tg":
        return
    cat_short = parts[2]  # tw or web
    try:
        idx = int(parts[3])
    except ValueError:
        return
    category = "twitter" if cat_short == "tw" else "websites"

    sources = get_user_source_list(telegram_id)
    names = sources.get(category, [])
    if idx < 0 or idx >= len(names):
        return
    name = names[idx]

    disabled = get_disabled_sources_set(telegram_id)
    key = f"{category}:{name}"
    currently_disabled = key in disabled
    set_source_enabled(telegram_id, category, name, enabled=currently_disabled)

    if category == "twitter":
        await view_twitter_sources(update, context)
    else:
        await view_website_sources(update, context)


async def sources_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Return to sources menu."""
    query = update.callback_query
    await safe_answer_callback_query(query)

    telegram_id = str(query.from_user.id)
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)
    sources = get_user_source_list(telegram_id)
    disabled = get_disabled_sources_set(telegram_id)
    twitter_list = sources.get("twitter", [])
    website_list = sources.get("websites", [])

    def _stats_suffix(category: str, names: list) -> str:
        off = sum(1 for n in names if f"{category}:{n}" in disabled)
        on_count = len(names) - off
        return " " + ui.get("sources_stats_suffix", "({enabled} on, {disabled} off)").format(
            enabled=on_count, disabled=off
        )

    twitter_line = f"  • {ui.get('sources_twitter', 'Twitter')}: {len(twitter_list)}{_stats_suffix('twitter', twitter_list)}"
    website_line = f"  • {ui.get('sources_websites', 'Websites')}: {len(website_list)}{_stats_suffix('websites', website_list)}"

    keyboard = [
        [
            InlineKeyboardButton(ui.get("sources_twitter", "Twitter"), callback_data="sources_twitter"),
            InlineKeyboardButton(ui.get("sources_websites", "Websites"), callback_data="sources_websites"),
        ],
        [InlineKeyboardButton(ui.get("sources_bulk_import", "Bulk Import"), callback_data="sources_bulk_import")],
        [InlineKeyboardButton(ui.get("sources_suggest", "Suggest"), callback_data="sources_suggest")],
        [InlineKeyboardButton(ui.get("back", "Back"), callback_data="back_to_start")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"{ui.get('sources_title', 'Sources')}\n"
        f"{ui['divider']}\n\n"
        f"{ui.get('sources_monitoring', 'Currently monitoring:')}\n"
        f"{twitter_line}\n"
        f"{website_line}\n\n"
        f"{ui.get('sources_choose_category', 'Select a category.')}",
        reply_markup=reply_markup
    )


async def cancel_sources(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel sources conversation."""
    user = update.effective_user
    telegram_id = str(user.id) if user else "0"
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)

    keyboard = [
        [
            InlineKeyboardButton(ui.get("sources_title", "Sources"), callback_data="sources_back"),
            InlineKeyboardButton(ui.get("menu_main", "Main Menu"), callback_data="back_to_start"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"{ui.get('cancelled', 'Cancelled')}\n\n"
        f"{ui.get('can_restart', 'You can start again anytime.')}",
        reply_markup=reply_markup
    )
    return ConversationHandler.END


def get_sources_handler() -> ConversationHandler:
    """Create and return the sources conversation handler."""
    return ConversationHandler(
        entry_points=[
            CommandHandler("sources", sources_command),
            CallbackQueryHandler(start_source_suggestion, pattern="^sources_suggest$"),
            CallbackQueryHandler(start_add_twitter, pattern="^sources_add_twitter$"),
            CallbackQueryHandler(start_add_website, pattern="^sources_add_website$"),
            CallbackQueryHandler(start_bulk_import, pattern="^sources_bulk_import$"),
        ],
        states={
            AWAITING_SOURCE_SUGGESTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_source_suggestion),
            ],
            AWAITING_TWITTER_ADD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_twitter_add),
                CallbackQueryHandler(show_twitter_tutorial, pattern="^twitter_tutorial$"),
                CallbackQueryHandler(start_add_twitter, pattern="^sources_add_twitter$"),
            ],
            AWAITING_WEBSITE_ADD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_website_add),
            ],
            AWAITING_BULK_IMPORT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_bulk_import),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_sources),
        ],
        conversation_timeout=300,  # Auto-cancel after 5 minutes idle
    )


def get_sources_callbacks():
    """Get standalone callback handlers for sources menu."""
    return [
        CallbackQueryHandler(view_twitter_sources, pattern="^sources_twitter$"),
        CallbackQueryHandler(view_website_sources, pattern="^sources_websites$"),
        CallbackQueryHandler(handle_source_toggle, pattern=r"^src_tg_(tw|web)_\d+$"),
        CallbackQueryHandler(show_delete_twitter, pattern="^sources_del_twitter$"),
        CallbackQueryHandler(show_delete_website, pattern="^sources_del_website$"),
        CallbackQueryHandler(handle_delete_twitter, pattern="^del_tw_"),
        CallbackQueryHandler(handle_delete_website, pattern="^del_web_"),
        CallbackQueryHandler(sources_back, pattern="^sources_back$"),
        # Note: twitter_tutorial is handled inside ConversationHandler states (AWAITING_TWITTER_ADD)
    ]
