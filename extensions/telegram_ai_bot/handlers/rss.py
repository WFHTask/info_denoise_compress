from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import Message
from core.db import add_user_source, delete_user_source, get_user_sources
from services.rss_service import fetch_single_rss

router = Router()

@router.message(Command("add_rss"))
async def add_rss(msg: Message):
    url = msg.text.replace("/add_rss", "", 1).strip()
    if not url:
        await msg.answer("用法：/add_rss <RSS地址>")
        return
    
    # 简单校验
    if not url.startswith("http"):
        await msg.answer("❌ 请输入有效的 HTTP/HTTPS URL")
        return

    user_id = msg.from_user.id
    status_msg = await msg.answer("⏳ 正在添加并尝试抓取...")
    
    success = await add_user_source(user_id, url)
    if not success:
        await status_msg.edit_text("❌ 添加失败，可能是已存在该订阅。")
        return

    # 尝试立即抓取
    fetch_ok = await fetch_single_rss(url)
    if fetch_ok:
        await status_msg.edit_text(f"✅ 成功添加订阅：{url}\n首次抓取成功！")
    else:
        await status_msg.edit_text(f"✅ 成功添加订阅：{url}\n但首次抓取失败，稍后重试。")

@router.message(Command("remove_rss"))
async def remove_rss(msg: Message):
    url = msg.text.replace("/remove_rss", "", 1).strip()
    if not url:
        await msg.answer("用法：/remove_rss <RSS地址>")
        return
        
    user_id = msg.from_user.id
    success = await delete_user_source(user_id, url)
    if success:
        await msg.answer(f"✅ 已取消订阅：{url}")
    else:
        await msg.answer("❌ 取消订阅失败，未找到该订阅。")

@router.message(Command("list_rss"))
async def list_rss(msg: Message):
    user_id = msg.from_user.id
    sources = await get_user_sources(user_id)
    if not sources:
        await msg.answer("📭 您当前没有订阅任何 RSS 源。")
        return
        
    text = "📋 **您的 RSS 订阅列表**：\n\n"
    for i, s in enumerate(sources, 1):
        name = s.get('name') or '未命名'
        text += f"{i}. {s['url']} ({name})\n"
        
    await msg.answer(text)
