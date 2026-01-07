# coding=utf-8
"""
ME News (MetaEra) 爬虫

网站: https://www.me.news
数据源: 新闻页面 (https://www.me.news/news)

ME News (原 MetaEra) 是香港 Web3.0 媒体平台，提供区块链行业资讯和深度报道。
由于网站使用 JavaScript 渲染，此爬虫通过其 API 接口获取数据。
"""

import re
from datetime import datetime
from typing import List, Optional, Dict, Any

from .fetcher import Web3Crawler, ParsedWeb3Item


class MeNewsCrawler(Web3Crawler):
    """ME News (MetaEra) 爬虫"""

    # API 接口地址 (需要根据实际情况调整)
    NEWS_API_URL = "https://www.me.news/api/news/list"
    FLASH_API_URL = "https://www.me.news/api/flash/list"
    ARTICLE_API_URL = "https://www.me.news/api/article/list"

    # 备用 API (MetaEra 旧域名)
    LEGACY_NEWS_API = "https://api.metaera.media/api/news/list"
    LEGACY_FLASH_API = "https://api.metaera.media/api/flash/list"

    # 网站基础 URL
    BASE_URL = "https://www.me.news"
    LEGACY_BASE_URL = "https://metaera.media"

    @property
    def source_id(self) -> str:
        return "menews"

    @property
    def source_name(self) -> str:
        return "ME News"

    def crawl(self, max_items: int = 50) -> List[ParsedWeb3Item]:
        """
        抓取 ME News 新闻

        Args:
            max_items: 最大条目数

        Returns:
            解析后的新闻条目列表
        """
        items = []

        # 1. 尝试从主 API 获取新闻
        news_items = self._fetch_news(max_items)
        items.extend(news_items)

        # 2. 如果主 API 失败，尝试备用 API
        if not items:
            print("[MeNews] 主 API 无数据，尝试备用 API...")
            news_items = self._fetch_news_legacy(max_items)
            items.extend(news_items)

        # 3. 如果 API 都失败，尝试 HTML 抓取
        if not items:
            print("[MeNews] API 无数据，尝试 HTML 抓取...")
            html_items = self.crawl_by_html(max_items)
            items.extend(html_items)

        # 4. 补充快讯数据
        if len(items) < max_items:
            remaining = max_items - len(items)
            flash_items = self._fetch_flash(remaining)
            items.extend(flash_items)

        return items[:max_items]

    def _fetch_news(self, max_items: int = 50) -> List[ParsedWeb3Item]:
        """
        从主 API 获取新闻列表

        Args:
            max_items: 最大条目数

        Returns:
            新闻条目列表
        """
        items = []

        try:
            # 尝试多种 API 路径
            api_urls = [
                self.NEWS_API_URL,
                f"{self.BASE_URL}/api/v1/news/list",
                f"{self.BASE_URL}/api/v1/article/list",
                f"{self.BASE_URL}/api/news",
            ]

            for api_url in api_urls:
                params = {
                    "page": 1,
                    "pageSize": max_items,
                    "size": max_items,
                    "limit": max_items,
                }

                data = self.fetch_json(api_url, params=params)

                if data and self._has_valid_data(data):
                    news_list = self._extract_list_from_response(data)

                    if news_list:
                        for news in news_list:
                            item = self._parse_news_item(news)
                            if item:
                                items.append(item)

                            if len(items) >= max_items:
                                break

                        if items:
                            print(f"[MeNews] 从 {api_url} 获取 {len(items)} 条新闻")
                            break

        except Exception as e:
            print(f"[MeNews] 获取新闻失败: {e}")

        return items

    def _fetch_news_legacy(self, max_items: int = 50) -> List[ParsedWeb3Item]:
        """
        从备用 API 获取新闻列表

        Args:
            max_items: 最大条目数

        Returns:
            新闻条目列表
        """
        items = []

        try:
            api_urls = [
                self.LEGACY_NEWS_API,
                self.LEGACY_FLASH_API,
                f"{self.LEGACY_BASE_URL}/api/news/list",
            ]

            for api_url in api_urls:
                params = {
                    "page": 1,
                    "pageSize": max_items,
                }

                data = self.fetch_json(api_url, params=params)

                if data and self._has_valid_data(data):
                    news_list = self._extract_list_from_response(data)

                    if news_list:
                        for news in news_list:
                            item = self._parse_news_item(news)
                            if item:
                                items.append(item)

                            if len(items) >= max_items:
                                break

                        if items:
                            print(f"[MeNews] 从备用 API {api_url} 获取 {len(items)} 条新闻")
                            break

        except Exception as e:
            print(f"[MeNews] 备用 API 获取失败: {e}")

        return items

    def _fetch_flash(self, max_items: int = 20) -> List[ParsedWeb3Item]:
        """
        获取快讯列表

        Args:
            max_items: 最大条目数

        Returns:
            快讯条目列表
        """
        items = []

        try:
            api_urls = [
                self.FLASH_API_URL,
                f"{self.BASE_URL}/api/v1/flash/list",
                f"{self.BASE_URL}/api/flash",
            ]

            for api_url in api_urls:
                params = {
                    "page": 1,
                    "pageSize": max_items,
                }

                data = self.fetch_json(api_url, params=params)

                if data and self._has_valid_data(data):
                    flash_list = self._extract_list_from_response(data)

                    if flash_list:
                        for flash in flash_list:
                            item = self._parse_flash_item(flash)
                            if item:
                                items.append(item)

                            if len(items) >= max_items:
                                break

                        if items:
                            break

        except Exception as e:
            print(f"[MeNews] 获取快讯失败: {e}")

        return items

    def _has_valid_data(self, data: Dict[str, Any]) -> bool:
        """检查响应是否包含有效数据"""
        if not isinstance(data, dict):
            return False

        # 检查常见的成功标志
        code = data.get("code")
        if code is not None and code not in [0, 200, "0", "200", "success"]:
            return False

        # 检查是否有数据
        if "data" in data or "list" in data or "items" in data or "records" in data:
            return True

        return False

    def _extract_list_from_response(self, data: Dict[str, Any]) -> List[Dict]:
        """
        从 API 响应中提取数据列表

        Args:
            data: API 响应数据

        Returns:
            数据列表
        """
        if not isinstance(data, dict):
            return []

        # 尝试多种响应格式
        # 格式1: {"code": 0, "data": {"list": [...]}}
        if "data" in data:
            inner_data = data["data"]
            if isinstance(inner_data, dict):
                for key in ["list", "items", "records", "rows", "content"]:
                    if key in inner_data:
                        result = inner_data[key]
                        if isinstance(result, list):
                            return result
            elif isinstance(inner_data, list):
                return inner_data

        # 格式2: {"list": [...]}
        for key in ["list", "items", "records", "rows", "content"]:
            if key in data:
                result = data[key]
                if isinstance(result, list):
                    return result

        return []

    def _parse_news_item(self, news: Dict[str, Any]) -> Optional[ParsedWeb3Item]:
        """
        解析新闻条目

        Args:
            news: 新闻数据

        Returns:
            解析后的条目
        """
        try:
            # 提取标题
            title = news.get("title") or news.get("name") or news.get("headline", "")
            title = self.clean_text(title)

            if not title:
                return None

            # 截断过长的标题
            if len(title) > 200:
                title = title[:197] + "..."

            # 提取 URL
            url = self._build_url(news)

            # 提取发布时间
            published_at = self._parse_time(news)

            # 提取摘要
            summary = (
                news.get("summary") or
                news.get("description") or
                news.get("desc") or
                news.get("content") or
                news.get("abstract", "")
            )
            summary = self.clean_text(summary)
            if summary and len(summary) > 500:
                summary = summary[:497] + "..."

            # 提取作者
            author = self._parse_author(news)

            # 生成唯一标识
            guid = self.generate_guid(url, title)

            return ParsedWeb3Item(
                title=title,
                url=url,
                published_at=published_at,
                summary=summary or None,
                author=author,
                guid=guid,
            )

        except Exception as e:
            print(f"[MeNews] 解析新闻失败: {e}")
            return None

    def _parse_flash_item(self, flash: Dict[str, Any]) -> Optional[ParsedWeb3Item]:
        """
        解析快讯条目

        Args:
            flash: 快讯数据

        Returns:
            解析后的条目
        """
        try:
            # 提取标题/内容
            title = flash.get("title") or flash.get("content", "")
            title = self.clean_text(title)

            if not title:
                return None

            # 截断过长的标题
            if len(title) > 200:
                title = title[:197] + "..."

            # 提取 URL
            url = self._build_url(flash, item_type="flash")

            # 提取发布时间
            published_at = self._parse_time(flash)

            # 提取内容作为摘要
            content = flash.get("content") or flash.get("body", "")
            summary = self.clean_text(content)
            if summary and len(summary) > 500:
                summary = summary[:497] + "..."

            # 生成唯一标识
            guid = self.generate_guid(url, title)

            return ParsedWeb3Item(
                title=title,
                url=url,
                published_at=published_at,
                summary=summary or None,
                author="ME News",
                guid=guid,
            )

        except Exception as e:
            print(f"[MeNews] 解析快讯失败: {e}")
            return None

    def _build_url(self, data: Dict[str, Any], item_type: str = "news") -> str:
        """
        构建文章 URL

        Args:
            data: 数据字典
            item_type: 条目类型 (news/flash/article)

        Returns:
            完整 URL
        """
        # 优先使用原始 URL
        url = data.get("url") or data.get("link") or data.get("href", "")
        if url:
            if url.startswith("http"):
                return url
            elif url.startswith("/"):
                return f"{self.BASE_URL}{url}"

        # 根据 ID 构建 URL
        item_id = data.get("id") or data.get("articleId") or data.get("newsId")
        if item_id:
            if item_type == "flash":
                return f"{self.BASE_URL}/flash/{item_id}"
            else:
                return f"{self.BASE_URL}/news/{item_id}"

        return ""

    def _parse_author(self, data: Dict[str, Any]) -> str:
        """
        解析作者信息

        Args:
            data: 数据字典

        Returns:
            作者名称
        """
        author = data.get("author") or data.get("source") or data.get("writer")

        if isinstance(author, dict):
            author = author.get("name") or author.get("nickname", "")
        elif isinstance(author, list) and author:
            if isinstance(author[0], dict):
                author = author[0].get("name", "")
            else:
                author = str(author[0])

        if author:
            return self.clean_text(str(author))

        return "ME News"

    def _parse_time(self, data: Dict[str, Any]) -> Optional[str]:
        """
        解析时间字段

        Args:
            data: 包含时间字段的数据

        Returns:
            ISO 格式时间字符串
        """
        # 尝试多个时间字段
        time_fields = [
            "publishTime", "publish_time", "publishedAt", "published_at",
            "createTime", "create_time", "createdAt", "created_at",
            "updateTime", "update_time", "updatedAt", "updated_at",
            "time", "date", "datetime"
        ]

        for field in time_fields:
            time_value = data.get(field)
            if time_value:
                parsed = self._convert_time(time_value)
                if parsed:
                    return parsed

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
            # 时间戳（秒或毫秒）
            if isinstance(time_value, (int, float)):
                # 毫秒时间戳转换
                if time_value > 1e12:
                    time_value = time_value / 1000
                dt = datetime.fromtimestamp(time_value)
                return dt.isoformat()

            # 字符串时间
            if isinstance(time_value, str):
                time_value = time_value.strip()

                # 空字符串
                if not time_value:
                    return None

                # ISO 格式
                if "T" in time_value:
                    time_value = time_value.replace("Z", "+00:00")
                    try:
                        dt = datetime.fromisoformat(time_value)
                        return dt.isoformat()
                    except ValueError:
                        pass

                # 常见格式
                formats = [
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%d %H:%M",
                    "%Y-%m-%d",
                    "%Y/%m/%d %H:%M:%S",
                    "%Y/%m/%d %H:%M",
                    "%Y/%m/%d",
                    "%m-%d %H:%M",
                    "%m/%d %H:%M",
                    "%d/%m/%Y %H:%M:%S",
                    "%d/%m/%Y %H:%M",
                ]

                for fmt in formats:
                    try:
                        dt = datetime.strptime(time_value, fmt)
                        # 如果没有年份，使用当前年份
                        if dt.year == 1900:
                            dt = dt.replace(year=datetime.now().year)
                        return dt.isoformat()
                    except ValueError:
                        continue

        except Exception:
            pass

        return None

    def crawl_by_html(self, max_items: int = 50) -> List[ParsedWeb3Item]:
        """
        通过 HTML 页面抓取（备用方法）

        当 API 不可用时，可以使用此方法通过解析 HTML 获取数据

        Args:
            max_items: 最大条目数

        Returns:
            解析后的新闻条目列表
        """
        items = []

        try:
            # 尝试多个页面
            urls_to_try = [
                f"{self.BASE_URL}/news",
                f"{self.BASE_URL}/",
                f"{self.LEGACY_BASE_URL}/news",
            ]

            for page_url in urls_to_try:
                html_content = self.fetch_page(page_url)

                if not html_content:
                    continue

                # 检查是否为有效 HTML（非 JavaScript 渲染提示）
                if "doesn't work properly without JavaScript" in html_content:
                    print(f"[MeNews] {page_url} 需要 JavaScript 渲染")
                    continue

                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')

                # 查找新闻列表项
                selectors = [
                    '.news-item',
                    '.article-item',
                    '[class*="news-list"] > *',
                    '[class*="article-list"] > *',
                    'article',
                    '.card',
                    '[class*="item"]',
                ]

                news_items = []
                for selector in selectors:
                    found = soup.select(selector)
                    if found and len(found) > 3:  # 至少找到3个条目才认为有效
                        news_items = found
                        break

                for news_item in news_items[:max_items]:
                    try:
                        # 提取标题
                        title_elem = news_item.select_one(
                            'h1, h2, h3, h4, .title, [class*="title"], a[href]'
                        )
                        if not title_elem:
                            continue

                        title = self.clean_text(title_elem.get_text())
                        if not title or len(title) < 5:
                            continue

                        # 提取链接
                        link_elem = news_item.select_one('a[href]')
                        url = ""
                        if link_elem:
                            href = link_elem.get('href', '')
                            if href.startswith('/'):
                                url = f"{self.BASE_URL}{href}"
                            elif href.startswith('http'):
                                url = href

                        # 提取时间
                        time_elem = news_item.select_one(
                            '[class*="time"], [class*="date"], time, [datetime]'
                        )
                        published_at = None
                        if time_elem:
                            time_text = time_elem.get('datetime') or self.clean_text(
                                time_elem.get_text()
                            )
                            published_at = self._convert_time(time_text)

                        # 提取摘要
                        summary_elem = news_item.select_one(
                            '.summary, .desc, .description, .content, p'
                        )
                        summary = None
                        if summary_elem:
                            summary = self.clean_text(summary_elem.get_text())
                            if summary and len(summary) > 500:
                                summary = summary[:497] + "..."

                        guid = self.generate_guid(url, title)

                        items.append(ParsedWeb3Item(
                            title=title,
                            url=url,
                            published_at=published_at,
                            summary=summary,
                            author="ME News",
                            guid=guid,
                        ))

                    except Exception as e:
                        continue

                if items:
                    print(f"[MeNews] 从 HTML 抓取 {len(items)} 条新闻")
                    break

        except Exception as e:
            print(f"[MeNews] HTML 抓取失败: {e}")

        return items
