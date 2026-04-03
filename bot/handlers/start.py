"""
Telegram Bot Start Handler

Handles /start command and user registration flow.
Uses ConversationHandler for AI-driven preference collection.

Reference: python-telegram-bot v22.x official examples (Exa verified 2025-01-12)
"""
import asyncio
import logging

# Timeout for digest generation (seconds)
DIGEST_TIMEOUT = 180
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
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
from utils.telegram_utils import safe_answer_callback_query, send_message_safe
from utils.json_storage import (
    get_user,
    create_user,
    save_user_profile,
    get_user_profile,
    track_event,
    get_user_language,
    update_user_activity,
)
from utils.auth import whitelist_required
from services.language_service import normalize_language_code, get_language_native_name
from utils.language import detect_language_from_text, is_supported_language
from locales.ui_strings import get_ui_locale

logger = logging.getLogger(__name__)

# Conversation states
ONBOARDING_ROUND_1, ONBOARDING_ROUND_2, ONBOARDING_ROUND_3, CONFIRM_PROFILE, SOURCE_CHOICE, ADDING_SOURCES = range(6)


@whitelist_required
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle /start command.
    Check if user exists, show appropriate welcome message.
    """
    user = update.effective_user
    chat = update.effective_chat
    telegram_id = str(user.id)

    # 埋点：会话开始 + 更新活跃时间
    track_event(telegram_id, "session_start", {"command": "start"})
    update_user_activity(telegram_id)

    # In groups, /start acts as a setup guide instead of opening the private main menu.
    if chat and chat.type in ("group", "supergroup"):
        lang = normalize_language_code(getattr(user, "language_code", None))
        ui = get_ui_locale(lang)
        await update.message.reply_text(ui["group_welcome_on_join"])
        return ConversationHandler.END

    # Check if user already registered
    existing_user = get_user(telegram_id)

    if existing_user:
        # Existing user - get language and show main menu
        from handlers.admin import is_admin
        
        lang = get_user_language(telegram_id)
        # For unsupported languages, trigger async AI translation (caches for future use)
        if lang not in ("zh", "en", "ja", "ko"):
            try:
                from services.language_service import get_ui_strings
                ui = await get_ui_strings(telegram_id)
            except Exception:
                ui = get_ui_locale(lang, telegram_id=telegram_id)
        else:
            ui = get_ui_locale(lang, telegram_id=telegram_id)
        
        keyboard = [
            [InlineKeyboardButton(ui["menu_view_digest"], callback_data="view_digest")],
            [
                InlineKeyboardButton(ui["menu_preferences"], callback_data="update_preferences"),
                InlineKeyboardButton(ui["menu_sources"], callback_data="manage_sources"),
            ],
            [InlineKeyboardButton(ui["menu_stats"], callback_data="view_stats")],
        ]
        try:
            from config import FEATURE_PAYMENT
            if FEATURE_PAYMENT:
                keyboard.append([InlineKeyboardButton(ui["menu_subscribe"], callback_data="payment_plans")])
        except Exception:
            pass
        if is_admin(user.id):
            keyboard.append([InlineKeyboardButton(ui["menu_admin"], callback_data="admin_panel")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"{ui['welcome_back'].format(name=user.first_name)}\n"
            f"{ui['divider']}\n\n"
            f"{ui['welcome_back_desc']}\n\n"
            f"{ui['welcome_choose']}",
            reply_markup=reply_markup
        )
        return ConversationHandler.END

    else:
        # New user - get language from Telegram and start onboarding
        # Clear only onboarding-related state from previous incomplete registration
        # (Don't use .clear() to avoid affecting other potential features)
        context.user_data["conversation_history"] = []
        context.user_data["current_round"] = 1
        
        # Detect and store user's language from Telegram (initial; may be overridden by reply language later)
        lang = normalize_language_code(user.language_code)
        context.user_data["language"] = lang
        context.user_data["language_native"] = get_language_native_name(lang)
        logger.info("[onboarding_lang] /start new user telegram_id=%s language_code=%s -> lang=%s", user.id, getattr(user, "language_code", None), lang)
        ui = get_ui_locale(lang)

        # Show welcome message + typing indicator
        await update.message.reply_text(
            f"{ui['onboarding_title']}\n"
            f"{ui['divider']}\n\n"
            f"{ui['onboarding_welcome']}\n\n"
            f"{ui['onboarding_intro']}\n\n"
            f"⏳ <i>{ui['onboarding_thinking']}</i>",
            parse_mode="HTML"
        )

        await update.message.chat.send_action(ChatAction.TYPING)

        # Load prompt from file with user's language
        user_language = context.user_data["language_native"]
        system_instruction = get_prompt("onboarding_round1.txt", user_language=user_language)

        try:
            ai_response = await call_gemini(
                prompt="Start the conversation by asking the user about their Web3 interests.",
                system_instruction=system_instruction,
                temperature=0.9
            )
        except Exception as e:
            logger.error(f"Onboarding round 1 failed: {e}")
            keyboard = [
                [InlineKeyboardButton(ui["btn_retry"], callback_data="start_onboarding")],
            ]
            await update.message.reply_text(
                ui["error_occurred"],
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return ConversationHandler.END

        step_text = ui["onboarding_step"].format(current=1, total=3)
        await update.message.reply_text(
            f"{step_text}\n\n{ai_response}"
        )

        return ONBOARDING_ROUND_1


@whitelist_required
async def start_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Begin the AI-driven preference collection (3 rounds)."""
    from utils.conv_manager import activate_conv
    activate_conv(context, "onboarding")

    query = update.callback_query
    
    # Get language from context (set during start) or default
    lang = context.user_data.get("language", "zh")
    user_language = context.user_data.get("language_native", get_language_native_name(lang))
    ui = get_ui_locale(lang)

    # Anti-debounce: Prevent duplicate clicks
    if context.user_data.get("processing"):
        await safe_answer_callback_query(query, ui["onboarding_thinking"], show_alert=True)
        return ONBOARDING_ROUND_1

    context.user_data["processing"] = True
    await safe_answer_callback_query(query)

    # Initialize conversation history
    context.user_data["conversation_history"] = []
    context.user_data["current_round"] = 1

    # Show typing indicator while AI generates response
    await query.message.chat.send_action(ChatAction.TYPING)

    # Load prompt from file with user's language
    system_instruction = get_prompt("onboarding_round1.txt", user_language=user_language)

    try:
        ai_response = await call_gemini(
            prompt="Start the conversation by asking the user about their Web3 interests.",
            system_instruction=system_instruction,
            temperature=0.9
        )
    except Exception as e:
        logger.error(f"Onboarding round 1 failed: {e}")
        context.user_data.pop("processing", None)  # Release lock on error
        keyboard = [
            [InlineKeyboardButton(ui["retry"], callback_data="start_onboarding")],
            [InlineKeyboardButton(ui["back_to_main"], callback_data="back_to_start")],
        ]
        await query.edit_message_text(
            ui["ai_unavailable"],
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END

    context.user_data.pop("processing", None)  # Release lock on success
    step_text = ui["onboarding_step"].format(current=1, total=3)
    await query.edit_message_text(
        f"{step_text} {ui['onboarding_set_prefs']}\n\n{ai_response}"
    )

    return ONBOARDING_ROUND_1


async def handle_round_1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle user response in round 1, proceed to round 2."""
    from utils.conv_manager import is_active_conv
    if not is_active_conv(context, "onboarding"):
        return ConversationHandler.END

    user_message = update.message.text
    # Dynamically adjust language based on user's reply
    lang_before = context.user_data.get("language", "zh")
    detected_lang = detect_language_from_text(user_message)
    supported = bool(detected_lang and is_supported_language(detected_lang))
    if supported:
        context.user_data["language"] = detected_lang
        context.user_data["language_native"] = get_language_native_name(detected_lang)
    lang = context.user_data.get("language", "zh")
    logger.info(
        "[onboarding_lang] round=1 user_msg=%r lang_before=%s detected=%s supported=%s lang_after=%s",
        (user_message or "")[:60], lang_before, detected_lang, supported, lang
    )
    user_language = context.user_data.get("language_native", get_language_native_name(lang))
    ui = get_ui_locale(lang)
    
    context.user_data["conversation_history"].append({
        "round": 1,
        "user_input": user_message
    })
    context.user_data["current_round"] = 2

    # Show typing indicator while AI generates response
    await update.message.chat.send_action(ChatAction.TYPING)

    # Load prompt from file with user input and language
    system_instruction = get_prompt("onboarding_round2.txt", user_input=user_message, user_language=user_language)

    try:
        ai_response = await call_gemini(
            prompt=f"The user said: '{user_message}'. Ask follow-up questions about content preferences.",
            system_instruction=system_instruction,
            temperature=0.9
        )
    except Exception as e:
        logger.error(f"Onboarding round 2 failed: {e}")
        keyboard = [
            [InlineKeyboardButton(ui["retry"], callback_data="start_onboarding")],
            [InlineKeyboardButton(ui["back_to_main"], callback_data="back_to_start")],
        ]
        await update.message.reply_text(
            ui["ai_unavailable"],
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END

    step_text = ui["onboarding_step"].format(current=2, total=3)
    await update.message.reply_text(
        f"{step_text} {ui['onboarding_content_prefs']}\n\n{ai_response}"
    )

    return ONBOARDING_ROUND_2


async def handle_round_2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle user response in round 2, proceed to round 3 (confirmation)."""
    from utils.conv_manager import is_active_conv
    if not is_active_conv(context, "onboarding"):
        return ConversationHandler.END

    # Fix4: Anti-debounce — prevent duplicate submissions
    if context.user_data.get("processing_round2"):
        return ONBOARDING_ROUND_2
    context.user_data["processing_round2"] = True

    user_message = update.message.text
    # Dynamically adjust language based on user's reply
    lang_before = context.user_data.get("language", "zh")
    detected_lang = detect_language_from_text(user_message)
    supported = bool(detected_lang and is_supported_language(detected_lang))
    if supported:
        context.user_data["language"] = detected_lang
        context.user_data["language_native"] = get_language_native_name(detected_lang)
    lang = context.user_data.get("language", "zh")
    logger.info(
        "[onboarding_lang] round=2 user_msg=%r lang_before=%s detected=%s supported=%s lang_after=%s",
        (user_message or "")[:60], lang_before, detected_lang, supported, lang
    )
    user_language = context.user_data.get("language_native", get_language_native_name(lang))
    ui = get_ui_locale(lang)
    
    context.user_data["conversation_history"].append({
        "round": 2,
        "user_input": user_message
    })
    context.user_data["current_round"] = 3

    # Show progress message
    progress_msg = await update.message.reply_text(
        f"<i>{ui['generating_profile']}</i>",
        parse_mode="HTML"
    )

    # Show typing indicator while AI generates response
    await update.message.chat.send_action(ChatAction.TYPING)

    # Build conversation context
    history = context.user_data["conversation_history"]
    round_1 = history[0]["user_input"]
    round_2 = user_message

    # Load prompt from file with language
    system_instruction = get_prompt("onboarding_round3.txt", round_1=round_1, round_2=round_2, user_language=user_language)

    try:
        ai_response = await call_gemini(
            prompt=f"Summarize preferences: Round 1: '{round_1}', Round 2: '{round_2}'",
            system_instruction=system_instruction,
            temperature=0.7
        )
    except Exception as e:
        logger.error(f"Onboarding round 3 failed: {e}")
        context.user_data.pop("processing_round2", None)
        # Fix1: Clean up progress message on error
        try:
            await progress_msg.delete()
        except Exception:
            pass
        keyboard = [
            [InlineKeyboardButton(ui["retry"], callback_data="retry_round_2")],
            [InlineKeyboardButton(ui["back_to_main"], callback_data="back_to_start")],
        ]
        await update.message.reply_text(
            ui["ai_unavailable"],
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END

    # Store the generated profile summary
    context.user_data["profile_summary"] = ai_response
    context.user_data["_profile_adjusted"] = False  # Track if user has used their one adjustment

    # Fix1: Delete progress message now that profile is ready
    try:
        await progress_msg.delete()
    except Exception:
        pass  # Ignore if already deleted or permission issue

    # Add confirmation buttons with one-time adjust option
    keyboard = [
        [InlineKeyboardButton(ui["btn_confirm"], callback_data="confirm_profile")],
        [InlineKeyboardButton(
            ui.get("btn_adjust_profile", "✏️ 调整画像"),
            callback_data="adjust_profile"
        )],
        [InlineKeyboardButton(ui["btn_restart"], callback_data="start_onboarding")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    step_text = ui["onboarding_step"].format(current=3, total=3)

    # Fix2: Truncate AI response if too long for Telegram (4096 char limit)
    confirm_prefix = f"{step_text} {ui['onboarding_confirm_prefs']}\n\n"
    max_response_len = 4000 - len(confirm_prefix)
    if len(ai_response) > max_response_len:
        ai_response = ai_response[:max_response_len] + "..."
        context.user_data["profile_summary"] = ai_response  # Update stored version too

    # Fix2: Wrap in try-except to prevent silent failure
    try:
        await update.message.reply_text(
            f"{confirm_prefix}{ai_response}",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Failed to send profile confirmation: {e}")
        # Fallback: try sending a shorter version
        try:
            short_response = ai_response[:1000] + "..." if len(ai_response) > 1000 else ai_response
            await update.message.reply_text(
                f"{confirm_prefix}{short_response}",
                reply_markup=reply_markup
            )
        except Exception as e2:
            logger.error(f"Fallback profile confirmation also failed: {e2}")
            context.user_data.pop("processing_round2", None)
            keyboard_err = [
                [InlineKeyboardButton(ui["retry"], callback_data="retry_round_2")],
                [InlineKeyboardButton(ui["back_to_main"], callback_data="back_to_start")],
            ]
            await update.message.reply_text(
                ui.get("error_occurred", "An error occurred. Please try again."),
                reply_markup=InlineKeyboardMarkup(keyboard_err)
            )
            return ConversationHandler.END

    context.user_data.pop("processing_round2", None)
    return CONFIRM_PROFILE


async def retry_round_2_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Retry round 2 with the same round 1 data."""
    lang = context.user_data.get("language", "zh")
    user_language = context.user_data.get("language_native", get_language_native_name(lang))
    ui = get_ui_locale(lang)
    
    query = update.callback_query
    await query.answer(ui["retrying"])

    # Get round 1 data from conversation_history
    conversation_history = context.user_data.get("conversation_history", [])
    round_1_entries = [h for h in conversation_history if h.get("round") == 1]
    round_1 = round_1_entries[-1]["user_input"] if round_1_entries else None
    if not round_1:
        await query.edit_message_text(
            ui["retry_failed"],
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(ui["btn_restart"], callback_data="start_onboarding")
            ]])
        )
        return ConversationHandler.END

    # Load prompt from file with language
    system_instruction = get_prompt("onboarding_round2.txt", user_input=round_1, user_language=user_language)

    try:
        ai_response = await call_gemini(
            prompt=f"The user said: '{round_1}'. Ask follow-up questions about content preferences.",
            system_instruction=system_instruction,
            temperature=0.9
        )

        step_text = ui["onboarding_step"].format(current=2, total=3)
        await query.edit_message_text(
            f"{step_text} {ui['onboarding_content_prefs']}\n\n{ai_response}"
        )

        return ONBOARDING_ROUND_2

    except Exception as e:
        logger.error(f"Retry round 2 failed: {e}")
        keyboard = [
            [InlineKeyboardButton(ui["retry"], callback_data="retry_round_2")],
            [InlineKeyboardButton(ui["back_to_main"], callback_data="back_to_start")],
        ]
        await query.edit_message_text(
            ui["ai_unavailable"],
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END


async def adjust_profile_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show prompt for user to describe profile adjustments. One-time only."""
    query = update.callback_query
    lang = context.user_data.get("language", "zh")
    ui = get_ui_locale(lang)
    await safe_answer_callback_query(query)

    # Guard: only allow one adjustment
    if context.user_data.get("_profile_adjusted"):
        await query.edit_message_text(
            f"{context.user_data.get('profile_summary', '')}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(ui["btn_confirm"], callback_data="confirm_profile")],
                [InlineKeyboardButton(ui["btn_restart"], callback_data="start_onboarding")],
            ])
        )
        return CONFIRM_PROFILE

    profile_summary = context.user_data.get("profile_summary", "")

    adjust_hint_default = '例如：「去掉 NFT 相关的，多加一些 DeFi 协议的内容」\n直接在聊天窗口输入你的修改意见：'
    await query.edit_message_text(
        f"{ui.get('adjust_profile_prompt', '✏️ 请告诉我你想怎么调整画像：')}\n\n"
        f"{ui.get('adjust_profile_current', '当前画像：')}\n{profile_summary}\n\n"
        f"{ui.get('adjust_profile_hint', adjust_hint_default)}"
    )

    return ONBOARDING_ROUND_3  # Reuse round 3 state for adjustment text input


async def handle_profile_adjustment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle user's profile adjustment request, regenerate profile."""
    from utils.conv_manager import is_active_conv
    if not is_active_conv(context, "onboarding"):
        return ConversationHandler.END

    lang = context.user_data.get("language", "zh")
    user_language = context.user_data.get("language_native", get_language_native_name(lang))
    ui = get_ui_locale(lang)

    adjustment_text = update.message.text
    current_profile = context.user_data.get("profile_summary", "")
    history = context.user_data.get("conversation_history", [])

    # Show typing indicator
    await update.message.chat.send_action(ChatAction.TYPING)

    # Build context for AI
    round_1 = history[0]["user_input"] if len(history) > 0 else ""
    round_2 = history[1]["user_input"] if len(history) > 1 else ""

    system_instruction = get_prompt(
        "onboarding_round3.txt",
        round_1=round_1,
        round_2=round_2,
        user_language=user_language
    )

    try:
        ai_response = await call_gemini(
            prompt=(
                f"Previous profile: '{current_profile}'\n"
                f"User adjustment request: '{adjustment_text}'\n"
                f"Original conversation - Round 1: '{round_1}', Round 2: '{round_2}'\n"
                f"Please regenerate the profile incorporating the user's adjustments."
            ),
            system_instruction=system_instruction,
            temperature=0.7
        )
    except Exception as e:
        logger.error(f"Profile adjustment failed: {e}")
        # On error, still allow the one adjustment attempt
        keyboard = [
            [InlineKeyboardButton(ui["btn_confirm"], callback_data="confirm_profile")],
            [InlineKeyboardButton(
                ui.get("btn_adjust_profile", "✏️ 调整画像"),
                callback_data="adjust_profile"
            )],
            [InlineKeyboardButton(ui["btn_restart"], callback_data="start_onboarding")],
        ]
        await update.message.reply_text(
            ui["ai_unavailable"],
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return CONFIRM_PROFILE

    # Update stored profile
    context.user_data["profile_summary"] = ai_response
    context.user_data["_profile_adjusted"] = True  # Mark adjustment used

    # After adjustment: only Confirm or Restart (no more adjust)
    keyboard = [
        [InlineKeyboardButton(ui["btn_confirm"], callback_data="confirm_profile")],
        [InlineKeyboardButton(ui["btn_restart"], callback_data="start_onboarding")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    step_text = ui["onboarding_step"].format(current=3, total=3)
    await update.message.reply_text(
        f"{step_text} {ui.get('profile_adjusted', '画像已更新 ✨')}\n\n{ai_response}",
        reply_markup=reply_markup
    )

    return CONFIRM_PROFILE


async def confirm_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save confirmed user profile and complete registration."""
    query = update.callback_query
    
    # Get language settings from context
    lang = context.user_data.get("language", "zh")
    ui = get_ui_locale(lang)
    user_language = context.user_data.get("language_native", get_language_native_name(lang))

    # Anti-debounce: Prevent duplicate clicks
    if context.user_data.get("processing"):
        await safe_answer_callback_query(query, ui.get("processing_wait", "Processing..."), show_alert=True)
        return CONFIRM_PROFILE

    context.user_data["processing"] = True
    await safe_answer_callback_query(query)

    user = update.effective_user
    telegram_id = str(user.id)

    # T8 Fix: Use send_message instead of edit_message_text to preserve
    # the profile summary message (prevents overwriting the preference summary)
    await context.bot.send_message(
        chat_id=query.message.chat.id,
        text=f"<i>{ui.get('saving_prefs', '⏳ Saving preferences...')}</i>",
        parse_mode="HTML"
    )

    # Create user record with language (save user_id to avoid file lock race condition)
    created_user = create_user(
        telegram_id=telegram_id,
        username=user.username,
        first_name=user.first_name,
        language=lang  # Pass language to storage
    )
    user_id = created_user['id']

    # Save profile (natural language description)
    profile_summary = context.user_data.get("profile_summary", "")
    history = context.user_data.get("conversation_history", [])

    # Load prompt from file with language and conversation summary
    system_instruction = get_prompt(
        "onboarding_confirm.txt",
        user_language=user_language,
        conversation_summary=f"History: {history}. Summary: {profile_summary}"
    )

    try:
        full_profile = await call_gemini(
            prompt=f"Create profile from: {history}. Summary: {profile_summary}",
            system_instruction=system_instruction,
            temperature=0.5
        )
    except Exception as e:
        logger.error(f"Failed to generate profile: {e}")
        context.user_data.pop("processing", None)  # Release lock on error
        keyboard = [
            [InlineKeyboardButton(ui.get("retry", "Retry"), callback_data="confirm_profile")],
            [InlineKeyboardButton(ui.get("back_to_main", "Back to Main"), callback_data="back_to_start")],
        ]
        # Fix3: Use send_message instead of edit_message_text to preserve
        # the profile summary message (don't overwrite user's profile preview)
        await context.bot.send_message(
            chat_id=query.message.chat.id,
            text=ui.get("error_occurred", "An error occurred. Please try again later."),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return CONFIRM_PROFILE

    # Pass user_id to avoid re-querying users.json (Windows file lock race condition)
    save_user_profile(telegram_id, full_profile, user_id=user_id)

    # Clear conversation data
    context.user_data.clear()

    # Show source choice: default sources (recommended) / custom sources
    # Simplified flow: encourage users to start with defaults, customize later
    from config import DEFAULT_USER_SOURCES

    default_sources_preview = ", ".join(list(DEFAULT_USER_SOURCES.get("websites", {}).keys())[:3])

    keyboard = [
        [InlineKeyboardButton(ui.get("source_choice_default", "🚀 Start Now (Recommended)"), callback_data="source_default_no_push")],
        [InlineKeyboardButton(ui.get("source_choice_custom", "🎯 Add My Own Sources"), callback_data="source_custom_no_push")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # T8 Fix: Also use send_message here to keep profile summary visible
    await context.bot.send_message(
        chat_id=query.message.chat.id,
        text=f"{ui.get('prefs_saved_title', '✅ Preferences Saved!')}\n\n"
             f"{ui.get('prefs_saved_desc', 'Your interest profile has been recorded.')}\n\n"
             f"{ui.get('push_time_title', '📅 Push Schedule')}\n"
             f"{ui.get('push_time_desc', 'Daily at 9:00 AM')}\n\n"
             f"{ui.get('push_daily_reason', '💡 Why once daily?')}\n"
             f"{ui.get('push_daily_explain', 'AI summarizes 24h content to avoid overload.')}\n\n"
             f"{ui['divider']}\n\n"
             f"📰 <b>{ui.get('sources_title', 'Sources')}</b>\n\n"
             f"📌 {default_sources_preview}\n\n"
             f"{ui.get('push_now_desc', 'After selecting sources, you can start immediately.')}",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

    return SOURCE_CHOICE


async def learn_more(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show more information about the service."""
    query = update.callback_query
    await safe_answer_callback_query(query)
    
    user = update.effective_user
    telegram_id = str(user.id) if user else "0"
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)

    keyboard = [
        [InlineKeyboardButton(ui.get("btn_start", "Start"), callback_data="start_onboarding")],
        [InlineKeyboardButton(ui.get("back", "Back"), callback_data="back_to_start")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"{ui.get('learn_more_title', 'Learn More')}\n"
        f"{ui['divider']}\n\n"
        f"{ui.get('learn_more_what', 'What we do:')}\n"
        f"{ui.get('learn_more_scan', '• Scan 50+ sources daily')}\n"
        f"{ui.get('learn_more_filter', '• Filter noise, curate content')}\n"
        f"{ui.get('learn_more_push', '• Push what truly matters')}\n\n"
        f"{ui.get('learn_more_time_save', 'Save ~2 hours daily')}",
        reply_markup=reply_markup
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation."""
    context.user_data.clear()
    
    user = update.effective_user
    telegram_id = str(user.id) if user else "0"
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)

    keyboard = [
        [InlineKeyboardButton(ui.get("btn_start", "Start"), callback_data="start_onboarding")],
        [InlineKeyboardButton(ui.get("btn_learn_more", "Learn More"), callback_data="learn_more")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"{ui.get('cancelled', 'Cancelled')}\n\n"
        f"{ui.get('can_restart', 'You can start again anytime.')}",
        reply_markup=reply_markup
    )
    return ConversationHandler.END


async def back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Return to the main start menu."""
    query = update.callback_query
    await safe_answer_callback_query(query)

    user = update.effective_user
    telegram_id = str(user.id)
    existing_user = get_user(telegram_id)
    
    # Get user's language setting
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang, telegram_id=telegram_id)

    if existing_user:
        from handlers.admin import is_admin
        
        # For unsupported languages, use cached or async-translated UI
        if lang not in ("zh", "en", "ja", "ko"):
            try:
                from services.language_service import get_ui_strings
                ui = await get_ui_strings(telegram_id)
            except Exception:
                pass  # ui already set above

        keyboard = [
            [InlineKeyboardButton(ui["menu_view_digest"], callback_data="view_digest")],
            [
                InlineKeyboardButton(ui["menu_preferences"], callback_data="update_preferences"),
                InlineKeyboardButton(ui["menu_sources"], callback_data="manage_sources"),
            ],
            [InlineKeyboardButton(ui["menu_stats"], callback_data="view_stats")],
        ]
        try:
            from config import FEATURE_PAYMENT
            if FEATURE_PAYMENT:
                keyboard.append([InlineKeyboardButton(ui["menu_subscribe"], callback_data="payment_plans")])
        except Exception:
            pass
        if is_admin(user.id):
            keyboard.append([InlineKeyboardButton(ui["menu_admin"], callback_data="admin_panel")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"{ui['welcome_back'].format(name=user.first_name)}\n"
            f"{ui['divider']}\n\n"
            f"{ui['welcome_back_desc']}\n\n"
            f"{ui['welcome_choose']}",
            reply_markup=reply_markup
        )
    else:
        keyboard = [
            [InlineKeyboardButton(ui["start_setup"], callback_data="start_onboarding")],
            [InlineKeyboardButton(ui["learn_more"], callback_data="learn_more")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"{ui['onboarding_title']}\n"
            f"{ui['divider']}\n\n"
            f"{ui['onboarding_welcome']}\n\n"
            f"{ui['learn_more_what']}\n"
            f"  {ui['learn_more_scan']}\n"
            f"  {ui['learn_more_filter']}\n"
            f"  {ui['learn_more_push']}\n\n"
            f"{ui['learn_more_time_save']}",
            reply_markup=reply_markup
        )


async def view_digest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show today's digest or a message if not available."""
    query = update.callback_query
    await safe_answer_callback_query(query)

    from utils.json_storage import get_user_daily_stats, get_user_profile
    from services.report_generator import prepare_digest_messages, detect_user_language, get_ai_summary
    from handlers.feedback import create_item_feedback_keyboard, get_item_feedback_status
    from config import PUSH_HOUR, PUSH_MINUTE
    from datetime import datetime

    telegram_id = str(query.from_user.id)
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)
    today = datetime.now().strftime("%Y-%m-%d")

    # Get today's stats
    stats = get_user_daily_stats(telegram_id, today)

    if not stats or not stats.get("filtered_items"):
        # No digest available yet
        keyboard = [
            [InlineKeyboardButton(ui.get("back", "Back"), callback_data="back_to_start")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        push_time_msg = ui.get('digest_push_time', '⏰ Push time: {time}').format(time=f'{PUSH_HOUR:02d}:{PUSH_MINUTE:02d}')
        await query.edit_message_text(
            f"{ui.get('digest_today', 'Today Digest')}\n"
            f"{ui['divider']}\n\n"
            f"{push_time_msg}\n\n"
            f"{ui.get('digest_auto_push', 'Your digest will be pushed automatically.')}\n\n"
            f"{ui.get('digest_hint', '💡 Tip: Use /settings to customize preferences.')}",
            reply_markup=reply_markup
        )
        return

    # Get filtered items and generate messages
    filtered_items = stats["filtered_items"]
    profile = get_user_profile(telegram_id) or ""
    user_lang = detect_user_language(profile)

    # Generate AI summary if not already in stats
    ai_summary = stats.get("ai_summary", "")
    if not ai_summary and filtered_items:
        from services.content_filter import get_ai_summary
        ai_summary = await get_ai_summary(filtered_items, profile)
    
    # === Final output translation (all at once) ===
    from services.content_filter import translate_text, translate_content, _extract_user_language
    target_language = _extract_user_language(profile)
    if target_language != "English":
        # Translate both items and summary before output
        filtered_items = await translate_content(filtered_items, target_language)
        ai_summary = await translate_text(ai_summary, target_language)

    # Prepare messages
    header, item_messages = prepare_digest_messages(
        filtered_items=filtered_items,
        ai_summary=ai_summary,
        sources_count=stats.get("sources_monitored", 0),
        raw_count=stats.get("raw_items_scanned", 0),
        lang=user_lang
    )

    # Send header
    await query.edit_message_text(
        f"[回顾] {header}",
        parse_mode="HTML",
        disable_web_page_preview=True
    )

    # Send each item with feedback buttons
    for item_msg, item_id, item_url in item_messages:
        # Check feedback status
        feedback_status = get_item_feedback_status(item_id)

        # Section headers don't get feedback buttons
        if item_id.startswith("section_"):
            await send_message_safe(
                context,
                chat_id=query.from_user.id,
                text=item_msg,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        else:
            # Create feedback keyboard based on status
            if feedback_status:
                # Already has feedback, show status
                status_text = "📖 已查看" if feedback_status in ("like", "click") else "👎 已标记"
                item_keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(status_text, callback_data=f"noop")]
                ])
            else:
                # No feedback yet, show buttons with item URL
                item_keyboard = create_item_feedback_keyboard(item_id, item_url=item_url)

            await send_message_safe(
                context,
                chat_id=query.from_user.id,
                text=item_msg,
                reply_markup=item_keyboard,
                parse_mode="HTML",
                disable_web_page_preview=True
            )


async def update_preferences(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Redirect to settings for preference update."""
    query = update.callback_query
    await safe_answer_callback_query(query)
    
    telegram_id = str(query.from_user.id)
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)

    keyboard = [
        [
            InlineKeyboardButton(ui["settings_view"], callback_data="settings_view"),
            InlineKeyboardButton(ui["settings_update"], callback_data="settings_update"),
        ],
        [InlineKeyboardButton(ui["back"], callback_data="back_to_start")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"{ui['settings_title']}\n"
        f"{ui['divider']}\n\n"
        f"{ui['settings_desc']}",
        reply_markup=reply_markup
    )


async def manage_sources(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Redirect to sources management."""
    query = update.callback_query
    await safe_answer_callback_query(query)
    
    telegram_id = str(query.from_user.id)
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)

    keyboard = [
        [
            InlineKeyboardButton(ui["sources_twitter"], callback_data="sources_twitter"),
            InlineKeyboardButton(ui["sources_websites"], callback_data="sources_websites"),
        ],
        [InlineKeyboardButton(ui["sources_suggest"], callback_data="sources_suggest")],
        [InlineKeyboardButton(ui["back"], callback_data="back_to_start")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"{ui['sources_title']}\n"
        f"{ui['divider']}\n\n"
        f"{ui['sources_choose_category']}",
        reply_markup=reply_markup
    )


async def view_sample(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show a sample digest preview."""
    query = update.callback_query
    await safe_answer_callback_query(query)

    telegram_id = str(query.from_user.id) if query.from_user else "0"
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)

    keyboard = [
        [InlineKeyboardButton(ui["back"], callback_data="back_to_start")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    from datetime import datetime
    date_str = datetime.now().strftime("%Y-%m-%d")

    sample_text = f"""示例预览
{date_str}
{'━' * 28}

以下是你每日简报的样式预览。

今日必看

1. 重大协议升级公告
   关键进展的简要摘要...
   [The Block]

2. 链上巨鲸活动监测
   DeFi 领域的重大资金流动...
   [lookonchain]

{'─' * 28}

DeFi (3)
  • DeFi 相关新闻 [来源]
  • 另一条相关更新 [来源]

{'─' * 28}

统计
  信息源       50+
  扫描条数     200+
  精选条数     15
  节省时间     约 2 小时

{'━' * 28}

你的首次简报将于注册后约 24 小时内推送。"""

    await query.edit_message_text(
        sample_text,
        reply_markup=reply_markup
    )


async def view_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user statistics via callback."""
    query = update.callback_query
    await safe_answer_callback_query(query)

    from services.profile_updater import analyze_feedback_trends

    user = update.effective_user
    telegram_id = str(user.id)
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)

    def _translate_trend(trend: str) -> str:
        trend_map = {
            "improving": ui.get("stats_trend_improving", "改善中"),
            "declining": ui.get("stats_trend_declining", "下降中"),
            "stable": ui.get("stats_trend_stable", "稳定"),
            "no_data": ui.get("stats_trend_no_data", "暂无数据"),
        }
        return trend_map.get(trend, trend.replace('_', ' '))

    db_user = get_user(telegram_id)
    if not db_user:
        keyboard = [[InlineKeyboardButton(ui["back"], callback_data="back_to_start")]]
        await query.edit_message_text(
            ui["not_registered"],
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    trends = await analyze_feedback_trends(telegram_id, days=30)
    
    created_date = db_user.get('created', '----')[:10]
    issues_line = f"  {ui.get('stats_main_issues', 'Main issues')}         {', '.join(trends['common_issues'][:2])}" if trends['common_issues'] else ""
    registered_msg = ui.get('stats_registered', 'Registered: {date}').format(date=created_date)

    stats_text = f"""{ui.get('stats_your_stats', 'Your Statistics')}
{ui['divider']}

{registered_msg}

{ui.get('stats_last_30_days', '最近 30 天')}
  {ui.get('stats_feedback_count', '反馈次数')}         {trends['total_feedbacks']}
  {ui.get('stats_positive', '正面评价')}         {trends['positive_count']}
  {ui.get('stats_negative', '负面评价')}         {trends['negative_count']}
  {ui.get('stats_satisfaction', '满意度')}           {trends['positive_rate']:.0%}
  {ui.get('stats_trend', '趋势')}             {_translate_trend(trends['trend'])}
{issues_line}

{ui['divider']}

{ui['stats_settings_hint']}"""

    keyboard = [
        [
            InlineKeyboardButton(ui["settings_update"], callback_data="settings_update"),
            InlineKeyboardButton(ui["back"], callback_data="back_to_start"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(stats_text, reply_markup=reply_markup)


async def trigger_first_digest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Trigger first digest immediately for new users."""
    query = update.callback_query
    await safe_answer_callback_query(query)

    telegram_id = str(query.from_user.id)

    # Show progress message - describe actual business flow
    await query.edit_message_text(
        "正在生成你的首份简报...\n\n"
        "🔍 第一步：从信息源抓取最新内容\n"
        "🤖 第二步：AI 智能筛选去重\n"
        "📊 第三步：生成个性化简报\n\n"
        "⏳ 正在处理，请稍候..."
    )

    try:
        from datetime import datetime
        from services.digest_processor import process_single_user

        today = datetime.now().strftime("%Y-%m-%d")
        user = get_user(telegram_id)

        if not user:
            await query.edit_message_text(
                "用户信息未找到，请使用 /start 重新开始。"
            )
            return

        # Trigger digest generation with timeout protection
        try:
            result = await asyncio.wait_for(
                process_single_user(context, user, today),
                timeout=DIGEST_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.error(f"Digest generation timeout for {telegram_id} (>{DIGEST_TIMEOUT}s)")
            keyboard = [
                [InlineKeyboardButton("返回主菜单", callback_data="back_to_start")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"⏱️ 生成超时\n\n"
                f"服务器繁忙，请等待下次自动推送（约 24 小时后）。",
                reply_markup=reply_markup
            )
            return

        if result.get("status") == "success":
            items_count = result.get("items_sent", 0)
            # Success - digest messages already sent by process_single_user
            # Just send a final summary message
            keyboard = [[InlineKeyboardButton("返回主菜单", callback_data="back_to_start")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await send_message_safe(
                context,
                chat_id=int(telegram_id),
                text=f"✅ 首份简报推送完成！\n\n"
                     f"已为你精选 {items_count} 条内容。\n\n"
                     f"💡 提示：\n"
                     f"  • 每条内容都有反馈按钮（👍/👎）\n"
                     f"  • 你的反馈会让简报更懂你\n"
                     f"  • 下次推送：约 24 小时后\n\n"
                     f"使用 /help 查看更多功能。",
                reply_markup=reply_markup
            )
        else:
            # Error occurred
            error_msg = result.get("error", "未知错误")
            keyboard = [
                [InlineKeyboardButton("返回主菜单", callback_data="back_to_start")],
                [InlineKeyboardButton("查看帮助", callback_data="show_help")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                f"推送失败\n\n"
                f"原因：{error_msg[:100]}\n\n"
                f"请等待下次自动推送（约 24 小时后）。",
                reply_markup=reply_markup
            )

    except Exception as e:
        logger.error(f"First digest trigger failed for {telegram_id}: {e}")
        keyboard = [[InlineKeyboardButton("返回主菜单", callback_data="back_to_start")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "推送失败，请等待下次自动推送（约 24 小时后）。",
            reply_markup=reply_markup
        )


async def skip_first_digest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Skip first digest and show main menu."""
    query = update.callback_query
    await safe_answer_callback_query(query)

    user = update.effective_user
    telegram_id = str(user.id)
    from utils.json_storage import set_onboarding_paid_redeem_available
    set_onboarding_paid_redeem_available(telegram_id)

    keyboard = [
        [
            InlineKeyboardButton("偏好设置", callback_data="update_preferences"),
            InlineKeyboardButton("信息源", callback_data="manage_sources"),
        ],
        [InlineKeyboardButton("查看统计", callback_data="view_stats")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"好的，{user.first_name}！\n\n"
        f"你的首份简报将在约 24 小时后推送。\n\n"
        f"在此之前，你可以：\n"
        f"  • 调整偏好设置\n"
        f"  • 添加更多信息源\n\n"
        f"使用 /help 查看所有功能。",
        reply_markup=reply_markup
    )

    return ConversationHandler.END


async def add_custom_sources(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Enter quick add sources mode."""
    query = update.callback_query
    await safe_answer_callback_query(query)

    # Initialize adding counters
    context.user_data["added_sources_count"] = 0
    context.user_data["added_sources_list"] = []

    keyboard = [
        [InlineKeyboardButton("✅ 完成添加，开始推送", callback_data="finish_sources")],
        [InlineKeyboardButton("📡 使用默认源", callback_data="finish_sources_default")],
        [InlineKeyboardButton("⏰ 稍后再说", callback_data="source_skip")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "🎯 添加你关注的信息源\n\n"
        "只支持两种方式：推特 List 或 网站。\n\n"
        "📱 推特 List：粘贴链接（如 rss.app 生成）\n"
        "📰 网站：https://example.com/rss 或 域名\n\n"
        "💡 可连续发送多个，完成后点击按钮：",
        reply_markup=reply_markup
    )

    return ADDING_SOURCES


async def handle_add_source(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle user adding a source."""
    from utils.conv_manager import is_active_conv
    if not is_active_conv(context, "onboarding"):
        return ConversationHandler.END

    from services.rss_fetcher import validate_url, validate_rss_url
    from utils.json_storage import get_user_sources, save_user_sources
    from urllib.parse import urlparse

    text = update.message.text.strip()
    telegram_id = str(update.effective_user.id)

    # Get current sources
    user_sources = get_user_sources(telegram_id)

    success = False
    added_name = ""

    if text.startswith("http"):
        # Try as Twitter RSS first (rss.app etc.)
        rss_validation = await validate_rss_url(text)
        if rss_validation["valid"]:
            feed_title = rss_validation.get("title", "Twitter List RSS")
            if feed_title not in user_sources.get("twitter", {}):
                user_sources.setdefault("twitter", {})[feed_title] = text
                added_name = f"Twitter: {feed_title}"
                success = True
        if not success:
            # Website RSS URL
            validation = await validate_url(text)
            if validation["valid"]:
                url = validation["url"]
                parsed = urlparse(url)
                domain = parsed.netloc.replace("www.", "")
                name = domain.split(".")[0].title()
                if name not in user_sources.get("websites", {}):
                    user_sources.setdefault("websites", {})[name] = url
                    added_name = f"{name} ({domain})"
                    success = True

    if success:
        # Save
        save_user_sources(telegram_id, user_sources)

        # Update counter
        context.user_data["added_sources_count"] = context.user_data.get("added_sources_count", 0) + 1
        context.user_data.setdefault("added_sources_list", []).append(added_name)

        count = context.user_data["added_sources_count"]
        sources_list = context.user_data["added_sources_list"]

        keyboard = [
            [InlineKeyboardButton("✅ 完成添加，开始推送", callback_data="finish_sources")],
            [InlineKeyboardButton("📡 补充默认源一起推送", callback_data="finish_sources_default")],
            [InlineKeyboardButton("⏰ 稍后再说", callback_data="source_skip")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        sources_text = "\n".join([f"  • {s}" for s in sources_list])

        await update.message.reply_text(
            f"✅ 已添加：{added_name}\n\n"
            f"📊 当前已添加 {count} 个信息源：\n{sources_text}\n\n"
            f"继续发送更多，或选择：",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            f"❌ 格式错误：{text[:20]}\n\n"
            f"请使用以下格式：\n"
            f"• Twitter: @用户名\n"
            f"• 网站: https://...\n\n"
            f"📊 当前已添加 {context.user_data.get('added_sources_count', 0)} 个信息源"
        )

    return ADDING_SOURCES


async def finish_adding_sources(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Finish adding sources and trigger digest."""
    query = update.callback_query
    await safe_answer_callback_query(query)

    telegram_id = str(query.from_user.id)
    from utils.json_storage import set_onboarding_paid_redeem_available
    set_onboarding_paid_redeem_available(telegram_id)

    count = context.user_data.get("added_sources_count", 0)

    # Boundary: 0 sources
    if count == 0:
        keyboard = [
            [InlineKeyboardButton("确认使用默认源", callback_data="finish_sources_default")],
            [InlineKeyboardButton("返回继续添加", callback_data="source_custom")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "你还没有添加任何信息源。\n\n"
            "📡 将使用默认推荐源为你推送。",
            reply_markup=reply_markup
        )
        return SOURCE_CHOICE

    # Clear temp data
    context.user_data.pop("added_sources_count", None)
    context.user_data.pop("added_sources_list", None)

    # Trigger digest (using user's custom sources)
    await trigger_first_digest_internal(update, context, use_default=False)

    return ConversationHandler.END


async def finish_with_default(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Finish with user sources + default sources."""
    query = update.callback_query
    await safe_answer_callback_query(query)

    telegram_id = str(query.from_user.id)
    from utils.json_storage import get_user_sources, save_user_sources, set_onboarding_paid_redeem_available
    set_onboarding_paid_redeem_available(telegram_id)
    from config import DEFAULT_USER_SOURCES
    import asyncio

    # Merge user sources + default sources
    user_sources = get_user_sources(telegram_id)
    for category, sources in DEFAULT_USER_SOURCES.items():
        user_sources.setdefault(category, {}).update(sources)

    save_user_sources(telegram_id, user_sources)

    # Windows file lock mitigation: Brief delay to ensure file lock is released
    await asyncio.sleep(0.1)

    # Clear temp data
    context.user_data.pop("added_sources_count", None)
    context.user_data.pop("added_sources_list", None)

    # Trigger digest
    await trigger_first_digest_internal(update, context, use_default=False)

    return ConversationHandler.END


async def use_default_sources(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Use default sources and trigger digest."""
    query = update.callback_query
    await safe_answer_callback_query(query)

    # Trigger digest (using default sources)
    await trigger_first_digest_internal(update, context, use_default=True)

    return ConversationHandler.END


async def use_default_sources_no_push(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Use default sources without triggering immediate digest - wait for scheduled push."""
    query = update.callback_query
    await safe_answer_callback_query(query)

    user = update.effective_user
    telegram_id = str(user.id)
    from utils.json_storage import set_onboarding_paid_redeem_available
    set_onboarding_paid_redeem_available(telegram_id)

    keyboard = [
        [
            InlineKeyboardButton("偏好设置", callback_data="update_preferences"),
            InlineKeyboardButton("信息源", callback_data="manage_sources"),
        ],
        [InlineKeyboardButton("返回主菜单", callback_data="back_to_start")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"✅ 设置完成！\n\n"
        f"{user.first_name}，你已成功订阅默认信息源。\n\n"
        f"📅 你的首份简报将在约 <b>24 小时后</b>自动推送。\n\n"
        f"系统会持续监控信息源，为你积攒一整天的内容后集中筛选。",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

    return ConversationHandler.END


async def add_custom_sources_no_push(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Enter custom sources mode without immediate digest trigger."""
    query = update.callback_query
    await safe_answer_callback_query(query)

    # Initialize adding counters
    context.user_data["added_sources_count"] = 0
    context.user_data["added_sources_list"] = []
    context.user_data["no_push_mode"] = True  # Flag to indicate no immediate push

    keyboard = [
        [InlineKeyboardButton("✅ 完成添加", callback_data="finish_sources_no_push")],
        [InlineKeyboardButton("📡 使用默认源", callback_data="source_default_no_push")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "🎯 添加你关注的信息源\n\n"
        "只支持两种方式：推特 List 或 网站。\n\n"
        "📱 推特 List：粘贴链接（如 rss.app 生成）\n"
        "📰 网站：https://example.com/rss 或 域名\n\n"
        "💡 可连续发送多个，完成后点击按钮：",
        reply_markup=reply_markup
    )

    return ADDING_SOURCES


async def finish_sources_no_push(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Finish adding sources without triggering immediate digest."""
    query = update.callback_query
    await safe_answer_callback_query(query)

    user = update.effective_user
    telegram_id = str(user.id)
    from utils.json_storage import set_onboarding_paid_redeem_available
    set_onboarding_paid_redeem_available(telegram_id)

    added_count = context.user_data.get("added_sources_count", 0)

    keyboard = [
        [
            InlineKeyboardButton("偏好设置", callback_data="update_preferences"),
            InlineKeyboardButton("信息源", callback_data="manage_sources"),
        ],
        [InlineKeyboardButton("返回主菜单", callback_data="back_to_start")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if added_count > 0:
        msg = (
            f"✅ 设置完成！\n\n"
            f"{user.first_name}，你已添加 {added_count} 个信息源。\n\n"
            f"📅 你的首份简报将在约 <b>24 小时后</b>自动推送。\n\n"
            f"系统会持续监控信息源，为你积攒一整天的内容后集中筛选。"
        )
    else:
        msg = (
            f"✅ 设置完成！\n\n"
            f"{user.first_name}，你将使用默认信息源。\n\n"
            f"📅 你的首份简报将在约 <b>24 小时后</b>自动推送。\n\n"
            f"系统会持续监控信息源，为你积攒一整天的内容后集中筛选。"
        )

    await query.edit_message_text(msg, reply_markup=reply_markup, parse_mode="HTML")

    # Clear user data
    context.user_data.pop("no_push_mode", None)
    context.user_data.pop("added_sources_count", None)
    context.user_data.pop("added_sources_list", None)

    return ConversationHandler.END


async def test_digest_hint(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Redirect to main menu (test command is admin-only)."""
    query = update.callback_query
    await safe_answer_callback_query(query)

    keyboard = [[InlineKeyboardButton("返回主菜单", callback_data="back_to_start")]]
    await query.edit_message_text(
        "📅 你的简报将在约 24 小时后自动推送。\n\n"
        "届时请查看消息通知。",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def trigger_first_digest_internal(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    use_default: bool = True
) -> None:
    """Internal function to trigger first digest."""
    query = update.callback_query
    telegram_id = str(query.from_user.id)
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)

    source_type = ui.get("first_digest_using_default", "📡 Using default sources") if use_default else ui.get("first_digest_using_custom", "🎯 Using your sources")
    await query.edit_message_text(
        f"{ui.get('first_digest_generating', 'Preparing your first digest...')}\n\n"
        f"{source_type}\n"
        f"{ui.get('first_digest_ai_filtering', '🤖 AI filtering')}\n\n"
        f"{ui.get('expected_time', 'This may take 10-20 seconds...')}"
    )

    next_push_key = "next_push_time"
    wait_next_key = "first_digest_wait_next"
    try:
        from datetime import datetime
        from services.digest_processor import process_single_user
        from utils.permissions import check_feature

        today = datetime.now().strftime("%Y-%m-%d")
        user = get_user(telegram_id)
        if check_feature(telegram_id, "priority_push"):
            next_push_key = "next_push_time_pro"
            wait_next_key = "first_digest_wait_next_pro"

        if not user:
            await query.edit_message_text(ui.get("user_not_found", "User not found. Please use /start."))
            return

        # Trigger digest generation with timeout protection
        try:
            result = await asyncio.wait_for(
                process_single_user(context, user, today),
                timeout=DIGEST_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.error(f"Digest generation timeout for {telegram_id} (>{DIGEST_TIMEOUT}s)")
            keyboard = [[InlineKeyboardButton(ui.get("back_to_main", "Back to Main"), callback_data="back_to_start")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"{ui.get('first_digest_timeout', '⏱️ Generation timed out')}\n\n"
                f"{ui.get('first_digest_timeout_desc', 'Server is busy. Next digest in ~24 hours.')}",
                reply_markup=reply_markup
            )
            return

        if result.get("status") == "success":
            items_count = result.get("items_sent", 0)

            if items_count == 0:
                # No content - guide user to add sources
                keyboard = [[InlineKeyboardButton(ui.get("menu_sources", "Sources"), callback_data="manage_sources")]]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await send_message_safe(
                    context,
                    chat_id=int(telegram_id),
                    text=f"{ui.get('first_digest_no_content', 'No new content available.')}\n\n"
                         f"{ui.get('first_digest_suggestion', '💡 Suggestion')}\n"
                         f"{ui.get('first_digest_add_sources', '• Add more sources (/sources)')}\n"
                         f"{ui.get(next_push_key, ui.get('next_push_time', 'Next push: ~24 hours'))}",
                    reply_markup=reply_markup
                )
            else:
                # Success - digest messages already sent
                keyboard = [[InlineKeyboardButton(ui.get("back_to_main", "Back to Main"), callback_data="back_to_start")]]
                reply_markup = InlineKeyboardMarkup(keyboard)

                items_msg = ui.get('first_digest_items_count', 'Curated {count} items').format(count=items_count)
                await send_message_safe(
                    context,
                    chat_id=int(telegram_id),
                    text=f"{ui.get('first_digest_complete', '✅ First digest sent!')}\n\n"
                         f"{items_msg}\n\n"
                         f"{ui.get('first_digest_tip_title', '💡 Tips')}\n"
                         f"{ui.get('first_digest_tip_feedback', '• Use feedback buttons to improve')}\n"
                         f"{ui.get('first_digest_tip_settings', '• /settings to adjust preferences')}\n"
                         f"{ui.get(next_push_key, ui.get('next_push_time', 'Next push: ~24 hours'))}",
                    reply_markup=reply_markup
                )
        else:
            # Error occurred
            error_msg = result.get("error", "Unknown error")
            keyboard = [
                [InlineKeyboardButton(ui.get("back_to_main", "Back to Main"), callback_data="back_to_start")],
                [InlineKeyboardButton(ui.get("help_title", "Help"), callback_data="show_help")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            reason_msg = ui.get('first_digest_reason', 'Reason: {reason}').format(reason=error_msg[:100])
            await query.edit_message_text(
                f"{ui.get('first_digest_failed', 'Push failed')}\n\n"
                f"{reason_msg}\n\n"
                f"{ui.get(wait_next_key, ui.get('first_digest_wait_next', 'Please wait for the next push.'))}",
                reply_markup=reply_markup
            )

    except Exception as e:
        logger.error(f"First digest trigger failed for {telegram_id}: {e}")
        keyboard = [[InlineKeyboardButton(ui.get("back_to_main", "Back to Main"), callback_data="back_to_start")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"{ui.get('first_digest_failed', 'Push failed')}, {ui.get(wait_next_key, ui.get('first_digest_wait_next', 'please wait for the next push.'))}",
            reply_markup=reply_markup
        )


def get_start_callbacks():
    """Get standalone callback handlers for start menu."""
    return [
        CallbackQueryHandler(back_to_start, pattern="^back_to_start$"),
        CallbackQueryHandler(view_digest, pattern="^view_digest$"),
        CallbackQueryHandler(update_preferences, pattern="^update_preferences$"),
        CallbackQueryHandler(manage_sources, pattern="^manage_sources$"),
        CallbackQueryHandler(view_sample, pattern="^view_sample$"),
        CallbackQueryHandler(view_stats, pattern="^view_stats$"),
        CallbackQueryHandler(learn_more, pattern="^learn_more$"),
        CallbackQueryHandler(test_digest_hint, pattern="^test_digest_hint$"),
    ]


def get_start_handler() -> ConversationHandler:
    """Create and return the conversation handler for start/onboarding."""
    return ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(start_onboarding, pattern="^start_onboarding$"),
            CallbackQueryHandler(retry_round_2_callback, pattern="^retry_round_2$"),
        ],
        states={
            ONBOARDING_ROUND_1: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_round_1),
            ],
            ONBOARDING_ROUND_2: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_round_2),
            ],
            ONBOARDING_ROUND_3: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_profile_adjustment),
            ],
            CONFIRM_PROFILE: [
                CallbackQueryHandler(confirm_profile, pattern="^confirm_profile$"),
                CallbackQueryHandler(adjust_profile_prompt, pattern="^adjust_profile$"),
                CallbackQueryHandler(start_onboarding, pattern="^start_onboarding$"),
            ],
            SOURCE_CHOICE: [
                CallbackQueryHandler(add_custom_sources, pattern="^source_custom$"),
                CallbackQueryHandler(use_default_sources, pattern="^source_default$"),
                CallbackQueryHandler(skip_first_digest, pattern="^source_skip$"),
                # New handlers for no-push mode
                CallbackQueryHandler(add_custom_sources_no_push, pattern="^source_custom_no_push$"),
                CallbackQueryHandler(use_default_sources_no_push, pattern="^source_default_no_push$"),
            ],
            ADDING_SOURCES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_source),
                CallbackQueryHandler(finish_adding_sources, pattern="^finish_sources$"),
                CallbackQueryHandler(finish_with_default, pattern="^finish_sources_default$"),
                CallbackQueryHandler(skip_first_digest, pattern="^source_skip$"),
                # New handlers for no-push mode
                CallbackQueryHandler(finish_sources_no_push, pattern="^finish_sources_no_push$"),
                CallbackQueryHandler(use_default_sources_no_push, pattern="^source_default_no_push$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(start_onboarding, pattern="^start_onboarding$"),
            CallbackQueryHandler(learn_more, pattern="^learn_more$"),
        ],
        conversation_timeout=600,  # Auto-cancel after 10 minutes idle
    )
