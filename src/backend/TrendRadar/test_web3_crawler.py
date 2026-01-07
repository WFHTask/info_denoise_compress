#!/usr/bin/env python
# coding=utf-8
"""
Web3 爬虫测试脚本

测试 ChainCatcher 和 ME News 爬虫是否正常工作
运行方式: python test_web3_crawler.py
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime


def print_separator(title: str = ""):
    """打印分隔线"""
    if title:
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}")
    else:
        print("-" * 60)


def print_item(item, index: int):
    """打印单个条目"""
    print(f"\n[{index}] {item.title[:80]}{'...' if len(item.title) > 80 else ''}")
    print(f"    URL: {item.url[:60]}{'...' if len(item.url) > 60 else ''}")
    if item.published_at:
        print(f"    时间: {item.published_at}")
    if item.author:
        print(f"    作者: {item.author}")
    if item.summary:
        summary = item.summary[:100] + "..." if len(item.summary) > 100 else item.summary
        print(f"    摘要: {summary}")


def test_chaincatcher():
    """测试 ChainCatcher 爬虫"""
    print_separator("测试 ChainCatcher 爬虫")

    try:
        from trendradar.crawler.web3.chaincatcher import ChainCatcherCrawler

        crawler = ChainCatcherCrawler(timeout=30)
        print(f"爬虫初始化成功")
        print(f"数据源 ID: {crawler.source_id}")
        print(f"数据源名称: {crawler.source_name}")

        print("\n正在抓取数据...")
        items = crawler.crawl(max_items=10)

        print(f"\n抓取结果: 共 {len(items)} 条")

        if items:
            print("\n前 5 条内容:")
            for i, item in enumerate(items[:5], 1):
                print_item(item, i)
            return True
        else:
            print("⚠️ 未抓取到数据")
            return False

    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        print("请确保已安装依赖: pip install beautifulsoup4 requests")
        return False
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_menews():
    """测试 ME News 爬虫"""
    print_separator("测试 ME News 爬虫")

    try:
        from trendradar.crawler.web3.menews import MeNewsCrawler

        crawler = MeNewsCrawler(timeout=30)
        print(f"爬虫初始化成功")
        print(f"数据源 ID: {crawler.source_id}")
        print(f"数据源名称: {crawler.source_name}")

        print("\n正在抓取数据...")
        items = crawler.crawl(max_items=10)

        print(f"\n抓取结果: 共 {len(items)} 条")

        if items:
            print("\n前 5 条内容:")
            for i, item in enumerate(items[:5], 1):
                print_item(item, i)
            return True
        else:
            print("⚠️ 未抓取到数据（可能是网站需要 JavaScript 渲染）")
            return False

    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        print("请确保已安装依赖: pip install beautifulsoup4 requests")
        return False
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_web3_fetcher():
    """测试 Web3Fetcher 整合抓取"""
    print_separator("测试 Web3Fetcher 整合抓取")

    try:
        from trendradar.crawler.web3.fetcher import Web3Fetcher, Web3FeedConfig

        # 配置信息源
        feeds = [
            Web3FeedConfig(
                id="chaincatcher",
                name="ChainCatcher 链捕手",
                url="https://www.chaincatcher.com/news",
                crawler_type="chaincatcher",
                max_items=10,
                enabled=True,
            ),
            Web3FeedConfig(
                id="menews",
                name="ME News",
                url="https://www.me.news/news",
                crawler_type="menews",
                max_items=10,
                enabled=True,
            ),
        ]

        fetcher = Web3Fetcher(
            feeds=feeds,
            request_interval=2000,
            timeout=30,
        )

        print(f"Fetcher 初始化成功，配置了 {len(feeds)} 个信息源")

        print("\n正在抓取所有信息源...")
        rss_data = fetcher.fetch_all()

        print(f"\n抓取日期: {rss_data.date}")
        print(f"抓取时间: {rss_data.crawl_time}")
        print(f"成功数量: {len(rss_data.items)} 个源")
        print(f"失败数量: {len(rss_data.failed_ids)} 个源")
        print(f"总条目数: {rss_data.get_total_count()} 条")

        if rss_data.failed_ids:
            print(f"\n失败的源: {', '.join(rss_data.failed_ids)}")

        # 显示每个源的结果
        for feed_id, items in rss_data.items.items():
            feed_name = rss_data.id_to_name.get(feed_id, feed_id)
            print(f"\n--- {feed_name} ({len(items)} 条) ---")
            for i, item in enumerate(items[:3], 1):
                print(f"  [{i}] {item.title[:60]}{'...' if len(item.title) > 60 else ''}")

        return rss_data.get_total_count() > 0

    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config_loading():
    """测试从配置文件加载"""
    print_separator("测试配置文件加载")

    try:
        import yaml
        config_path = os.path.join(
            os.path.dirname(__file__),
            "config",
            "web3_sources.yaml"
        )

        if not os.path.exists(config_path):
            print(f"⚠️ 配置文件不存在: {config_path}")
            return False

        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        web3_config = config.get("web3", {})
        print(f"配置加载成功")
        print(f"启用状态: {web3_config.get('enabled', False)}")
        print(f"请求间隔: {web3_config.get('request_interval', 0)} ms")

        feeds = web3_config.get("feeds", [])
        print(f"配置的信息源数量: {len(feeds)}")

        for feed in feeds:
            status = "✓" if feed.get("enabled", True) else "✗"
            print(f"  {status} {feed.get('name', 'Unknown')} ({feed.get('crawler_type', 'unknown')})")

        return True

    except ImportError:
        print("⚠️ 需要安装 pyyaml: pip install pyyaml")
        return False
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        return False


def main():
    """主测试函数"""
    print(f"\n{'#'*60}")
    print(f"#  Web3 爬虫测试")
    print(f"#  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*60}")

    results = {}

    # 测试配置加载
    results["配置加载"] = test_config_loading()

    # 测试 ChainCatcher
    results["ChainCatcher"] = test_chaincatcher()

    # 测试 ME News
    results["ME News"] = test_menews()

    # 测试整合抓取
    results["Web3Fetcher"] = test_web3_fetcher()

    # 打印测试结果汇总
    print_separator("测试结果汇总")

    all_passed = True
    for name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("🎉 所有测试通过!")
    else:
        print("⚠️ 部分测试未通过，请检查错误信息")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
