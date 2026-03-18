"""Tests for the notification system: webhook, scheduler, and config."""

import asyncio
import datetime
from unittest.mock import AsyncMock, patch

import pytest

import app.db.engine as db_engine
from app.db.repository import (
    get_notification_config,
    save_notification_config,
)
from app.models.schemas import WatchlistItemResponse
from app.notifications.scheduler import NotificationScheduler
from app.notifications.webhook import _build_payload, send_webhook


@pytest.fixture
async def db():
    """Initialize a fresh in-memory database for each test."""
    await db_engine.init_db("sqlite+aiosqlite://")
    yield


def _make_alert(**overrides) -> WatchlistItemResponse:
    defaults = dict(
        id=1,
        name="BTC Price",
        source="coingecko",
        query="bitcoin:price",
        threshold_direction="above",
        threshold_value=50000.0,
        last_value=55000.0,
        created_at=datetime.datetime.now(datetime.UTC),
        triggered=True,
        trend_direction="rising",
    )
    defaults.update(overrides)
    return WatchlistItemResponse(**defaults)


# --- Webhook payload formatting ---


class TestWebhookPayload:
    def test_slack_format(self):
        alerts = [_make_alert()]
        payload = _build_payload("slack", alerts)
        assert "text" in payload
        assert "TrendLab Alert" in payload["text"]
        assert "BTC Price" in payload["text"]

    def test_discord_format(self):
        alerts = [_make_alert()]
        payload = _build_payload("discord", alerts)
        assert "content" in payload
        assert "TrendLab Alert" in payload["content"]

    def test_generic_format(self):
        alerts = [_make_alert()]
        payload = _build_payload("generic", alerts)
        assert "alerts" in payload
        assert "timestamp" in payload
        assert len(payload["alerts"]) == 1
        assert payload["alerts"][0]["name"] == "BTC Price"

    def test_multiple_alerts(self):
        alerts = [
            _make_alert(id=1, name="Alert A"),
            _make_alert(id=2, name="Alert B"),
        ]
        payload = _build_payload("slack", alerts)
        assert "Alert A" in payload["text"]
        assert "Alert B" in payload["text"]
        assert "2 thresholds" in payload["text"]


# --- Webhook sending ---


class TestSendWebhook:
    @pytest.mark.asyncio
    async def test_success(self):
        alerts = [_make_alert()]
        with patch(
            "app.notifications.webhook.httpx.AsyncClient"
        ) as mock_cls:
            mock_client = AsyncMock()
            mock_resp = AsyncMock()
            mock_resp.raise_for_status = lambda: None
            mock_client.post.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await send_webhook(
                "https://hooks.example.com/test",
                "slack",
                alerts,
            )
            assert result is True
            mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_failure_returns_false(self):
        alerts = [_make_alert()]
        with patch(
            "app.notifications.webhook.httpx.AsyncClient"
        ) as mock_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = Exception("Connection refused")
            mock_client.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await send_webhook(
                "https://hooks.example.com/bad",
                "slack",
                alerts,
            )
            assert result is False


# --- Notification config CRUD ---


class TestNotificationConfigCrud:
    @pytest.mark.asyncio
    async def test_get_returns_none_when_empty(self, db):
        cfg = await get_notification_config()
        assert cfg is None

    @pytest.mark.asyncio
    async def test_save_and_get(self, db):
        await save_notification_config(
            webhook_url="https://hooks.example.com/abc",
            channel="slack",
            enabled=True,
        )
        cfg = await get_notification_config()
        assert cfg is not None
        assert cfg.webhook_url == "https://hooks.example.com/abc"
        assert cfg.channel == "slack"
        assert cfg.enabled is True

    @pytest.mark.asyncio
    async def test_upsert_updates_existing(self, db):
        await save_notification_config(
            webhook_url="https://hooks.example.com/first",
            channel="slack",
        )
        await save_notification_config(
            webhook_url="https://hooks.example.com/second",
            channel="discord",
            enabled=False,
        )
        cfg = await get_notification_config()
        assert cfg is not None
        assert cfg.webhook_url == "https://hooks.example.com/second"
        assert cfg.channel == "discord"
        assert cfg.enabled is False


# --- Scheduler ---


class TestScheduler:
    @pytest.mark.asyncio
    async def test_start_and_stop(self):
        scheduler = NotificationScheduler()
        assert scheduler.running is False

        scheduler.start()
        assert scheduler.running is True

        await scheduler.stop()
        assert scheduler.running is False

    @pytest.mark.asyncio
    async def test_stop_when_not_started(self):
        scheduler = NotificationScheduler()
        await scheduler.stop()  # Should not raise
        assert scheduler.running is False

    @pytest.mark.asyncio
    async def test_scheduler_handles_errors_gracefully(self, db):
        """Scheduler loop should not crash on exceptions."""
        scheduler = NotificationScheduler()

        # Mock config to return enabled config
        with patch.object(
            scheduler,
            "_get_config",
            new_callable=AsyncMock,
        ) as mock_cfg, patch.object(
            scheduler,
            "_get_interval",
            new_callable=AsyncMock,
            return_value=0,
        ), patch(
            "app.notifications.scheduler.check_watchlist",
            new_callable=AsyncMock,
            side_effect=RuntimeError("boom"),
        ):
            mock_cfg.return_value = AsyncMock(
                webhook_url="https://x.com",
                channel="slack",
                enabled=True,
            )

            scheduler.start()
            # Let it run one iteration
            await asyncio.sleep(0.2)
            # Should still be running (didn't crash)
            assert scheduler.running is True
            await scheduler.stop()
