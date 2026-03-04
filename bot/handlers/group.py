"""
Group Chat Handler (T7 v2)

Handles group chat functionality:
- /setup command with AI-driven 3-round preference collection (reuses private chat pattern)
- Group treated as "virtual user" with structured AI-generated profile
- Only group admin can interact; other members' messages are ignored
- Bot removal detection
- Group digest generation

Controlled by FEATURE_GROUP_CHAT feature flag.
"""
import json
import os
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from telegram import (
    ForceReply,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    ChatMemberUpdated,
)
from telegram.constants import ChatAction
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ChatMemberHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from locales.ui_strings import get_ui_locale
from services.language_service import normalize_language_code, get_language_native_name
from services.gemini import call_gemini
from utils.prompt_loader import get_prompt
from utils.language import detect_language_from_text, is_supported_language

logger = logging.getLogger(__name__)

# Conversation states for group setup (AI-driven onboarding)
(
    GROUP_ONBOARD_R1,
    GROUP_ONBOARD_R2,
    GROUP_CONFIRM_PROFILE,
    GROUP_ADJUST,
    GROUP_PUSH_TIME,
    GROUP_LANGUAGE,
) = range(100, 106)


def _get_group_config_path(group_id: str) -> str:
    """Get path to group config file."""
    from config import GROUP_CONFIGS_DIR
    os.makedirs(GROUP_CONFIGS_DIR, exist_ok=True)
    return os.path.join(GROUP_CONFIGS_DIR, f"{group_id}.json")


def load_group_config(group_id: str) -> Optional[Dict[str, Any]]:
    """Load group configuration."""
    path = _get_group_config_path(group_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return None


def save_group_config(group_id: str, config: Dict[str, Any]) -> bool:
    """Save group configuration."""
    path = _get_group_config_path(group_id)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except IOError as e:
        logger.error(f"Failed to save group config for {group_id}: {e}")
        return False


def get_all_group_configs() -> list:
    """Get all enabled group configurations."""
    from config import GROUP_CONFIGS_DIR
    configs = []
    if not os.path.exists(GROUP_CONFIGS_DIR):
        return configs
    for filename in os.listdir(GROUP_CONFIGS_DIR):
        if filename.endswith(".json"):
            filepath = os.path.join(GROUP_CONFIGS_DIR, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    if config.get("enabled", True):
                        configs.append(config)
            except (json.JSONDecodeError, IOError):
                continue
    return configs


def _get_ui_for_group(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    group_id: str = None,
    prefer_user_language: bool = False,
):
    """Get UI strings for group context."""
    user = update.effective_user
    raw_code = getattr(user, "language_code", None) if user else None
    user_lang = normalize_language_code(raw_code) if raw_code else None

    if prefer_user_language:
        resolved = user_lang or "en"
        return get_ui_locale(resolved)

    if group_id:
        config = load_group_config(group_id)
        if config and config.get("language"):
            return get_ui_locale(config["language"])

    if user_lang:
        return get_ui_locale(user_lang)

    return get_ui_locale("en")


async def _is_group_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if the user is a group admin."""
    user = update.effective_user
    chat = update.effective_chat

    if not user or not chat:
        return False

    try:
        admins = await context.bot.get_chat_administrators(chat.id)
        admin_ids = [admin.user.id for admin in admins]
        return user.id in admin_ids
    except Exception as e:
        logger.error(f"Failed to check admin status: {e}")
        return False


def _is_setup_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if the message sender is the admin who initiated the setup."""
    user = update.effective_user
    if not user:
        return False
    setup_admin_id = context.chat_data.get("setup_admin_id")
    return setup_admin_id is not None and user.id == setup_admin_id


# ============ Entry Point ============

async def setup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /setup command in group chat. Starts AI-driven 3-round onboarding."""
    from config import FEATURE_GROUP_CHAT

    if not FEATURE_GROUP_CHAT:
        return ConversationHandler.END

    chat = update.effective_chat
    if not chat or chat.type not in ("group", "supergroup"):
        ui = _get_ui_for_group(update, context, prefer_user_language=True)
        await update.message.reply_text(
            f"{ui['group_guide_title']}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{ui['group_guide_add_bot']}\n\n"
            f"{ui['group_guide_step1']}\n"
            f"{ui['group_guide_step2']}\n"
            f"{ui['group_guide_step3']}\n"
            f"{ui['group_guide_step4']}\n"
            f"{ui['group_guide_step5']}\n\n"
            f"{ui['group_guide_config_flow']}\n"
            f"{ui['group_guide_config_desc']}\n\n"
            f"{ui['group_guide_footer']}"
        )
        return ConversationHandler.END

    if not await _is_group_admin(update, context):
        ui = _get_ui_for_group(update, context, prefer_user_language=True)
        await update.message.reply_text(ui['group_admin_only'])
        return ConversationHandler.END

    group_id = str(chat.id)
    existing = load_group_config(group_id)
    ui = _get_ui_for_group(
        update, context, group_id, prefer_user_language=(not existing)
    )

    # Track which admin started setup
    context.chat_data["setup_admin_id"] = update.effective_user.id

    if existing:
        keyboard = [
            [InlineKeyboardButton(ui['group_btn_update'], callback_data="group_update")],
            [InlineKeyboardButton(ui['group_btn_view'], callback_data="group_view")],
            [InlineKeyboardButton(ui['group_btn_disable'], callback_data="group_disable")],
        ]
        await update.message.reply_text(
            f"{ui['group_already_configured']}\n\n"
            f"{ui['group_label_name']}: {existing.get('group_title', chat.title)}\n"
            f"{ui['group_label_interests']}: {(existing.get('profile', 'N/A'))[:80]}...\n"
            f"{ui['group_label_push_time']}: {existing.get('push_hour', 9)}:00\n"
            f"{ui['group_label_language']}: {existing.get('language', 'en')}\n\n"
            f"{ui['group_choose_action']}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return GROUP_ONBOARD_R1
    else:
        return await _start_ai_onboarding(update, context, is_callback=False)


async def _start_ai_onboarding(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    is_callback: bool = False,
) -> int:
    """Start the AI-driven 3-round onboarding for group setup."""
    user = update.effective_user
    chat = update.effective_chat
    ui = _get_ui_for_group(update, context, prefer_user_language=True)

    # Initialize conversation state in chat_data
    context.chat_data["conversation_history"] = []
    context.chat_data["current_round"] = 1
    context.chat_data["setup_admin_id"] = user.id

    raw_code = getattr(user, "language_code", None) if user else None
    lang = normalize_language_code(raw_code) if raw_code else "en"
    context.chat_data["language"] = lang
    context.chat_data["language_native"] = get_language_native_name(lang)

    user_language = context.chat_data["language_native"]

    # Send welcome + typing
    welcome_text = (
        f"{ui['group_welcome_new']}\n\n"
        f"{ui.get('group_ai_onboard_intro', '🤖 AI will help configure the group digest through a short conversation.')}\n\n"
        f"⏳ <i>{ui.get('onboarding_thinking', 'Thinking...')}</i>"
    )

    if is_callback:
        query = update.callback_query
        await query.edit_message_text(welcome_text, parse_mode="HTML")
        await chat.send_action(ChatAction.TYPING)
    else:
        await update.message.reply_text(welcome_text, parse_mode="HTML")
        await chat.send_action(ChatAction.TYPING)

    system_instruction = get_prompt("group_onboarding_round1.txt", user_language=user_language)

    try:
        ai_response = await call_gemini(
            prompt="Start the conversation by asking about the group's Web3 interests.",
            system_instruction=system_instruction,
            temperature=0.9
        )
    except Exception as e:
        logger.error(f"Group onboarding round 1 failed: {e}")
        keyboard = [
            [InlineKeyboardButton(ui.get("btn_retry", "🔄 Retry"), callback_data="group_restart_onboarding")],
        ]
        error_text = ui.get("ai_unavailable", "AI is temporarily unavailable. Please try again.")
        if is_callback:
            await context.bot.send_message(
                chat_id=chat.id, text=error_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text(
                error_text, reply_markup=InlineKeyboardMarkup(keyboard)
            )
        return ConversationHandler.END

    step_text = ui.get("onboarding_step", "Step {current}/{total}").format(current=1, total=3)
    admin_name = user.first_name or "Admin"

    await context.bot.send_message(
        chat_id=chat.id,
        text=f"{step_text}\n\n{ai_response}\n\n"
             f"💡 <i>{ui.get('group_admin_hint', 'Only {admin} can respond').format(admin=admin_name)}</i>\n\n"
             f"↩️ <i>{ui.get('group_reply_hint', 'Please reply to this message to respond')}</i>",
        parse_mode="HTML",
        reply_markup=ForceReply(selective=True),
    )

    return GROUP_ONBOARD_R1


# ============ AI Onboarding Handlers ============

async def handle_onboard_r1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle admin's round 1 response, proceed to round 2."""
    if not _is_setup_admin(update, context):
        return GROUP_ONBOARD_R1

    user_message = update.message.text
    chat = update.effective_chat

    # Detect language from admin's reply
    lang_before = context.chat_data.get("language", "en")
    detected_lang = detect_language_from_text(user_message)
    if detected_lang and is_supported_language(detected_lang):
        context.chat_data["language"] = detected_lang
        context.chat_data["language_native"] = get_language_native_name(detected_lang)

    lang = context.chat_data.get("language", "en")
    user_language = context.chat_data.get("language_native", get_language_native_name(lang))
    ui = get_ui_locale(lang)

    context.chat_data["conversation_history"].append({
        "round": 1,
        "user_input": user_message
    })
    context.chat_data["current_round"] = 2

    await chat.send_action(ChatAction.TYPING)

    system_instruction = get_prompt(
        "group_onboarding_round2.txt",
        user_input=user_message,
        user_language=user_language
    )

    try:
        ai_response = await call_gemini(
            prompt=f"The admin said: '{user_message}'. Ask follow-up questions about content preferences for the group.",
            system_instruction=system_instruction,
            temperature=0.9
        )
    except Exception as e:
        logger.error(f"Group onboarding round 2 failed: {e}")
        keyboard = [
            [InlineKeyboardButton(ui.get("btn_retry", "🔄 Retry"), callback_data="group_restart_onboarding")],
        ]
        await update.message.reply_text(
            ui.get("ai_unavailable", "AI is temporarily unavailable."),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END

    step_text = ui.get("onboarding_step", "Step {current}/{total}").format(current=2, total=3)
    await update.message.reply_text(
        f"{step_text}\n\n{ai_response}",
        reply_markup=ForceReply(selective=True),
    )

    return GROUP_ONBOARD_R2


async def handle_onboard_r2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle admin's round 2 response, generate profile summary."""
    if not _is_setup_admin(update, context):
        return GROUP_ONBOARD_R2

    user_message = update.message.text
    chat = update.effective_chat

    # Detect language
    detected_lang = detect_language_from_text(user_message)
    if detected_lang and is_supported_language(detected_lang):
        context.chat_data["language"] = detected_lang
        context.chat_data["language_native"] = get_language_native_name(detected_lang)

    lang = context.chat_data.get("language", "en")
    user_language = context.chat_data.get("language_native", get_language_native_name(lang))
    ui = get_ui_locale(lang)

    context.chat_data["conversation_history"].append({
        "round": 2,
        "user_input": user_message
    })
    context.chat_data["current_round"] = 3

    progress_msg = await update.message.reply_text(
        f"<i>{ui.get('generating_profile', '⏳ Generating profile...')}</i>",
        parse_mode="HTML"
    )

    await chat.send_action(ChatAction.TYPING)

    history = context.chat_data["conversation_history"]
    round_1 = history[0]["user_input"]
    round_2 = user_message

    system_instruction = get_prompt(
        "group_onboarding_round3.txt",
        round_1=round_1,
        round_2=round_2,
        user_language=user_language
    )

    try:
        ai_response = await call_gemini(
            prompt=f"Summarize group preferences: Round 1: '{round_1}', Round 2: '{round_2}'",
            system_instruction=system_instruction,
            temperature=0.7
        )
    except Exception as e:
        logger.error(f"Group onboarding round 3 failed: {e}")
        try:
            await progress_msg.delete()
        except Exception:
            pass
        keyboard = [
            [InlineKeyboardButton(ui.get("btn_retry", "🔄 Retry"), callback_data="group_restart_onboarding")],
        ]
        await update.message.reply_text(
            ui.get("ai_unavailable", "AI is temporarily unavailable."),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END

    context.chat_data["profile_summary"] = ai_response
    context.chat_data["_profile_adjusted"] = False

    try:
        await progress_msg.delete()
    except Exception:
        pass

    keyboard = [
        [InlineKeyboardButton(
            ui.get("btn_confirm", "✅ Confirm"),
            callback_data="group_confirm_profile"
        )],
        [InlineKeyboardButton(
            ui.get("btn_adjust_profile", "✏️ Adjust"),
            callback_data="group_adjust_profile"
        )],
        [InlineKeyboardButton(
            ui.get("btn_restart", "🔄 Restart"),
            callback_data="group_restart_onboarding"
        )],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    step_text = ui.get("onboarding_step", "Step {current}/{total}").format(current=3, total=3)

    confirm_prefix = f"{step_text} {ui.get('onboarding_confirm_prefs', 'Please confirm:')}\n\n"
    max_len = 4000 - len(confirm_prefix)
    if len(ai_response) > max_len:
        ai_response = ai_response[:max_len] + "..."
        context.chat_data["profile_summary"] = ai_response

    await update.message.reply_text(
        f"{confirm_prefix}{ai_response}",
        reply_markup=reply_markup
    )

    return GROUP_CONFIRM_PROFILE


# ============ Profile Confirmation ============

async def handle_confirm_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Admin confirmed the profile. Generate structured profile and proceed to push time."""
    query = update.callback_query

    if not _is_setup_admin(update, context):
        await query.answer("Only the admin who started /setup can interact.", show_alert=True)
        return GROUP_CONFIRM_PROFILE

    await query.answer()

    chat = update.effective_chat
    lang = context.chat_data.get("language", "en")
    user_language = context.chat_data.get("language_native", get_language_native_name(lang))
    ui = get_ui_locale(lang)

    await context.bot.send_message(
        chat_id=chat.id,
        text=f"<i>{ui.get('saving_prefs', '⏳ Saving preferences...')}</i>",
        parse_mode="HTML"
    )

    profile_summary = context.chat_data.get("profile_summary", "")
    history = context.chat_data.get("conversation_history", [])

    system_instruction = get_prompt(
        "group_onboarding_confirm.txt",
        user_language=user_language,
        conversation_summary=f"History: {history}. Summary: {profile_summary}"
    )

    try:
        full_profile = await call_gemini(
            prompt=f"Create group profile from: {history}. Summary: {profile_summary}",
            system_instruction=system_instruction,
            temperature=0.5
        )
    except Exception as e:
        logger.error(f"Failed to generate group profile: {e}")
        keyboard = [
            [InlineKeyboardButton(ui.get("btn_retry", "Retry"), callback_data="group_confirm_profile")],
            [InlineKeyboardButton(ui.get("btn_restart", "Restart"), callback_data="group_restart_onboarding")],
        ]
        await context.bot.send_message(
            chat_id=chat.id,
            text=ui.get("error_occurred", "An error occurred. Please try again."),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return GROUP_CONFIRM_PROFILE

    context.chat_data["full_profile"] = full_profile

    # Proceed to push time selection
    keyboard = [
        [
            InlineKeyboardButton("7:00", callback_data="group_time_7"),
            InlineKeyboardButton("8:00", callback_data="group_time_8"),
            InlineKeyboardButton("9:00", callback_data="group_time_9"),
        ],
        [
            InlineKeyboardButton("10:00", callback_data="group_time_10"),
            InlineKeyboardButton("12:00", callback_data="group_time_12"),
            InlineKeyboardButton("18:00", callback_data="group_time_18"),
        ],
    ]

    await context.bot.send_message(
        chat_id=chat.id,
        text=f"✅ {ui.get('group_profile_saved', 'Group profile saved!')}\n\n"
             f"{ui['group_select_push_time']}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return GROUP_PUSH_TIME


async def handle_adjust_profile_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show prompt for admin to adjust the group profile."""
    query = update.callback_query

    if not _is_setup_admin(update, context):
        await query.answer("Only the admin who started /setup can interact.", show_alert=True)
        return GROUP_CONFIRM_PROFILE

    await query.answer()

    lang = context.chat_data.get("language", "en")
    ui = get_ui_locale(lang)

    if context.chat_data.get("_profile_adjusted"):
        profile_summary = context.chat_data.get("profile_summary", "")
        await query.edit_message_text(
            f"{profile_summary}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(ui.get("btn_confirm", "✅ Confirm"), callback_data="group_confirm_profile")],
                [InlineKeyboardButton(ui.get("btn_restart", "🔄 Restart"), callback_data="group_restart_onboarding")],
            ])
        )
        return GROUP_CONFIRM_PROFILE

    profile_summary = context.chat_data.get("profile_summary", "")

    await query.edit_message_text(
        f"{ui.get('adjust_profile_prompt', '✏️ How would you like to adjust the profile?')}\n\n"
        f"{ui.get('adjust_profile_current', 'Current profile:')}\n{profile_summary}"
    )

    chat = update.effective_chat
    await context.bot.send_message(
        chat_id=chat.id,
        text=f"{ui.get('adjust_profile_hint', 'Type your adjustment request:')}",
        reply_markup=ForceReply(selective=True),
    )

    return GROUP_ADJUST


async def handle_profile_adjustment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle admin's profile adjustment request."""
    if not _is_setup_admin(update, context):
        return GROUP_ADJUST

    chat = update.effective_chat
    lang = context.chat_data.get("language", "en")
    user_language = context.chat_data.get("language_native", get_language_native_name(lang))
    ui = get_ui_locale(lang)

    adjustment_text = update.message.text
    current_profile = context.chat_data.get("profile_summary", "")
    history = context.chat_data.get("conversation_history", [])

    await chat.send_action(ChatAction.TYPING)

    round_1 = history[0]["user_input"] if len(history) > 0 else ""
    round_2 = history[1]["user_input"] if len(history) > 1 else ""

    system_instruction = get_prompt(
        "group_onboarding_round3.txt",
        round_1=round_1,
        round_2=round_2,
        user_language=user_language
    )

    try:
        ai_response = await call_gemini(
            prompt=(
                f"Previous group profile: '{current_profile}'\n"
                f"Admin adjustment request: '{adjustment_text}'\n"
                f"Original conversation - Round 1: '{round_1}', Round 2: '{round_2}'\n"
                f"Please regenerate the group profile incorporating the adjustments."
            ),
            system_instruction=system_instruction,
            temperature=0.7
        )
    except Exception as e:
        logger.error(f"Group profile adjustment failed: {e}")
        keyboard = [
            [InlineKeyboardButton(ui.get("btn_confirm", "✅ Confirm"), callback_data="group_confirm_profile")],
            [InlineKeyboardButton(ui.get("btn_restart", "🔄 Restart"), callback_data="group_restart_onboarding")],
        ]
        await update.message.reply_text(
            ui.get("ai_unavailable", "AI is temporarily unavailable."),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return GROUP_CONFIRM_PROFILE

    context.chat_data["profile_summary"] = ai_response
    context.chat_data["_profile_adjusted"] = True

    keyboard = [
        [InlineKeyboardButton(ui.get("btn_confirm", "✅ Confirm"), callback_data="group_confirm_profile")],
        [InlineKeyboardButton(ui.get("btn_restart", "🔄 Restart"), callback_data="group_restart_onboarding")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    step_text = ui.get("onboarding_step", "Step {current}/{total}").format(current=3, total=3)
    await update.message.reply_text(
        f"{step_text} {ui.get('profile_adjusted', '✨ Profile updated')}\n\n{ai_response}",
        reply_markup=reply_markup
    )

    return GROUP_CONFIRM_PROFILE


# ============ Push Time & Language ============

async def handle_push_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle push time selection."""
    query = update.callback_query

    if not _is_setup_admin(update, context):
        await query.answer("Only the admin who started /setup can interact.", show_alert=True)
        return GROUP_PUSH_TIME

    await query.answer()

    hour = int(query.data.replace("group_time_", ""))
    context.chat_data["push_hour"] = hour

    chat = update.effective_chat
    group_id = str(chat.id) if chat else None
    lang = context.chat_data.get("language", "en")
    ui = get_ui_locale(lang)

    keyboard = [
        [
            InlineKeyboardButton("🇨🇳 中文", callback_data="group_lang_zh"),
            InlineKeyboardButton("🇺🇸 English", callback_data="group_lang_en"),
        ],
        [
            InlineKeyboardButton("🇯🇵 日本語", callback_data="group_lang_ja"),
            InlineKeyboardButton("🇰🇷 한국어", callback_data="group_lang_ko"),
        ],
    ]

    await query.edit_message_text(
        f"{ui['group_time_saved'].format(hour=hour)}\n\n"
        f"{ui['group_select_language']}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return GROUP_LANGUAGE


async def handle_language_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle language selection and save full config."""
    query = update.callback_query

    if not _is_setup_admin(update, context):
        await query.answer("Only the admin who started /setup can interact.", show_alert=True)
        return GROUP_LANGUAGE

    await query.answer()

    lang = query.data.replace("group_lang_", "")
    chat = update.effective_chat
    group_id = str(chat.id)

    config = {
        "group_id": group_id,
        "group_title": chat.title or "Unknown Group",
        "admin_id": str(update.effective_user.id),
        "profile": context.chat_data.get("full_profile", context.chat_data.get("profile_summary", "")),
        "push_hour": context.chat_data.get("push_hour", 9),
        "language": lang,
        "created": datetime.now().isoformat(),
        "enabled": True,
    }

    save_group_config(group_id, config)

    lang_names = {"zh": "中文", "en": "English", "ja": "日本語", "ko": "한국어"}

    ui = get_ui_locale(lang)

    profile_preview = config["profile"][:120] + "..." if len(config["profile"]) > 120 else config["profile"]

    await query.edit_message_text(
        f"{ui['group_setup_complete']}\n\n"
        f"{ui['group_setup_interests'].format(profile=profile_preview)}\n"
        f"{ui['group_setup_push'].format(hour=config['push_hour'])}\n"
        f"{ui['group_setup_lang'].format(lang_name=lang_names.get(lang, lang))}\n\n"
        f"{ui['group_setup_footer']}"
    )

    # Clear chat data
    for key in list(context.chat_data.keys()):
        if key.startswith(("conversation_", "current_", "setup_", "profile_", "full_", "push_", "language", "_profile")):
            context.chat_data.pop(key, None)

    return ConversationHandler.END


# ============ View / Disable (for existing configs) ============

async def handle_group_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """View current group config."""
    query = update.callback_query
    await query.answer()

    group_id = str(update.effective_chat.id)
    config = load_group_config(group_id)

    if config:
        lang = config.get("language", "en")
        ui = get_ui_locale(lang)
        status = ui['group_status_enabled'] if config.get('enabled', True) else ui['group_status_disabled']
        profile_preview = config.get('profile', 'N/A')
        if len(profile_preview) > 200:
            profile_preview = profile_preview[:200] + "..."
        await query.edit_message_text(
            f"{ui['group_view_title']}\n\n"
            f"{ui['group_label_interests']}:\n{profile_preview}\n\n"
            f"{ui['group_label_push_time']}: {config.get('push_hour', 9)}:00\n"
            f"{ui['group_label_language']}: {config.get('language', 'en')}\n"
            f"{ui['group_label_status']}: {status}\n"
            f"{ui['group_label_created']}: {config.get('created', 'N/A')[:10]}\n\n"
            f"{ui['group_view_footer']}"
        )
    else:
        ui = _get_ui_for_group(update, context)
        await query.edit_message_text(ui['group_no_config'])

    return ConversationHandler.END


async def handle_group_disable(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Disable group push."""
    query = update.callback_query
    await query.answer()

    group_id = str(update.effective_chat.id)
    config = load_group_config(group_id)

    if config:
        config["enabled"] = False
        save_group_config(group_id, config)
        lang = config.get("language", "en")
        ui = get_ui_locale(lang)
        await query.edit_message_text(
            f"{ui['group_disabled']}\n\n"
            f"{ui['group_disabled_footer']}"
        )

    return ConversationHandler.END


async def handle_group_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start AI-driven update flow (restart onboarding)."""
    query = update.callback_query

    if not _is_setup_admin(update, context):
        if update.effective_user:
            context.chat_data["setup_admin_id"] = update.effective_user.id

    return await _start_ai_onboarding(update, context, is_callback=True)


async def handle_restart_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Restart the AI onboarding from scratch."""
    query = update.callback_query
    if query:
        await query.answer()
    return await _start_ai_onboarding(update, context, is_callback=bool(query))


# ============ Bot Added/Removed Handlers ============

async def handle_bot_added(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcome message when bot is added to a group."""
    from config import FEATURE_GROUP_CHAT
    if not FEATURE_GROUP_CHAT:
        return

    my_chat_member = update.my_chat_member
    if not my_chat_member:
        return

    chat = my_chat_member.chat
    if chat.type not in ("group", "supergroup"):
        return

    from_user = my_chat_member.from_user
    raw_code = getattr(from_user, "language_code", None) if from_user else None
    lang = normalize_language_code(raw_code) if raw_code else "en"
    ui = get_ui_locale(lang)

    try:
        await context.bot.send_message(
            chat_id=chat.id,
            text=ui["group_welcome_on_join"]
        )
        logger.info(f"Welcome message sent to group {chat.id} ({chat.title})")
    except Exception as e:
        logger.warning(f"Failed to send welcome to group {chat.id}: {e}")


async def handle_bot_removed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle bot being removed from group."""
    from config import FEATURE_GROUP_CHAT
    if not FEATURE_GROUP_CHAT:
        return

    my_chat_member = update.my_chat_member
    if not my_chat_member:
        return

    new_status = my_chat_member.new_chat_member.status
    chat = my_chat_member.chat

    if new_status in ("left", "kicked"):
        group_id = str(chat.id)
        config = load_group_config(group_id)
        if config:
            config["enabled"] = False
            save_group_config(group_id, config)
            logger.info(f"Bot removed from group {group_id} ({chat.title}), disabled config")


async def handle_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route my_chat_member updates to add or remove handler."""
    my_chat_member = update.my_chat_member
    if not my_chat_member:
        return

    new_status = my_chat_member.new_chat_member.status

    if new_status in ("member", "administrator"):
        await handle_bot_added(update, context)
    elif new_status in ("left", "kicked"):
        await handle_bot_removed(update, context)


# ============ Handler Registration ============

def get_group_handler() -> Optional[ConversationHandler]:
    """Create group setup conversation handler with AI-driven onboarding."""
    from config import FEATURE_GROUP_CHAT
    if not FEATURE_GROUP_CHAT:
        return None

    return ConversationHandler(
        entry_points=[
            CommandHandler("setup", setup_command),
        ],
        states={
            GROUP_ONBOARD_R1: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_onboard_r1),
                CallbackQueryHandler(handle_group_update, pattern="^group_update$"),
                CallbackQueryHandler(handle_group_view, pattern="^group_view$"),
                CallbackQueryHandler(handle_group_disable, pattern="^group_disable$"),
                CallbackQueryHandler(handle_restart_onboarding, pattern="^group_restart_onboarding$"),
            ],
            GROUP_ONBOARD_R2: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_onboard_r2),
                CallbackQueryHandler(handle_restart_onboarding, pattern="^group_restart_onboarding$"),
            ],
            GROUP_CONFIRM_PROFILE: [
                CallbackQueryHandler(handle_confirm_profile, pattern="^group_confirm_profile$"),
                CallbackQueryHandler(handle_adjust_profile_prompt, pattern="^group_adjust_profile$"),
                CallbackQueryHandler(handle_restart_onboarding, pattern="^group_restart_onboarding$"),
            ],
            GROUP_ADJUST: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_profile_adjustment),
                CallbackQueryHandler(handle_restart_onboarding, pattern="^group_restart_onboarding$"),
            ],
            GROUP_PUSH_TIME: [
                CallbackQueryHandler(handle_push_time, pattern=r"^group_time_\d+$"),
            ],
            GROUP_LANGUAGE: [
                CallbackQueryHandler(handle_language_choice, pattern=r"^group_lang_\w+$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", lambda u, c: ConversationHandler.END),
            CallbackQueryHandler(handle_restart_onboarding, pattern="^group_restart_onboarding$"),
        ],
        per_chat=True,
        conversation_timeout=600,
    )


def get_group_callbacks():
    """Get standalone group callback handlers."""
    from config import FEATURE_GROUP_CHAT
    if not FEATURE_GROUP_CHAT:
        return []
    return [
        ChatMemberHandler(handle_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER),
    ]
