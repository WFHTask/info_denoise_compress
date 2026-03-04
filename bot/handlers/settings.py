"""
Telegram Bot Settings Handler

Handles /settings command for users to view and update their preferences.
Supports viewing current profile and re-running preference setup.

Reference: python-telegram-bot v22.x (Exa verified 2025-01-12)
"""
import html
import logging
from telegram import ForceReply, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from services.gemini import call_gemini
from utils.prompt_loader import get_prompt
from utils.telegram_utils import safe_answer_callback_query
from utils.json_storage import (
    get_user,
    get_user_profile,
    save_user_profile,
    track_event,
    get_user_language,
    get_user_setting,
    set_user_setting,
)
from utils.permissions import check_feature
from services.language_service import (
    get_language_native_name,
    update_user_language,
    SUPPORTED_UI_LANGUAGES,
    LANGUAGE_NATIVE_NAMES,
)
from locales.ui_strings import get_ui_locale

logger = logging.getLogger(__name__)

# Conversation states
(AWAITING_PROFILE_UPDATE,) = range(1)


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /settings command - show settings menu."""
    user = update.effective_user
    telegram_id = str(user.id)
    
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)

    db_user = get_user(telegram_id)
    if not db_user:
        await update.message.reply_text(ui["not_registered"])
        return

    # Get current language display name
    current_lang_name = get_language_native_name(lang)
    
    keyboard = [
        [InlineKeyboardButton(ui["settings_view"], callback_data="settings_view")],
        [
            InlineKeyboardButton(ui["settings_update"], callback_data="settings_update"),
            InlineKeyboardButton(ui["settings_reset"], callback_data="settings_reset"),
        ],
        [InlineKeyboardButton(ui.get("settings_push_interval", "📅 推送间隔"), callback_data="settings_push_interval")],
        [InlineKeyboardButton(f"🌐 {current_lang_name}", callback_data="settings_language")],
        [InlineKeyboardButton(ui["back"], callback_data="back_to_start")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"{ui['settings_title']}\n"
        f"{ui['divider']}\n\n"
        f"{ui['settings_desc']}",
        reply_markup=reply_markup
    )


async def view_current_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user's current preference profile."""
    query = update.callback_query
    await safe_answer_callback_query(query)

    user = update.effective_user
    telegram_id = str(user.id)
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)

    profile = get_user_profile(telegram_id)

    if profile:
        text = (
            f"{ui['settings_your_prefs']}\n"
            f"{ui['divider']}\n\n"
            f"{html.escape(profile)}\n\n"
            f"{ui['divider']}\n"
            f"{ui['settings_use_settings']}"
        )
    else:
        text = (
            f"{ui['settings_your_prefs']}\n"
            f"{ui['divider']}\n\n"
            f"{ui['settings_no_prefs']}"
        )

    keyboard = [[InlineKeyboardButton(ui["back"], callback_data="settings_back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup)


async def start_profile_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the profile update conversation."""
    from utils.conv_manager import activate_conv
    activate_conv(context, "settings")

    query = update.callback_query
    await safe_answer_callback_query(query)

    user = update.effective_user
    telegram_id = str(user.id)
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)

    profile = get_user_profile(telegram_id)
    examples = ui.get("settings_examples", "Examples:\n  • 'Add more DeFi'\n  • 'Less NFT'\n  • 'Focus on Arbitrum'")

    if profile:
        await query.edit_message_text(
            f"{ui.get('settings_update_title', 'Update Preferences')}\n"
            f"{ui['divider']}\n\n"
            f"{ui.get('settings_current', 'Current preferences:')}\n"
            f"{html.escape(profile)}\n\n"
            f"{ui['divider']}\n\n"
            f"{ui.get('settings_what_change', 'What would you like to change?')}\n\n"
            f"{examples}"
        )
    else:
        await query.edit_message_text(
            f"{ui.get('settings_update_title', 'Update Preferences')}\n"
            f"{ui['divider']}\n\n"
            f"{ui.get('settings_no_prefs', 'No preferences set yet.')}\n\n"
            f"{examples}"
        )

    chat = update.effective_chat
    is_group = chat and chat.type in ("group", "supergroup")
    await context.bot.send_message(
        chat_id=chat.id,
        text=ui.get("settings_input_or_cancel", "Enter or /cancel:"),
        reply_markup=ForceReply(selective=True) if is_group else None,
    )

    return AWAITING_PROFILE_UPDATE


async def handle_profile_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle user's profile update input."""
    from utils.conv_manager import is_active_conv, clear_active_conv

    # Check if this conversation is still the active one
    if not is_active_conv(context, "settings"):
        logger.info("Settings text handler yielding - another conversation is active")
        await update.message.reply_text(
            "⚠️ 偏好更新已取消（你已切换到其他操作）。\n"
            "请重新发送你的输入。\n\n"
            "Profile update cancelled. Please resend your input."
        )
        return ConversationHandler.END

    clear_active_conv(context)
    user = update.effective_user
    telegram_id = str(user.id)
    user_input = update.message.text
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)

    # Get current profile
    current_profile = get_user_profile(telegram_id) or ""

    # Load prompt from file
    system_instruction = get_prompt(
        "settings_update.txt",
        current_profile=current_profile or "No existing profile",
        user_input=user_input
    )

    try:
        updated_profile = await call_gemini(
            prompt=f"Update profile with: {user_input}",
            system_instruction=system_instruction,
            temperature=0.5
        )

        # Save updated profile
        save_user_profile(telegram_id, updated_profile)

        # 埋点：设置变更
        track_event(telegram_id, "settings_changed", {"action": "update", "input": user_input[:100]})

        await update.message.reply_text(
            f"{ui.get('settings_updated_success', '✅ Preferences Updated')}\n"
            f"{ui['divider']}\n\n"
            f"{html.escape(updated_profile)}"
        )

        logger.info(f"Updated profile for {telegram_id}")

    except Exception as e:
        logger.error(f"Failed to update profile for {telegram_id}: {e}")
        keyboard = [
            [InlineKeyboardButton(ui.get("retry", "Retry"), callback_data="settings_update")],
            [InlineKeyboardButton(ui.get("settings_back", "Back"), callback_data="settings_back")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            ui.get("settings_update_failed", "Unable to update preferences. Please try again later."),
            reply_markup=reply_markup
        )

    return ConversationHandler.END


async def confirm_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ask for confirmation before resetting preferences."""
    query = update.callback_query
    await safe_answer_callback_query(query)

    user = update.effective_user
    telegram_id = str(user.id) if user else "0"
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)

    keyboard = [
        [
            InlineKeyboardButton(ui.get("btn_cancel", "Cancel"), callback_data="settings_back"),
            InlineKeyboardButton(ui.get("btn_confirm_reset", "Confirm Reset"), callback_data="settings_reset_confirm"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"{ui.get('settings_reset_title', 'Reset Preferences')}\n"
        f"{ui['divider']}\n\n"
        f"{ui.get('settings_reset_confirm_msg', 'This will delete your preferences. Are you sure?')}",
        reply_markup=reply_markup
    )


async def execute_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Execute profile reset."""
    query = update.callback_query
    await safe_answer_callback_query(query)

    user = update.effective_user
    telegram_id = str(user.id)
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)

    # Reset profile to default
    default_profile = """[User Type]
Web3 new user, general interest

[Focus Areas]
- Web3 general news
- Major ecosystem updates
- Market dynamics

[Content Preferences]
- Balanced news and analysis
- Moderate amount (10-15 items)

[Dislikes]
- None yet"""

    save_user_profile(telegram_id, default_profile)

    # 埋点：设置重置
    track_event(telegram_id, "settings_changed", {"action": "reset"})

    await query.edit_message_text(
        f"{ui.get('settings_reset_done', '✅ Preferences Reset')}\n"
        f"{ui['divider']}\n\n"
        f"{ui.get('settings_use_settings', 'Use /settings to customize.')}"
    )

    logger.info(f"Reset profile for {telegram_id}")


async def settings_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Return to settings menu."""
    query = update.callback_query
    await safe_answer_callback_query(query)

    user = update.effective_user
    telegram_id = str(user.id) if user else "0"
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)
    current_lang_name = get_language_native_name(lang)

    keyboard = [
        [InlineKeyboardButton(ui.get("settings_view", "View Preferences"), callback_data="settings_view")],
        [
            InlineKeyboardButton(ui.get("settings_update", "Update"), callback_data="settings_update"),
            InlineKeyboardButton(ui.get("settings_reset", "Reset"), callback_data="settings_reset"),
        ],
        [InlineKeyboardButton(ui.get("settings_push_interval", "📅 推送间隔"), callback_data="settings_push_interval")],
        [InlineKeyboardButton(f"🌐 {current_lang_name}", callback_data="settings_language")],
        [InlineKeyboardButton(ui.get("back", "Back"), callback_data="back_to_start")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"{ui.get('settings_title', 'Preferences')}\n"
        f"{ui['divider']}\n\n"
        f"{ui.get('settings_desc', 'Manage your preferences.')}",
        reply_markup=reply_markup
    )


async def cancel_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel settings conversation."""
    user = update.effective_user
    telegram_id = str(user.id) if user else "0"
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)

    keyboard = [
        [
            InlineKeyboardButton(ui.get("settings_title", "Settings"), callback_data="settings_back"),
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


def get_settings_handler() -> ConversationHandler:
    """Create and return the settings conversation handler."""
    return ConversationHandler(
        entry_points=[
            CommandHandler("settings", settings_command),
            CallbackQueryHandler(start_profile_update, pattern="^settings_update$"),
        ],
        states={
            AWAITING_PROFILE_UPDATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_profile_update),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_settings),
        ],
        conversation_timeout=300,  # Auto-cancel after 5 minutes idle
    )


async def show_language_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show language selection menu."""
    query = update.callback_query
    await safe_answer_callback_query(query)

    user = update.effective_user
    telegram_id = str(user.id)
    current_lang = get_user_language(telegram_id)
    ui = get_ui_locale(current_lang)

    # Build language selection keyboard
    # Show supported languages first, then a few common others
    keyboard = []

    # Supported languages with predefined UI
    for lang_code in SUPPORTED_UI_LANGUAGES:
        lang_name = get_language_native_name(lang_code)
        is_current = "✓ " if lang_code == current_lang else ""
        keyboard.append([
            InlineKeyboardButton(f"{is_current}{lang_name}", callback_data=f"set_lang_{lang_code}")
        ])

    # Add separator and other common languages
    other_langs = ["ru", "es", "fr", "de", "vi", "th"]
    other_row = []
    for lang_code in other_langs:
        if lang_code not in SUPPORTED_UI_LANGUAGES:
            lang_name = get_language_native_name(lang_code)
            is_current = "✓ " if lang_code == current_lang else ""
            other_row.append(
                InlineKeyboardButton(f"{is_current}{lang_name[:3]}", callback_data=f"set_lang_{lang_code}")
            )
            if len(other_row) == 3:
                keyboard.append(other_row)
                other_row = []
    if other_row:
        keyboard.append(other_row)

    keyboard.append([InlineKeyboardButton(f"← {ui['back']}", callback_data="settings_back")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    current_lang_name = get_language_native_name(current_lang)

    await query.edit_message_text(
        f"{ui['lang_settings_title']}\n"
        f"{'─' * 24}\n\n"
        f"{ui['lang_current'].format(lang=current_lang_name)}\n\n"
        f"{ui['lang_select']}",
        reply_markup=reply_markup
    )


async def change_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle language change selection."""
    query = update.callback_query
    await safe_answer_callback_query(query)
    
    user = update.effective_user
    telegram_id = str(user.id)
    
    # Extract language code from callback data: set_lang_xx
    lang_code = query.data.replace("set_lang_", "")
    
    # Update language
    success = update_user_language(telegram_id, lang_code)
    
    if success:
        # Track event
        track_event(telegram_id, "settings_changed", {"action": "language", "new_lang": lang_code})
        
        # Get new UI strings
        ui = get_ui_locale(lang_code)
        lang_name = get_language_native_name(lang_code)
        
        keyboard = [
            [InlineKeyboardButton(f"🌐 {ui.get('settings_change_lang', '修改语言')}", callback_data="settings_language")],
            [InlineKeyboardButton(ui.get("back", "Back"), callback_data="settings_back")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"✓ {ui.get('lang_updated', 'Language updated to')} {lang_name}\n\n"
            f"{ui.get('lang_future_msg', 'All future messages will be in')} {lang_name}.",
            reply_markup=reply_markup
        )
        
        logger.info(f"Changed language for {telegram_id} to {lang_code}")
    else:
        # Fallback to English UI for error message since language update failed
        from locales.ui_strings import get_ui_locale as get_fallback_ui
        fallback_ui = get_fallback_ui("en")
        keyboard = [[InlineKeyboardButton(fallback_ui["retry"], callback_data="settings_language")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            fallback_ui.get("lang_update_failed", "Failed to update language. Please try again."),
            reply_markup=reply_markup
        )


async def show_push_interval_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show push interval options. Pro: 1/2/6/12/24h; Free: 24h only."""
    query = update.callback_query
    await safe_answer_callback_query(query)

    telegram_id = str(query.from_user.id)
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)

    current = get_user_setting(telegram_id, "push_interval_hours")
    from config import PUSH_INTERVAL_HOURS, PUSH_INTERVAL_PRO_HOURS
    if current is None:
        current = PUSH_INTERVAL_PRO_HOURS if check_feature(telegram_id, "priority_push") else PUSH_INTERVAL_HOURS
    else:
        current = max(1, min(24, int(current)))

    title = ui.get("settings_push_interval_title", "推送间隔")
    desc = ui.get("settings_push_interval_desc", "选择简报推送频率（Pro 可自定义，免费版固定一天一次）")
    current_label = ui.get("settings_push_interval_current", "当前：每 {hours} 小时推送一次").format(hours=current)

    keyboard = []
    if check_feature(telegram_id, "priority_push"):
        for h in [1, 2, 6, 12, 24]:
            label = ui.get(f"settings_interval_{h}h", f"{h} 小时")
            if h == current:
                label = f"✓ {label}"
            keyboard.append([InlineKeyboardButton(label, callback_data=f"settings_set_interval_{h}")])
    else:
        label = ui.get("settings_interval_24h", "24 小时（一天一次）")
        if current >= 24:
            label = f"✓ {label}"
        keyboard.append([InlineKeyboardButton(label, callback_data="settings_set_interval_24")])
    keyboard.append([InlineKeyboardButton(ui["back"], callback_data="settings_back")])

    await query.edit_message_text(
        f"{title}\n{ui['divider']}\n\n{desc}\n\n{current_label}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def set_push_interval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Save user's chosen push interval and confirm."""
    query = update.callback_query
    await safe_answer_callback_query(query)

    telegram_id = str(query.from_user.id)
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)

    # callback_data: settings_set_interval_1 | _2 | _6 | _12 | _24
    try:
        hours = int(query.data.replace("settings_set_interval_", ""))
        hours = max(1, min(24, hours))
    except (ValueError, TypeError):
        hours = 24

    if not check_feature(telegram_id, "priority_push"):
        hours = 24

    ok = set_user_setting(telegram_id, "push_interval_hours", hours)
    if ok:
        track_event(telegram_id, "settings_changed", {"action": "push_interval", "hours": hours})
    msg = ui.get("settings_push_interval_saved", "已设置为每 {hours} 小时推送一次").format(hours=hours) if ok else ui.get("settings_save_failed", "保存失败，请重试")

    keyboard = [[InlineKeyboardButton(ui["back"], callback_data="settings_back")]]
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))


def get_settings_callbacks():
    """Get standalone callback handlers for settings menu."""
    return [
        CallbackQueryHandler(view_current_profile, pattern="^settings_view$"),
        CallbackQueryHandler(confirm_reset, pattern="^settings_reset$"),
        CallbackQueryHandler(execute_reset, pattern="^settings_reset_confirm$"),
        CallbackQueryHandler(settings_back, pattern="^settings_back$"),
        CallbackQueryHandler(show_push_interval_settings, pattern="^settings_push_interval$"),
        CallbackQueryHandler(set_push_interval, pattern="^settings_set_interval_"),
        CallbackQueryHandler(show_language_settings, pattern="^settings_language$"),
        CallbackQueryHandler(change_language, pattern="^set_lang_"),
    ]
