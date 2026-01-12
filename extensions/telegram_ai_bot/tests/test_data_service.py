import unittest
from unittest.mock import patch

from services.data_service import filter_news, get_todays_news


class TestFilterNews(unittest.TestCase):
    def test_block_keyword_filters_out(self):
        items = [
            {"title": "New meme token launched", "rank": 1, "platform_id": "X"},
            {"title": "Protocol upgrade released", "rank": 2, "platform_id": "Y"},
        ]
        cfg = {
            "priority": ["security", "funding", "protocol", "regulation"],
            "block_keywords": ["meme"],
            "allow_keywords": [],
            "enable_noise_filter": False,
        }

        filtered, stats = filter_news(items, cfg)
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["dropped_block"], 1)
        self.assertEqual(len(filtered), 1)
        self.assertIn("Protocol", filtered[0]["title"])

    def test_noise_filter_filters_out(self):
        items = [
            {"title": "Big airdrop giveaway now", "rank": 1, "platform_id": "X"},
            {"title": "SEC regulation hearing announced", "rank": 2, "platform_id": "Y"},
        ]
        cfg = {
            "priority": ["security", "funding", "protocol", "regulation"],
            "block_keywords": [],
            "allow_keywords": [],
            "enable_noise_filter": True,
        }

        with patch("services.data_service.GLOBAL_NOISE_KEYWORDS", []):
            filtered, stats = filter_news(items, cfg)
            self.assertEqual(stats["total"], 2)
            self.assertEqual(stats["dropped_noise"], 1)
            self.assertEqual(len(filtered), 1)
            self.assertIn("SEC", filtered[0]["title"])


class TestGetTodaysNews(unittest.IsolatedAsyncioTestCase):
    async def test_get_todays_news_no_db_returns_empty(self):
        result = await get_todays_news(limit=10)
        self.assertIsInstance(result, list)
