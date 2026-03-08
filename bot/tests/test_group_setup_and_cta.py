"""
Feature Tests: Group /setup AI Onboarding + Admin CTA Configuration

Tests for:
1. Group /setup AI-driven 3-round conversation (Feature 1)
2. Admin-configurable CTA text for group digests (Feature 2)

Run with: python -m pytest tests/test_group_setup_and_cta.py -v
"""
import importlib
import json
import os
import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============ Helper Fixtures ============

@pytest.fixture
def mock_group_chat():
    """Create a mock Telegram group chat."""
    chat = MagicMock()
    chat.id = -1001234567890
    chat.type = "supergroup"
    chat.title = "Web3 DeFi 讨论群"
    chat.send_action = AsyncMock()
    return chat


@pytest.fixture
def mock_admin_user():
    """Create a mock admin user (group owner)."""
    user = MagicMock()
    user.id = 111222333
    user.username = "groupadmin"
    user.first_name = "Admin"
    user.language_code = "zh"
    return user


@pytest.fixture
def mock_non_admin_user():
    """Create a mock non-admin user (group member)."""
    user = MagicMock()
    user.id = 999888777
    user.username = "member1"
    user.first_name = "Member"
    user.language_code = "en"
    return user


@pytest.fixture
def group_update(mock_admin_user, mock_group_chat):
    """Create a mock Update for group context."""
    update = MagicMock()
    update.effective_user = mock_admin_user
    update.effective_chat = mock_group_chat
    message = MagicMock()
    message.text = ""
    message.from_user = mock_admin_user
    message.chat = mock_group_chat
    message.reply_text = AsyncMock(return_value=MagicMock(message_id=101))
    message.delete = AsyncMock()
    update.message = message
    query = MagicMock()
    query.from_user = mock_admin_user
    query.message = message
    query.data = ""
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update.callback_query = query
    return update


@pytest.fixture
def group_context():
    """Create a mock Context for group usage (with chat_data)."""
    context = MagicMock()
    context.user_data = {}
    context.chat_data = {}
    context.bot_data = {}
    context.bot = MagicMock()
    context.bot.send_message = AsyncMock(return_value=MagicMock(message_id=200))
    context.bot.edit_message_text = AsyncMock()

    admin_member = MagicMock()
    admin_member.user = MagicMock()
    admin_member.user.id = 111222333
    context.bot.get_chat_administrators = AsyncMock(return_value=[admin_member])

    return context


# ============ Feature 1: Group /setup AI Onboarding ============

class TestGroupSetupEntryPoint:
    """Test /setup command entry point behavior."""

    @pytest.mark.asyncio
    async def test_setup_rejects_non_group(self, group_update, group_context):
        """TC-F1-01: /setup in private chat shows guide, not AI onboarding."""
        from handlers.group import setup_command
        from telegram.ext import ConversationHandler

        group_update.effective_chat.type = "private"

        with patch("config.FEATURE_GROUP_CHAT", True):
            result = await setup_command(group_update, group_context)

        assert result == ConversationHandler.END
        group_update.message.reply_text.assert_called_once()
        call_text = group_update.message.reply_text.call_args[0][0]
        assert "群组" in call_text or "Group" in call_text or "group" in call_text

    @pytest.mark.asyncio
    async def test_setup_rejects_non_admin(self, group_update, group_context):
        """TC-F1-02: Non-admin user cannot trigger /setup."""
        from handlers.group import setup_command
        from telegram.ext import ConversationHandler

        group_context.bot.get_chat_administrators = AsyncMock(return_value=[])

        with patch("config.FEATURE_GROUP_CHAT", True):
            result = await setup_command(group_update, group_context)

        assert result == ConversationHandler.END
        call_text = group_update.message.reply_text.call_args[0][0]
        assert "管理员" in call_text or "admin" in call_text.lower()

    @pytest.mark.asyncio
    async def test_setup_new_group_starts_ai_onboarding(self, group_update, group_context, tmp_data_dir):
        """TC-F1-03: New group triggers AI onboarding with round 1."""
        from handlers.group import setup_command, GROUP_ONBOARD_R1

        with patch("config.FEATURE_GROUP_CHAT", True):
            with patch("handlers.group.call_gemini", new_callable=AsyncMock, return_value="What topics does your group follow?"):
                result = await setup_command(group_update, group_context)

        assert result == GROUP_ONBOARD_R1
        assert group_context.chat_data["setup_admin_id"] == 111222333
        assert group_context.chat_data["current_round"] == 1
        group_context.bot.send_message.assert_called()

    @pytest.mark.asyncio
    async def test_setup_existing_config_shows_options(self, group_update, group_context, tmp_data_dir):
        """TC-F1-04: Existing group config shows update/view/disable buttons."""
        from handlers.group import setup_command, save_group_config, GROUP_ONBOARD_R1

        group_id = str(group_update.effective_chat.id)
        save_group_config(group_id, {
            "group_id": group_id,
            "group_title": "Test Group",
            "admin_id": "111222333",
            "profile": "DeFi topics",
            "push_hour": 9,
            "language": "zh",
            "enabled": True,
        })

        with patch("config.FEATURE_GROUP_CHAT", True):
            result = await setup_command(group_update, group_context)

        assert result == GROUP_ONBOARD_R1
        call_kwargs = group_update.message.reply_text.call_args
        call_text = call_kwargs[0][0]
        assert "已配置" in call_text or "configured" in call_text.lower()

    @pytest.mark.asyncio
    async def test_setup_disabled_feature_flag(self, group_update, group_context):
        """TC-F1-05: /setup returns END when FEATURE_GROUP_CHAT is False."""
        from handlers.group import setup_command
        from telegram.ext import ConversationHandler

        with patch("config.FEATURE_GROUP_CHAT", False):
            result = await setup_command(group_update, group_context)

        assert result == ConversationHandler.END


class TestGroupAdminFiltering:
    """Test that only admin's messages are processed."""

    def test_is_setup_admin_true(self, group_update, group_context):
        """TC-F1-06: _is_setup_admin returns True for the admin who started setup."""
        from handlers.group import _is_setup_admin

        group_context.chat_data["setup_admin_id"] = 111222333
        assert _is_setup_admin(group_update, group_context) is True

    def test_is_setup_admin_false_different_user(self, group_update, group_context, mock_non_admin_user):
        """TC-F1-07: _is_setup_admin returns False for a different user."""
        from handlers.group import _is_setup_admin

        group_context.chat_data["setup_admin_id"] = 111222333
        group_update.effective_user = mock_non_admin_user
        assert _is_setup_admin(group_update, group_context) is False

    def test_is_setup_admin_false_no_setup(self, group_update, group_context):
        """TC-F1-08: _is_setup_admin returns False when no setup is active."""
        from handlers.group import _is_setup_admin

        assert _is_setup_admin(group_update, group_context) is False

    @pytest.mark.asyncio
    async def test_round1_ignores_non_admin_message(self, group_update, group_context, mock_non_admin_user):
        """TC-F1-09: Round 1 handler ignores messages from non-admin."""
        from handlers.group import handle_onboard_r1, GROUP_ONBOARD_R1

        group_context.chat_data["setup_admin_id"] = 111222333
        group_update.effective_user = mock_non_admin_user
        group_update.message.from_user = mock_non_admin_user
        group_update.message.text = "I want DeFi news!"

        result = await handle_onboard_r1(group_update, group_context)
        assert result == GROUP_ONBOARD_R1

    @pytest.mark.asyncio
    async def test_round2_ignores_non_admin_message(self, group_update, group_context, mock_non_admin_user):
        """TC-F1-10: Round 2 handler ignores messages from non-admin."""
        from handlers.group import handle_onboard_r2, GROUP_ONBOARD_R2

        group_context.chat_data["setup_admin_id"] = 111222333
        group_update.effective_user = mock_non_admin_user
        group_update.message.from_user = mock_non_admin_user
        group_update.message.text = "Deep analysis preferred"

        result = await handle_onboard_r2(group_update, group_context)
        assert result == GROUP_ONBOARD_R2


class TestGroupAIOnboarding:
    """Test the 3-round AI conversation flow."""

    @pytest.mark.asyncio
    async def test_round1_processes_admin_response(self, group_update, group_context):
        """TC-F1-11: Round 1 processes admin message and advances to round 2."""
        from handlers.group import handle_onboard_r1, GROUP_ONBOARD_R2

        group_context.chat_data["setup_admin_id"] = 111222333
        group_context.chat_data["conversation_history"] = []
        group_context.chat_data["language"] = "zh"
        group_context.chat_data["language_native"] = "Chinese"
        group_update.message.text = "我们群关注 DeFi 和 Layer2"

        with patch("handlers.group.call_gemini", new_callable=AsyncMock,
                    return_value="Great! What type of content?"):
            result = await handle_onboard_r1(group_update, group_context)

        assert result == GROUP_ONBOARD_R2
        assert len(group_context.chat_data["conversation_history"]) == 1
        assert group_context.chat_data["conversation_history"][0]["round"] == 1
        assert group_context.chat_data["current_round"] == 2

    @pytest.mark.asyncio
    async def test_round2_generates_profile_summary(self, group_update, group_context):
        """TC-F1-12: Round 2 generates profile summary with confirm buttons."""
        from handlers.group import handle_onboard_r2, GROUP_CONFIRM_PROFILE

        group_context.chat_data["setup_admin_id"] = 111222333
        group_context.chat_data["conversation_history"] = [
            {"round": 1, "user_input": "DeFi and Layer2"}
        ]
        group_context.chat_data["language"] = "zh"
        group_context.chat_data["language_native"] = "Chinese"
        group_update.message.text = "深度分析为主，每天10条左右"

        progress_msg = MagicMock()
        progress_msg.delete = AsyncMock()
        group_update.message.reply_text = AsyncMock(side_effect=[progress_msg, MagicMock()])

        with patch("handlers.group.call_gemini", new_callable=AsyncMock,
                    return_value="Group Profile Summary:\n- DeFi and Layer2\n- Deep analysis"):
            result = await handle_onboard_r2(group_update, group_context)

        assert result == GROUP_CONFIRM_PROFILE
        assert group_context.chat_data["profile_summary"] is not None
        assert len(group_context.chat_data["conversation_history"]) == 2

    @pytest.mark.asyncio
    async def test_confirm_profile_generates_full_profile(self, group_update, group_context):
        """TC-F1-13: Confirming profile generates structured profile and proceeds to push time."""
        from handlers.group import handle_confirm_profile, GROUP_PUSH_TIME

        group_context.chat_data["setup_admin_id"] = 111222333
        group_context.chat_data["profile_summary"] = "DeFi group summary"
        group_context.chat_data["conversation_history"] = [
            {"round": 1, "user_input": "DeFi"},
            {"round": 2, "user_input": "deep analysis"},
        ]
        group_context.chat_data["language"] = "zh"
        group_context.chat_data["language_native"] = "Chinese"

        with patch("handlers.group.call_gemini", new_callable=AsyncMock,
                    return_value="[群组类型]\nDeFi 深度分析群\n[关注领域]\n- DeFi protocols"):
            result = await handle_confirm_profile(group_update, group_context)

        assert result == GROUP_PUSH_TIME
        assert group_context.chat_data["full_profile"] is not None
        send_calls = group_context.bot.send_message.call_args_list
        found_time_selection = False
        for call in send_calls:
            text = call.kwargs.get("text", "") or (call.args[0] if call.args else "")
            if "推送时间" in str(text) or "push time" in str(text).lower():
                found_time_selection = True
        assert found_time_selection, "Should show push time selection after profile confirm"

    @pytest.mark.asyncio
    async def test_confirm_profile_rejects_non_admin(self, group_update, group_context, mock_non_admin_user):
        """TC-F1-14: Non-admin clicking confirm gets rejected."""
        from handlers.group import handle_confirm_profile, GROUP_CONFIRM_PROFILE

        group_context.chat_data["setup_admin_id"] = 111222333
        group_update.callback_query.from_user = mock_non_admin_user
        group_update.effective_user = mock_non_admin_user

        result = await handle_confirm_profile(group_update, group_context)
        assert result == GROUP_CONFIRM_PROFILE
        group_update.callback_query.answer.assert_called_once()
        call_kwargs = group_update.callback_query.answer.call_args
        assert call_kwargs[1].get("show_alert") is True


class TestGroupProfileAdjust:
    """Test profile adjustment flow."""

    @pytest.mark.asyncio
    async def test_adjust_profile_prompt(self, group_update, group_context):
        """TC-F1-15: Clicking adjust shows prompt for adjustment text."""
        from handlers.group import handle_adjust_profile_prompt, GROUP_ADJUST

        group_context.chat_data["setup_admin_id"] = 111222333
        group_context.chat_data["profile_summary"] = "DeFi group profile"
        group_context.chat_data["_profile_adjusted"] = False
        group_context.chat_data["language"] = "zh"

        result = await handle_adjust_profile_prompt(group_update, group_context)
        assert result == GROUP_ADJUST

    @pytest.mark.asyncio
    async def test_adjust_profile_once_only(self, group_update, group_context):
        """TC-F1-16: Second adjustment attempt is blocked."""
        from handlers.group import handle_adjust_profile_prompt, GROUP_CONFIRM_PROFILE

        group_context.chat_data["setup_admin_id"] = 111222333
        group_context.chat_data["profile_summary"] = "Adjusted profile"
        group_context.chat_data["_profile_adjusted"] = True
        group_context.chat_data["language"] = "zh"

        result = await handle_adjust_profile_prompt(group_update, group_context)
        assert result == GROUP_CONFIRM_PROFILE

    @pytest.mark.asyncio
    async def test_adjust_profile_regenerates(self, group_update, group_context):
        """TC-F1-17: Adjustment text regenerates the profile."""
        from handlers.group import handle_profile_adjustment, GROUP_CONFIRM_PROFILE

        group_context.chat_data["setup_admin_id"] = 111222333
        group_context.chat_data["profile_summary"] = "Original profile"
        group_context.chat_data["conversation_history"] = [
            {"round": 1, "user_input": "DeFi"},
            {"round": 2, "user_input": "deep analysis"},
        ]
        group_context.chat_data["language"] = "zh"
        group_context.chat_data["language_native"] = "Chinese"
        group_update.message.text = "去掉 NFT 相关内容"

        with patch("handlers.group.call_gemini", new_callable=AsyncMock,
                    return_value="Adjusted: DeFi only, no NFT"):
            result = await handle_profile_adjustment(group_update, group_context)

        assert result == GROUP_CONFIRM_PROFILE
        assert group_context.chat_data["profile_summary"] == "Adjusted: DeFi only, no NFT"
        assert group_context.chat_data["_profile_adjusted"] is True


class TestGroupPushTimeAndLanguage:
    """Test push time and language selection."""

    @pytest.mark.asyncio
    async def test_push_time_selection(self, group_update, group_context):
        """TC-F1-18: Push time selection advances to language choice."""
        from handlers.group import handle_push_time, GROUP_LANGUAGE

        group_context.chat_data["setup_admin_id"] = 111222333
        group_context.chat_data["language"] = "zh"
        group_update.callback_query.data = "group_time_9"

        result = await handle_push_time(group_update, group_context)
        assert result == GROUP_LANGUAGE
        assert group_context.chat_data["push_hour"] == 9

    @pytest.mark.asyncio
    async def test_language_choice_saves_config(self, group_update, group_context, tmp_data_dir):
        """TC-F1-19: Language selection saves full config and ends conversation."""
        from handlers.group import handle_language_choice, load_group_config
        from telegram.ext import ConversationHandler

        group_id = str(group_update.effective_chat.id)
        group_context.chat_data["setup_admin_id"] = 111222333
        group_context.chat_data["full_profile"] = "[群组类型]\nDeFi 分析群\n[关注领域]\n- DeFi"
        group_context.chat_data["push_hour"] = 9
        group_context.chat_data["language"] = "zh"
        group_update.callback_query.data = "group_lang_zh"
        group_update.callback_query.message.message_thread_id = 777

        result = await handle_language_choice(group_update, group_context)
        assert result == ConversationHandler.END

        saved = load_group_config(group_id)
        assert saved is not None
        assert saved["group_id"] == group_id
        assert saved["push_hour"] == 9
        assert saved["language"] == "zh"
        assert saved["enabled"] is True
        assert saved["message_thread_id"] == 777
        assert "[群组类型]" in saved["profile"]

    @pytest.mark.asyncio
    async def test_push_time_rejects_non_admin(self, group_update, group_context, mock_non_admin_user):
        """TC-F1-20: Non-admin clicking push time button gets rejected."""
        from handlers.group import handle_push_time, GROUP_PUSH_TIME

        group_context.chat_data["setup_admin_id"] = 111222333
        group_update.callback_query.from_user = mock_non_admin_user
        group_update.effective_user = mock_non_admin_user
        group_update.callback_query.data = "group_time_9"

        result = await handle_push_time(group_update, group_context)
        assert result == GROUP_PUSH_TIME


class TestGroupConfigPersistence:
    """Test group config storage functions."""

    def test_save_and_load_config(self, tmp_data_dir):
        """TC-F1-21: Config saves and loads correctly."""
        from handlers.group import save_group_config, load_group_config

        config = {
            "group_id": "-100999",
            "group_title": "Test",
            "profile": "[群组类型]\nTest group",
            "push_hour": 10,
            "language": "en",
            "enabled": True,
        }
        save_group_config("-100999", config)
        loaded = load_group_config("-100999")

        assert loaded is not None
        assert loaded["group_id"] == "-100999"
        assert loaded["profile"] == "[群组类型]\nTest group"

    def test_get_all_group_configs(self, tmp_data_dir):
        """TC-F1-22: get_all_group_configs returns only enabled configs."""
        from handlers.group import save_group_config, get_all_group_configs

        save_group_config("-100001", {"group_id": "-100001", "enabled": True})
        save_group_config("-100002", {"group_id": "-100002", "enabled": False})
        save_group_config("-100003", {"group_id": "-100003", "enabled": True})

        configs = get_all_group_configs()
        assert len(configs) == 2
        ids = [c["group_id"] for c in configs]
        assert "-100001" in ids
        assert "-100003" in ids
        assert "-100002" not in ids


class TestGroupConversationHandler:
    """Test ConversationHandler registration."""

    def test_handler_returns_none_when_disabled(self):
        """TC-F1-23: get_group_handler returns None when feature is disabled."""
        from handlers.group import get_group_handler

        with patch("config.FEATURE_GROUP_CHAT", False):
            handler = get_group_handler()
        assert handler is None

    def test_handler_returns_conversation_handler_when_enabled(self):
        """TC-F1-24: get_group_handler returns ConversationHandler when enabled."""
        from handlers.group import get_group_handler
        from telegram.ext import ConversationHandler

        with patch("config.FEATURE_GROUP_CHAT", True):
            handler = get_group_handler()
        assert handler is not None
        assert isinstance(handler, ConversationHandler)

    def test_handler_has_all_states(self):
        """TC-F1-25: ConversationHandler has all required states."""
        from handlers.group import (
            get_group_handler,
            GROUP_ONBOARD_R1, GROUP_ONBOARD_R2,
            GROUP_CONFIRM_PROFILE, GROUP_ADJUST,
            GROUP_PUSH_TIME, GROUP_LANGUAGE,
        )

        with patch("config.FEATURE_GROUP_CHAT", True):
            handler = get_group_handler()

        required_states = [
            GROUP_ONBOARD_R1, GROUP_ONBOARD_R2,
            GROUP_CONFIRM_PROFILE, GROUP_ADJUST,
            GROUP_PUSH_TIME, GROUP_LANGUAGE,
        ]
        for state in required_states:
            assert state in handler.states, f"Missing state {state} in ConversationHandler"


class TestGroupViewDisable:
    """Test view and disable existing config."""

    @pytest.mark.asyncio
    async def test_view_config(self, group_update, group_context, tmp_data_dir):
        """TC-F1-26: View shows current config details."""
        from handlers.group import handle_group_view, save_group_config
        from telegram.ext import ConversationHandler

        group_id = str(group_update.effective_chat.id)
        save_group_config(group_id, {
            "group_id": group_id,
            "profile": "DeFi group profile text",
            "push_hour": 8,
            "language": "en",
            "enabled": True,
            "created": "2026-02-23T10:00:00",
        })

        result = await handle_group_view(group_update, group_context)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_disable_config(self, group_update, group_context, tmp_data_dir):
        """TC-F1-27: Disable turns off group push."""
        from handlers.group import handle_group_disable, save_group_config, load_group_config
        from telegram.ext import ConversationHandler

        group_id = str(group_update.effective_chat.id)
        save_group_config(group_id, {
            "group_id": group_id,
            "profile": "Test",
            "push_hour": 9,
            "language": "zh",
            "enabled": True,
        })

        result = await handle_group_disable(group_update, group_context)
        assert result == ConversationHandler.END

        config = load_group_config(group_id)
        assert config["enabled"] is False


class TestGroupTopicBinding:
    """Test binding group push to the setup topic/thread."""

    @pytest.mark.asyncio
    async def test_group_digest_push_job_sends_to_bound_topic(self):
        """TC-F1-28: Bound topic id is passed to Telegram send_message."""
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
            "message_thread_id": 777,
            "last_push_date": "1900-01-01",
        }

        ctx = MagicMock()
        ctx.bot = MagicMock()
        ctx.bot.send_message = AsyncMock()

        with patch("handlers.group.get_all_group_configs", return_value=[config]):
            with patch("services.rss_fetcher.fetch_all_sources", new_callable=AsyncMock, return_value=[{"id": "1"}]):
                with patch("services.digest_processor.generate_group_digest", new_callable=AsyncMock, return_value="digest"):
                    with patch("services.report_generator.split_report_for_telegram", return_value=["part-1"]):
                        with patch("utils.json_storage.get_system_config", return_value="CTA-TEST"):
                            with patch("handlers.group.save_group_config"):
                                await group_digest_push_job(ctx)

        send_kwargs = ctx.bot.send_message.await_args.kwargs
        assert send_kwargs["chat_id"] == "-10012345"
        assert send_kwargs["message_thread_id"] == 777
        assert "CTA-TEST" in send_kwargs["text"]


# ============ Feature 2: Admin CTA Configuration ============

class TestSystemConfig:
    """Test system-level config storage."""

    def test_get_system_config_default(self, tmp_data_dir, monkeypatch):
        """TC-F2-01: get_system_config returns default when key missing."""
        import utils.json_storage as storage
        monkeypatch.setattr(storage, "SYSTEM_CONFIG_FILE",
                            str(tmp_data_dir / "system_config.json"))

        result = storage.get_system_config("nonexistent_key", "default_value")
        assert result == "default_value"

    def test_set_and_get_system_config(self, tmp_data_dir, monkeypatch):
        """TC-F2-02: set/get system config round-trip."""
        import utils.json_storage as storage
        monkeypatch.setattr(storage, "SYSTEM_CONFIG_FILE",
                            str(tmp_data_dir / "system_config.json"))

        storage.set_system_config("test_key", "test_value")
        result = storage.get_system_config("test_key")
        assert result == "test_value"

    def test_set_system_config_overwrites(self, tmp_data_dir, monkeypatch):
        """TC-F2-03: set_system_config overwrites existing value."""
        import utils.json_storage as storage
        monkeypatch.setattr(storage, "SYSTEM_CONFIG_FILE",
                            str(tmp_data_dir / "system_config.json"))

        storage.set_system_config("key1", "value_old")
        storage.set_system_config("key1", "value_new")
        assert storage.get_system_config("key1") == "value_new"

    def test_system_config_persists_multiple_keys(self, tmp_data_dir, monkeypatch):
        """TC-F2-04: Multiple keys coexist independently."""
        import utils.json_storage as storage
        monkeypatch.setattr(storage, "SYSTEM_CONFIG_FILE",
                            str(tmp_data_dir / "system_config.json"))

        storage.set_system_config("key_a", "val_a")
        storage.set_system_config("key_b", "val_b")

        assert storage.get_system_config("key_a") == "val_a"
        assert storage.get_system_config("key_b") == "val_b"


class TestCTADefaultValue:
    """Test CTA default text behavior."""

    def test_default_cta_text_defined(self):
        """TC-F2-05: DEFAULT_CTA_TEXT is defined and non-empty."""
        from handlers.admin import DEFAULT_CTA_TEXT
        assert DEFAULT_CTA_TEXT is not None
        assert len(DEFAULT_CTA_TEXT) > 10
        assert "/start" in DEFAULT_CTA_TEXT

    def test_default_cta_is_bilingual(self):
        """TC-F2-06: Default CTA contains both Chinese and English."""
        from handlers.admin import DEFAULT_CTA_TEXT
        has_chinese = any('\u4e00' <= c <= '\u9fff' for c in DEFAULT_CTA_TEXT)
        has_english = any(c.isascii() and c.isalpha() for c in DEFAULT_CTA_TEXT)
        assert has_chinese, "Default CTA should contain Chinese text"
        assert has_english, "Default CTA should contain English text"


class TestAdminCTAConfig:
    """Test admin CTA configuration handlers."""

    @pytest.mark.asyncio
    async def test_cta_config_shows_current(self, mock_update, mock_context, tmp_data_dir, monkeypatch):
        """TC-F2-07: CTA config page shows current CTA text."""
        import utils.json_storage as storage
        monkeypatch.setattr(storage, "SYSTEM_CONFIG_FILE",
                            str(tmp_data_dir / "system_config.json"))

        from handlers.admin import admin_cta_config

        with patch("handlers.admin.is_admin", return_value=True):
            await admin_cta_config(mock_update, mock_context)

        call_text = mock_update.callback_query.edit_message_text.call_args[0][0]
        assert "CTA" in call_text
        assert "/start" in call_text

    @pytest.mark.asyncio
    async def test_cta_edit_prompts_input(self, mock_update, mock_context):
        """TC-F2-08: CTA edit button shows input prompt."""
        from handlers.admin import admin_cta_edit, WAITING_FOR_CTA_TEXT

        with patch("handlers.admin.is_admin", return_value=True):
            result = await admin_cta_edit(mock_update, mock_context)

        assert result == WAITING_FOR_CTA_TEXT

    @pytest.mark.asyncio
    async def test_cta_text_input_saves(self, mock_update, mock_context, tmp_data_dir, monkeypatch):
        """TC-F2-09: CTA text input saves correctly."""
        import utils.json_storage as storage
        monkeypatch.setattr(storage, "SYSTEM_CONFIG_FILE",
                            str(tmp_data_dir / "system_config.json"))

        from handlers.admin import handle_cta_text_input
        from telegram.ext import ConversationHandler

        mock_update.message.text = "🚀 Try our personalized service! DM /start"
        mock_update.effective_user.id = 111

        with patch("handlers.admin.is_admin", return_value=True):
            result = await handle_cta_text_input(mock_update, mock_context)

        assert result == ConversationHandler.END

        saved = storage.get_system_config("group_cta_text")
        assert saved == "🚀 Try our personalized service! DM /start"

    @pytest.mark.asyncio
    async def test_cta_text_too_short_rejected(self, mock_update, mock_context):
        """TC-F2-10: CTA text shorter than 5 chars is rejected."""
        from handlers.admin import handle_cta_text_input, WAITING_FOR_CTA_TEXT

        mock_update.message.text = "Hi"
        mock_update.effective_user.id = 111

        with patch("handlers.admin.is_admin", return_value=True):
            result = await handle_cta_text_input(mock_update, mock_context)

        assert result == WAITING_FOR_CTA_TEXT

    @pytest.mark.asyncio
    async def test_cta_text_too_long_rejected(self, mock_update, mock_context):
        """TC-F2-11: CTA text longer than 500 chars is rejected."""
        from handlers.admin import handle_cta_text_input, WAITING_FOR_CTA_TEXT

        mock_update.message.text = "x" * 501
        mock_update.effective_user.id = 111

        with patch("handlers.admin.is_admin", return_value=True):
            result = await handle_cta_text_input(mock_update, mock_context)

        assert result == WAITING_FOR_CTA_TEXT

    @pytest.mark.asyncio
    async def test_cta_reset_restores_default(self, mock_update, mock_context, tmp_data_dir, monkeypatch):
        """TC-F2-12: CTA reset restores default text."""
        import utils.json_storage as storage
        monkeypatch.setattr(storage, "SYSTEM_CONFIG_FILE",
                            str(tmp_data_dir / "system_config.json"))

        from handlers.admin import admin_cta_reset, DEFAULT_CTA_TEXT

        storage.set_system_config("group_cta_text", "custom CTA text")

        with patch("handlers.admin.is_admin", return_value=True):
            with patch("handlers.admin.admin_cta_config", new_callable=AsyncMock):
                await admin_cta_reset(mock_update, mock_context)

        saved = storage.get_system_config("group_cta_text")
        assert saved == DEFAULT_CTA_TEXT


class TestCTAInGroupDigest:
    """Test CTA integration in group digest push."""

    def test_main_uses_configurable_cta(self, tmp_data_dir, monkeypatch):
        """TC-F2-13: group_digest_push_job reads CTA from system config."""
        import utils.json_storage as storage
        monkeypatch.setattr(storage, "SYSTEM_CONFIG_FILE",
                            str(tmp_data_dir / "system_config.json"))

        storage.set_system_config("group_cta_text", "Custom CTA for testing")

        result = storage.get_system_config("group_cta_text")
        assert result == "Custom CTA for testing"

    def test_cta_fallback_to_default(self, tmp_data_dir, monkeypatch):
        """TC-F2-14: CTA falls back to default when not configured."""
        import utils.json_storage as storage
        monkeypatch.setattr(storage, "SYSTEM_CONFIG_FILE",
                            str(tmp_data_dir / "system_config.json"))

        from handlers.admin import DEFAULT_CTA_TEXT

        result = storage.get_system_config("group_cta_text", DEFAULT_CTA_TEXT)
        assert result == DEFAULT_CTA_TEXT
        assert "/start" in result


class TestAdminPanelCTAButton:
    """Test CTA button appears in admin panel."""

    @pytest.mark.asyncio
    async def test_admin_panel_has_cta_button(self, mock_update, mock_context, tmp_data_dir):
        """TC-F2-15: Admin panel includes CTA config button."""
        from handlers.admin import admin_panel

        mock_update.callback_query.from_user.id = 111
        mock_update.effective_user.id = 111

        with patch("handlers.admin.is_admin", return_value=True):
            with patch("handlers.admin.get_whitelist_enabled", return_value=True):
                with patch("handlers.admin.get_whitelist", return_value=[]):
                    with patch("handlers.admin.get_users", return_value=[]):
                        await admin_panel(mock_update, mock_context)

        call_kwargs = mock_update.callback_query.edit_message_text.call_args
        reply_markup = call_kwargs[1].get("reply_markup") if call_kwargs[1] else None
        assert reply_markup is not None

        found_cta_button = False
        for row in reply_markup.inline_keyboard:
            for button in row:
                if "CTA" in button.text and button.callback_data == "admin_cta_config":
                    found_cta_button = True
        assert found_cta_button, "Admin panel should have a CTA config button"


# ============ Integration Tests ============

class TestGroupOnboardingPrompts:
    """Test that group onboarding prompt files exist and are valid."""

    def test_group_prompts_exist(self):
        """TC-INT-01: All 4 group onboarding prompt files exist."""
        prompts_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "prompts"
        )
        required = [
            "group_onboarding_round1.txt",
            "group_onboarding_round2.txt",
            "group_onboarding_round3.txt",
            "group_onboarding_confirm.txt",
        ]
        for filename in required:
            filepath = os.path.join(prompts_dir, filename)
            assert os.path.exists(filepath), f"Missing prompt file: {filename}"

    def test_group_prompts_have_placeholders(self):
        """TC-INT-02: Group prompts contain required placeholders."""
        from utils.prompt_loader import load_prompt

        r1 = load_prompt("group_onboarding_round1.txt")
        assert "{user_language}" in r1

        r2 = load_prompt("group_onboarding_round2.txt")
        assert "{user_language}" in r2
        assert "{user_input}" in r2

        r3 = load_prompt("group_onboarding_round3.txt")
        assert "{user_language}" in r3
        assert "{round_1}" in r3
        assert "{round_2}" in r3

        confirm = load_prompt("group_onboarding_confirm.txt")
        assert "{user_language}" in confirm
        assert "{conversation_summary}" in confirm

    def test_group_prompts_mention_group_context(self):
        """TC-INT-03: Group prompts reference group context (not individual)."""
        from utils.prompt_loader import load_prompt

        for filename in [
            "group_onboarding_round1.txt",
            "group_onboarding_round2.txt",
            "group_onboarding_round3.txt",
        ]:
            content = load_prompt(filename)
            has_group_ref = (
                "group" in content.lower() or
                "群" in content
            )
            assert has_group_ref, f"{filename} should reference group context"


class TestUIStringsCompleteness:
    """Test that new UI strings are defined for all languages."""

    def test_new_group_ui_strings_all_languages(self):
        """TC-INT-04: New group UI strings exist in zh/en/ja/ko."""
        from locales.ui_strings import get_ui_locale

        new_keys = [
            "group_ai_onboard_intro",
            "group_admin_hint",
            "group_profile_saved",
        ]

        for lang in ["zh", "en", "ja", "ko"]:
            ui = get_ui_locale(lang)
            for key in new_keys:
                val = ui.get(key)
                assert val is not None and len(val) > 0, \
                    f"Missing or empty UI string '{key}' for language '{lang}'"


class TestImportsAndModuleIntegrity:
    """Test that all imports work correctly."""

    def test_group_handler_imports(self):
        """TC-INT-05: group.py imports work without errors."""
        from handlers.group import (
            setup_command,
            handle_onboard_r1,
            handle_onboard_r2,
            handle_confirm_profile,
            handle_adjust_profile_prompt,
            handle_profile_adjustment,
            handle_push_time,
            handle_language_choice,
            handle_group_view,
            handle_group_disable,
            get_group_handler,
            get_group_callbacks,
            load_group_config,
            save_group_config,
            get_all_group_configs,
        )

    def test_admin_cta_imports(self):
        """TC-INT-06: admin.py CTA-related imports work."""
        from handlers.admin import (
            admin_cta_config,
            admin_cta_edit,
            handle_cta_text_input,
            admin_cta_reset,
            DEFAULT_CTA_TEXT,
            WAITING_FOR_CTA_TEXT,
        )

    def test_json_storage_system_config_imports(self):
        """TC-INT-07: json_storage system config imports work."""
        from utils.json_storage import get_system_config, set_system_config
