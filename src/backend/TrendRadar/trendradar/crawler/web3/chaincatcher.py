# coding=utf-8
"""
ChainCatcher (链捕手) 爬虫

网站: https://www.chaincatcher.com
数据源: 快讯页面 (https://www.chaincatcher.com/news)

ChainCatcher 是中文区块链资讯平台，提供实时快讯和深度文章。
由于 API 接口有访问限制，此爬虫主要通过 HTML 页面解析获取数据。
"""

import re
from datetime import datetime
from typing import List, Optional, Dict, Any

from .fetcher import Web3Crawler, ParsedWeb3Item


class ChainCatcherCrawler(Web3Crawler):
    """ChainCatcher 爬虫"""

    # 网站基础 URL
    BASE_URL = "https://www.chaincatcher.com"
    NEWS_URL = "https://www.chaincatcher.com/news"

    @property
    def source_id(self) -> str:
        return "chaincatcher"

    @property
    def source_name(self) -> str:
        return "ChainCatcher 链捕手"

    def crawl(self, max_items: int = 50) -> List[ParsedWeb3Item]:
        """
        抓取 ChainCatcher 快讯

        Args:
            max_items: 最大条目数

        Returns:
            解析后的新闻条目列表
        """
        items = []

        # 主要使用 HTML 解析方式
        html_items = self._crawl_by_html(max_items)
        items.extend(html_items)

        return items[:max_items]

    def _crawl_by_html(self, max_items: int = 50) -> List[ParsedWeb3Item]:
        """
        通过 HTML 页面抓取

        Args:
            max_items: 最大条目数

        Returns:
            解析后的新闻条目列表
        """
        items = []

        try:
            print(f"[ChainCatcher] 正在获取页面: {self.NEWS_URL}")
            html_content = self.fetch_page(self.NEWS_URL)

            if not html_content:
                print("[ChainCatcher] 获取 HTML 页面失败")
                return items

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')

            # 方法1: 查找快讯列表中的 h3 标题元素
            # 根据实际 HTML 结构，快讯标题通常在 h3 标签中
            news_titles = soup.find_all('h3')

            for h3 in news_titles[:max_items * 2]:  # 获取更多以便过滤
                try:
                    title_text = self.clean_text(h3.get_text())

                    # 清理标题中的无关后缀
                    title_text = title_text.replace('微信扫码', '').strip()

                    # 过滤无效标题
                    if not title_text or len(title_text) < 5:
                        continue

                    # 跳过导航类标题
                    if title_text in ['区块链快讯', '最新快讯', '精选事件', '快讯']:
                        continue

                    # 查找父元素中的链接
                    parent = h3.find_parent(['div', 'article', 'li', 'a'])
                    url = ""

                    # 查找链接
                    if parent:
                        link_elem = parent.find('a', href=True)
                        if link_elem:
                            href = link_elem.get('href', '')
                            url = self._build_url(href)

                    # 如果 h3 本身在 a 标签内
                    if not url:
                        parent_a = h3.find_parent('a')
                        if parent_a:
                            url = self._build_url(parent_a.get('href', ''))

                    # 查找时间信息
                    published_at = None
                    if parent:
                        # 查找包含时间的元素
                        time_patterns = [
                            r'\d{2}-\d{2}\s+\d{2}:\d{2}',  # 01-07 16:50
                            r'\d{4}-\d{2}-\d{2}',  # 2026-01-07
                            r'\d{2}:\d{2}',  # 16:50
                        ]

                        parent_text = parent.get_text()
                        for pattern in time_patterns:
                            match = re.search(pattern, parent_text)
                            if match:
                                time_str = match.group()
                                published_at = self._parse_time_string(time_str)
                                if published_at:
                                    break

                    # 提取摘要 - 查找标题后的内容段落
                    summary = None
                    if parent:
                        # 查找可能的摘要元素
                        for elem in parent.find_all(['p', 'div', 'span']):
                            text = self.clean_text(elem.get_text())
                            # 摘要通常以 "ChainCatcher 消息" 开头
                            if text and len(text) > 20 and text != title_text:
                                if 'ChainCatcher' in text or len(text) > 50:
                                    summary = text[:500] + "..." if len(text) > 500 else text
                                    break

                    guid = self.generate_guid(url or title_text, title_text)

                    # 检查是否重复
                    if any(item.guid == guid for item in items):
                        continue

                    items.append(ParsedWeb3Item(
                        title=title_text,
                        url=url,
                        published_at=published_at,
                        summary=summary,
                        author="ChainCatcher",
                        guid=guid,
                    ))

                    if len(items) >= max_items:
                        break

                except Exception as e:
                    continue

            # 方法2: 如果上面没有找到足够的内容，尝试其他选择器
            if len(items) < max_items:
                # 查找所有可能的新闻容器
                containers = soup.select('[class*="news"], [class*="flash"], [class*="item"]')

                for container in containers:
                    if len(items) >= max_items:
                        break

                    try:
                        # 提取标题
                        title_elem = container.select_one('h3, h4, .title, a')
                        if not title_elem:
                            continue

                        title_text = self.clean_text(title_elem.get_text())
                        # 清理标题中的无关后缀
                        title_text = title_text.replace('微信扫码', '').strip()
                        if not title_text or len(title_text) < 5:
                            continue

                        # 跳过导航类标题
                        if title_text in ['区块链快讯', '最新快讯', '精选事件', '快讯']:
                            continue

                        # 提取链接
                        link_elem = container.select_one('a[href]')
                        url = ""
                        if link_elem:
                            url = self._build_url(link_elem.get('href', ''))

                        guid = self.generate_guid(url or title_text, title_text)

                        # 检查是否重复
                        if any(item.guid == guid for item in items):
                            continue

                        items.append(ParsedWeb3Item(
                            title=title_text,
                            url=url,
                            published_at=None,
                            summary=None,
                            author="ChainCatcher",
                            guid=guid,
                        ))

                    except Exception:
                        continue

            print(f"[ChainCatcher] 从 HTML 解析获取 {len(items)} 条新闻")

        except Exception as e:
            print(f"[ChainCatcher] HTML 抓取失败: {e}")
            import traceback
            traceback.print_exc()

        return items

    def _build_url(self, href: str) -> str:
        """
        构建完整 URL

        Args:
            href: 原始链接

        Returns:
            完整 URL
        """
        if not href:
            return ""

        if href.startswith('http'):
            return href
        elif href.startswith('/'):
            return f"{self.BASE_URL}{href}"
        else:
            return f"{self.BASE_URL}/{href}"

    def _parse_time_string(self, time_str: str) -> Optional[str]:
        """
        解析时间字符串

        Args:
            time_str: 时间字符串

        Returns:
            ISO 格式时间字符串
        """
        if not time_str:
            return None

        try:
            time_str = time_str.strip()
            now = datetime.now()

            # 格式: 01-07 16:50
            if re.match(r'\d{2}-\d{2}\s+\d{2}:\d{2}', time_str):
                dt = datetime.strptime(f"{now.year}-{time_str}", "%Y-%m-%d %H:%M")
                return dt.isoformat()

            # 格式: 2026-01-07
            if re.match(r'\d{4}-\d{2}-\d{2}', time_str):
                dt = datetime.strptime(time_str, "%Y-%m-%d")
                return dt.isoformat()

            # 格式: 2026-01-07 16:50
            if re.match(r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}', time_str):
                dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
                return dt.isoformat()

            # 格式: 16:50 (只有时间，使用今天日期)
            if re.match(r'^\d{2}:\d{2}$', time_str):
                dt = datetime.strptime(f"{now.strftime('%Y-%m-%d')} {time_str}", "%Y-%m-%d %H:%M")
                return dt.isoformat()

        except Exception:
            pass

        return None

    def _convert_time(self, time_value: Any) -> Optional[str]:
        """
        转换时间值为 ISO 格式

        Args:
            time_value: 时间值（可能是时间戳、字符串等）

        Returns:
            ISO 格式时间字符串
        """
        try:
            # 时间戳（秒）
            if isinstance(time_value, (int, float)):
                # 毫秒时间戳转换
                if time_value > 1e12:
                    time_value = time_value / 1000
                dt = datetime.fromtimestamp(time_value)
                return dt.isoformat()

            # 字符串时间
            if isinstance(time_value, str):
                return self._parse_time_string(time_value)

        except Exception:
            pass

        return None
