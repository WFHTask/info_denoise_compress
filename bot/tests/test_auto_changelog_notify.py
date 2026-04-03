"""
Adversarial tests for startup changelog auto-notify.

Goal:
- Verify strict startup behavior and blind-spot scenarios.
"""
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.mark.asyncio
async def test_startup_notify_skips_when_version_unchanged(tmp_data_dir, monkeypatch):
    """Blind spot: reboot should not re-send same version."""
    import utils.json_storage as storage
    from main import startup_changelog_notify_job

    monkeypatch.setattr(storage, "SYSTEM_CONFIG_FILE", str(tmp_data_dir / "system_config.json"))
    storage.set_system_config("last_notified_version", "v1.2.3")

    ctx = MagicMock()

    with patch("scripts.send_changelog_update.parse_latest_changelog", return_value={"version": "v1.2.3"}):
        with patch("scripts.send_changelog_update.send_latest_changelog_update", new_callable=AsyncMock) as mock_send:
            await startup_changelog_notify_job(ctx)
            mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_startup_notify_sends_and_persists_new_version(tmp_data_dir, monkeypatch):
    """Core case: new version should send and update marker."""
    import utils.json_storage as storage
    from main import startup_changelog_notify_job

    monkeypatch.setattr(storage, "SYSTEM_CONFIG_FILE", str(tmp_data_dir / "system_config.json"))
    storage.set_system_config("last_notified_version", "v1.2.3")

    ctx = MagicMock()
    send_result = {
        "version": "v1.2.4",
        "date": "2026-03-01",
        "total_users": 10,
        "success_count": 10,
        "fail_count": 0,
    }

    with patch("scripts.send_changelog_update.parse_latest_changelog", return_value={"version": "v1.2.4"}):
        with patch(
            "scripts.send_changelog_update.send_latest_changelog_update",
            new_callable=AsyncMock,
            return_value=send_result,
        ) as mock_send:
            await startup_changelog_notify_job(ctx)
            mock_send.assert_awaited_once()

    assert storage.get_system_config("last_notified_version") == "v1.2.4"


@pytest.mark.asyncio
async def test_startup_notify_does_not_persist_when_partial_fail(tmp_data_dir, monkeypatch):
    """Blind spot: partial delivery failure must keep old marker for retry."""
    import utils.json_storage as storage
    from main import startup_changelog_notify_job

    monkeypatch.setattr(storage, "SYSTEM_CONFIG_FILE", str(tmp_data_dir / "system_config.json"))
    storage.set_system_config("last_notified_version", "v1.2.3")

    ctx = MagicMock()
    send_result = {
        "version": "v1.2.4",
        "date": "2026-03-01",
        "total_users": 10,
        "success_count": 9,
        "fail_count": 1,
    }

    with patch("scripts.send_changelog_update.parse_latest_changelog", return_value={"version": "v1.2.4"}):
        with patch(
            "scripts.send_changelog_update.send_latest_changelog_update",
            new_callable=AsyncMock,
            return_value=send_result,
        ):
            await startup_changelog_notify_job(ctx)

    assert storage.get_system_config("last_notified_version") == "v1.2.3"


@pytest.mark.asyncio
async def test_startup_notify_skips_when_changelog_parse_fails(tmp_data_dir, monkeypatch):
    """Blind spot: parsing failure should not crash and should not send."""
    import utils.json_storage as storage
    from main import startup_changelog_notify_job

    monkeypatch.setattr(storage, "SYSTEM_CONFIG_FILE", str(tmp_data_dir / "system_config.json"))
    storage.set_system_config("last_notified_version", "v1.2.3")
    ctx = MagicMock()

    with patch("scripts.send_changelog_update.parse_latest_changelog", return_value=None):
        with patch("scripts.send_changelog_update.send_latest_changelog_update", new_callable=AsyncMock) as mock_send:
            await startup_changelog_notify_job(ctx)
            mock_send.assert_not_called()

    assert storage.get_system_config("last_notified_version") == "v1.2.3"
