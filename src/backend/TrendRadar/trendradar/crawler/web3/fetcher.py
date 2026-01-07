# coding=utf-8
"""
Web3 信息源爬虫抓取器

负责从不提供 RSS 的 Web3 媒体网站抓取数据，支持：
- ChainCatcher (链捕手)
- ME News (MetaEra)
"""

import time
import random
import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any

import requests
from bs4 import BeautifulSoup

from trendradar.storage.base import RSSItem, RSSData
from trendradar.utils.time import get_configured_time, is_within_days, DEFAULT_TIMEZONE


@dataclass
class Web3FeedConfig:
    """Web3 信息源配置"""
    id: str                     # 源 ID
    name: str                   # 显示名称
    url: str                    # 网站 URL
    crawler_type: str           # 爬虫类型: chaincatcher, menews
    max_items: int = 50         # 最大条目数
    enabled: bool = True        # 是否启用
    max_age_days: Optional[int] = None  # 文章最大年龄（天）


@dataclass
class ParsedWeb3Item:
    """解析后的 Web3 新闻条目"""
    title: str
    url: str
    published_at: Optional[str] = None
    summary: Optional[str] = None
    author: Optional[str] = None
    guid: Optional[str] = None


class Web3Crawler(ABC):
    """Web3 爬虫基类"""

    # 默认请求头
    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
    }

    def __init__(
        self,
        timeout: int = 30,
        use_proxy: bool = False,
        proxy_url: str = "",
        max_retries: int = 3,
    ):
        """
        初始化爬虫

        Args:
            timeout: 请求超时（秒）
            use_proxy: 是否使用代理
            proxy_url: 代理 URL
            max_retries: 最大重试次数
        """
        self.timeout = timeout
        self.use_proxy = use_proxy
        self.proxy_url = proxy_url
        self.max_retries = max_retries
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """创建请求会话"""
        session = requests.Session()
        session.headers.update(self.DEFAULT_HEADERS)

        if self.use_proxy and self.proxy_url:
            session.proxies = {
                "http": self.proxy_url,
                "https": self.proxy_url,
            }

        return session

    def fetch_page(self, url: str) -> Optional[str]:
        """
        获取页面内容

        Args:
            url: 页面 URL

        Returns:
            页面 HTML 内容，失败返回 None
        """
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                response.encoding = response.apparent_encoding or 'utf-8'
                return response.text
            except requests.RequestException as e:
                if attempt < self.max_retries - 1:
                    wait_time = (attempt + 1) * 2 + random.uniform(0, 1)
                    print(f"[Web3] 请求失败: {e}, {wait_time:.1f}秒后重试...")
                    time.sleep(wait_time)
                else:
                    print(f"[Web3] 请求失败: {e}")
                    return None
        return None

    def fetch_json(self, url: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        获取 JSON 数据

        Args:
            url: API URL
            params: 请求参数

        Returns:
            JSON 数据，失败返回 None
        """
        for attempt in range(self.max_retries):
            try:
                headers = self.DEFAULT_HEADERS.copy()
                headers["Accept"] = "application/json"

                response = self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.timeout
                )
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ValueError) as e:
                if attempt < self.max_retries - 1:
                    wait_time = (attempt + 1) * 2 + random.uniform(0, 1)
                    print(f"[Web3] JSON 请求失败: {e}, {wait_time:.1f}秒后重试...")
                    time.sleep(wait_time)
                else:
                    print(f"[Web3] JSON 请求失败: {e}")
                    return None
        return None

    @abstractmethod
    def crawl(self, max_items: int = 50) -> List[ParsedWeb3Item]:
        """
        抓取新闻列表

        Args:
            max_items: 最大条目数

        Returns:
            解析后的新闻条目列表
        """
        pass

    @property
    @abstractmethod
    def source_id(self) -> str:
        """返回数据源 ID"""
        pass

    @property
    @abstractmethod
    def source_name(self) -> str:
        """返回数据源名称"""
        pass

    @staticmethod
    def clean_text(text: str) -> str:
        """清理文本"""
        if not text:
            return ""
        import re
        import html

        # 解码 HTML 实体
        text = html.unescape(text)
        # 移除多余空白
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    @staticmethod
    def generate_guid(url: str, title: str) -> str:
        """生成唯一标识"""
        content = f"{url}:{title}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()


class Web3Fetcher:
    """Web3 信息源抓取器"""

    def __init__(
        self,
        feeds: List[Web3FeedConfig],
        request_interval: int = 3000,
        timeout: int = 30,
        use_proxy: bool = False,
        proxy_url: str = "",
        timezone: str = DEFAULT_TIMEZONE,
        freshness_enabled: bool = True,
        default_max_age_days: int = 3,
    ):
        """
        初始化抓取器

        Args:
            feeds: Web3 源配置列表
            request_interval: 请求间隔（毫秒）
            timeout: 请求超时（秒）
            use_proxy: 是否使用代理
            proxy_url: 代理 URL
            timezone: 时区配置
            freshness_enabled: 是否启用新鲜度过滤
            default_max_age_days: 默认最大文章年龄（天）
        """
        self.feeds = [f for f in feeds if f.enabled]
        self.request_interval = request_interval
        self.timeout = timeout
        self.use_proxy = use_proxy
        self.proxy_url = proxy_url
        self.timezone = timezone
        self.freshness_enabled = freshness_enabled
        self.default_max_age_days = default_max_age_days

        # 爬虫实例缓存
        self._crawlers: Dict[str, Web3Crawler] = {}

    def _get_crawler(self, crawler_type: str) -> Optional[Web3Crawler]:
        """
        获取爬虫实例

        Args:
            crawler_type: 爬虫类型

        Returns:
            爬虫实例
        """
        if crawler_type in self._crawlers:
            return self._crawlers[crawler_type]

        crawler = None

        if crawler_type == "chaincatcher":
            from .chaincatcher import ChainCatcherCrawler
            crawler = ChainCatcherCrawler(
                timeout=self.timeout,
                use_proxy=self.use_proxy,
                proxy_url=self.proxy_url,
            )
        elif crawler_type == "menews":
            from .menews import MeNewsCrawler
            crawler = MeNewsCrawler(
                timeout=self.timeout,
                use_proxy=self.use_proxy,
                proxy_url=self.proxy_url,
            )

        if crawler:
            self._crawlers[crawler_type] = crawler

        return crawler

    def fetch_feed(self, feed: Web3FeedConfig) -> Tuple[List[RSSItem], Optional[str]]:
        """
        抓取单个 Web3 信息源

        Args:
            feed: 信息源配置

        Returns:
            (条目列表, 错误信息) 元组
        """
        try:
            crawler = self._get_crawler(feed.crawler_type)
            if not crawler:
                return [], f"未知的爬虫类型: {feed.crawler_type}"

            parsed_items = crawler.crawl(max_items=feed.max_items)

            # 转换为 RSSItem
            now = get_configured_time(self.timezone)
            crawl_time = now.strftime("%H:%M")
            items = []

            for parsed in parsed_items:
                item = RSSItem(
                    title=parsed.title,
                    feed_id=feed.id,
                    feed_name=feed.name,
                    url=parsed.url,
                    published_at=parsed.published_at or "",
                    summary=parsed.summary or "",
                    author=parsed.author or "",
                    crawl_time=crawl_time,
                    first_time=crawl_time,
                    last_time=crawl_time,
                    count=1,
                )
                items.append(item)

            print(f"[Web3] {feed.name}: 获取 {len(items)} 条")
            return items, None

        except Exception as e:
            error = f"抓取失败: {e}"
            print(f"[Web3] {feed.name}: {error}")
            return [], error

    def fetch_all(self) -> RSSData:
        """
        抓取所有 Web3 信息源

        Returns:
            RSSData 对象
        """
        all_items: Dict[str, List[RSSItem]] = {}
        id_to_name: Dict[str, str] = {}
        failed_ids: List[str] = []

        # 使用配置的时区
        now = get_configured_time(self.timezone)
        crawl_time = now.strftime("%H:%M")
        crawl_date = now.strftime("%Y-%m-%d")

        print(f"[Web3] 开始抓取 {len(self.feeds)} 个 Web3 信息源...")

        for i, feed in enumerate(self.feeds):
            # 请求间隔
            if i > 0:
                interval = self.request_interval / 1000
                jitter = random.uniform(-0.5, 0.5)
                time.sleep(interval + jitter)

            items, error = self.fetch_feed(feed)

            id_to_name[feed.id] = feed.name

            if error:
                failed_ids.append(feed.id)
            else:
                all_items[feed.id] = items

        total_items = sum(len(items) for items in all_items.values())
        print(f"[Web3] 抓取完成: {len(all_items)} 个源成功, {len(failed_ids)} 个失败, 共 {total_items} 条")

        return RSSData(
            date=crawl_date,
            crawl_time=crawl_time,
            items=all_items,
            id_to_name=id_to_name,
            failed_ids=failed_ids,
        )

    @classmethod
    def from_config(cls, config: Dict) -> "Web3Fetcher":
        """
        从配置字典创建抓取器

        Args:
            config: 配置字典

        Returns:
            Web3Fetcher 实例
        """
        freshness_config = config.get("freshness_filter", {})
        freshness_enabled = freshness_config.get("enabled", True)
        default_max_age_days = freshness_config.get("max_age_days", 3)

        feeds = []
        for feed_config in config.get("feeds", []):
            max_age_days_raw = feed_config.get("max_age_days")
            max_age_days = None
            if max_age_days_raw is not None:
                try:
                    max_age_days = int(max_age_days_raw)
                    if max_age_days < 0:
                        max_age_days = None
                except (ValueError, TypeError):
                    max_age_days = None

            feed = Web3FeedConfig(
                id=feed_config.get("id", ""),
                name=feed_config.get("name", ""),
                url=feed_config.get("url", ""),
                crawler_type=feed_config.get("crawler_type", ""),
                max_items=feed_config.get("max_items", 50),
                enabled=feed_config.get("enabled", True),
                max_age_days=max_age_days,
            )
            if feed.id and feed.crawler_type:
                feeds.append(feed)

        return cls(
            feeds=feeds,
            request_interval=config.get("request_interval", 3000),
            timeout=config.get("timeout", 30),
            use_proxy=config.get("use_proxy", False),
            proxy_url=config.get("proxy_url", ""),
            timezone=config.get("timezone", DEFAULT_TIMEZONE),
            freshness_enabled=freshness_enabled,
            default_max_age_days=default_max_age_days,
        )
