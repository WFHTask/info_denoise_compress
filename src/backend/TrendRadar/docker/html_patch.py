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
    
    # 默认的简化模板（原代码）
    from datetime import datetime
    from trendradar.report.helpers import html_escape
    
    if get_time_func is None:
        get_time_func = datetime.now
    
    # 获取当前时间
    now = get_time_func()
    time_str = now.strftime("%Y-%m-%d %H:%M:%S")
    
    # 处理报告数据
    stats = report_data.get("stats", [])
    new_titles = report_data.get("new_titles", {})
    failed_ids = report_data.get("failed_ids", [])
    total_new_count = report_data.get("total_new_count", 0)
    
    # 生成HTML内容
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>热点新闻分析</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js" integrity="sha512-BNaRQnYJYiPSqHHDb58B0yaPfCu+Wgds8Gp/gU33kqBtgNS4tSPHuGibyoeqMV/TJlSKda6FXzoEyYGjTe+vXA==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
            margin: 0;
            padding: 16px;
            background: #fafafa;
            color: #333;
            line-height: 1.5;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 2px 16px rgba(0,0,0,0.06);
        }}
        .header {{
            background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
            color: white;
            padding: 32px 24px;
            text-align: center;
            position: relative;
        }}
        .save-buttons {{
            position: absolute;
            top: 16px;
            right: 16px;
            display: flex;
            gap: 8px;
        }}
        .save-btn {{
            background: rgba(255, 255, 255, 0.2);
            border: 1px solid rgba(255, 255, 255, 0.3);
            color: white;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 500;
            transition: all 0.2s ease;
            backdrop-filter: blur(10px);
            white-space: nowrap;
        }}
        .save-btn:hover {{
            background: rgba(255, 255, 255, 0.3);
            border-color: rgba(255, 255, 255, 0.5);
            transform: translateY(-1px);
        }}
        .header-title {{
            font-size: 22px;
            font-weight: 700;
            margin: 0 0 20px 0;
        }}
        .header-info {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
            font-size: 14px;
            opacity: 0.95;
        }}
        .info-item {{
            text-align: center;
        }}
        .info-label {{
            display: block;
            font-size: 12px;
            opacity: 0.8;
            margin-bottom: 4px;
        }}
        .info-value {{
            font-weight: 600;
            font-size: 16px;
        }}
        .content {{
            padding: 24px;
        }}
        .summary {{
            background: #f8f9fa;
            padding: 16px;
            border-radius: 8px;
            margin-bottom: 24px;
        }}
        .summary-title {{
            font-size: 16px;
            font-weight: 600;
            margin: 0 0 12px 0;
            color: #1a1a1a;
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 12px;
        }}
        .summary-item {{
            text-align: center;
            padding: 12px;
            background: white;
            border-radius: 6px;
            border: 1px solid #e5e7eb;
        }}
        .summary-value {{
            font-size: 18px;
            font-weight: 700;
            color: #4f46e5;
        }}
        .summary-label {{
            font-size: 12px;
            color: #666;
            margin-top: 4px;
        }}
        .word-group {{
            margin-bottom: 40px;
        }}
        .word-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 20px;
            padding-bottom: 8px;
            border-bottom: 1px solid #f0f0f0;
        }}
        .word-info {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .word-name {{
            font-size: 17px;
            font-weight: 600;
            color: #1a1a1a;
        }}
        .word-count {{
            color: #666;
            font-size: 13px;
            font-weight: 500;
        }}
        .word-count.hot {{ color: #dc2626; font-weight: 600; }}
        .word-count.warm {{ color: #ea580c; font-weight: 600; }}
        .word-index {{
            color: #999;
            font-size: 12px;
        }}
        .news-item {{
            margin-bottom: 20px;
            padding: 16px 0;
            border-bottom: 1px solid #f5f5f5;
            position: relative;
            display: flex;
            gap: 12px;
            align-items: center;
        }}
        .news-item:last-child {{
            border-bottom: none;
        }}
        .news-item.new::after {{
            content: "NEW";
            position: absolute;
            top: 12px;
            right: 0;
            background: #fbbf24;
            color: #92400e;
            font-size: 9px;
            font-weight: 700;
            padding: 3px 6px;
            border-radius: 4px;
            letter-spacing: 0.5px;
        }}
        .news-number {{
            color: #999;
            font-size: 13px;
            font-weight: 600;
            min-width: 20px;
            text-align: center;
            flex-shrink: 0;
            background: #f8f9fa;
            border-radius: 50%;
            width: 24px;
            height: 24px;
            display: flex;
            align-items: center;
            justify-content: center;
            align-self: flex-start;
            margin-top: 8px;
        }}
        .news-content {{
            flex: 1;
            min-width: 0;
            padding-right: 40px;
        }}
        .news-title {{
            font-size: 15px;
            font-weight: 500;
            color: #1a1a1a;
            text-decoration: none;
            line-height: 1.4;
            display: block;
            margin-bottom: 6px;
        }}
        .news-title:hover {{
            color: #4f46e5;
        }}
        .news-meta {{
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 12px;
            color: #666;
        }}
        .platform-badge {{
            background: #e5e7eb;
            color: #374151;
            padding: 2px 8px;
            border-radius: 12px;
            font-weight: 500;
        }}
        .time-info {{
            color: #999;
        }}
        .rank-info {{
            margin-left: auto;
            font-weight: 600;
        }}
        .rank-info.top {{ color: #dc2626; }}
        .rank-info.high {{ color: #ea580c; }}
        .no-data {{
            text-align: center;
            padding: 60px 24px;
            color: #666;
        }}
        .no-data-icon {{
            font-size: 48px;
            margin-bottom: 16px;
            opacity: 0.3;
        }}
        .no-data-text {{
            font-size: 16px;
            margin-bottom: 8px;
        }}
        .no-data-hint {{
            font-size: 14px;
            color: #999;
        }}
        @media (max-width: 640px) {{
            .container {{
                margin: 0;
                border-radius: 0;
            }}
            .header {{
                padding: 24px 16px;
            }}
            .content {{
                padding: 16px;
            }}
            .news-item {{
                padding: 12px 0;
            }}
            .news-content {{
                padding-right: 20px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="save-buttons">
                <button class="save-btn" onclick="saveAsImage()">&#128247; 保存图片</button>
                <button class="save-btn" onclick="window.print()">&#128438; 打印</button>
            </div>
            <h1 class="header-title">热点新闻分析</h1>
            <div class="header-info">
                <div class="info-item">
                    <span class="info-label">生成时间</span>
                    <span class="info-value">{time_str}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">新闻总数</span>
                    <span class="info-value">{total_titles}</span>
                </div>
            </div>
        </div>
        
        <div class="content">
            <div class="summary">
                <h2 class="summary-title">&#128202; 数据概览</h2>
                <div class="summary-grid">
                    <div class="summary-item">
                        <div class="summary-value">{len(stats)}</div>
                        <div class="summary-label">监控平台</div>
                    </div>
                    <div class="summary-item">
                        <div class="summary-value">{total_new_count}</div>
                        <div class="summary-label">新增热点</div>
                    </div>
                    <div class="summary-item">
                        <div class="summary-value">{len(failed_ids)}</div>
                        <div class="summary-label">失败数量</div>
                    </div>
                </div>
            </div>
            
            {"".join([f"""
            <div class="word-group">
                <div class="word-header">
                    <div class="word-info">
                        <span class="word-name">{html_escape(stat.get('name', ''))}</span>
                        <span class="word-count">{len(stat.get('titles', []))} 条</span>
                    </div>
                    <span class="word-index">#{idx + 1}</span>
                </div>
                <div class="news-list">
                    {"".join([f"""
                    <div class="news-item {'new' if title.get('is_new', False) else ''}">
                        <div class="news-number">{i + 1}</div>
                        <div class="news-content">
                            <a href="{title.get('url', '#')}" target="_blank" class="news-title">
                                {html_escape(title.get('title', ''))}
                            </a>
                            <div class="news-meta">
                                <span class="platform-badge">{html_escape(stat.get('name', ''))}</span>
                                <span class="time-info">{title.get('time', '')}</span>
                                <span class="rank-info {'top' if i < 3 else 'high' if i < 10 else ''}">#{title.get('rank', i + 1)}</span>
                            </div>
                        </div>
                    </div>
                    """ for i, title in enumerate(stat.get('titles', []))])}
                </div>
            </div>
            """ for idx, stat in enumerate(stats)]) if stats else """
            <div class="no-data">
                <div class="no-data-icon">&#128231;</div>
                <div class="no-data-text">暂无数据</div>
                <div class="no-data-hint">请检查配置或稍后再试</div>
            </div>
            """}
        </div>
    </div>
    
    <script>
        function saveAsImage() {
            const element = document.querySelector('.container');
            html2canvas(element, {
                scale: 2,
                useCORS: true,
                allowTaint: true,
                backgroundColor: '#ffffff'
            }).then(canvas => {
                const link = document.createElement('a');
                link.download = '热点新闻分析_' + new Date().toISOString().slice(0, 19).replace(/[:-]/g, '') + '.png';
                link.href = canvas.toDataURL();
                link.click();
            });
        }
    </script>
</body>
</html>"""
    
    return html
