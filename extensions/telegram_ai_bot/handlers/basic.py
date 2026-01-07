from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from core.db import add_user_source, get_config, get_user_sources, save_config
from core.formatting import escape_markdown_v2
from services import data_service, scheduler_service
from services.llm_service import generate_brief
from services.rss_service import get_user_rss_items

router = Router()

EVENT_CN = {
    "security": "安全事件",
    "funding": "融资",
    "protocol": "协议/产品更新",
    "regulation": "监管/政策",
}


def pref_keyboard(priority):
    rows = []
    for i, key in enumerate(priority):
        up = InlineKeyboardButton(text="⬆️", callback_data=f"pref:up:{i}")
        down = InlineKeyboardButton(text="⬇️", callback_data=f"pref:down:{i}")
        rows.append(
            [
                InlineKeyboardButton(text=f"{i+1}. {EVENT_CN.get(key, key)}", callback_data="noop"),
                up,
                down,
            ]
        )
    rows.append([InlineKeyboardButton(text="✅保存", callback_data="pref:save")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Command("start"))
async def start(msg: Message):
    user_id = msg.from_user.id
    cfg = await get_config(user_id)
    await save_config(user_id, cfg)
    await scheduler_service.refresh_user_schedule(msg.bot, user_id)
    brief_times = scheduler_service.get_brief_times(cfg)

    user_sources = await get_user_sources(user_id)
    if not user_sources:
        defaults = [
            ("https://cointelegraph.com/rss", "Cointelegraph"),
            ("https://me.news/rss", "ME News (MarsBit)"),
            ("https://rsshub.app/chaincatcher/news", "ChainCatcher (RSSHub)"),
            ("https://rsshub.app/techflow/news", "TechFlow (RSSHub)"),
        ]
        added_count = 0
        for url, name in defaults:
            if await add_user_source(user_id, url, name):
                added_count += 1
        if added_count > 0:
            await msg.answer(f"✅已为您初始化 {added_count} 个 Web3 默认订阅源。")

    text = (
        "已连接 Trend 配置 Bot。\n\n"
        f"当前优先级：{' > '.join(EVENT_CN.get(x, x) for x in cfg['priority'])}\n"
        f"屏蔽词：{', '.join(cfg['block_keywords']) or '（无）'}\n"
        f"白名单：{', '.join(cfg['allow_keywords']) or '（无）'}\n\n"
        f"定时推送：每天 {len(brief_times)} 次，时间为 {'、'.join(brief_times)}\n\n"
        "🔧 基础命令：\n"
        "/pref  调整优先级\n"
        "/block <词>  添加屏蔽词\n"
        "/allow <词>  添加白名单词\n"
        "/noise <on/off>  开关智能降噪\n"
        "/preview  生成今日 Web3 信号简报\n\n"
        "📡 RSS 订阅：\n"
        "/add_rss <url>  添加 RSS 订阅源\n"
        "/list_rss  查看已订阅列表\n"
        "/remove_rss <url>  移除订阅\n\n"
        "⏰ 定时推送：\n"
        "可直接聊天设置，例如：\n"
        "“每天 9 点和 18 点推送简报”\n"
        "“每天推送 2 次”\n\n"
        "⚙️ 高级配置：\n"
        "/rules  查看完整配置 JSON\n"
        "/export  导出配置文件\n"
        "/import  导入配置（回复 JSON 或发送内容）\n"
        "/apikey <key>\n"
        "/apikey <provider> <key>\n"
        "/apikey <provider> <key> <model>\n\n"
        "💬 也可以直接聊天控制以上功能。"
    )
    await msg.answer(text)


@router.message(Command("pref"))
async def pref(msg: Message):
    cfg = await get_config(msg.from_user.id)
    await msg.answer("调整简报优先级：", reply_markup=pref_keyboard(cfg["priority"]))


@router.callback_query(F.data.startswith("pref:"))
async def pref_cb(cb: CallbackQuery):
    user_id = cb.from_user.id
    cfg = await get_config(user_id)
    parts = cb.data.split(":")
    action = parts[1]

    if action in ("up", "down"):
        idx = int(parts[2])
        pr = cfg["priority"]
        changed = False
        if action == "up" and idx > 0:
            pr[idx - 1], pr[idx] = pr[idx], pr[idx - 1]
            changed = True
        if action == "down" and idx < len(pr) - 1:
            pr[idx + 1], pr[idx] = pr[idx], pr[idx + 1]
            changed = True

        if changed:
            cfg["priority"] = pr
            await save_config(user_id, cfg)
            await cb.message.edit_reply_markup(reply_markup=pref_keyboard(pr))

        await cb.answer()
        return

    if action == "save":
        await cb.answer("已保存")
        await cb.message.edit_text("✅优先级已保存。")
        return


@router.message(Command("block"))
async def block(msg: Message):
    term = msg.text.replace("/block", "", 1).strip()
    if not term:
        await msg.answer("用法：/block <关键词>")
        return
    cfg = await get_config(msg.from_user.id)
    if term not in cfg["block_keywords"]:
        cfg["block_keywords"].append(term)
    await save_config(msg.from_user.id, cfg)
    await msg.answer(f"✅已添加屏蔽词：{term}")


@router.message(Command("allow"))
async def allow(msg: Message):
    term = msg.text.replace("/allow", "", 1).strip()
    if not term:
        await msg.answer("用法：/allow <关键词>")
        return
    cfg = await get_config(msg.from_user.id)
    if term not in cfg["allow_keywords"]:
        cfg["allow_keywords"].append(term)
    await save_config(msg.from_user.id, cfg)
    await msg.answer(f"✅已添加白名单词：{term}")


@router.message(Command("noise"))
async def toggle_noise(msg: Message):
    arg = msg.text.replace("/noise", "", 1).strip().lower()
    if arg not in ("on", "off"):
        await msg.answer("用法：/noise on（开启降噪）或 /noise off（关闭降噪）")
        return

    cfg = await get_config(msg.from_user.id)
    is_on = arg == "on"
    cfg["enable_noise_filter"] = is_on
    await save_config(msg.from_user.id, cfg)

    state_text = "✅已开启" if is_on else "🚫 已关闭"
    await msg.answer(
        f"{state_text} Web3 智能降噪过滤。\n\n"
        "开启后会自动过滤空投、广告、教程等低价值信息。"
    )


async def execute_preview(msg: Message, user_id: int):
    status_msg = await msg.answer("🔍 正在读取今日热榜数据...")

    cfg = await get_config(user_id)
    events = await data_service.get_todays_news(limit=100)

    user_sources = await get_user_sources(user_id)
    if user_sources:
        source_urls = [s["url"] for s in user_sources]
        rss_items = await get_user_rss_items(source_urls, limit=50)
        for item in rss_items:
            item["platform_id"] = "RSS"
            item["rank"] = 0
            item["is_subscribed"] = True
            events.append(item)

    if not events:
        await status_msg.edit_text("⚠️ 今日暂无数据，请稍后再试。")
        return

    filtered_events, stats = data_service.filter_news(events, cfg)

    stats_text = escape_markdown_v2(
        f"🔍 扫描: {stats['total']} | ✅保留: {stats['kept']} | 🗑️过滤: {stats['dropped']}\n"
        f"(其中: 噪音 {stats['dropped_noise']}, 屏蔽词 {stats['dropped_block']})"
    )

    if not filtered_events:
        prefix = escape_markdown_v2("⚠️ 今日暂无符合条件的新闻。\n\n")
        await status_msg.edit_text(f"{prefix}{stats_text}", parse_mode="MarkdownV2")
        return

    prefix = escape_markdown_v2("🤖 正在生成智能简报...\n\n")
    await status_msg.edit_text(f"{prefix}{stats_text}", parse_mode="MarkdownV2")

    brief_text, err = await generate_brief(
        filtered_events,
        cfg,
        api_key=cfg.get("api_key"),
        model=cfg.get("llm_model"),
    )
    if err:
        await status_msg.edit_text(f"❌生成简报失败：{err}")
        return

    final_text = f"{stats_text}\n\n{brief_text}"
    try:
        await status_msg.edit_text(final_text, parse_mode="MarkdownV2")
    except Exception:
        if len(final_text) > 4000:
            await status_msg.edit_text(final_text[:4000] + "\n...(截断)", parse_mode="MarkdownV2")
        else:
            await status_msg.edit_text(final_text, parse_mode="MarkdownV2")


@router.message(Command("preview"))
async def preview(msg: Message):
    await execute_preview(msg, msg.from_user.id)
