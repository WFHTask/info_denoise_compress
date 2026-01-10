#!/usr/bin/env python
# coding=utf-8
"""
Web3 资讯 HTML 报告模板 - 赛博朋克风格

超炫酷特效：
- 粒子背景动画
- 霓虹灯光效果
- 3D 卡片悬浮
- 渐变流光动画
- 打字机效果
- 数字滚动动画
"""


def generate_cyber_html(all_items, source_stats, date_str, time_str, now_str):
    """生成赛博朋克风格的 HTML 报告"""

    # 生成新闻列表 HTML
    news_items_html = ""
    for i, item in enumerate(all_items, 1):
        delay = (i % 20) * 0.05
        # 使用 data-source 属性存储来源，用于筛选
        source_name = item['source'].replace('"', '&quot;')
        news_items_html += f'''
            <div class="news-item" data-source="{source_name}" style="animation-delay: {delay}s">
                <div class="news-rank {'top-3' if i <= 3 else ''}">{i}</div>
                <div class="news-content">
                    <a class="news-title" href="{item['url']}" target="_blank">
                        {item['title']}
                        <span class="link-icon">↗</span>
                    </a>
                    <div class="news-meta">
                        <span class="source-badge">{item['source']}</span>
                        <span class="time-badge">{'🕐 ' + item.get('time', '')[:16] if item.get('time') else ''}</span>
                    </div>
                </div>
                <div class="news-glow"></div>
            </div>
        '''

    # 统计爬虫源和 RSS 源
    crawler_sources = {}  # 爬虫源
    rss_sources = {}      # RSS 源

    for item in all_items:
        source = item['source']
        item_type = item.get('type', 'rss')
        if item_type == 'web3':
            crawler_sources[source] = crawler_sources.get(source, 0) + 1
        else:
            rss_sources[source] = rss_sources.get(source, 0) + 1

    # 生成来源标签 HTML - 分组显示
    colors_crawler = ['#06ffa5', '#00f5d4', '#39ff14']  # 绿色系 - 爬虫
    colors_rss = ['#00d4ff', '#ff006e', '#8338ec', '#ffbe0b', '#ff5400', '#f72585', '#00b4d8', '#e056fd']  # 多彩 - RSS

    # 全部按钮
    source_tags_html = '''
            <div class="source-tag active" data-filter="all" style="--tag-color: #ffffff">
                <span class="tag-dot"></span>
                全部
                <span class="tag-count">''' + str(len(all_items)) + '''</span>
            </div>
    '''

    # 爬虫源标签 HTML
    crawler_tags_html = ""
    for idx, (source, count) in enumerate(sorted(crawler_sources.items(), key=lambda x: -x[1])):
        color = colors_crawler[idx % len(colors_crawler)]
        source_name = source.replace('"', '&quot;')
        crawler_tags_html += f'''
            <div class="source-tag crawler-tag" data-filter="{source_name}" style="--tag-color: {color}">
                <span class="tag-dot"></span>
                <span class="tag-icon">🤖</span>
                {source}
                <span class="tag-count">{count}</span>
            </div>
        '''

    # RSS 源标签 HTML
    rss_tags_html = ""
    for idx, (source, count) in enumerate(sorted(rss_sources.items(), key=lambda x: -x[1])):
        color = colors_rss[idx % len(colors_rss)]
        source_name = source.replace('"', '&quot;')
        rss_tags_html += f'''
            <div class="source-tag rss-tag" data-filter="{source_name}" style="--tag-color: {color}">
                <span class="tag-dot"></span>
                <span class="tag-icon">📡</span>
                {source}
                <span class="tag-count">{count}</span>
            </div>
        '''

    total_count = len(all_items)
    source_count = len(source_stats)
    web3_count = sum(crawler_sources.values())
    rss_count = sum(rss_sources.values())
    crawler_source_count = len(crawler_sources)
    rss_source_count = len(rss_sources)

    html_content = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🌐 Web3 资讯日报 - {date_str}</title>
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Rajdhani:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --neon-blue: #00d4ff;
            --neon-purple: #8338ec;
            --neon-pink: #ff006e;
            --neon-green: #06ffa5;
            --neon-yellow: #ffbe0b;
            --dark-bg: #0a0a0f;
            --card-bg: rgba(15, 15, 25, 0.8);
        }}

        * {{ box-sizing: border-box; margin: 0; padding: 0; }}

        body {{
            font-family: 'Rajdhani', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--dark-bg);
            min-height: 100vh;
            color: #e0e0e0;
            overflow-x: hidden;
        }}

        /* ========== 粒子背景 Canvas ========== */
        #particles-canvas {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: 0;
            pointer-events: none;
        }}

        /* ========== 网格背景 ========== */
        .grid-bg {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 200%;
            background-image:
                linear-gradient(rgba(0, 212, 255, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 212, 255, 0.03) 1px, transparent 1px);
            background-size: 60px 60px;
            z-index: 0;
            transform: perspective(500px) rotateX(60deg);
            transform-origin: top;
            animation: gridScroll 15s linear infinite;
        }}

        @keyframes gridScroll {{
            0% {{ transform: perspective(500px) rotateX(60deg) translateY(0); }}
            100% {{ transform: perspective(500px) rotateX(60deg) translateY(60px); }}
        }}

        /* ========== 光晕球体 ========== */
        .glow-orb {{
            position: fixed;
            border-radius: 50%;
            filter: blur(100px);
            opacity: 0.3;
            z-index: 0;
            animation: floatOrb 10s ease-in-out infinite;
        }}

        .glow-orb-1 {{
            width: 500px;
            height: 500px;
            background: var(--neon-blue);
            top: -150px;
            right: -150px;
        }}

        .glow-orb-2 {{
            width: 400px;
            height: 400px;
            background: var(--neon-purple);
            bottom: -100px;
            left: -100px;
            animation-delay: -5s;
        }}

        .glow-orb-3 {{
            width: 300px;
            height: 300px;
            background: var(--neon-pink);
            top: 40%;
            left: 60%;
            animation-delay: -2.5s;
        }}

        @keyframes floatOrb {{
            0%, 100% {{ transform: translate(0, 0) scale(1); }}
            25% {{ transform: translate(50px, -50px) scale(1.1); }}
            50% {{ transform: translate(-30px, 30px) scale(0.95); }}
            75% {{ transform: translate(20px, 50px) scale(1.05); }}
        }}

        /* ========== 扫描线效果 ========== */
        .scanline {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: linear-gradient(
                to bottom,
                transparent 50%,
                rgba(0, 0, 0, 0.1) 50%
            );
            background-size: 100% 4px;
            z-index: 1;
            pointer-events: none;
            opacity: 0.3;
        }}

        /* ========== 主容器 ========== */
        .container {{
            max-width: 1100px;
            margin: 0 auto;
            padding: 30px 20px;
            position: relative;
            z-index: 2;
        }}

        /* ========== 超炫酷头部 ========== */
        .header {{
            text-align: center;
            padding: 60px 40px;
            margin-bottom: 50px;
            position: relative;
            overflow: hidden;
        }}

        .header::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(135deg,
                rgba(0, 212, 255, 0.08) 0%,
                rgba(131, 56, 236, 0.08) 50%,
                rgba(255, 0, 110, 0.08) 100%);
            border: 1px solid rgba(0, 212, 255, 0.2);
            border-radius: 30px;
            z-index: -1;
        }}

        .header::after {{
            content: '';
            position: absolute;
            top: -3px;
            left: -3px;
            right: -3px;
            bottom: -3px;
            background: linear-gradient(45deg,
                var(--neon-blue),
                var(--neon-purple),
                var(--neon-pink),
                var(--neon-green),
                var(--neon-blue));
            background-size: 400% 400%;
            border-radius: 32px;
            z-index: -2;
            opacity: 0.5;
            filter: blur(15px);
            animation: borderGlow 4s ease infinite;
        }}

        @keyframes borderGlow {{
            0% {{ background-position: 0% 50%; opacity: 0.5; }}
            50% {{ background-position: 100% 50%; opacity: 0.8; }}
            100% {{ background-position: 0% 50%; opacity: 0.5; }}
        }}

        /* 标题动画 */
        .cyber-title {{
            font-family: 'Orbitron', monospace;
            font-size: 52px;
            font-weight: 900;
            background: linear-gradient(90deg,
                var(--neon-blue),
                var(--neon-purple),
                var(--neon-pink),
                var(--neon-blue));
            background-size: 300% 100%;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            animation: gradientFlow 4s ease infinite;
            margin-bottom: 15px;
            letter-spacing: 6px;
            text-transform: uppercase;
            position: relative;
        }}

        .cyber-title::after {{
            content: 'WEB3 DAILY';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            background: linear-gradient(90deg,
                var(--neon-blue),
                var(--neon-purple),
                var(--neon-pink),
                var(--neon-blue));
            background-size: 300% 100%;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            animation: gradientFlow 4s ease infinite;
            filter: blur(20px);
            opacity: 0.6;
            z-index: -1;
        }}

        @keyframes gradientFlow {{
            0% {{ background-position: 0% center; }}
            50% {{ background-position: 100% center; }}
            100% {{ background-position: 0% center; }}
        }}

        .cyber-subtitle {{
            font-family: 'Orbitron', monospace;
            font-size: 12px;
            color: var(--neon-green);
            letter-spacing: 10px;
            text-transform: uppercase;
            margin-bottom: 25px;
            animation: flicker 3s infinite;
        }}

        @keyframes flicker {{
            0%, 100% {{ opacity: 1; }}
            92% {{ opacity: 1; }}
            93% {{ opacity: 0.3; }}
            94% {{ opacity: 1; }}
            95% {{ opacity: 0.5; }}
            96% {{ opacity: 1; }}
        }}

        .date-display {{
            font-size: 18px;
            color: rgba(255, 255, 255, 0.6);
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 20px;
        }}

        .date-display .date {{
            color: var(--neon-blue);
            font-weight: 700;
            font-family: 'Orbitron', monospace;
        }}

        .date-display .separator {{
            width: 30px;
            height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-blue), transparent);
        }}

        /* ========== 统计卡片 - 3D 全息效果 ========== */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 50px;
        }}

        .stat-card {{
            background: var(--card-bg);
            border: 1px solid rgba(0, 212, 255, 0.15);
            border-radius: 20px;
            padding: 30px 20px;
            text-align: center;
            position: relative;
            overflow: hidden;
            transform-style: preserve-3d;
            transition: all 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            cursor: pointer;
        }}

        .stat-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: -150%;
            width: 150%;
            height: 100%;
            background: linear-gradient(
                90deg,
                transparent,
                rgba(255, 255, 255, 0.1),
                transparent
            );
            transform: skewX(-20deg);
            transition: left 0.7s ease;
        }}

        .stat-card:hover {{
            transform: translateY(-15px) rotateX(10deg) rotateY(-5deg);
            border-color: var(--neon-blue);
            box-shadow:
                0 30px 60px rgba(0, 212, 255, 0.3),
                0 0 50px rgba(0, 212, 255, 0.1),
                inset 0 0 50px rgba(0, 212, 255, 0.05);
        }}

        .stat-card:hover::before {{
            left: 150%;
        }}

        .stat-icon {{
            font-size: 36px;
            margin-bottom: 15px;
            display: block;
        }}

        .stat-number {{
            font-family: 'Orbitron', monospace;
            font-size: 48px;
            font-weight: 900;
            background: linear-gradient(180deg, #ffffff, var(--neon-blue));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            position: relative;
            display: inline-block;
        }}

        .stat-number::after {{
            content: attr(data-value);
            position: absolute;
            top: 0;
            left: 0;
            background: linear-gradient(180deg, #ffffff, var(--neon-blue));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            filter: blur(15px);
            opacity: 0.5;
        }}

        .stat-label {{
            font-size: 11px;
            color: rgba(255, 255, 255, 0.4);
            text-transform: uppercase;
            letter-spacing: 3px;
            margin-top: 10px;
        }}

        /* ========== 来源标签区域 ========== */
        .source-section {{
            margin-bottom: 50px;
        }}

        .section-title {{
            font-family: 'Orbitron', monospace;
            font-size: 14px;
            color: var(--neon-blue);
            letter-spacing: 6px;
            text-transform: uppercase;
            margin-bottom: 25px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 20px;
        }}

        .section-title::before,
        .section-title::after {{
            content: '';
            width: 100px;
            height: 1px;
            background: linear-gradient(90deg, transparent, var(--neon-blue), transparent);
        }}

        /* 分组容器 */
        .source-groups {{
            display: flex;
            flex-direction: column;
            gap: 30px;
        }}

        .source-group {{
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 20px;
            padding: 25px;
        }}

        .source-group-header {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }}

        .source-group-icon {{
            font-size: 24px;
        }}

        .source-group-title {{
            font-family: 'Orbitron', monospace;
            font-size: 13px;
            letter-spacing: 3px;
            text-transform: uppercase;
        }}

        .source-group.crawler .source-group-title {{
            color: var(--neon-green);
        }}

        .source-group.rss .source-group-title {{
            color: var(--neon-blue);
        }}

        .source-group-count {{
            font-family: 'Orbitron', monospace;
            font-size: 11px;
            color: rgba(255, 255, 255, 0.4);
            margin-left: auto;
        }}

        .source-tags {{
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            justify-content: flex-start;
        }}

        .all-filter {{
            display: flex;
            justify-content: center;
            margin-bottom: 25px;
        }}

        .tag-icon {{
            font-size: 12px;
            margin-right: 2px;
        }}

        .source-tag {{
            background: rgba(0, 0, 0, 0.5);
            border: 1px solid var(--tag-color);
            padding: 12px 22px;
            border-radius: 30px;
            font-size: 14px;
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 12px;
            transition: all 0.4s ease;
            position: relative;
            overflow: hidden;
        }}

        .source-tag::before {{
            content: '';
            position: absolute;
            top: 50%;
            left: 50%;
            width: 0;
            height: 0;
            background: var(--tag-color);
            border-radius: 50%;
            transform: translate(-50%, -50%);
            transition: all 0.5s ease;
            opacity: 0.1;
        }}

        .source-tag:hover {{
            transform: scale(1.08) translateY(-3px);
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3), 0 0 30px var(--tag-color);
        }}

        .source-tag:hover::before {{
            width: 300px;
            height: 300px;
        }}

        .tag-dot {{
            width: 10px;
            height: 10px;
            background: var(--tag-color);
            border-radius: 50%;
            box-shadow: 0 0 15px var(--tag-color);
            animation: pulse 2s ease-in-out infinite;
        }}

        @keyframes pulse {{
            0%, 100% {{ opacity: 1; transform: scale(1); box-shadow: 0 0 15px var(--tag-color); }}
            50% {{ opacity: 0.6; transform: scale(1.3); box-shadow: 0 0 25px var(--tag-color); }}
        }}

        .tag-count {{
            background: var(--tag-color);
            color: #000;
            padding: 3px 12px;
            border-radius: 20px;
            font-weight: 700;
            font-size: 12px;
            font-family: 'Orbitron', monospace;
        }}

        /* ========== 来源标签交互样式 ========== */
        .source-tag {{
            cursor: pointer;
            user-select: none;
        }}

        .source-tag.active {{
            transform: scale(1.08) translateY(-3px);
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3), 0 0 30px var(--tag-color);
            background: rgba(var(--tag-color), 0.2);
        }}

        .source-tag.active::before {{
            width: 300px;
            height: 300px;
        }}

        .source-tag.active .tag-dot {{
            animation: pulse 0.8s ease-in-out infinite;
        }}

        /* ========== 筛选状态栏 ========== */
        .filter-status {{
            display: none;
            align-items: center;
            gap: 15px;
            padding: 15px 35px;
            background: linear-gradient(90deg, rgba(0, 212, 255, 0.1), rgba(131, 56, 236, 0.1));
            border-bottom: 1px solid rgba(0, 212, 255, 0.15);
            font-size: 14px;
            color: rgba(255, 255, 255, 0.7);
            animation: slideDown 0.3s ease;
        }}

        .filter-status.show {{
            display: flex;
        }}

        @keyframes slideDown {{
            from {{
                opacity: 0;
                transform: translateY(-10px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}

        .filter-source {{
            font-family: 'Orbitron', monospace;
            font-weight: 700;
            color: var(--neon-blue);
            background: rgba(0, 212, 255, 0.15);
            padding: 5px 15px;
            border-radius: 20px;
            border: 1px solid rgba(0, 212, 255, 0.3);
        }}

        .filter-count {{
            font-family: 'Orbitron', monospace;
            color: var(--neon-green);
        }}

        .clear-filter {{
            margin-left: auto;
            background: rgba(255, 0, 110, 0.15);
            border: 1px solid rgba(255, 0, 110, 0.3);
            color: var(--neon-pink);
            padding: 8px 18px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 12px;
            font-weight: 600;
            transition: all 0.3s ease;
        }}

        .clear-filter:hover {{
            background: rgba(255, 0, 110, 0.3);
            box-shadow: 0 0 20px rgba(255, 0, 110, 0.4);
            transform: scale(1.05);
        }}

        /* ========== 新闻条目隐藏样式 ========== */
        .news-item.hidden {{
            display: none !important;
        }}

        /* ========== 新闻列表区域 ========== */
        .news-section {{
            background: var(--card-bg);
            border: 1px solid rgba(0, 212, 255, 0.12);
            border-radius: 24px;
            overflow: hidden;
            position: relative;
        }}

        /* LIVE 指示器 */
        .live-indicator {{
            position: absolute;
            top: 25px;
            right: 25px;
            display: flex;
            align-items: center;
            gap: 10px;
            font-family: 'Orbitron', monospace;
            font-size: 10px;
            color: var(--neon-green);
            letter-spacing: 3px;
        }}

        .live-dot {{
            width: 10px;
            height: 10px;
            background: var(--neon-green);
            border-radius: 50%;
            box-shadow: 0 0 20px var(--neon-green);
            animation: livePulse 1.5s infinite;
        }}

        @keyframes livePulse {{
            0%, 100% {{ opacity: 1; transform: scale(1); }}
            50% {{ opacity: 0.4; transform: scale(0.8); }}
        }}

        .news-header {{
            padding: 30px 35px;
            border-bottom: 1px solid rgba(0, 212, 255, 0.08);
            display: flex;
            align-items: center;
            gap: 20px;
        }}

        .news-header h2 {{
            font-family: 'Orbitron', monospace;
            font-size: 18px;
            color: #fff;
            letter-spacing: 3px;
            text-transform: uppercase;
        }}

        .header-line {{
            flex: 1;
            height: 1px;
            background: linear-gradient(90deg, var(--neon-blue), transparent);
        }}

        .news-list {{
            max-height: 900px;
            overflow-y: auto;
            scroll-behavior: smooth;
        }}

        .news-list::-webkit-scrollbar {{
            width: 8px;
        }}

        .news-list::-webkit-scrollbar-track {{
            background: rgba(0, 0, 0, 0.3);
        }}

        .news-list::-webkit-scrollbar-thumb {{
            background: linear-gradient(180deg, var(--neon-blue), var(--neon-purple));
            border-radius: 4px;
        }}

        .news-item {{
            display: flex;
            align-items: flex-start;
            gap: 18px;
            padding: 22px 35px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.02);
            position: relative;
            transition: all 0.4s ease;
            animation: slideInNews 0.6s ease forwards;
            opacity: 0;
            transform: translateX(-30px);
        }}

        @keyframes slideInNews {{
            to {{
                opacity: 1;
                transform: translateX(0);
            }}
        }}

        .news-item:hover {{
            background: linear-gradient(90deg, rgba(0, 212, 255, 0.08), transparent);
        }}

        .news-item:hover .news-glow {{
            opacity: 1;
            height: 100%;
        }}

        .news-glow {{
            position: absolute;
            left: 0;
            top: 50%;
            transform: translateY(-50%);
            height: 0;
            width: 4px;
            background: linear-gradient(180deg, var(--neon-blue), var(--neon-purple), var(--neon-pink));
            opacity: 0;
            transition: all 0.4s ease;
            border-radius: 2px;
            box-shadow: 0 0 20px var(--neon-blue);
        }}

        .news-rank {{
            font-family: 'Orbitron', monospace;
            font-size: 13px;
            font-weight: 700;
            min-width: 40px;
            height: 40px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            color: rgba(255, 255, 255, 0.5);
            transition: all 0.3s ease;
        }}

        .news-rank.top-3 {{
            background: linear-gradient(135deg, var(--neon-blue), var(--neon-purple));
            border: none;
            color: #fff;
            box-shadow: 0 0 25px rgba(0, 212, 255, 0.5);
            animation: glowPulse 2s ease-in-out infinite;
        }}

        @keyframes glowPulse {{
            0%, 100% {{ box-shadow: 0 0 25px rgba(0, 212, 255, 0.5); }}
            50% {{ box-shadow: 0 0 35px rgba(0, 212, 255, 0.8); }}
        }}

        .news-content {{
            flex: 1;
            min-width: 0;
        }}

        .news-title {{
            font-size: 16px;
            font-weight: 500;
            color: #fff;
            text-decoration: none;
            line-height: 1.7;
            display: block;
            transition: all 0.3s ease;
        }}

        .news-title:hover {{
            color: var(--neon-blue);
            text-shadow: 0 0 30px rgba(0, 212, 255, 0.5);
        }}

        .link-icon {{
            opacity: 0;
            margin-left: 10px;
            transition: all 0.3s ease;
            display: inline-block;
            color: var(--neon-blue);
        }}

        .news-title:hover .link-icon {{
            opacity: 1;
            transform: translate(5px, -5px);
        }}

        .news-meta {{
            margin-top: 12px;
            display: flex;
            align-items: center;
            gap: 15px;
            flex-wrap: wrap;
        }}

        .source-badge {{
            font-size: 11px;
            padding: 5px 14px;
            background: rgba(131, 56, 236, 0.15);
            border: 1px solid rgba(131, 56, 236, 0.25);
            border-radius: 20px;
            color: var(--neon-purple);
            font-weight: 500;
        }}

        .time-badge {{
            font-size: 11px;
            color: rgba(255, 255, 255, 0.35);
            font-family: 'Orbitron', monospace;
            letter-spacing: 1px;
        }}

        /* ========== 页脚 ========== */
        .footer {{
            text-align: center;
            padding: 60px 20px 40px;
            position: relative;
        }}

        .footer-logo {{
            font-family: 'Orbitron', monospace;
            font-size: 28px;
            font-weight: 900;
            background: linear-gradient(90deg, var(--neon-blue), var(--neon-purple), var(--neon-pink));
            background-size: 200% auto;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            animation: gradientFlow 3s ease infinite;
            margin-bottom: 15px;
        }}

        .footer-line {{
            width: 150px;
            height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-blue), var(--neon-purple), transparent);
            margin: 20px auto;
        }}

        .footer-text {{
            color: rgba(255, 255, 255, 0.3);
            font-size: 12px;
            letter-spacing: 3px;
            text-transform: uppercase;
        }}

        .footer-time {{
            margin-top: 15px;
            font-family: 'Orbitron', monospace;
            font-size: 11px;
            color: var(--neon-blue);
            opacity: 0.6;
        }}

        /* ========== 响应式设计 ========== */
        @media (max-width: 900px) {{
            .stats-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
        }}

        @media (max-width: 600px) {{
            .cyber-title {{
                font-size: 28px;
                letter-spacing: 3px;
            }}

            .stat-number {{
                font-size: 32px;
            }}

            .stats-grid {{
                grid-template-columns: 1fr 1fr;
                gap: 12px;
            }}

            .stat-card {{
                padding: 20px 15px;
            }}

            .news-item {{
                padding: 18px 20px;
            }}

            .source-tags {{
                gap: 10px;
            }}

            .source-tag {{
                padding: 8px 15px;
                font-size: 12px;
            }}
        }}

        /* ========== 加载动画 ========== */
        .loading-overlay {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: var(--dark-bg);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            z-index: 9999;
            transition: all 0.8s ease;
        }}

        .loading-overlay.hidden {{
            opacity: 0;
            visibility: hidden;
        }}

        .loader-ring {{
            width: 80px;
            height: 80px;
            border-radius: 50%;
            position: relative;
        }}

        .loader-ring::before,
        .loader-ring::after {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            border-radius: 50%;
            border: 3px solid transparent;
        }}

        .loader-ring::before {{
            border-top-color: var(--neon-blue);
            animation: spin 1s linear infinite;
        }}

        .loader-ring::after {{
            border-bottom-color: var(--neon-pink);
            animation: spin 1s linear infinite reverse;
        }}

        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}

        .loader-text {{
            font-family: 'Orbitron', monospace;
            font-size: 12px;
            color: var(--neon-blue);
            letter-spacing: 5px;
            margin-top: 30px;
            animation: flicker 2s infinite;
        }}
    </style>
</head>
<body>
    <!-- 加载动画 -->
    <div class="loading-overlay" id="loader">
        <div class="loader-ring"></div>
        <div class="loader-text">LOADING</div>
    </div>

    <!-- 背景特效 -->
    <canvas id="particles-canvas"></canvas>
    <div class="grid-bg"></div>
    <div class="glow-orb glow-orb-1"></div>
    <div class="glow-orb glow-orb-2"></div>
    <div class="glow-orb glow-orb-3"></div>
    <div class="scanline"></div>

    <div class="container">
        <!-- 头部 -->
        <header class="header">
            <div class="cyber-subtitle">// BLOCKCHAIN INTELLIGENCE //</div>
            <h1 class="cyber-title">WEB3 DAILY</h1>
            <div class="date-display">
                <span class="separator"></span>
                <span class="date">{date_str}</span>
                <span class="separator"></span>
                <span>{time_str} 更新</span>
                <span class="separator"></span>
            </div>
        </header>

        <!-- 统计卡片 -->
        <div class="stats-grid">
            <div class="stat-card">
                <span class="stat-icon">📊</span>
                <div class="stat-number" data-value="{total_count}">{total_count}</div>
                <div class="stat-label">Total News</div>
            </div>
            <div class="stat-card">
                <span class="stat-icon">🌐</span>
                <div class="stat-number" data-value="{source_count}">{source_count}</div>
                <div class="stat-label">Data Sources</div>
            </div>
            <div class="stat-card">
                <span class="stat-icon">🤖</span>
                <div class="stat-number" data-value="{web3_count}">{web3_count}</div>
                <div class="stat-label">Crawler</div>
            </div>
            <div class="stat-card">
                <span class="stat-icon">📡</span>
                <div class="stat-number" data-value="{rss_count}">{rss_count}</div>
                <div class="stat-label">RSS Feed</div>
            </div>
        </div>

        <!-- 来源标签 -->
        <div class="source-section">
            <div class="section-title">DATA SOURCES</div>

            <!-- 全部按钮 -->
            <div class="all-filter">
                <div class="source-tags">
                    {source_tags_html}
                </div>
            </div>

            <!-- 分组显示 -->
            <div class="source-groups">
                <!-- 爬虫源 -->
                <div class="source-group crawler">
                    <div class="source-group-header">
                        <span class="source-group-icon">🤖</span>
                        <span class="source-group-title">Web3 Crawler</span>
                        <span class="source-group-count">{crawler_source_count} 源 / {web3_count} 条</span>
                    </div>
                    <div class="source-tags">
                        {crawler_tags_html}
                    </div>
                </div>

                <!-- RSS 源 -->
                <div class="source-group rss">
                    <div class="source-group-header">
                        <span class="source-group-icon">📡</span>
                        <span class="source-group-title">RSS Feed</span>
                        <span class="source-group-count">{rss_source_count} 源 / {rss_count} 条</span>
                    </div>
                    <div class="source-tags">
                        {rss_tags_html}
                    </div>
                </div>
            </div>
        </div>

        <!-- 新闻列表 -->
        <div class="news-section">
            <div class="live-indicator">
                <div class="live-dot"></div>
                LIVE FEED
            </div>
            <div class="news-header">
                <h2>📰 Latest News</h2>
                <div class="header-line"></div>
            </div>
            <div class="filter-status" id="filterStatus">
                <span>📍 当前筛选：</span>
                <span class="filter-source" id="filterSourceName">-</span>
                <span class="filter-count"><span id="filterCount">0</span> 条</span>
                <button class="clear-filter" onclick="clearFilter()">✕ 清除筛选</button>
            </div>
            <div class="news-list" id="newsList">
                {news_items_html}
            </div>
        </div>

        <!-- 页脚 -->
        <footer class="footer">
            <div class="footer-logo">VOIVERSE</div>
            <div class="footer-line"></div>
            <div class="footer-text">Web3 Intelligence System</div>
            <div class="footer-time">Generated: {now_str}</div>
        </footer>
    </div>

    <!-- 粒子动画脚本 -->
    <script>
        // 隐藏加载动画
        window.addEventListener('load', function() {{
            setTimeout(function() {{
                document.getElementById('loader').classList.add('hidden');
            }}, 800);
        }});

        // 粒子背景
        const canvas = document.getElementById('particles-canvas');
        const ctx = canvas.getContext('2d');

        function resizeCanvas() {{
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
        }}
        resizeCanvas();
        window.addEventListener('resize', resizeCanvas);

        const particles = [];
        const particleCount = 80;
        const colors = ['#00d4ff', '#8338ec', '#ff006e', '#06ffa5'];

        class Particle {{
            constructor() {{
                this.reset();
            }}

            reset() {{
                this.x = Math.random() * canvas.width;
                this.y = Math.random() * canvas.height;
                this.size = Math.random() * 2 + 0.5;
                this.speedX = (Math.random() - 0.5) * 0.5;
                this.speedY = (Math.random() - 0.5) * 0.5;
                this.color = colors[Math.floor(Math.random() * colors.length)];
                this.alpha = Math.random() * 0.5 + 0.2;
            }}

            update() {{
                this.x += this.speedX;
                this.y += this.speedY;

                if (this.x < 0 || this.x > canvas.width) this.speedX *= -1;
                if (this.y < 0 || this.y > canvas.height) this.speedY *= -1;
            }}

            draw() {{
                ctx.beginPath();
                ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
                ctx.fillStyle = this.color;
                ctx.globalAlpha = this.alpha;
                ctx.fill();
                ctx.globalAlpha = 1;
            }}
        }}

        // 初始化粒子
        for (let i = 0; i < particleCount; i++) {{
            particles.push(new Particle());
        }}

        // 连接粒子的线
        function connectParticles() {{
            for (let i = 0; i < particles.length; i++) {{
                for (let j = i + 1; j < particles.length; j++) {{
                    const dx = particles[i].x - particles[j].x;
                    const dy = particles[i].y - particles[j].y;
                    const distance = Math.sqrt(dx * dx + dy * dy);

                    if (distance < 150) {{
                        ctx.beginPath();
                        ctx.strokeStyle = particles[i].color;
                        ctx.globalAlpha = 0.1 * (1 - distance / 150);
                        ctx.lineWidth = 0.5;
                        ctx.moveTo(particles[i].x, particles[i].y);
                        ctx.lineTo(particles[j].x, particles[j].y);
                        ctx.stroke();
                        ctx.globalAlpha = 1;
                    }}
                }}
            }}
        }}

        // 动画循环
        function animate() {{
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            particles.forEach(particle => {{
                particle.update();
                particle.draw();
            }});

            connectParticles();
            requestAnimationFrame(animate);
        }}

        animate();

        // 数字滚动动画
        function animateNumbers() {{
            const numbers = document.querySelectorAll('.stat-number');
            numbers.forEach(num => {{
                const target = parseInt(num.getAttribute('data-value'));
                const duration = 2000;
                const start = performance.now();

                function update(currentTime) {{
                    const elapsed = currentTime - start;
                    const progress = Math.min(elapsed / duration, 1);
                    const easeOut = 1 - Math.pow(1 - progress, 3);
                    const current = Math.floor(target * easeOut);
                    num.textContent = current;

                    if (progress < 1) {{
                        requestAnimationFrame(update);
                    }}
                }}

                requestAnimationFrame(update);
            }});
        }}

        // 页面加载后启动数字动画
        setTimeout(animateNumbers, 1000);

        // 鼠标移动视差效果
        document.addEventListener('mousemove', function(e) {{
            const orbs = document.querySelectorAll('.glow-orb');
            const x = e.clientX / window.innerWidth;
            const y = e.clientY / window.innerHeight;

            orbs.forEach((orb, index) => {{
                const speed = (index + 1) * 20;
                orb.style.transform = `translate(${{(x - 0.5) * speed}}px, ${{(y - 0.5) * speed}}px)`;
            }});
        }});

        // ========== 数据源筛选功能 ==========
        let currentFilter = 'all';

        // 为所有来源标签添加点击事件
        document.querySelectorAll('.source-tag').forEach(tag => {{
            tag.addEventListener('click', function() {{
                const filterValue = this.getAttribute('data-filter');
                filterNews(filterValue, this);
            }});
        }});

        // 筛选新闻函数
        function filterNews(source, clickedTag) {{
            currentFilter = source;
            const newsItems = document.querySelectorAll('.news-item');
            const filterStatus = document.getElementById('filterStatus');
            const filterSourceName = document.getElementById('filterSourceName');
            const filterCount = document.getElementById('filterCount');

            // 更新标签激活状态
            document.querySelectorAll('.source-tag').forEach(tag => {{
                tag.classList.remove('active');
            }});
            clickedTag.classList.add('active');

            let visibleCount = 0;

            if (source === 'all') {{
                // 显示全部
                newsItems.forEach((item, index) => {{
                    item.classList.remove('hidden');
                    item.style.animationDelay = (index % 20) * 0.05 + 's';
                    visibleCount++;
                }});
                filterStatus.classList.remove('show');
            }} else {{
                // 筛选特定来源
                newsItems.forEach((item, index) => {{
                    const itemSource = item.getAttribute('data-source');
                    if (itemSource === source) {{
                        item.classList.remove('hidden');
                        item.style.animationDelay = (visibleCount % 20) * 0.03 + 's';
                        visibleCount++;
                    }} else {{
                        item.classList.add('hidden');
                    }}
                }});

                // 显示筛选状态
                filterSourceName.textContent = source;
                filterCount.textContent = visibleCount;
                filterStatus.classList.add('show');
            }}

            // 更新序号
            updateRankNumbers();

            // 滚动到新闻列表顶部
            document.getElementById('newsList').scrollTop = 0;
        }}

        // 更新新闻序号
        function updateRankNumbers() {{
            const visibleItems = document.querySelectorAll('.news-item:not(.hidden)');
            visibleItems.forEach((item, index) => {{
                const rankEl = item.querySelector('.news-rank');
                const newRank = index + 1;
                rankEl.textContent = newRank;

                // 更新 top-3 样式
                if (newRank <= 3) {{
                    rankEl.classList.add('top-3');
                }} else {{
                    rankEl.classList.remove('top-3');
                }}
            }});
        }}

        // 清除筛选
        function clearFilter() {{
            const allTag = document.querySelector('.source-tag[data-filter="all"]');
            filterNews('all', allTag);
        }}

        // 快捷键支持：ESC 清除筛选
        document.addEventListener('keydown', function(e) {{
            if (e.key === 'Escape' && currentFilter !== 'all') {{
                clearFilter();
            }}
        }});
    </script>
</body>
</html>'''

    return html_content
