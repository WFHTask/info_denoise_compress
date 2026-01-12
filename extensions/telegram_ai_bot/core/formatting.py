import re


def escape_markdown_v2(text: str) -> str:
    """
    Escapes special characters for Telegram MarkdownV2.
    """
    if not text:
        return ""
    # Special characters to escape:
    # _ * [ ] ( ) ~ > # + - = | { } . !
    special_chars = r"_*[]()~>#+-=|{}.!"
    return re.sub(f"([{re.escape(special_chars)}])", r"\\\1", str(text))

def escape_markdown_v2_url(url: str) -> str:
    """
    Escapes URL for Telegram MarkdownV2 link syntax.
    """
    if not url:
        return ""
    return url.replace("\\", "\\\\").replace(")", "\\)")


def render_brief_data(data: dict) -> str:
    """
    Renders structured brief data into Telegram MarkdownV2 format.

    Expected data structure:
    {
        "date": "YYYY-MM-DD",
        "signals": [
            {
                "title": "...",
                "impact": "...",
                "related": "...",
                "hotness": "...",
                "priority": "high" | "medium" | "low"
            },
            ...
        ],
        "comment": "...",
        "stats": {
            "total": 123
        }
    }
    """
    date_str = escape_markdown_v2(data.get("date", ""))

    # Header
    lines = [f"📊 *今日 Web3 核心信号* \\({date_str}\\)"]
    lines.append("")

    # Signals
    signals = data.get("signals", [])
    if not signals:
        lines.append(escape_markdown_v2("今日无重要信号。"))
    else:
        for signal in signals:
            priority = signal.get("priority", "low")
            icon = "🔴" if priority == "high" else ("🟡" if priority == "medium" else "🟢")

            title = escape_markdown_v2(signal.get("title", ""))
            url = signal.get("url", "")

            impact = escape_markdown_v2(signal.get("impact", ""))
            related = escape_markdown_v2(signal.get("related", ""))
            hotness = escape_markdown_v2(signal.get("hotness", ""))

            # Title line: Icon *Title* (with link if available)
            if url:
                # Escape URL for MarkdownV2 link syntax
                safe_url = escape_markdown_v2_url(url)
                lines.append(f"{icon} *[{title}]({safe_url})*")
            else:
                lines.append(f"{icon} *{title}*")

            # Details: using simple indentation
            if impact:
                lines.append(f"  📍 影响: {impact}")
            if related:
                lines.append(f"  🔗 相关: {related}")
            if hotness:
                lines.append(f"  📊 热度: {hotness}")
            lines.append("")

    # Comment
    comment = data.get("comment", "")
    if comment:
        lines.append("💡 *趋势点评*")
        lines.append(escape_markdown_v2(comment))
        lines.append("")

    # Stats
    stats = data.get("stats", {})
    total = stats.get("total", 0)
    lines.append("📈 *数据统计*")
    lines.append(escape_markdown_v2(f"- 候选信号: {total}条 (Top 50)"))

    return "\n".join(lines)


def render_event_analysis(data: dict) -> str:
    title = escape_markdown_v2(data.get("title", ""))
    url = data.get("url", "")
    summary = escape_markdown_v2(data.get("summary", ""))
    analysis = escape_markdown_v2(data.get("analysis", ""))
    impact = escape_markdown_v2(data.get("impact", ""))
    risks = data.get("risks", [])
    watch = data.get("watch", [])

    lines = [f"🔎 *事件解读*"]
    if title:
        if url:
            safe_url = escape_markdown_v2_url(url)
            lines.append(f"*标题*: [{title}]({safe_url})")
        else:
            lines.append(f"*标题*: {title}")
    if summary:
        lines.append(f"*摘要*: {summary}")
    if analysis:
        lines.append(f"*解读*: {analysis}")
    if impact:
        lines.append(f"*影响*: {impact}")
    if risks:
        lines.append("*风险*: " + ", ".join(escape_markdown_v2(x) for x in risks))
    if watch:
        lines.append("*关注*: " + ", ".join(escape_markdown_v2(x) for x in watch))

    return "\n".join(lines)
