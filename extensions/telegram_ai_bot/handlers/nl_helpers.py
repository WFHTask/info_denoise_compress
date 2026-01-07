import re

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message


PREVIEW_KEYWORDS = ["简报", "日报", "预览", "看看新闻", "summary", "brief", "preview", "report"]
INSIGHT_KEYWORDS = ["解读", "分析", "详解", "详细", "怎么看", "发生了什么"]
SCHEDULE_KEYWORDS = ["推送", "发送", "定时", "定点", "每天", "每早", "每晚", "每次", "次数", "次"]
CONFIG_KEYWORDS = [
    "修改",
    "设置",
    "屏蔽",
    "关注",
    "priority",
    "block",
    "allow",
    "only",
    "只看",
    "不看",
    "去掉",
    "加上",
    "add",
    "remove",
]


def build_confirm_keyboard(confirm_cb: str, cancel_cb: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅确认", callback_data=confirm_cb),
                InlineKeyboardButton(text="❌取消", callback_data=cancel_cb),
            ]
        ]
    )


def redact_config(cfg: dict) -> dict:
    redacted = dict(cfg or {})
    if "api_key" in redacted and redacted["api_key"]:
        redacted["api_key"] = "***"
    return redacted


async def ensure_private(msg: Message) -> bool:
    if msg.chat.type == "private":
        return True
    await msg.answer("⚠️ 出于安全考虑，此操作仅支持私聊使用。请私聊我后重试。")
    return False


def get_fast_flags(user_text: str) -> dict:
    lower_text = user_text.lower()
    is_insight_fast = any(k in lower_text for k in INSIGHT_KEYWORDS)
    is_schedule_fast = any(k in lower_text for k in SCHEDULE_KEYWORDS)
    is_config_fast = any(k in lower_text for k in CONFIG_KEYWORDS)
    is_preview_fast = (
        (not is_config_fast)
        and (not is_schedule_fast)
        and (not is_insight_fast)
        and any(k in lower_text for k in PREVIEW_KEYWORDS)
    )
    return {
        "is_insight_fast": is_insight_fast,
        "is_schedule_fast": is_schedule_fast,
        "is_config_fast": is_config_fast,
        "is_preview_fast": is_preview_fast,
    }


def strip_bot_mention(text: str, bot_username: str) -> str:
    if not bot_username:
        return text
    pattern = re.compile(f"@{re.escape(bot_username)}", re.IGNORECASE)
    return pattern.sub("", text).strip()
