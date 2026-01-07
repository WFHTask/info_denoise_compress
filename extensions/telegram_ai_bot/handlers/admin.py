import json
import re

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, Message

from core import config as core_config
from core.db import get_config, save_config
from core.validation import validate_config

router = Router()


DEFAULT_MODEL_BY_PROVIDER = {
    "openai": "openai/gpt-4o-mini",
    "anthropic": "anthropic/claude-3-5-sonnet-latest",
    "deepseek": "deepseek/deepseek-chat",
}


def _redact_config(cfg: dict) -> dict:
    redacted = dict(cfg or {})
    if "api_key" in redacted and redacted["api_key"]:
        redacted["api_key"] = "***"
    return redacted


async def _ensure_private(msg: Message) -> bool:
    if msg.chat.type == "private":
        return True
    await msg.answer("⚠️ 出于安全考虑，此命令仅支持私聊使用。请私聊我后重试。")
    return False


@router.message(Command("rules"))
async def show_rules(msg: Message):
    if not await _ensure_private(msg):
        return
    cfg = await get_config(msg.from_user.id)
    safe_cfg = _redact_config(cfg)
    text = f"📜 **当前配置规则**：\n\n```json\n{json.dumps(safe_cfg, indent=2, ensure_ascii=False)}\n```"
    try:
        await msg.answer(text, parse_mode="Markdown")
    except Exception:
        await msg.answer(text)


@router.message(Command("export"))
async def export_rules(msg: Message):
    if not await _ensure_private(msg):
        return
    cfg = await get_config(msg.from_user.id)
    safe_cfg = _redact_config(cfg)
    file_data = json.dumps(safe_cfg, indent=2, ensure_ascii=False).encode("utf-8")
    input_file = BufferedInputFile(file_data, filename=f"trend_config_{msg.from_user.id}.json")
    await msg.answer_document(input_file, caption="这是您的配置导出文件。")


@router.message(Command("import"))
async def import_rules(msg: Message):
    if not await _ensure_private(msg):
        return
    target_text = ""
    if msg.reply_to_message and msg.reply_to_message.text:
        target_text = msg.reply_to_message.text
    else:
        target_text = msg.text.replace("/import", "", 1).strip()

    if not target_text:
        await msg.answer(
            "用法：\n"
            "1. 回复包含 JSON 的消息发送 `/import`\n"
            "2. 或直接发送 `/import <JSON内容>`"
        )
        return

    try:
        match = re.search(r"```(?:json)?(.*?)```", target_text, re.DOTALL)
        if match:
            target_text = match.group(1)
        target_text = target_text.strip()
        new_cfg = json.loads(target_text)
    except json.JSONDecodeError:
        await msg.answer("❌JSON 格式错误，无法解析。")
        return

    if isinstance(new_cfg, dict):
        new_cfg.pop("api_key", None)

    is_valid, err = validate_config(new_cfg)
    if not is_valid:
        await msg.answer(f"❌配置不合法：{err}")
        return

    current_cfg = await get_config(msg.from_user.id)
    merged = current_cfg.copy()
    merged.update(new_cfg)

    await save_config(msg.from_user.id, merged)
    await msg.answer("✅配置导入成功。")


@router.message(Command("apikey"))
async def set_apikey(msg: Message):
    if not await _ensure_private(msg):
        return
    tokens = msg.text.split()
    if len(tokens) == 1:
        await msg.answer(
            "用法：\n"
            "1) /apikey <key>\n"
            "2) /apikey <provider> <key>\n"
            "3) /apikey <provider> <key> <model>\n\n"
            "示例：\n"
            "/apikey sk-xxxxxx\n"
            "/apikey openai sk-xxxxxx\n"
            "/apikey openai sk-xxxxxx openai/gpt-4o-mini"
        )
        return

    provider = None
    key = None
    model = None

    if len(tokens) == 2:
        key = tokens[1].strip()
    else:
        provider = tokens[1].strip().lower()
        key = tokens[2].strip()
        if len(tokens) >= 4:
            model = tokens[3].strip()

    if not key:
        await msg.answer("❌缺少 API Key，请提供完整 Key。")
        return

    cfg = await get_config(msg.from_user.id)
    cfg["api_key"] = key
    if provider:
        cfg["api_provider"] = provider
    if model:
        cfg["llm_model"] = model
    elif provider and not cfg.get("llm_model"):
        cfg["llm_model"] = DEFAULT_MODEL_BY_PROVIDER.get(provider, core_config.LLM_MODEL)

    await save_config(msg.from_user.id, cfg)
    await msg.answer("✅API Key 已保存，后续请求将优先使用您的 Key。")
