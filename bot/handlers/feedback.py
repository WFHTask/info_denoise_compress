"""
Telegram Bot Feedback Handler

Handles feedback collection through inline keyboard buttons.
Supports overall rating, reason selection, and item-level feedback.

Reference: python-telegram-bot v22.x (Exa verified 2025-01-12)
"""
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from utils.telegram_utils import safe_answer_callback_query
from utils.json_storage import save_feedback, get_user, track_event, get_user_language, update_user_activity
from locales.ui_strings import get_ui_locale

logger = logging.getLogger(__name__)

# Conversation states for feedback flow
SELECTING_REASON, ENTERING_CUSTOM_REASON = range(2)


def create_feedback_keyboard(report_id: str, lang: str = "zh") -> InlineKeyboardMarkup:
    """Create the main feedback buttons for a report."""
    ui = get_ui_locale(lang)
    keyboard = [
        [
            InlineKeyboardButton(ui["feedback_helpful"], callback_data=f"fb_positive_{report_id}"),
            InlineKeyboardButton(ui["feedback_not_helpful"], callback_data=f"fb_negative_{report_id}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def create_reason_keyboard(report_id: str, lang: str = "zh") -> InlineKeyboardMarkup:
    """Create reason selection buttons for negative feedback."""
    ui = get_ui_locale(lang)
    keyboard = [
        [
            InlineKeyboardButton(ui["reason_not_relevant"], callback_data=f"reason_not_relevant_{report_id}"),
            InlineKeyboardButton(ui["reason_missed"], callback_data=f"reason_missed_{report_id}"),
        ],
        [
            InlineKeyboardButton(ui["reason_too_much"], callback_data=f"reason_too_much_{report_id}"),
            InlineKeyboardButton(ui["reason_too_few"], callback_data=f"reason_too_few_{report_id}"),
        ],
        [InlineKeyboardButton(ui["reason_wrong_topics"], callback_data=f"reason_wrong_topics_{report_id}")],
        [InlineKeyboardButton(ui["reason_other"], callback_data=f"reason_other_{report_id}")],
        [InlineKeyboardButton(ui["cancel"], callback_data="feedback_cancel")],
    ]
    return InlineKeyboardMarkup(keyboard)


def create_item_feedback_keyboard(item_id: str, item_url: str = "", lang: str = "zh") -> InlineKeyboardMarkup:
    """
    Create feedback buttons for individual items.
    
    Buttons:
    - "查看原文" / "View Original" (callback button - tracks click, then shows URL)
    - "不感兴趣" / "Not interested" (dislike callback)
    
    Args:
        item_id: Item identifier for callback data
        item_url: Original article URL for the "View Original" button
        lang: Language code for button text
    
    Returns:
        InlineKeyboardMarkup with feedback buttons
    """
    # Get localized button text
    from services.report_generator import get_locale
    locale = get_locale(lang)
    
    view_original_text = locale.get("btn_view_original", "查看原文")
    not_interested_text = locale.get("btn_not_interested", "不感兴趣")
    
    buttons = []
    
    # "查看原文" button - callback type to track clicks
    # After click: records event, then shows URL button for user to open
    if item_url:
        buttons.append(InlineKeyboardButton(view_original_text, callback_data=f"item_click_{item_id}"))
    
    # "不感兴趣" button
    buttons.append(InlineKeyboardButton(not_interested_text, callback_data=f"item_dislike_{item_id}"))
    
    keyboard = [buttons]
    return InlineKeyboardMarkup(keyboard)


def get_item_feedback_status(item_id: str) -> str:
    """
    Check if an item has already received feedback.
    Returns "like", "dislike", or empty string if no feedback.
    """
    from utils.json_storage import FEEDBACK_DIR
    from datetime import datetime
    import os
    import json

    today = datetime.now().strftime("%Y-%m-%d")
    feedback_path = os.path.join(FEEDBACK_DIR, f"{today}.json")

    if not os.path.exists(feedback_path):
        return ""

    try:
        with open(feedback_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Check all feedbacks for this item_id
        for feedback in data.get("feedbacks", []):
            for item_fb in feedback.get("item_feedbacks", []):
                if item_fb.get("item_id") == item_id:
                    return item_fb.get("feedback", "")
    except Exception:
        return ""

    return ""


async def handle_feedback_positive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle positive feedback."""

    query = update.callback_query
    await safe_answer_callback_query(query)

    user = update.effective_user
    telegram_id = str(user.id)
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)

    # Extract report ID from callback data
    callback_data = query.data
    report_id = callback_data.replace("fb_positive_", "")

    # Get accumulated item feedbacks from session
    item_feedbacks = context.user_data.get("item_feedbacks", [])

    # Save positive feedback with item feedbacks
    save_feedback(
        telegram_id=telegram_id,
        overall_rating="positive",
        item_feedbacks=item_feedbacks,
    )

    # 埋点：正面反馈 + 更新活跃时间
    track_event(telegram_id, "feedback_positive", {"report_id": report_id})
    update_user_activity(telegram_id)

    # Clear item feedbacks after saving
    context.user_data.pop("item_feedbacks", None)

    await query.edit_message_text(
        query.message.text + f"\n\n---\n{ui['feedback_thanks']}"
    )

    logger.info(f"Positive feedback from {telegram_id} for report {report_id}")

    return ConversationHandler.END


async def handle_feedback_negative(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle negative feedback - show reason selection."""
    query = update.callback_query
    await safe_answer_callback_query(query)

    user = update.effective_user
    telegram_id = str(user.id)
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)

    callback_data = query.data
    report_id = callback_data.replace("fb_negative_", "")

    # Store report_id for later
    context.user_data["feedback_report_id"] = report_id

    reply_markup = create_reason_keyboard(report_id, lang)

    await query.edit_message_text(
        f"{ui['feedback_reason_title']}\n"
        f"{ui['divider']}\n\n"
        f"{ui['feedback_reason_prompt']}",
        reply_markup=reply_markup
    )

    return SELECTING_REASON


async def handle_reason_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle reason selection for negative feedback."""

    query = update.callback_query
    await safe_answer_callback_query(query)

    user = update.effective_user
    telegram_id = str(user.id)
    callback_data = query.data

    # Get user language
    from utils.json_storage import get_user_language
    from locales.ui_strings import get_ui_locale
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)

    if callback_data == "feedback_cancel":
        await query.edit_message_text(ui.get("feedback_cancelled", "Feedback cancelled."))
        return ConversationHandler.END

    # Parse reason from callback data (keep internal keys, display localized text)
    reason_map = {
        "reason_not_relevant_": ("not_relevant", ui.get("feedback_reason_not_relevant", "Not relevant")),
        "reason_missed_": ("missed", ui.get("feedback_reason_missed", "Missing important content")),
        "reason_too_much_": ("too_much", ui.get("feedback_reason_too_much", "Too much content")),
        "reason_too_few_": ("too_few", ui.get("feedback_reason_too_few", "Too little content")),
        "reason_wrong_topics_": ("wrong_topics", ui.get("feedback_reason_wrong_topics", "Wrong topics")),
    }

    selected_reason = None
    reason_display = None
    for prefix, (reason_key, reason_text) in reason_map.items():
        if callback_data.startswith(prefix):
            selected_reason = reason_key
            reason_display = reason_text
            break

    if callback_data.startswith("reason_other_"):
        context.user_data["feedback_reason_selected"] = ["other"]
        await query.edit_message_text(ui.get("feedback_input_prompt", "Please enter your feedback:"))
        return ENTERING_CUSTOM_REASON

    if selected_reason:
        # Get accumulated item feedbacks from session
        item_feedbacks = context.user_data.get("item_feedbacks", [])

        # Save feedback with selected reason and item feedbacks
        save_feedback(
            telegram_id=telegram_id,
            overall_rating="negative",
            reason_selected=[selected_reason],
            item_feedbacks=item_feedbacks,
        )

        # 埋点：负面反馈 + 更新活跃时间
        track_event(telegram_id, "feedback_negative", {"reason": selected_reason})
        update_user_activity(telegram_id)

        # Clear item feedbacks after saving
        context.user_data.pop("item_feedbacks", None)

        issue_msg = ui.get('feedback_issue', 'Issue: {reason}').format(reason=reason_display)
        await query.edit_message_text(
            f"{ui.get('feedback_received_title', 'Feedback Received')}\n"
            f"{ui['divider']}\n\n"
            f"{issue_msg}\n\n"
            f"{ui.get('feedback_will_adjust', 'We will adjust your preferences.')}"
        )

        logger.info(f"Negative feedback from {telegram_id}: {selected_reason}")

    return ConversationHandler.END


async def handle_custom_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle custom text reason for negative feedback."""

    user = update.effective_user
    telegram_id = str(user.id)
    custom_text = update.message.text

    # Get user language
    from utils.json_storage import get_user_language
    from locales.ui_strings import get_ui_locale
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)

    # Get accumulated item feedbacks from session
    item_feedbacks = context.user_data.get("item_feedbacks", [])

    # Save feedback with custom reason and item feedbacks
    save_feedback(
        telegram_id=telegram_id,
        overall_rating="negative",
        reason_selected=context.user_data.get("feedback_reason_selected", []),
        reason_text=custom_text,
        item_feedbacks=item_feedbacks,
    )

    # 埋点：负面反馈（自定义原因）
    track_event(telegram_id, "feedback_negative", {"reason": "custom", "text": custom_text[:100]})

    await update.message.reply_text(
        f"{ui.get('feedback_received_title', 'Feedback Received')}\n"
        f"{ui['divider']}\n\n"
        f"{ui.get('feedback_thanks_detail', 'Thanks for your detailed feedback!')}"
    )

    logger.info(f"Custom feedback from {telegram_id}: {custom_text[:50]}...")

    # Clear user data
    context.user_data.pop("feedback_reason_selected", None)
    context.user_data.pop("feedback_report_id", None)
    context.user_data.pop("item_feedbacks", None)

    return ConversationHandler.END


async def handle_item_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle click/dislike feedback on individual content items.
    
    item_click: User clicked "查看原文" - strong positive intent signal
    item_dislike: User clicked "不感兴趣" - negative signal
    """

    query = update.callback_query

    user = update.effective_user
    telegram_id = str(user.id)
    callback_data = query.data

    # Get user language for localized responses
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)

    # Parse item feedback (click or dislike)
    if callback_data.startswith("item_click_"):
        item_id = callback_data.replace("item_click_", "")
        feedback_type = "click"
        response = ui['item_opening']
    elif callback_data.startswith("item_dislike_"):
        item_id = callback_data.replace("item_dislike_", "")
        feedback_type = "dislike"
        response = ui['item_marked']
    # Legacy support for item_like (backward compatibility)
    elif callback_data.startswith("item_like_"):
        item_id = callback_data.replace("item_like_", "")
        feedback_type = "click"  # Treat like as click for backward compatibility
        response = ui['item_liked']
    else:
        await safe_answer_callback_query(query)
        return

    # Extract item content from the message for profile update
    # The message contains the news title and source
    original_text = query.message.text or ""
    
    # Try to extract title (first line after emoji indicator)
    lines = original_text.split("\n")
    item_title = lines[0] if lines else "Unknown"
    # Clean up the title (remove emoji indicators like 🔴 🔵 🟠 and numbering)
    import re
    item_title = re.sub(r'^[🔴🔵🟠]\s*\d+\.\s*', '', item_title).strip()
    item_title = re.sub(r'<[^>]+>', '', item_title)  # Remove HTML tags
    
    # Get URL from bot_data storage (set when digest was sent)
    item_url = ""
    if "item_urls" in context.bot_data:
        item_url = context.bot_data["item_urls"].get(item_id, "")
    
    # Fallback: if not in memory (e.g. after bot restart), try persistent file
    if not item_url:
        from utils.json_storage import get_item_url
        item_url = get_item_url(item_id)

    # Store item feedback in memory (for later aggregation)
    item_feedbacks = context.user_data.get("item_feedbacks", [])
    item_feedbacks.append({
        "item_id": item_id,
        "feedback": feedback_type,
        "title": item_title,
    })
    context.user_data["item_feedbacks"] = item_feedbacks

    # IMPORTANT: Also save immediately to file for real-time statistics
    # Create a lightweight feedback record for this single item
    from utils.json_storage import save_feedback
    save_feedback(
        telegram_id=telegram_id,
        overall_rating="positive" if feedback_type == "click" else "neutral",
        item_feedbacks=[{
            "item_id": item_id,
            "feedback": feedback_type,
            "title": item_title,
        }]
    )

    # 埋点：单条内容反馈 + 更新活跃时间
    # item_click 是强意图信号（用户点击查看原文）
    # item_dislike 是负向信号（用户不感兴趣）
    update_user_activity(telegram_id)
    event_type = "item_click" if feedback_type == "click" else "item_dislike"
    track_event(telegram_id, event_type, {
        "item_id": item_id, 
        "title": item_title[:50],
        "url": item_url[:200] if item_url else ""
    })

    # Show visual confirmation
    await safe_answer_callback_query(query, f"{response}", show_alert=False)

    # For item_click, replace buttons with a URL button to open the article
    if feedback_type == "click":
        try:
            if item_url:
                # Create a URL button for user to open the article
                open_text = ui['btn_open_link']
                
                open_button = InlineKeyboardButton(f"📖 {open_text}", url=item_url)
                new_keyboard = InlineKeyboardMarkup([[open_button]])
                await query.edit_message_reply_markup(reply_markup=new_keyboard)
            else:
                # No URL available, just remove buttons
                await query.edit_message_reply_markup(reply_markup=None)
        except Exception as e:
            logger.warning(f"Failed to update message after click: {e}")
    else:
        # For dislike, remove feedback buttons
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass  # Message may already be edited

    logger.info(f"Item feedback from {telegram_id}: {feedback_type} on '{item_title[:30]}'")


async def handle_unsubscribe_updates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle unsubscribe from system updates callback."""
    from utils.json_storage import get_user_subscribe_updates, set_user_subscribe_updates
    
    query = update.callback_query
    await safe_answer_callback_query(query)
    
    user = update.effective_user
    telegram_id = str(user.id)
    lang = get_user_language(telegram_id)
    ui = get_ui_locale(lang)
    
    # Check if already unsubscribed
    if not get_user_subscribe_updates(telegram_id):
        await query.answer(ui["already_unsubscribed"], show_alert=True)
        return
    
    # Unsubscribe user
    success = set_user_subscribe_updates(telegram_id, False)
    
    if success:
        # Track event
        track_event(telegram_id, "unsubscribe_updates")
        
        # Update the message to remove the button
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        
        # Send confirmation
        await context.bot.send_message(
            chat_id=telegram_id,
            text=ui["unsubscribed_updates"]
        )
        logger.info(f"User {telegram_id} unsubscribed from system updates")
    else:
        await query.answer("Error occurred", show_alert=True)


def get_feedback_handlers():
    """Create and return all feedback-related handlers."""
    # Main feedback conversation handler
    feedback_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handle_feedback_positive, pattern=r"^fb_positive_"),
            CallbackQueryHandler(handle_feedback_negative, pattern=r"^fb_negative_"),
        ],
        states={
            SELECTING_REASON: [
                CallbackQueryHandler(handle_reason_selection, pattern=r"^reason_"),
                CallbackQueryHandler(handle_reason_selection, pattern=r"^feedback_cancel$"),
            ],
            ENTERING_CUSTOM_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_reason),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(handle_reason_selection, pattern=r"^feedback_cancel$"),
        ],
        per_message=True,
    )

    # Item-level feedback handler
    item_handler = CallbackQueryHandler(handle_item_feedback, pattern=r"^item_")
    
    # Unsubscribe from updates handler
    unsubscribe_handler = CallbackQueryHandler(handle_unsubscribe_updates, pattern=r"^unsubscribe_updates$")

    return feedback_conv, item_handler, unsubscribe_handler
