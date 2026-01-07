import asyncio
import logging
import os
import sqlite3
import datetime
import feedparser
import urllib.request
import time
import gzip
import zlib
import io
from core.db import get_all_unique_sources
from core import config

logger = logging.getLogger(__name__)

OUTPUT_DIR = config.OUTPUT_DIR

def _build_opener():
    proxy_url = config.PROXY_URL
    if not proxy_url:
        return urllib.request.build_opener()
    handler = urllib.request.ProxyHandler({
        "http": proxy_url,
        "https": proxy_url,
    })
    return urllib.request.build_opener(handler)

def get_today_rss_db_path():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    rss_dir = os.path.join(OUTPUT_DIR, "rss")
    os.makedirs(rss_dir, exist_ok=True)
    return os.path.join(rss_dir, f"{today}.db")


def _get_recent_rss_db_paths(days: int = 7) -> list[str]:
    rss_dir = os.path.join(OUTPUT_DIR, "rss")
    if not os.path.exists(rss_dir):
        return []
    files = [f for f in os.listdir(rss_dir) if f.endswith(".db")]
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
            candidates.append((file_date, os.path.join(rss_dir, name)))
    candidates.sort(reverse=True)
    return [p for _, p in candidates]

def init_rss_db(db_path):
    conn = sqlite3.connect(db_path)
    # Replicate rss_schema.sql structure
    conn.execute("""
    CREATE TABLE IF NOT EXISTS rss_feeds (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        feed_url TEXT DEFAULT '',
        is_active INTEGER DEFAULT 1,
        last_fetch_time TEXT,
        last_fetch_status TEXT,
        item_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS rss_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        feed_id TEXT NOT NULL,
        url TEXT NOT NULL,
        published_at TEXT,
        summary TEXT,
        author TEXT,
        first_crawl_time TEXT NOT NULL,
        last_crawl_time TEXT NOT NULL,
        crawl_count INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (feed_id) REFERENCES rss_feeds(id)
    )
    """)
    # Unique index for deduplication
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_rss_url_feed ON rss_items(url, feed_id)")
    conn.commit()
    conn.close()

def _download_feed_data(url: str):
    """Helper to download feed data with retry and gzip handling"""
    opener = _build_opener()
    for i in range(config.RSS_RETRY + 1):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": config.RSS_USER_AGENT,
                "Accept-Encoding": "gzip, deflate"
            })
            with opener.open(req, timeout=config.RSS_TIMEOUT) as resp:
                data = resp.read()
                encoding = resp.info().get('Content-Encoding')
                if encoding == 'gzip':
                    data = gzip.decompress(data)
                elif encoding == 'deflate':
                    data = zlib.decompress(data)
            return feedparser.parse(data)
        except Exception as e:
            if i < config.RSS_RETRY:
                time.sleep(1)
            else:
                raise e
    return None

def _fetch_single_rss_sync(url: str) -> bool:
    try:
        db_path = get_today_rss_db_path()
        init_rss_db(db_path)
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        now_str = datetime.datetime.now().strftime("%H:%M")
        
        logger.info("Fetching single %s...", url)
        try:
            feed = _download_feed_data(url)
        except Exception as e:
            # Should be handled inside, but if raised:
            logger.error("Failed to fetch %s: %s", url, e)
            conn.close()
            return False
            
        if not feed or not feed.entries:
             logger.warning("No entries found for %s", url)
        
        feed_id = url
        feed_title = feed.feed.get('title', url)
        
        cursor.execute("""
            INSERT INTO rss_feeds (id, name, feed_url, last_fetch_time, last_fetch_status)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET 
                last_fetch_time=excluded.last_fetch_time,
                last_fetch_status=excluded.last_fetch_status,
                name=excluded.name
        """, (feed_id, feed_title, url, now_str, 'success'))
        
        for entry in feed.entries:
            title = entry.get('title', 'No Title')
            link = entry.get('link', '')
            if not link: continue
            
            published = entry.get('published', entry.get('updated', ''))
            summary = entry.get('summary', entry.get('description', ''))
            author = entry.get('author', '')
            
            try:
                cursor.execute("""
                    INSERT INTO rss_items (
                        title, feed_id, url, published_at, summary, author, 
                        first_crawl_time, last_crawl_time, crawl_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """, (title, feed_id, link, published, summary, author, now_str, now_str))
            except sqlite3.IntegrityError:
                cursor.execute("""
                    UPDATE rss_items SET 
                        last_crawl_time=?, 
                        crawl_count=crawl_count+1 
                    WHERE url=? AND feed_id=?
                """, (now_str, link, feed_id))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.exception("Error fetching single %s: %s", url, e)
        return False

async def fetch_single_rss(url: str):
    """Fetch a single RSS feed immediately"""
    return await asyncio.to_thread(_fetch_single_rss_sync, url)

def _get_user_rss_items_sync(source_urls: list, limit: int = 50) -> list:
    """Get RSS items for specific source URLs"""
    if not source_urls:
        return []
        
    db_path = get_today_rss_db_path()
    if not os.path.exists(db_path):
        return []
        
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        placeholders = ','.join(['?'] * len(source_urls))
        query = f"""
            SELECT title, url, feed_id, published_at, summary, author, created_at
            FROM rss_items
            WHERE feed_id IN ({placeholders})
            ORDER BY created_at DESC
            LIMIT ?
        """
        
        args = source_urls + [limit]
        cursor.execute(query, args)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    except Exception as e:
        logger.exception("Error reading RSS DB: %s", e)
        return []

async def get_user_rss_items(source_urls: list, limit: int = 50) -> list:
    return await asyncio.to_thread(_get_user_rss_items_sync, source_urls, limit)


def _get_recent_user_rss_items_sync(source_urls: list, days: int = 7, limit: int = 200) -> list:
    if not source_urls:
        return []
    db_paths = _get_recent_rss_db_paths(days)
    if not db_paths:
        return []
    results = []
    seen = set()
    for db_path in db_paths:
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            placeholders = ",".join(["?"] * len(source_urls))
            query = f"""
                SELECT title, url, feed_id, published_at, summary, author, created_at
                FROM rss_items
                WHERE feed_id IN ({placeholders})
                ORDER BY created_at DESC
                LIMIT ?
            """
            args = source_urls + [limit]
            cursor.execute(query, args)
            rows = cursor.fetchall()
            conn.close()
            for row in rows:
                item = dict(row)
                key = (item.get("url"), item.get("feed_id"))
                if key in seen:
                    continue
                seen.add(key)
                results.append(item)
                if len(results) >= limit:
                    break
            if len(results) >= limit:
                break
        except Exception as e:
            logger.exception("Error reading RSS DB %s: %s", db_path, e)
            continue
    return results[:limit]


async def get_recent_user_rss_items(source_urls: list, days: int = 7, limit: int = 200) -> list:
    return await asyncio.to_thread(_get_recent_user_rss_items_sync, source_urls, days, limit)

def _fetch_and_save_rss_sync(urls: list[str]):
    if not urls:
        logger.info("No user RSS sources found.")
        return

    db_path = get_today_rss_db_path()
    init_rss_db(db_path)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    now_str = datetime.datetime.now().strftime("%H:%M")
    
    for url in urls:
        try:
            logger.info("Fetching %s...", url)
            feed = _download_feed_data(url)
            
            if not feed:
                continue
            
            feed_id = url
            feed_title = feed.feed.get('title', url)
            
            cursor.execute("""
                INSERT INTO rss_feeds (id, name, feed_url, last_fetch_time, last_fetch_status)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET 
                    last_fetch_time=excluded.last_fetch_time,
                    last_fetch_status=excluded.last_fetch_status,
                    name=excluded.name
            """, (feed_id, feed_title, url, now_str, 'success'))
            
            count = 0
            for entry in feed.entries:
                title = entry.get('title', 'No Title')
                link = entry.get('link', '')
                if not link:
                    continue
                
                published = entry.get('published', entry.get('updated', ''))
                summary = entry.get('summary', entry.get('description', ''))
                author = entry.get('author', '')
                
                try:
                    cursor.execute("""
                        INSERT INTO rss_items (
                            title, feed_id, url, published_at, summary, author, 
                            first_crawl_time, last_crawl_time, crawl_count
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """, (title, feed_id, link, published, summary, author, now_str, now_str))
                    count += 1
                except sqlite3.IntegrityError:
                    cursor.execute("""
                        UPDATE rss_items SET 
                            last_crawl_time=?, 
                            crawl_count=crawl_count+1 
                        WHERE url=? AND feed_id=?
                    """, (now_str, link, feed_id))
            
            logger.info("Fetched %s items from %s", count, url)

        except Exception as e:
            logger.exception("Error fetching %s: %s", url, e)
            try:
                cursor.execute("""
                    INSERT INTO rss_feeds (id, name, feed_url, last_fetch_time, last_fetch_status)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET 
                        last_fetch_time=excluded.last_fetch_time,
                        last_fetch_status=excluded.last_fetch_status
                """, (url, url, url, now_str, 'failed'))
            except Exception:
                pass
            
    conn.commit()
    conn.close()
    logger.info("RSS fetch completed.")

async def fetch_and_save_rss():
    logger.info("Starting RSS fetch...")
    urls = await get_all_unique_sources()
    await asyncio.to_thread(_fetch_and_save_rss_sync, urls)

async def rss_fetcher_loop():
    while True:
        try:
            await fetch_and_save_rss()
        except Exception as e:
            logger.exception("Fetcher loop error: %s", e)
        await asyncio.sleep(1800) # 30 mins
