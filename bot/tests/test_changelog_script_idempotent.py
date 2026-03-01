"""
Adversarial tests for changelog script idempotency.
"""
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.mark.asyncio
async def test_send_latest_changelog_update_skips_when_already_notified():
    """Should skip sending when version is already notified."""
    from scripts.send_changelog_update import send_latest_changelog_update

    with patch("scripts.send_changelog_update.parse_latest_changelog", return_value={"version": "v1.8.0", "date": "2026-03-01", "content": "x"}):
        with patch("scripts.send_changelog_update.get_system_config", return_value="v1.8.0"):
            with patch("scripts.send_changelog_update.send_update_to_user", new_callable=AsyncMock) as mock_send:
                result = await send_latest_changelog_update(dry_run=False, skip_if_not_changed=True)

    assert result is not None
    assert result["skipped"] is True
    assert result["reason"] == "already_notified"
    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_send_latest_changelog_update_persists_version_after_full_success():
    """Should update version marker only when all sends succeed."""
    from scripts.send_changelog_update import send_latest_changelog_update

    users = [{"telegram_id": "1001"}, {"telegram_id": "1002"}]
    fake_bot = MagicMock()

    with patch("scripts.send_changelog_update.parse_latest_changelog", return_value={"version": "v1.8.1", "date": "2026-03-02", "content": "x"}):
        with patch("scripts.send_changelog_update.get_system_config", return_value="v1.8.0"):
            with patch("scripts.send_changelog_update.get_subscribed_users", return_value=users):
                with patch("scripts.send_changelog_update.get_user_language", return_value="zh"):
                    with patch("scripts.send_changelog_update.Bot", return_value=fake_bot):
                        with patch("scripts.send_changelog_update.send_update_to_user", new_callable=AsyncMock, side_effect=[True, True]):
                            with patch("scripts.send_changelog_update.set_system_config", return_value=True) as mock_set:
                                result = await send_latest_changelog_update(dry_run=False, skip_if_not_changed=True)

    assert result is not None
    assert result["fail_count"] == 0
    mock_set.assert_called_once_with("last_notified_version", "v1.8.1")


@pytest.mark.asyncio
async def test_send_latest_changelog_update_does_not_persist_on_partial_failure():
    """Blind spot: partial send failure must not update version marker."""
    from scripts.send_changelog_update import send_latest_changelog_update

    users = [{"telegram_id": "1001"}, {"telegram_id": "1002"}]
    fake_bot = MagicMock()

    with patch("scripts.send_changelog_update.parse_latest_changelog", return_value={"version": "v1.8.1", "date": "2026-03-02", "content": "x"}):
        with patch("scripts.send_changelog_update.get_system_config", return_value="v1.8.0"):
            with patch("scripts.send_changelog_update.get_subscribed_users", return_value=users):
                with patch("scripts.send_changelog_update.get_user_language", return_value="zh"):
                    with patch("scripts.send_changelog_update.Bot", return_value=fake_bot):
                        with patch("scripts.send_changelog_update.send_update_to_user", new_callable=AsyncMock, side_effect=[True, False]):
                            with patch("scripts.send_changelog_update.set_system_config", return_value=True) as mock_set:
                                result = await send_latest_changelog_update(dry_run=False, skip_if_not_changed=True)

    assert result is not None
    assert result["fail_count"] == 1
    mock_set.assert_not_called()
