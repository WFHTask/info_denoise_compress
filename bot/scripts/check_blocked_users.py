"""
静默检测哪些用户已屏蔽 bot（不发送任何消息）

原理：调用 Telegram Bot API 的 sendChatAction 方法（typing 动作），
被屏蔽的用户会返回 403 Forbidden，正常用户几乎无感知（typing 状态几秒后自动消失）。

用法（从项目根目录运行）：
  cd /home/ubuntu/github-projects/info_denoise_compress
  sudo DATA_DIR=./data python3 bot/scripts/check_blocked_users.py
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import TELEGRAM_BOT_TOKEN, USERS_FILE

import httpx


async def check_user_blocked(client: httpx.AsyncClient, token: str, telegram_id: str) -> dict:
    """Check if a user has blocked the bot using sendChatAction (minimal disturbance)."""
    url = f"https://api.telegram.org/bot{token}/sendChatAction"
    try:
        resp = await client.post(url, json={"chat_id": telegram_id, "action": "typing"}, timeout=10)
        data = resp.json()
        if data.get("ok"):
            return {"id": telegram_id, "status": "active"}
        desc = data.get("description", "")
        if "blocked" in desc.lower() or "Forbidden" in desc:
            return {"id": telegram_id, "status": "blocked"}
        if "deactivated" in desc.lower():
            return {"id": telegram_id, "status": "deactivated"}
        if "not found" in desc.lower() or "chat not found" in desc.lower():
            return {"id": telegram_id, "status": "not_found"}
        return {"id": telegram_id, "status": "unknown", "detail": desc}
    except Exception as e:
        return {"id": telegram_id, "status": "error", "detail": str(e)}


async def main():
    if not TELEGRAM_BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN not set")
        sys.exit(1)

    with open(USERS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    users = data.get("users", [])
    print(f"Total registered users: {len(users)}")

    results = {"active": [], "blocked": [], "deactivated": [], "not_found": [], "unknown": [], "error": []}

    async with httpx.AsyncClient() as client:
        tasks = []
        for user in users:
            tid = user.get("telegram_id")
            if tid:
                tasks.append(check_user_blocked(client, TELEGRAM_BOT_TOKEN, str(tid)))

        checks = await asyncio.gather(*tasks)
        for r in checks:
            results[r["status"]].append(r["id"])

    print(f"\n{'='*50}")
    print(f"RESULT SUMMARY")
    print(f"{'='*50}")
    print(f"  Active users:      {len(results['active'])}")
    print(f"  Blocked users:     {len(results['blocked'])}")
    print(f"  Deactivated users: {len(results['deactivated'])}")
    print(f"  Not found:         {len(results['not_found'])}")
    print(f"  Unknown/Error:     {len(results['unknown']) + len(results['error'])}")

    if results["blocked"]:
        print(f"\nBlocked user IDs ({len(results['blocked'])}):")
        for uid in results["blocked"]:
            print(f"  - {uid}")

    if results["deactivated"]:
        print(f"\nDeactivated user IDs ({len(results['deactivated'])}):")
        for uid in results["deactivated"]:
            print(f"  - {uid}")


if __name__ == "__main__":
    asyncio.run(main())
