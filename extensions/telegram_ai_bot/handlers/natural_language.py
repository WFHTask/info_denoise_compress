import json

from aiogram import Dispatcher, F, Router
from aiogram.exceptions import TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from core import config as core_config
from core import runtime
from core.db import add_user_source, delete_user_source, get_config, get_user_sources, save_config
from core.validation import validate_config
from handlers.basic import EVENT_CN, execute_preview
from handlers.nl_event import select_event_candidates
from handlers.nl_helpers import build_confirm_keyboard, ensure_private, get_fast_flags, redact_config, strip_bot_mention
from services import data_service, scheduler_service
from services.llm_service import analyze_event, parse_user_intent
from services.rss_service import fetch_single_rss, get_recent_user_rss_items


DEFAULT_MODEL_BY_PROVIDER = {
    "openai": "openai/gpt-4o-mini",
    "anthropic": "anthropic/claude-3-5-sonnet-latest",
    "deepseek": "deepseek/deepseek-chat",
}


class ConfigState(StatesGroup):
    confirming = State()


class ScheduleState(StatesGroup):
    confirming = State()


class ActionState(StatesGroup):
    confirming = State()


class EventInsightState(StatesGroup):
    selecting = State()


def _resolve_model_for_provider(provider: str, llm_model: str | None) -> str | None:
    if llm_model:
        return llm_model
    if provider:
        return DEFAULT_MODEL_BY_PROVIDER.get(provider)
    return None


def create_router(dispatcher: Dispatcher, bot_id_getter) -> Router:
    router = Router()

    @router.message(F.text)
    async def handle_natural_language(msg: Message, state: FSMContext):
        if msg.text.startswith("/"):
            return

        is_private = msg.chat.type == "private"
        is_mentioned = False

        if not is_private:
            if msg.entities:
                for ent in msg.entities:
                    if ent.type == "mention":
                        mention_text = msg.text[ent.offset : ent.offset + ent.length]
                        if runtime.BOT_USERNAME and mention_text.lower() == f"@{runtime.BOT_USERNAME.lower()}":
                            is_mentioned = True
                            break

            if not is_mentioned and msg.reply_to_message:
                reply_from = msg.reply_to_message.from_user
                if reply_from and reply_from.id == bot_id_getter():
                    is_mentioned = True

            if not is_mentioned:
                return

        user_text = msg.text
        if not is_private and runtime.BOT_USERNAME:
            user_text = strip_bot_mention(user_text, runtime.BOT_USERNAME)

        if not user_text:
            return

        flags = get_fast_flags(user_text)
        if flags["is_preview_fast"]:
            await execute_preview(msg, msg.from_user.id)
            return

        current_state = await state.get_state()
        if current_state == EventInsightState.selecting.state:
            data = await state.get_data()
            choices = data.get("event_choices") or []
            if not choices:
                await state.clear()
                await msg.answer("候选已过期，请重新发起解读请求。")
                return
            text = msg.text.strip()
            if text.lower() in ("取消", "cancel"):
                await state.clear()
                await msg.answer("已取消解读。")
                return
            if not text.isdigit():
                await msg.answer("请输入编号进行选择，或回复 取消。")
                return
            idx = int(text)
            if idx < 1 or idx > len(choices):
                await msg.answer("编号超出范围，请重新选择。")
                return
            selected = choices[idx - 1]
            cfg = await get_config(msg.from_user.id)
            analysis_text, err = await analyze_event(
                selected,
                api_key=cfg.get("api_key"),
                model=cfg.get("llm_model"),
            )
            if err:
                await msg.answer(f"❌事件解读失败：{err}")
            else:
                await msg.answer(analysis_text, parse_mode="MarkdownV2")
            await state.clear()
            return

        if current_state in (
            ConfigState.confirming.state,
            ScheduleState.confirming.state,
            ActionState.confirming.state,
        ):
            return

        processing_msg = None
        if is_private:
            processing_msg = await msg.answer("🤖 正在思考...")
        else:
            await msg.answer("📩 已收到，正在处理...", reply_to_message_id=msg.message_id)

        user_id = msg.from_user.id
        current_cfg = await get_config(user_id)
        await save_config(user_id, current_cfg)
        await scheduler_service.refresh_user_schedule(msg.bot, user_id)

        intent_data, error_msg = await parse_user_intent(
            user_text,
            current_cfg,
            api_key=current_cfg.get("api_key"),
        )

        if is_private and processing_msg:
            await processing_msg.delete()

        if error_msg or not intent_data:
            err_text = error_msg or "抱歉，我无法理解您的请求，请尝试换一种说法。"
            if is_private:
                await msg.answer(err_text)
            else:
                try:
                    await msg.bot.send_message(user_id, err_text)
                except TelegramForbiddenError:
                    await msg.answer("❌无法私信您结果，请先私聊我发送 /start")
            return

        intent_type = intent_data.get("type")

        if intent_type == "chat":
            reply = intent_data.get("reply", "🤔")
            if is_private:
                await msg.answer(reply)
            else:
                try:
                    await msg.bot.send_message(user_id, reply)
                except Exception:
                    pass
            return

        if intent_type == "preview":
            await execute_preview(msg, user_id)
            return

        if intent_type == "rss_list":
            sources = await get_user_sources(user_id)
            if not sources:
                await msg.answer("📭 您当前没有订阅任何 RSS 源。")
                return
            text = "📋 **您的 RSS 订阅列表**：\n\n"
            for i, s in enumerate(sources, 1):
                name = s.get("name") or "未命名"
                text += f"{i}. {s['url']} ({name})\n"
            await msg.answer(text)
            return

        if intent_type in ("rss_add", "rss_remove"):
            rss_url = (intent_data.get("rss_url") or "").strip()
            if not rss_url:
                await msg.answer("❌缺少 RSS 地址，请提供一个完整的 http/https URL。")
                return
            if not rss_url.startswith("http"):
                await msg.answer("❌请输入有效的 HTTP/HTTPS URL。")
                return

            action_text = "添加" if intent_type == "rss_add" else "移除"
            confirm_text = f"即将{action_text}订阅：{rss_url}\n是否确认？"
            kb = build_confirm_keyboard("action:confirm", "action:cancel")
            try:
                await msg.bot.send_message(chat_id=user_id, text=confirm_text, reply_markup=kb)
                from aiogram.fsm.storage.base import StorageKey

                key = StorageKey(bot_id=bot_id_getter(), chat_id=user_id, user_id=user_id)
                await dispatcher.storage.set_state(key, ActionState.confirming)
                await dispatcher.storage.set_data(
                    key,
                    {
                        "action_type": intent_type,
                        "rss_url": rss_url,
                    },
                )
            except TelegramForbiddenError:
                await msg.answer("❌无法私信您，请先私聊我发送 /start 启动机器人。")
            return

        if intent_type == "noise_toggle":
            enable_noise_filter = intent_data.get("enable_noise_filter")
            if not isinstance(enable_noise_filter, bool):
                await msg.answer("❌请明确开启或关闭降噪，例如：开启降噪 / 关闭降噪。")
                return
            cfg = await get_config(user_id)
            cfg["enable_noise_filter"] = enable_noise_filter
            await save_config(user_id, cfg)
            state_text = "✅已开启" if enable_noise_filter else "🚫 已关闭"
            await msg.answer(f"{state_text} Web3 智能降噪过滤。")
            return

        if intent_type == "schedule_update":
            cfg = await get_config(user_id)
            draft_cfg = cfg.copy()
            has_times = "brief_times" in intent_data
            has_count = "brief_count" in intent_data
            if has_times:
                draft_cfg["brief_times"] = intent_data.get("brief_times")
            if has_count:
                draft_cfg["brief_count"] = intent_data.get("brief_count")
                if not has_times:
                    draft_cfg["brief_times"] = []
            if has_times and not has_count:
                draft_cfg["brief_count"] = len(draft_cfg.get("brief_times") or [])

            is_valid, valid_err = validate_config(draft_cfg)
            if not is_valid:
                await msg.answer(f"⚠️ 配置解析异常：{valid_err}。请重试或更详细描述。")
                return

            times = scheduler_service.get_brief_times(draft_cfg)
            times_text = "、".join(times) if times else "未设置"
            confirm_text = (
                f"解析结果：将设置为 {times_text}，每天推送 {len(times)} 次。\n"
                "是否确认更新？"
            )
            kb = build_confirm_keyboard("schedule:confirm", "schedule:cancel")
            try:
                await msg.bot.send_message(chat_id=user_id, text=confirm_text, reply_markup=kb)
                from aiogram.fsm.storage.base import StorageKey

                key = StorageKey(bot_id=bot_id_getter(), chat_id=user_id, user_id=user_id)
                await dispatcher.storage.set_state(key, ScheduleState.confirming)
                await dispatcher.storage.set_data(
                    key,
                    {
                        "schedule_config": draft_cfg,
                        "schedule_times": times,
                    },
                )
            except TelegramForbiddenError:
                await msg.answer("❌无法私信您，请先私聊我发送 /start 启动机器人。")
            return

        if intent_type == "event_insight":
            query = (intent_data.get("event_query") or "").strip()
            if not query:
                await msg.answer("❌请提供要解读的事件关键词。")
                return

            events = await data_service.get_recent_news(days=7, limit=200)
            user_sources = await get_user_sources(user_id)
            if user_sources:
                source_urls = [s["url"] for s in user_sources]
                rss_items = await get_recent_user_rss_items(source_urls, days=7, limit=200)
                for item in rss_items:
                    item["platform_id"] = "RSS"
                    item["rank"] = 0
                    item["is_subscribed"] = True
                    events.append(item)

            top = select_event_candidates(events, query, limit=5)
            if not top:
                await msg.answer("未找到匹配的事件，请换个关键词试试。")
                return

            lines = ["匹配到以下事件，请回复编号选择："]
            for i, item in enumerate(top, 1):
                lines.append(f"{i}. {item.get('title', '')}")
            lines.append("回复 取消 可退出。")
            await msg.answer("\n".join(lines))

            from aiogram.fsm.storage.base import StorageKey

            key = StorageKey(bot_id=bot_id_getter(), chat_id=user_id, user_id=user_id)
            await dispatcher.storage.set_state(key, EventInsightState.selecting)
            await dispatcher.storage.set_data(key, {"event_choices": top})
            return

        if intent_type == "rules_show":
            if not await ensure_private(msg):
                return
            cfg = await get_config(user_id)
            safe_cfg = redact_config(cfg)
            text = f"📜 **当前配置规则**：\n\n```json\n{json.dumps(safe_cfg, indent=2, ensure_ascii=False)}\n```"
            try:
                await msg.answer(text, parse_mode="Markdown")
            except Exception:
                await msg.answer(text)
            return

        if intent_type == "export_config":
            if not await ensure_private(msg):
                return
            cfg = await get_config(user_id)
            safe_cfg = redact_config(cfg)
            file_data = json.dumps(safe_cfg, indent=2, ensure_ascii=False).encode("utf-8")
            input_file = BufferedInputFile(file_data, filename=f"trend_config_{user_id}.json")
            await msg.answer_document(input_file, caption="这是您的配置导出文件。")
            return

        if intent_type == "import_config":
            if not await ensure_private(msg):
                return
            config_json = intent_data.get("config_json") or ""
            if not config_json:
                await msg.answer("❌缺少配置 JSON，请直接粘贴配置内容。")
                return
            try:
                new_cfg = json.loads(config_json)
            except json.JSONDecodeError:
                await msg.answer("❌配置 JSON 格式错误，无法解析。")
                return

            if isinstance(new_cfg, dict):
                new_cfg.pop("api_key", None)
            else:
                await msg.answer("❌配置必须是 JSON 对象。")
                return

            is_valid, err = validate_config(new_cfg)
            if not is_valid:
                await msg.answer(f"❌配置不合法：{err}")
                return

            current_cfg = await get_config(user_id)
            merged = current_cfg.copy()
            merged.update(new_cfg)

            confirm_text = "即将导入配置并覆盖现有设置，是否确认？"
            kb = build_confirm_keyboard("action:confirm", "action:cancel")
            try:
                await msg.bot.send_message(chat_id=user_id, text=confirm_text, reply_markup=kb)
                from aiogram.fsm.storage.base import StorageKey

                key = StorageKey(bot_id=bot_id_getter(), chat_id=user_id, user_id=user_id)
                await dispatcher.storage.set_state(key, ActionState.confirming)
                await dispatcher.storage.set_data(
                    key,
                    {
                        "action_type": "import_config",
                        "config": merged,
                    },
                )
            except TelegramForbiddenError:
                await msg.answer("❌无法私信您，请先私聊我发送 /start 启动机器人。")
            return

        if intent_type == "apikey_set":
            if not await ensure_private(msg):
                return
            api_key = (intent_data.get("api_key") or "").strip()
            if not api_key:
                await msg.answer("❌缺少 API Key，请提供完整 Key。")
                return

            provider = (intent_data.get("api_provider") or "").strip().lower()
            llm_model = (intent_data.get("llm_model") or "").strip()
            if not provider and llm_model and "/" in llm_model:
                provider = llm_model.split("/", 1)[0].strip().lower()

            resolved_model = _resolve_model_for_provider(provider, llm_model)

            lines = ["即将更新 API Key："]
            if provider:
                lines.append(f"- Provider: {provider}")
            if resolved_model:
                lines.append(f"- Model: {resolved_model}")
            if not provider and not resolved_model:
                lines.append("- Provider/Model: 未指定，沿用当前配置")
            lines.append("是否确认？")
            confirm_text = "\n".join(lines)

            kb = build_confirm_keyboard("action:confirm", "action:cancel")
            try:
                await msg.bot.send_message(chat_id=user_id, text=confirm_text, reply_markup=kb)
                from aiogram.fsm.storage.base import StorageKey

                key = StorageKey(bot_id=bot_id_getter(), chat_id=user_id, user_id=user_id)
                await dispatcher.storage.set_state(key, ActionState.confirming)
                await dispatcher.storage.set_data(
                    key,
                    {
                        "action_type": "apikey_set",
                        "api_key": api_key,
                        "api_provider": provider,
                        "llm_model": resolved_model,
                    },
                )
            except TelegramForbiddenError:
                await msg.answer("❌无法私信您，请先私聊我发送 /start 启动机器人。")
            return

        if intent_type != "config_change":
            if is_private:
                await msg.answer("抱歉，我无法理解您的请求，请尝试换一种说法。")
            return

        partial_new_cfg = intent_data.get("config_changes")
        if not partial_new_cfg:
            await msg.answer("⚠️ LLM 返回配置为空，请重试。")
            return

        new_cfg = current_cfg.copy()
        new_cfg.update(partial_new_cfg)

        is_valid, valid_err = validate_config(new_cfg)
        if not is_valid:
            err_text = f"⚠️ 配置解析异常：{valid_err}。请重试或更详细描述。"
            if is_private:
                await msg.answer(err_text)
            else:
                try:
                    await msg.bot.send_message(user_id, err_text)
                except Exception:
                    pass
            return

        if new_cfg == current_cfg:
            no_change_text = "您的配置已经是这个状态了，无需修改。"
            if is_private:
                await msg.answer(no_change_text)
            else:
                try:
                    await msg.bot.send_message(user_id, no_change_text)
                except Exception:
                    pass
            return

        changes_text = "根据您的描述，建议进行以下调整：\n\n"

        if new_cfg["priority"] != current_cfg["priority"]:
            changes_text += (
                "📊 [优先级调整]\n"
                f"   旧：{' > '.join(EVENT_CN.get(x, x) for x in current_cfg['priority'])}\n"
                f"   新：{' > '.join(EVENT_CN.get(x, x) for x in new_cfg['priority'])}\n\n"
            )

        added_blocks = set(new_cfg["block_keywords"]) - set(current_cfg["block_keywords"])
        removed_blocks = set(current_cfg["block_keywords"]) - set(new_cfg["block_keywords"])
        if added_blocks or removed_blocks:
            changes_text += "🚫 [屏蔽词变更]\n"
            if added_blocks:
                changes_text += f"   新增：{', '.join(added_blocks)}\n"
            if removed_blocks:
                changes_text += f"   移除：{', '.join(removed_blocks)}\n"
            changes_text += "\n"

        added_allows = set(new_cfg["allow_keywords"]) - set(current_cfg["allow_keywords"])
        removed_allows = set(current_cfg["allow_keywords"]) - set(new_cfg["allow_keywords"])
        if added_allows or removed_allows:
            changes_text += "✅ [白名单变更]\n"
            if added_allows:
                changes_text += f"   新增：{', '.join(added_allows)}\n"
            if removed_allows:
                changes_text += f"   移除：{', '.join(removed_allows)}\n"
            changes_text += "\n"

        kb = build_confirm_keyboard("config:confirm", "config:cancel")

        try:
            await msg.bot.send_message(chat_id=user_id, text=changes_text, reply_markup=kb)
            from aiogram.fsm.storage.base import StorageKey

            key = StorageKey(bot_id=bot_id_getter(), chat_id=user_id, user_id=user_id)
            await dispatcher.storage.set_state(key, ConfigState.confirming)
            await dispatcher.storage.set_data(key, {"new_config": new_cfg})
        except TelegramForbiddenError:
            await msg.answer("❌无法私信您，请先私聊我发送 /start 启动机器人。")

    @router.callback_query(F.data.startswith("config:"))
    async def config_confirm_cb(cb: CallbackQuery, state: FSMContext):
        action = cb.data.split(":")[1]

        if action == "cancel":
            await cb.message.edit_text("已取消修改。")
            await state.clear()
            await cb.answer("已取消")
            return

        if action != "confirm":
            await cb.answer()
            return

        data = await state.get_data()
        new_cfg = data.get("new_config")

        if not new_cfg:
            await cb.message.edit_text("⚠️ 配置数据已过期，请重新发起请求。")
            await cb.answer("数据过期")
            return

        await save_config(cb.from_user.id, new_cfg)
        await scheduler_service.refresh_user_schedule(cb.message.bot, cb.from_user.id)
        await cb.message.edit_text("✅配置已更新成功！")
        await state.clear()
        await cb.answer("更新成功")

    @router.callback_query(F.data.startswith("schedule:"))
    async def schedule_confirm_cb(cb: CallbackQuery, state: FSMContext):
        action = cb.data.split(":")[1]

        if action == "cancel":
            await cb.message.edit_text("已取消更新。")
            await state.clear()
            await cb.answer("已取消")
            return

        if action != "confirm":
            await cb.answer()
            return

        data = await state.get_data()
        new_cfg = data.get("schedule_config")
        times = data.get("schedule_times") or []

        if not new_cfg:
            await cb.message.edit_text("⚠️ 配置数据已过期，请重新发起请求。")
            await cb.answer("数据过期")
            return

        await save_config(cb.from_user.id, new_cfg)
        await scheduler_service.refresh_user_schedule(cb.message.bot, cb.from_user.id)
        times_text = "、".join(times) if times else "未设置"
        await cb.message.edit_text(
            f"✅已更新推送计划：每天推送 {len(times)} 次，时间为 {times_text}"
        )
        await state.clear()
        await cb.answer("更新成功")

    @router.callback_query(F.data.startswith("action:"))
    async def action_confirm_cb(cb: CallbackQuery, state: FSMContext):
        action = cb.data.split(":")[1]

        if action == "cancel":
            await cb.message.edit_text("已取消操作。")
            await state.clear()
            await cb.answer("已取消")
            return

        if action != "confirm":
            await cb.answer()
            return

        data = await state.get_data()
        action_type = data.get("action_type")

        if not action_type:
            await cb.message.edit_text("⚠️ 操作数据已过期，请重新发起。")
            await cb.answer("数据过期")
            return

        if action_type == "rss_add":
            rss_url = data.get("rss_url")
            if not rss_url:
                await cb.message.edit_text("⚠️ RSS 地址缺失，请重试。")
            else:
                status_msg = await cb.message.edit_text("⏳ 正在添加并尝试抓取...")
                success = await add_user_source(cb.from_user.id, rss_url)
                if not success:
                    await status_msg.edit_text("❌添加失败，可能是已存在该订阅。")
                else:
                    fetch_ok = await fetch_single_rss(rss_url)
                    if fetch_ok:
                        await status_msg.edit_text(f"✅成功添加订阅：{rss_url}\n首次抓取成功。")
                    else:
                        await status_msg.edit_text(
                            f"✅成功添加订阅：{rss_url}\n但首次抓取失败，请稍后重试。"
                        )

        elif action_type == "rss_remove":
            rss_url = data.get("rss_url")
            if not rss_url:
                await cb.message.edit_text("⚠️ RSS 地址缺失，请重试。")
            else:
                success = await delete_user_source(cb.from_user.id, rss_url)
                if success:
                    await cb.message.edit_text(f"✅已取消订阅：{rss_url}")
                else:
                    await cb.message.edit_text("❌取消订阅失败，未找到该订阅。")

        elif action_type == "import_config":
            new_cfg = data.get("config")
            if not isinstance(new_cfg, dict):
                await cb.message.edit_text("⚠️ 配置数据已过期，请重试。")
            else:
                await save_config(cb.from_user.id, new_cfg)
                await scheduler_service.refresh_user_schedule(cb.message.bot, cb.from_user.id)
                await cb.message.edit_text("✅配置导入成功。")

        elif action_type == "apikey_set":
            api_key = data.get("api_key")
            api_provider = data.get("api_provider")
            llm_model = data.get("llm_model")
            if not api_key:
                await cb.message.edit_text("⚠️ API Key 缺失，请重试。")
            else:
                cfg = await get_config(cb.from_user.id)
                cfg["api_key"] = api_key
                if api_provider:
                    cfg["api_provider"] = api_provider
                if llm_model:
                    cfg["llm_model"] = llm_model
                elif api_provider and not cfg.get("llm_model"):
                    cfg["llm_model"] = DEFAULT_MODEL_BY_PROVIDER.get(api_provider, core_config.LLM_MODEL)
                await save_config(cb.from_user.id, cfg)
                await cb.message.edit_text("✅API Key 已保存，后续请求将优先使用您的 Key。")

        else:
            await cb.message.edit_text("⚠️ 未知操作类型。")

        await state.clear()
        await cb.answer("完成")

    return router
