#!/usr/bin/env python
# coding=utf-8
"""
Web3 资讯抓取与推送快速启动脚本

功能：
1. 抓取 Web3 信息源（ChainCatcher、Cointelegraph 等）
2. 生成资讯简报
3. 推送到配置的渠道（企业微信、Telegram 等）

使用方法：
    python run_web3_push.py              # 正常运行
    python run_web3_push.py --test       # 测试模式（只抓取不推送）
    python run_web3_push.py --dry-run    # 预览模式（显示将要推送的内容）
"""

import os
import sys
import argparse
from datetime import datetime

# 修复 Windows 终端编码问题
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def load_config():
    """加载配置文件"""
    import yaml

    config_path = os.path.join(os.path.dirname(__file__), "config", "config.yaml")

    if not os.path.exists(config_path):
        print(f"❌ 配置文件不存在: {config_path}")
        sys.exit(1)

    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def crawl_rss_sources(config):
    """抓取 RSS 信息源"""
    from trendradar.crawler.rss.fetcher import RSSFetcher

    rss_config = config.get("rss", {})
    if not rss_config.get("enabled", True):
        print("ℹ️ RSS 抓取已禁用")
        return None

    # 添加时区配置
    rss_config["timezone"] = config.get("app", {}).get("timezone", "Asia/Shanghai")

    fetcher = RSSFetcher.from_config(rss_config)
    return fetcher.fetch_all()


def crawl_web3_sources(config):
    """抓取 Web3 信息源"""
    from trendradar.crawler.web3.fetcher import Web3Fetcher, Web3FeedConfig

    web3_config = config.get("web3", {})
    if not web3_config.get("enabled", True):
        print("ℹ️ Web3 抓取已禁用")
        return None

    # 构建配置
    feeds = []
    for feed_config in web3_config.get("feeds", []):
        if not feed_config.get("enabled", True):
            continue

        feed = Web3FeedConfig(
            id=feed_config.get("id", ""),
            name=feed_config.get("name", ""),
            url=feed_config.get("url", ""),
            crawler_type=feed_config.get("crawler_type", ""),
            max_items=feed_config.get("max_items", 50),
            enabled=True,
            max_age_days=feed_config.get("max_age_days"),
        )
        if feed.id and feed.crawler_type:
            feeds.append(feed)

    if not feeds:
        print("ℹ️ 没有启用的 Web3 信息源")
        return None

    fetcher = Web3Fetcher(
        feeds=feeds,
        request_interval=web3_config.get("request_interval", 3000),
        timeout=web3_config.get("timeout", 30),
        use_proxy=web3_config.get("use_proxy", False),
        proxy_url=web3_config.get("proxy_url", ""),
        timezone=config.get("app", {}).get("timezone", "Asia/Shanghai"),
    )

    return fetcher.fetch_all()


def format_report(rss_data, web3_data, config):
    """格式化推送报告"""
    from trendradar.utils.time import get_configured_time

    timezone = config.get("app", {}).get("timezone", "Asia/Shanghai")
    now = get_configured_time(timezone)

    lines = []
    lines.append(f"[Web3 资讯日报] {now.strftime('%Y-%m-%d')}")
    lines.append("")
    lines.append("-----------------------------------")
    lines.append("")

    all_items = []

    # 收集 RSS 数据
    if rss_data and rss_data.items:
        for feed_id, items in rss_data.items.items():
            feed_name = rss_data.id_to_name.get(feed_id, feed_id)
            for item in items:
                all_items.append({
                    "title": item.title,
                    "url": item.url,
                    "source": feed_name,
                    "time": item.published_at,
                })

    # 收集 Web3 数据
    if web3_data and web3_data.items:
        for feed_id, items in web3_data.items.items():
            feed_name = web3_data.id_to_name.get(feed_id, feed_id)
            for item in items:
                all_items.append({
                    "title": item.title,
                    "url": item.url,
                    "source": feed_name,
                    "time": item.published_at,
                })

    if not all_items:
        lines.append("暂无新资讯")
    else:
        # 按时间排序（最新的在前）
        all_items.sort(key=lambda x: x.get("time") or "", reverse=True)

        # 显示前 20 条
        lines.append("** 今日热点 **")
        lines.append("")

        for i, item in enumerate(all_items[:20], 1):
            title = item["title"][:60] + "..." if len(item["title"]) > 60 else item["title"]
            source = item["source"]
            lines.append(f"{i}. [{title}]({item['url']})")
            lines.append(f"   > 来源: {source}")
            lines.append("")

    lines.append("-----------------------------------")
    lines.append("")

    # 统计信息
    sources = set()
    if rss_data and rss_data.id_to_name:
        sources.update(rss_data.id_to_name.values())
    if web3_data and web3_data.id_to_name:
        sources.update(web3_data.id_to_name.values())

    lines.append(f"数据来源: {', '.join(sources)}")
    lines.append(f"更新时间: {now.strftime('%H:%M')}")

    return "\n".join(lines)


def push_to_wework(content, config):
    """推送到企业微信"""
    import requests

    notification_config = config.get("notification", {})
    if not notification_config.get("enabled", False):
        print("[INFO] 推送功能未启用")
        return False

    wework_config = notification_config.get("channels", {}).get("wework", {})
    webhook_url = wework_config.get("webhook_url", "")

    if not webhook_url:
        print("[WARN] 企业微信 webhook_url 未配置")
        return False

    msg_type = wework_config.get("msg_type", "markdown")

    if msg_type == "markdown":
        payload = {
            "msgtype": "markdown",
            "markdown": {"content": content}
        }
    else:
        # text 模式，移除 markdown 语法
        import re
        plain_content = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', content)
        plain_content = plain_content.replace("**", "").replace("*", "")
        payload = {
            "msgtype": "text",
            "text": {"content": plain_content}
        }

    try:
        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )

        result = response.json()
        if result.get("errcode") == 0:
            print("[OK] 企业微信推送成功")
            return True
        else:
            print(f"[FAIL] 企业微信推送失败: {result.get('errmsg')}")
            return False

    except Exception as e:
        print(f"[ERROR] 企业微信推送出错: {e}")
        return False


def push_to_telegram(content, config):
    """推送到 Telegram"""
    import requests

    notification_config = config.get("notification", {})
    if not notification_config.get("enabled", False):
        return False

    telegram_config = notification_config.get("channels", {}).get("telegram", {})
    bot_token = telegram_config.get("bot_token", "")
    chat_id = telegram_config.get("chat_id", "")

    if not bot_token or not chat_id:
        return False

    # 转换为 Telegram 支持的格式
    import re
    text = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2">\1</a>', content)
    text = text.replace("**", "").replace("━", "—")

    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }

        response = requests.post(url, json=payload, timeout=30)
        result = response.json()

        if result.get("ok"):
            print("[OK] Telegram 推送成功")
            return True
        else:
            print(f"[FAIL] Telegram 推送失败: {result.get('description')}")
            return False

    except Exception as e:
        print(f"[ERROR] Telegram 推送出错: {e}")
        return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Web3 资讯抓取与推送")
    parser.add_argument("--test", action="store_true", help="测试模式（只抓取不推送）")
    parser.add_argument("--dry-run", action="store_true", help="预览模式（显示将要推送的内容）")
    args = parser.parse_args()

    print()
    print("=" * 60)
    print("  Web3 资讯抓取与推送系统")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()

    # 加载配置
    print("[1/4] 加载配置...")
    config = load_config()
    print("[OK] 配置加载成功")
    print()

    # 抓取 RSS 数据
    print("[2/4] 抓取 RSS 信息源...")
    rss_data = crawl_rss_sources(config)
    if rss_data:
        print(f"[OK] RSS 抓取完成: {rss_data.get_total_count()} 条")
    print()

    # 抓取 Web3 数据
    print("[3/4] 抓取 Web3 信息源...")
    web3_data = crawl_web3_sources(config)
    if web3_data:
        print(f"[OK] Web3 抓取完成: {web3_data.get_total_count()} 条")
    print()

    # 格式化报告
    print("[4/4] 生成推送报告...")
    report = format_report(rss_data, web3_data, config)
    print("[OK] 报告生成完成")
    print()

    # 预览模式
    if args.dry_run or args.test:
        print("=" * 60)
        print("  推送内容预览")
        print("=" * 60)
        print()
        print(report)
        print()
        print("=" * 60)

        if args.test:
            print("[OK] 测试完成（未实际推送）")
            return 0

    # 推送
    if not args.test:
        print("[PUSH] 开始推送...")
        print()

        # 企业微信
        push_to_wework(report, config)

        # Telegram
        push_to_telegram(report, config)

        print()
        print("=" * 60)
        print("  推送完成")
        print("=" * 60)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n[WARN] 用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] 运行出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
