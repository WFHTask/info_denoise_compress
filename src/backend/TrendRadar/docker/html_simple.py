#!/usr/bin/env python
# coding=utf-8

import os
from trendradar.utils.time import get_configured_time

def render_html_content(
    report_data, total_titles, is_daily_summary=False, mode="daily", update_info=None,
    *, reverse_content_order=False, get_time_func=None, rss_items=None, rss_new_items=None, display_mode="keyword"
):
    """渲染HTML内容"""
    
    # 检查是否启用赛博朋克模板
    if os.environ.get("ENABLE_CYBER_TEMPLATE", "false").lower() == "true":
        # 整合所有数据
        all_items = []
        
        # 添加 RSS 数据
        if rss_items:
            for item in rss_items:
                all_items.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "source": item.get("source", "RSS"),
                    "time": item.get("published", ""),
                    "type": "rss"
                })
        
        # 添加平台数据
        for stat in report_data.get("stats", []):
            for title_info in stat.get("titles", []):
                all_items.append({
                    "title": title_info.get("title", ""),
                    "url": title_info.get("url", ""),
                    "source": stat.get("name", "Unknown"),
                    "time": title_info.get("time", ""),
                    "type": "web3"
                })
        
        # 统计来源
        source_stats = {}
        for item in all_items:
            source = item["source"]
            source_stats[source] = source_stats.get(source, 0) + 1
        
        # 获取时间信息
        timezone = os.environ.get("TZ", "Asia/Shanghai")
        now = get_configured_time(timezone)
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H-%M")
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        
        # 导入并使用赛博朋克模板
        import sys
        sys.path.insert(0, '/app')
        from web3_html_template import generate_cyber_html
        return generate_cyber_html(all_items, source_stats, date_str, time_str, now_str)
    
    # 如果没有启用赛博朋克模板，返回简单的HTML
    return "<html><body><h1>请设置 ENABLE_CYBER_TEMPLATE=true 来启用赛博朋克模板</h1></body></html>"
