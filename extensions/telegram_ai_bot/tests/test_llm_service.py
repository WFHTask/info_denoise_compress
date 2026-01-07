import json
import unittest
from unittest.mock import AsyncMock, patch

from services import llm_service


class _FakeMessage:
    def __init__(self, content: str):
        self.content = content


class _FakeChoice:
    def __init__(self, content: str):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str):
        self.choices = [_FakeChoice(content)]


class TestLlmService(unittest.IsolatedAsyncioTestCase):
    async def test_parse_user_intent_json_success(self):
        payload = {"type": "chat", "reply": "ok"}
        fake = _FakeResponse(json.dumps(payload, ensure_ascii=False))

        with patch.object(llm_service.config, "LLM_API_KEY", "k"):
            with patch.object(llm_service.config, "LLM_MODEL", "deepseek/deepseek-chat"):
                with patch("services.llm_service.acompletion", new=AsyncMock(return_value=fake)):
                    result, err = await llm_service.parse_user_intent(
                        "hi",
                        {"priority": ["security", "funding", "protocol", "regulation"], "block_keywords": [], "allow_keywords": []},
                    )

        self.assertIsNone(err)
        self.assertEqual(result, payload)

    async def test_parse_user_intent_rss_add(self):
        payload = {"type": "rss_add", "rss_url": "https://example.com/feed.xml"}
        fake = _FakeResponse(json.dumps(payload, ensure_ascii=False))

        with patch.object(llm_service.config, "LLM_API_KEY", "k"):
            with patch.object(llm_service.config, "LLM_MODEL", "deepseek/deepseek-chat"):
                with patch("services.llm_service.acompletion", new=AsyncMock(return_value=fake)):
                    result, err = await llm_service.parse_user_intent(
                        "订阅这个 RSS：https://example.com/feed.xml",
                        {"priority": ["security", "funding", "protocol", "regulation"], "block_keywords": [], "allow_keywords": []},
                    )

        self.assertIsNone(err)
        self.assertEqual(result, payload)

    async def test_parse_user_intent_missing_key(self):
        with patch.object(llm_service.config, "LLM_API_KEY", None):
            with patch.object(llm_service.config, "LLM_MODEL", "deepseek/deepseek-chat"):
                result, err = await llm_service.parse_user_intent(
                    "hi",
                    {"priority": ["security", "funding", "protocol", "regulation"], "block_keywords": [], "allow_keywords": []},
                    api_key=None,
                )

        self.assertIsNone(result)
        self.assertIsInstance(err, str)
        self.assertIn("API Key", err)

    async def test_generate_brief_maps_url_from_source_id(self):
        payload = {
            "date": "2025-01-01",
            "signals": [
                {
                    "title": "signal",
                    "source_id": 1,
                    "impact": "",
                    "related": "",
                    "hotness": "X#1",
                    "priority": "high",
                }
            ],
            "comment": "",
            "stats": {"total": 1},
        }
        fake = _FakeResponse(json.dumps(payload, ensure_ascii=False))
        captured = {}

        def _render(data: dict) -> str:
            captured["data"] = data
            return "ok"

        events = [
            {
                "event_type": "security",
                "title": "t",
                "platform_id": "X",
                "rank": 1,
                "url": "https://example.com/a",
            }
        ]
        cfg = {"priority": ["security"], "allow_keywords": []}

        with patch.object(llm_service.config, "LLM_API_KEY", "k"):
            with patch.object(llm_service.config, "LLM_MODEL", "deepseek/deepseek-chat"):
                with patch("services.llm_service.acompletion", new=AsyncMock(return_value=fake)):
                    with patch("services.llm_service.render_brief_data", side_effect=_render):
                        result, err = await llm_service.generate_brief(events, cfg)

        self.assertIsNone(err)
        self.assertEqual(result, "ok")
        self.assertEqual(captured["data"]["signals"][0]["url"], "https://example.com/a")
