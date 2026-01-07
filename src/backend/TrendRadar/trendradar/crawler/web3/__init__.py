# coding=utf-8
"""
Web3 信息源爬虫模块

支持从以下 Web3 媒体网站采集新闻数据：
- ChainCatcher (链捕手): https://www.chaincatcher.com/news
- ME News (MetaEra): https://www.me.news/news

这些网站不提供 RSS 订阅，需要通过网页爬虫采集数据。
"""

from .fetcher import Web3Fetcher, Web3FeedConfig
from .chaincatcher import ChainCatcherCrawler
from .menews import MeNewsCrawler

__all__ = [
    "Web3Fetcher",
    "Web3FeedConfig",
    "ChainCatcherCrawler",
    "MeNewsCrawler",
]
