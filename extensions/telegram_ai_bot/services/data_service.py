import sqlite3
import asyncio
import os
import datetime
import re
import logging
from typing import List, Dict
from core import config

logger = logging.getLogger(__name__)

OUTPUT_DIR = config.OUTPUT_DIR
_GLOBAL_FILTER_PATH = config.BOT_ROOT.parent / "config" / "frequency_words.txt"


def _load_global_filter_keywords() -> list[str]:
    if not _GLOBAL_FILTER_PATH.exists():
        return []
    data = None
    for enc in ("utf-8", "gbk"):
        try:
            data = _GLOBAL_FILTER_PATH.read_text(encoding=enc)
            break
        except Exception:
            continue
    if data is None:
        return []
    lines = []
    in_global = False
    for raw in data.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            in_global = line == "[GLOBAL_FILTER]"
            continue
        if not in_global:
            continue
        if "=>" in line:
            continue
        lines.append(line)
    keywords = []
    for item in lines:
        for token in re.split(r"[\\s,;]+", item):
            token = token.strip()
            if token:
                keywords.append(token.lower())
    return list(dict.fromkeys(keywords))


GLOBAL_NOISE_KEYWORDS = _load_global_filter_keywords()

# Web3 事件分类规则（基于关键词匹配）
EVENT_PATTERNS = {
    "security": [
        r"漏洞|exploit|hack|攻击|盗币|安全|vulnerability|breach",
        r"black hat|white hat|audit|审计",
    ],
    "funding": [
        r"融资|funding|投资|raised|series [A-Z]|\$\d+[MB]",
        r"领投|跟投|天使轮|pre-seed|seed round",
    ],
    "protocol": [
        r"上线|launch|升级|upgrade|v\d+\.\d+|发布|release",
        r"主网|testnet|合约|protocol|更新|update",
    ],
    "regulation": [
        r"监管|regulation|SEC|政策|policy|禁令|ban|合规|compliance",
        r"法案|bill|听证会|hearing",
    ],
}

# Web3 噪音过滤规则
NOISE_PATTERNS = [
    r"空投|airdrop|giveaway|免费领取|白名单",
    r"教程|如何|怎么|指南|攻略",
    r"带货|推广|广告|赞助|sponsored",
]


def classify_event(title: str) -> str:
    """基于标题判断事件类型"""
    title_lower = title.lower()

    for event_type, patterns in EVENT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, title_lower):
                return event_type

    return "other"


def is_noise(title: str) -> bool:
    """判断是否为噪音信息"""
    title_lower = title.lower()

    for pattern in NOISE_PATTERNS:
        if re.search(pattern, title_lower):
            return True
    for keyword in GLOBAL_NOISE_KEYWORDS:
        if keyword and keyword in title_lower:
            return True
    return False


def get_latest_db_path(subdir: str = "news") -> str:
    """获取指定子目录下最新的数据库文件路径"""
    base_dir = os.path.join(OUTPUT_DIR, subdir)
    if not os.path.exists(base_dir):
        return None
    files = [f for f in os.listdir(base_dir) if f.endswith(".db")]
    if not files:
        return None
    # 按文件名（日期）排序，取最新的
    files.sort(reverse=True)
    return os.path.join(base_dir, files[0])


def _get_recent_db_paths(subdir: str, days: int) -> list[str]:
    base_dir = os.path.join(OUTPUT_DIR, subdir)
    if not os.path.exists(base_dir):
        return []
    files = [f for f in os.listdir(base_dir) if f.endswith(".db")]
    if not files:
        return []
    today = datetime.datetime.now().date()
    candidates = []
    for name in files:
        stem = os.path.splitext(name)[0]
        try:
            file_date = datetime.datetime.strptime(stem, "%Y-%m-%d").date()
        except ValueError:
            continue
        if (today - file_date).days <= days:
            candidates.append((file_date, os.path.join(base_dir, name)))
    candidates.sort(reverse=True)
    return [p for _, p in candidates]


def _get_todays_news_sync(limit: int = 100) -> List[Dict]:
    db_path = get_latest_db_path("news")
    if not db_path:
        return []

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 按 rank 排序，获取前 limit 条
        cursor.execute(
            """
            SELECT title, url, platform_id, rank, created_at
            FROM news_items
            ORDER BY rank ASC, created_at DESC
            LIMIT ?
            """,
            (limit,),
        )

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]
    except Exception as e:
        logger.exception("Error reading DB %s: %s", db_path, e)
        return []


async def get_todays_news(limit: int = 100) -> List[Dict]:
    """读取今日（或最新）的热榜新闻"""
    return await asyncio.to_thread(_get_todays_news_sync, limit)


def _get_recent_news_sync(days: int = 7, limit: int = 200) -> List[Dict]:
    db_paths = _get_recent_db_paths("news", days)
    if not db_paths:
        return []
    results: list[dict] = []
    for db_path in db_paths:
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT title, url, platform_id, rank, created_at
                FROM news_items
                ORDER BY rank ASC, created_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            conn.close()
            results.extend([dict(row) for row in rows])
            if len(results) >= limit:
                break
        except Exception as e:
            logger.exception("Error reading DB %s: %s", db_path, e)
            continue
    return results[:limit]


async def get_recent_news(days: int = 7, limit: int = 200) -> List[Dict]:
    """读取最近 N 天的热榜新闻"""
    return await asyncio.to_thread(_get_recent_news_sync, days, limit)


def filter_news(items: List[Dict], config: Dict) -> tuple[List[Dict], Dict]:
    """
    增强版过滤 Web3 降噪 + 用户配置
    返回: (filtered_items, stats_dict)
    """
    block_keywords = config.get("block_keywords", [])
    if not isinstance(block_keywords, list):
        block_keywords = []
    # 预处理屏蔽词为小写
    block_keywords = [k.lower() for k in block_keywords if k]

    allow_keywords = config.get("allow_keywords", [])
    if not isinstance(allow_keywords, list):
        allow_keywords = []
    allow_keywords = [k.lower() for k in allow_keywords if k]

    priority = config.get("priority", [])
    enable_noise_filter = config.get("enable_noise_filter", True)  # 默认开启
    filtered = []
    stats = {
        "total": len(items),
        "kept": 0,
        "dropped": 0,
        "dropped_noise": 0,
        "dropped_block": 0,
        "dropped_details": [],
    }

    for item in items:
        item = dict(item)
        title = item.get("title", "")
        if not title:
            continue

        title_lower = title.lower()

        # 0. 检查是否为订阅源（跳过噪音过滤）
        is_subscribed = item.get("is_subscribed", False)

        # 1. 噪音过滤（开启且非订阅源）
        if enable_noise_filter and not is_subscribed and is_noise(title):
            stats["dropped"] += 1
            stats["dropped_noise"] += 1
            continue

        # 2. 用户屏蔽词（忽略大小写）
        is_blocked = any(bk in title_lower for bk in block_keywords)
        if is_blocked:
            stats["dropped"] += 1
            stats["dropped_block"] += 1
            continue

        # 3. 事件分类
        event_type = classify_event(title)
        item["event_type"] = event_type

        # 4. 白名单强制保留
        has_allow_keyword = any(ak in title_lower for ak in allow_keywords)
        if has_allow_keyword or is_subscribed:
            item["priority_score"] = 100
            filtered.append(item)
            stats["kept"] += 1
            continue

        # 5. 根据用户优先级打分
        if event_type in priority:
            item["priority_score"] = (4 - priority.index(event_type)) * 10
        else:
            item["priority_score"] = 1

        filtered.append(item)
        stats["kept"] += 1

    # 按优先级和排名排序
    filtered.sort(key=lambda x: (x.get("priority_score", 0), -x.get("rank", 999)), reverse=True)

    return filtered, stats


def get_signal_summary(items: List[Dict]) -> Dict:
    """生成信号统计摘要"""
    stats = {
        "total": len(items),
        "by_type": {},
        "high_priority": [],
        "platforms": set(),
    }

    for item in items:
        event_type = item.get("event_type", "other")
        stats["by_type"][event_type] = stats["by_type"].get(event_type, 0) + 1

        if item.get("priority_score", 0) >= 30:
            stats["high_priority"].append(item)

        stats["platforms"].add(item.get("platform_id", "unknown"))

    stats["platforms"] = list(stats["platforms"])
    return stats
