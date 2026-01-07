# coding=utf-8
"""
爬虫模块 - 数据抓取功能

支持以下数据源：
1. DataFetcher - 热榜平台数据抓取（通过 NewsNow API）
2. RSSFetcher - RSS 订阅源抓取
3. Web3Fetcher - Web3 媒体网站爬虫（ChainCatcher、ME News 等）
"""

from trendradar.crawler.fetcher import DataFetcher

# RSS 抓取器
from trendradar.crawler.rss.fetcher import RSSFetcher, RSSFeedConfig

# Web3 爬虫
try:
    from trendradar.crawler.web3.fetcher import Web3Fetcher, Web3FeedConfig
    from trendradar.crawler.web3.chaincatcher import ChainCatcherCrawler
    from trendradar.crawler.web3.menews import MeNewsCrawler
    HAS_WEB3_CRAWLER = True
except ImportError:
    # 如果 beautifulsoup4 未安装，Web3 爬虫不可用
    HAS_WEB3_CRAWLER = False
    Web3Fetcher = None
    Web3FeedConfig = None
    ChainCatcherCrawler = None
    MeNewsCrawler = None

__all__ = [
    # 热榜抓取器
    "DataFetcher",

    # RSS 抓取器
    "RSSFetcher",
    "RSSFeedConfig",

    # Web3 爬虫
    "Web3Fetcher",
    "Web3FeedConfig",
    "ChainCatcherCrawler",
    "MeNewsCrawler",
    "HAS_WEB3_CRAWLER",
]
