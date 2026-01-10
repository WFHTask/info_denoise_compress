#!/usr/bin/env python
# coding=utf-8
"""
Web3 资讯抓取与推送脚本

功能：
1. 抓取 Web3 信息源（ChainCatcher、Cointelegraph 等）
2. 生成资讯简报并保存为 HTML 报告
3. 推送到配置的渠道（企业微信、Telegram 等）

使用方法：
    python run_web3_push.py              # 正常运行（抓取 + 保存 + 推送）
    python run_web3_push.py --test       # 测试模式（只抓取不推送）
    python run_web3_push.py --dry-run    # 预览模式（显示将要推送的内容）
    python run_web3_push.py --no-save    # 不保存到文件
"""

import os
import sys
import json
import argparse
from datetime import datetime

# 修复 Windows 终端编码问题
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Web3 相关的 RSS 源 ID
# 设置为 None 表示抓取所有已启用的 RSS 源
# 如需限制，可设置为列表，例如: ["cointelegraph", "coindesk"]
WEB3_RSS_IDS = None


def load_config():
    """加载配置文件"""
    import yaml

    config_path = os.path.join(os.path.dirname(__file__), "config", "config.yaml")

    if not os.path.exists(config_path):
        print(f"❌ 配置文件不存在: {config_path}")
        sys.exit(1)

    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def crawl_web3_rss_sources(config):
    """抓取所有已启用的 RSS 信息源"""
    from trendradar.crawler.rss.fetcher import RSSFetcher

    rss_config = config.get("rss", {})
    if not rss_config.get("enabled", True):
        print("ℹ️ RSS 抓取已禁用")
        return None

    # 获取所有已启用的 feeds
    original_feeds = rss_config.get("feeds", [])

    # 如果 WEB3_RSS_IDS 为 None，抓取所有已启用的源
    # 否则只抓取指定的源
    if WEB3_RSS_IDS is None:
        enabled_feeds = [f for f in original_feeds if f.get("enabled", True)]
    else:
        enabled_feeds = [f for f in original_feeds if f.get("id") in WEB3_RSS_IDS and f.get("enabled", True)]

    if not enabled_feeds:
        print("ℹ️ 没有启用的 RSS 源")
        return None

    # 创建 RSS 配置
    rss_fetch_config = rss_config.copy()
    rss_fetch_config["feeds"] = enabled_feeds
    rss_fetch_config["timezone"] = config.get("app", {}).get("timezone", "Asia/Shanghai")

    print(f"[RSS] 共 {len(enabled_feeds)} 个已启用的 RSS 源")
    for feed in enabled_feeds:
        print(f"       - {feed.get('name', feed.get('id'))}")

    fetcher = RSSFetcher.from_config(rss_fetch_config)
    return fetcher.fetch_all()


def crawl_web3_sources(config):
    """抓取 Web3 自定义爬虫信息源"""
    from trendradar.crawler.web3.fetcher import Web3Fetcher, Web3FeedConfig

    web3_config = config.get("web3", {})
    if not web3_config.get("enabled", True):
        print("ℹ️ Web3 爬虫已禁用")
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
        print("ℹ️ 没有启用的 Web3 爬虫源")
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


def collect_all_items(rss_data, web3_data):
    """收集所有新闻条目"""
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
                    "source_id": feed_id,
                    "time": item.published_at,
                    "summary": getattr(item, 'summary', '') or '',
                    "type": "rss",
                })

    # 收集 Web3 爬虫数据
    if web3_data and web3_data.items:
        for feed_id, items in web3_data.items.items():
            feed_name = web3_data.id_to_name.get(feed_id, feed_id)
            for item in items:
                all_items.append({
                    "title": item.title,
                    "url": item.url,
                    "source": feed_name,
                    "source_id": feed_id,
                    "time": item.published_at,
                    "summary": getattr(item, 'summary', '') or '',
                    "type": "web3",
                })

    # 按时间排序（最新的在前）
    all_items.sort(key=lambda x: x.get("time") or "", reverse=True)

    return all_items


def format_report(all_items, config, max_items=20):
    """格式化推送报告（Markdown 格式）"""
    from trendradar.utils.time import get_configured_time

    timezone = config.get("app", {}).get("timezone", "Asia/Shanghai")
    now = get_configured_time(timezone)

    lines = []
    lines.append(f"**[Web3 资讯日报]** {now.strftime('%Y-%m-%d')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    if not all_items:
        lines.append("暂无新资讯")
    else:
        lines.append("**📰 今日热点**")
        lines.append("")

        for i, item in enumerate(all_items[:max_items], 1):
            title = item["title"][:55] + "..." if len(item["title"]) > 55 else item["title"]
            source = item["source"]
            lines.append(f"{i}. [{title}]({item['url']})")
            lines.append(f"   > 来源: {source}")
            lines.append("")

    lines.append("---")
    lines.append("")

    # 统计信息
    sources = set(item["source"] for item in all_items)
    lines.append(f"📊 数据来源: {len(sources)} 个平台 | 共 {len(all_items)} 条资讯")
    lines.append(f"🕐 更新时间: {now.strftime('%H:%M')}")

    return "\n".join(lines)


def save_json_data(all_items, output_dir, date_str, time_str):
    """保存 JSON 数据"""
    json_dir = os.path.join(output_dir, "web3", date_str)
    os.makedirs(json_dir, exist_ok=True)

    json_path = os.path.join(json_dir, f"{time_str}.json")

    data = {
        "date": date_str,
        "time": time_str,
        "total_count": len(all_items),
        "items": all_items,
    }

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[SAVE] JSON 数据已保存: {json_path}")
    return json_path


def generate_html_report(all_items, config, output_dir, date_str, time_str):
    """生成超炫酷 HTML 报告 - 赛博朋克风格"""
    from trendradar.utils.time import get_configured_time
    from web3_html_template import generate_cyber_html

    timezone = config.get("app", {}).get("timezone", "Asia/Shanghai")
    now = get_configured_time(timezone)
    now_str = now.strftime('%Y-%m-%d %H:%M:%S')

    html_dir = os.path.join(output_dir, "web3", date_str, "html")
    os.makedirs(html_dir, exist_ok=True)

    # 按来源分组统计
    source_stats = {}
    for item in all_items:
        source = item["source"]
        source_stats[source] = source_stats.get(source, 0) + 1

    # 使用新的炫酷模板生成 HTML
    html_content = generate_cyber_html(all_items, source_stats, date_str, time_str, now_str)

    # 保存 HTML 文件
    html_path = os.path.join(html_dir, f"{time_str}.html")
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    # 保存汇总文件
    summary_path = os.path.join(html_dir, "Web3资讯汇总.html")
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    # 创建根目录的 index.html，直接嵌入汇总报告内容，避免重定向问题
    # 直接使用汇总报告的 HTML 内容，不需要重定向
    index_html = html_content

    # 保存到 output 根目录
    root_index_path = os.path.join(output_dir, "index.html")
    with open(root_index_path, 'w', encoding='utf-8') as f:
        f.write(index_html)

    print(f"[SAVE] HTML 报告已保存: {html_path}")
    print(f"[SAVE] 汇总报告已保存: {summary_path}")
    print(f"[SAVE] 首页已保存: {root_index_path}")

    return html_path, summary_path


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
            print("[OK] 企业微信推送成功 ✅")
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
    text = text.replace("**", "<b>").replace("**", "</b>")
    text = text.replace("---", "—" * 20)

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
            print("[OK] Telegram 推送成功 ✅")
            return True
        else:
            print(f"[FAIL] Telegram 推送失败: {result.get('description')}")
            return False

    except Exception as e:
        print(f"[ERROR] Telegram 推送出错: {e}")
        return False


def open_html_report(html_path):
    """在浏览器中打开 HTML 报告"""
    import webbrowser

    abs_path = os.path.abspath(html_path)
    file_url = f"file://{abs_path}"

    print(f"[OPEN] 正在打开报告: {file_url}")
    webbrowser.open(file_url)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Web3 资讯抓取与推送")
    parser.add_argument("--test", action="store_true", help="测试模式（只抓取不推送）")
    parser.add_argument("--dry-run", action="store_true", help="预览模式（显示将要推送的内容）")
    parser.add_argument("--no-save", action="store_true", help="不保存数据到文件")
    parser.add_argument("--no-open", action="store_true", help="不自动打开 HTML 报告")
    args = parser.parse_args()

    print()
    print("=" * 60)
    print("  🌐 Web3 资讯抓取与推送系统")
    print(f"  📅 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()

    # 加载配置
    print("[1/5] 加载配置...")
    config = load_config()
    print("[OK] 配置加载成功 ✅")
    print()

    # 抓取 Web3 RSS 数据
    print("[2/5] 抓取 Web3 RSS 信息源...")
    rss_data = crawl_web3_rss_sources(config)
    rss_count = rss_data.get_total_count() if rss_data else 0
    print(f"[OK] Web3 RSS 抓取完成: {rss_count} 条 ✅")
    print()

    # 抓取 Web3 爬虫数据
    print("[3/5] 抓取 Web3 爬虫信息源...")
    web3_data = crawl_web3_sources(config)
    web3_count = web3_data.get_total_count() if web3_data else 0
    print(f"[OK] Web3 爬虫抓取完成: {web3_count} 条 ✅")
    print()

    # 收集所有数据
    all_items = collect_all_items(rss_data, web3_data)
    print(f"[INFO] 共收集 {len(all_items)} 条 Web3 资讯")
    print()

    # 生成报告
    print("[4/5] 生成推送报告...")
    report = format_report(all_items, config)
    print("[OK] 报告生成完成 ✅")
    print()

    # 保存数据
    if not args.no_save:
        print("[5/5] 保存数据...")
        output_dir = os.path.join(os.path.dirname(__file__), "output")
        date_str = datetime.now().strftime("%Y-%m-%d")
        time_str = datetime.now().strftime("%H-%M")

        # 保存 JSON
        save_json_data(all_items, output_dir, date_str, time_str)

        # 生成 HTML
        html_path, summary_path = generate_html_report(all_items, config, output_dir, date_str, time_str)

        print("[OK] 数据保存完成 ✅")
        print()

        # 自动打开 HTML
        if not args.no_open and not args.test:
            open_html_report(summary_path)
    else:
        print("[5/5] 跳过保存（--no-save）")
        print()

    # 预览模式
    if args.dry_run or args.test:
        print("=" * 60)
        print("  📋 推送内容预览")
        print("=" * 60)
        print()
        print(report)
        print()
        print("=" * 60)

        if args.test:
            print("[OK] 测试完成（未实际推送）✅")
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
        print("  ✅ 推送完成")
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
