"""
Adversarial tests for group digest generation.

Focus:
- Real AI digest path instead of fallback summary text
- Link preservation and HTML output safety
- Long message split behavior for Telegram limits
"""
import os
import sys
import importlib
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.mark.asyncio
async def test_generate_group_digest_contains_html_links_and_sections():
    """Blind spot: each selected item should keep clickable source link."""
    from services.digest_processor import generate_group_digest

    raw_content = [
        {"id": "1", "title": "ETH ETF inflow surges", "summary": "Large capital inflow today", "source": "CoinDesk", "link": "https://a.com/1"},
        {"id": "2", "title": "L2 fees drop", "summary": "Arbitrum and Base fees declined", "source": "The Block", "link": "https://a.com/2"},
    ]

    ai_result = {
        "must_read": [{"n": 1, "r": "market-moving"}],
        "macro_insights": [{"n": 2, "r": "industry trend"}],
        "recommended": [],
        "other": [],
    }

    with patch("services.llm_factory.call_llm_json", new_callable=AsyncMock, return_value=(ai_result, "mock-model")):
        with patch("services.content_filter.get_ai_summary", new_callable=AsyncMock, return_value="Key market themes today."):
            with patch("services.content_filter.translate_content", new_callable=AsyncMock, side_effect=lambda items, lang: items):
                with patch("services.content_filter.translate_text", new_callable=AsyncMock, side_effect=lambda text, lang: text):
                    digest = await generate_group_digest(raw_content, "Web3 macro + DeFi", "en")

    assert "<b>" in digest
    assert '<a href="https://a.com/1">' in digest
    assert '<a href="https://a.com/2">' in digest
    assert "MUST READ" in digest or "must_read" in digest
    assert "Industry Context" in digest or "macro_insights" in digest


@pytest.mark.asyncio
async def test_generate_group_digest_fallback_keeps_links_when_ai_fails():
    """Blind spot: malformed AI output should still send usable digest with links."""
    from services.digest_processor import generate_group_digest

    raw_content = [
        {"id": "1", "title": "A", "summary": "B", "source": "S1", "link": "https://x.com/1"},
        {"id": "2", "title": "C", "summary": "D", "source": "S2", "link": "https://x.com/2"},
    ]

    with patch("services.llm_factory.call_llm_json", new_callable=AsyncMock, return_value=(None, "mock-model")):
        with patch("services.content_filter.get_ai_summary", new_callable=AsyncMock, return_value="Fallback summary"):
            with patch("services.content_filter.translate_content", new_callable=AsyncMock, side_effect=lambda items, lang: items):
                with patch("services.content_filter.translate_text", new_callable=AsyncMock, side_effect=lambda text, lang: text):
                    digest = await generate_group_digest(raw_content, "General", "en")

    assert "Fallback summary" in digest
    assert '<a href="https://x.com/1">' in digest
    assert '<a href="https://x.com/2">' in digest


@pytest.mark.asyncio
async def test_group_digest_push_job_splits_long_message_and_appends_footer():
    """Adversarial: overlong digest should be split and footer appears on final chunk."""
    with patch("logging.handlers.TimedRotatingFileHandler", return_value=MagicMock()):
        if "main" in sys.modules:
            del sys.modules["main"]
        group_digest_push_job = importlib.import_module("main").group_digest_push_job

    beijing_hour = datetime.now(ZoneInfo("Asia/Shanghai")).hour
    config = {
        "group_id": "-10012345",
        "push_hour": beijing_hour,
        "profile": "General Web3",
        "language": "zh",
        "last_push_date": "1900-01-01",
    }

    ctx = MagicMock()
    ctx.bot = MagicMock()
    ctx.bot.send_message = AsyncMock()

    with patch("handlers.group.get_all_group_configs", return_value=[config]):
        with patch("services.rss_fetcher.fetch_all_sources", new_callable=AsyncMock, return_value=[{"id": "1"}]):
            with patch("services.digest_processor.generate_group_digest", new_callable=AsyncMock, return_value="LONG_DIGEST"):
                with patch("services.report_generator.split_report_for_telegram", return_value=["part-1", "part-2"]):
                    with patch("utils.json_storage.get_system_config", return_value="CTA-TEST"):
                        with patch("handlers.group.save_group_config") as mock_save:
                            await group_digest_push_job(ctx)

    assert ctx.bot.send_message.await_count == 2
    first_text = ctx.bot.send_message.await_args_list[0].kwargs["text"]
    second_text = ctx.bot.send_message.await_args_list[1].kwargs["text"]
    assert first_text == "part-1"
    assert "part-2" in second_text
    assert "CTA-TEST" in second_text
    mock_save.assert_called_once()
