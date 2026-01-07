import aiosqlite
import json
import logging
import os
import base64
import hashlib
from typing import Any, Dict, List
from . import config
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

DB_PATH = config.DB_PATH

DEFAULT_CONFIG = {
    "priority": ["security", "funding", "protocol", "regulation"],
    "block_keywords": [],
    "allow_keywords": [],
    "enable_noise_filter": True,
    "sources": [],
    "daily_time": "09:00",  # 兼容旧配置
    "brief_times": ["09:00"],
    "brief_count": 1,
}

_FERNET = None
_SECRET = config.SECRET_KEY
if _SECRET:
    _key = base64.urlsafe_b64encode(hashlib.sha256(_SECRET.encode()).digest())
    _FERNET = Fernet(_key)


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
        CREATE TABLE IF NOT EXISTS user_config (
            user_id INTEGER PRIMARY KEY,
            config_json TEXT NOT NULL
        )
        """
        )
        await db.execute(
            """
        CREATE TABLE IF NOT EXISTS user_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            url TEXT NOT NULL,
            name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, url)
        )
        """
        )
        await db.commit()


async def add_user_source(user_id: int, url: str, name: str = None) -> bool:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO user_sources (user_id, url, name) VALUES (?, ?, ?)",
                (user_id, url, name),
            )
            await db.commit()
        return True
    except Exception as e:
        logger.exception("Error adding source: %s", e)
        return False


async def get_user_sources(user_id: int) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM user_sources WHERE user_id=?", (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def delete_user_source(user_id: int, url: str) -> bool:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM user_sources WHERE user_id=? AND url=?", (user_id, url))
            await db.commit()
        return True
    except Exception as e:
        logger.exception("Error deleting source: %s", e)
        return False


async def get_all_unique_sources() -> List[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT DISTINCT url FROM user_sources") as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]


async def get_all_user_ids() -> List[int]:
    """获取所有已配置的用户ID"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT DISTINCT user_id FROM user_config") as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]


async def get_config(user_id: int) -> Dict[str, Any]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT config_json FROM user_config WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        if not row:
            return DEFAULT_CONFIG.copy()
        cfg = json.loads(row[0])
        for key, value in DEFAULT_CONFIG.items():
            cfg.setdefault(key, value)
        v = cfg.get("api_key")
        if isinstance(v, str) and v.startswith("enc:") and _FERNET:
            try:
                token = v[4:].encode()
                plain = _FERNET.decrypt(token).decode()
                cfg["api_key"] = plain
            except Exception:
                cfg["api_key"] = None
        return cfg


async def save_config(user_id: int, config: Dict[str, Any]):
    cfg = dict(config or {})
    v = cfg.get("api_key")
    if isinstance(v, str) and v and _FERNET:
        if not v.startswith("enc:"):
            try:
                token = _FERNET.encrypt(v.encode()).decode()
                cfg["api_key"] = "enc:" + token
            except Exception:
                pass
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO user_config (user_id, config_json) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET config_json=excluded.config_json",
            (user_id, json.dumps(cfg, ensure_ascii=False)),
        )
        await db.commit()
