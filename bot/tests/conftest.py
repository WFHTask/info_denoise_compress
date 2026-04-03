"""
Pytest configuration and shared fixtures for Sprint1 tests.

Provides:
- Mock Telegram Bot/Context/Update/CallbackQuery
- Mock LLM Provider (returns preset JSON)
- Temporary data directories for isolated tests
- Test data factory functions
"""
import os
import sys
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add bot directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============ Temporary Data Directory Fixture ============

@pytest.fixture
def tmp_data_dir(tmp_path, monkeypatch):
    """Create temporary data directory for tests with all subdirectories."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    subdirs = [
        "profiles", "feedback", "daily_stats", "raw_content",
        "user_sources", "prefetch_cache", "events", "logs",
        "source_health", "group_configs"
    ]
    for subdir in subdirs:
        (data_dir / subdir).mkdir()

    monkeypatch.setattr("config.DATA_DIR", str(data_dir))
    monkeypatch.setattr("config.USERS_FILE", str(data_dir / "users.json"))
    monkeypatch.setattr("config.PROFILES_DIR", str(data_dir / "profiles"))
    monkeypatch.setattr("config.FEEDBACK_DIR", str(data_dir / "feedback"))
    monkeypatch.setattr("config.DAILY_STATS_DIR", str(data_dir / "daily_stats"))
    monkeypatch.setattr("config.RAW_CONTENT_DIR", str(data_dir / "raw_content"))
    monkeypatch.setattr("config.USER_SOURCES_DIR", str(data_dir / "user_sources"))
    monkeypatch.setattr("config.PREFETCH_CACHE_DIR", str(data_dir / "prefetch_cache"))
    monkeypatch.setattr("config.EVENTS_DIR", str(data_dir / "events"))
    monkeypatch.setattr("config.SOURCE_HEALTH_DIR", str(data_dir / "source_health"))
    monkeypatch.setattr("config.GROUP_CONFIGS_DIR", str(data_dir / "group_configs"))
    monkeypatch.setattr("config.PLAN_CONFIG_FILE", str(data_dir / "plan_config.json"))
    monkeypatch.setattr("config.WHITELIST_FILE", str(data_dir / "whitelist.json"))
    monkeypatch.setattr("config.WHITELIST_SETTINGS_FILE", str(data_dir / "whitelist_settings.json"))

    try:
        import utils.json_storage as storage
        monkeypatch.setattr(storage, "SYSTEM_CONFIG_FILE", str(data_dir / "system_config.json"))
        monkeypatch.setattr(storage, "DATA_DIR", str(data_dir))
        monkeypatch.setattr(storage, "USERS_FILE", str(data_dir / "users.json"))
        monkeypatch.setattr(storage, "PROFILES_DIR", str(data_dir / "profiles"))
        monkeypatch.setattr(storage, "FEEDBACK_DIR", str(data_dir / "feedback"))
        monkeypatch.setattr(storage, "DAILY_STATS_DIR", str(data_dir / "daily_stats"))
        monkeypatch.setattr(storage, "RAW_CONTENT_DIR", str(data_dir / "raw_content"))
        monkeypatch.setattr(storage, "USER_SOURCES_DIR", str(data_dir / "user_sources"))
        monkeypatch.setattr(storage, "PREFETCH_CACHE_DIR", str(data_dir / "prefetch_cache"))
        monkeypatch.setattr(storage, "EVENTS_DIR", str(data_dir / "events"))
    except Exception:
        pass

    return data_dir


# ============ Mock Telegram Objects ============

@pytest.fixture
def mock_user():
    """Create a mock Telegram User."""
    user = MagicMock()
    user.id = 123456789
    user.username = "testuser"
    user.first_name = "Test"
    user.last_name = "User"
    user.language_code = "zh"
    user.is_bot = False
    return user


@pytest.fixture
def mock_chat():
    """Create a mock Telegram Chat."""
    chat = MagicMock()
    chat.id = 123456789
    chat.type = "private"
    chat.send_action = AsyncMock()
    return chat


@pytest.fixture
def mock_message(mock_user, mock_chat):
    """Create a mock Telegram Message."""
    message = MagicMock()
    message.text = ""
    message.from_user = mock_user
    message.chat = mock_chat
    message.message_id = 100
    message.reply_text = AsyncMock(return_value=MagicMock(message_id=101))
    message.edit_text = AsyncMock()
    return message


@pytest.fixture
def mock_callback_query(mock_user, mock_message):
    """Create a mock Telegram CallbackQuery."""
    query = MagicMock()
    query.id = "callback_123"
    query.from_user = mock_user
    query.message = mock_message
    query.data = ""
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    return query


@pytest.fixture
def mock_update(mock_user, mock_message, mock_callback_query):
    """Create a mock Telegram Update."""
    update = MagicMock()
    update.effective_user = mock_user
    update.effective_chat = mock_message.chat
    update.message = mock_message
    update.callback_query = mock_callback_query
    return update


@pytest.fixture
def mock_context():
    """Create a mock Telegram Context with bot."""
    context = MagicMock()
    context.user_data = {}
    context.chat_data = {}
    context.bot_data = {}
    context.bot = MagicMock()
    context.bot.send_message = AsyncMock(return_value=MagicMock(message_id=200))
    context.bot.edit_message_text = AsyncMock()
    context.bot.get_chat_administrators = AsyncMock(return_value=[])
    context.bot.send_invoice = AsyncMock()
    return context


# ============ Mock LLM Provider ============

@pytest.fixture
def mock_llm_json():
    """Mock LLM JSON responses. Returns a patcher factory."""
    def _mock(return_value=None):
        if return_value is None:
            return_value = ({"must_read": [], "recommended": [], "other": []}, "mock-model")
        return patch(
            "services.llm_factory.call_llm_json",
            new_callable=AsyncMock,
            return_value=return_value
        )
    return _mock


@pytest.fixture
def mock_llm_text():
    """Mock LLM text responses. Returns a patcher factory."""
    def _mock(return_value=None):
        if return_value is None:
            return_value = ("Mock AI response", "mock-model")
        return patch(
            "services.llm_factory.call_llm_text",
            new_callable=AsyncMock,
            return_value=return_value
        )
    return _mock
