"""Tests for WebSocket progress updates."""

import time
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.testclient import TestClient

from app.main import app
from app.services.progress import (
    ProgressBus,
    ProgressEvent,
    current_request_id,
    emit_progress,
    progress_bus,
)


class TestProgressEvent:
    def test_to_dict(self):
        event = ProgressEvent(stage="fetch", progress=0.3, message="Fetching")
        d = event.to_dict()
        assert d == {
            "stage": "fetch",
            "progress": 0.3,
            "message": "Fetching",
        }


class TestProgressBus:
    def test_subscribe_and_emit(self):
        bus = ProgressBus()
        queue = bus.subscribe("req-1")

        bus.emit("req-1", "fetch", 0.3, "Fetching data")

        assert not queue.empty()
        event = queue.get_nowait()
        assert event.stage == "fetch"
        assert event.progress == 0.3
        assert event.message == "Fetching data"

    def test_emit_to_nonexistent_subscriber(self):
        bus = ProgressBus()
        # Should not raise
        bus.emit("no-such-id", "fetch", 0.3, "Fetching")

    def test_unsubscribe(self):
        bus = ProgressBus()
        bus.subscribe("req-2")
        bus.unsubscribe("req-2")

        # Emit after unsubscribe should be a no-op
        bus.emit("req-2", "fetch", 0.3, "Fetching")

    def test_unsubscribe_nonexistent(self):
        bus = ProgressBus()
        # Should not raise
        bus.unsubscribe("no-such-id")

    def test_multiple_subscribers_independent(self):
        bus = ProgressBus()
        q1 = bus.subscribe("req-a")
        q2 = bus.subscribe("req-b")

        bus.emit("req-a", "fetch", 0.3, "A fetching")
        bus.emit("req-b", "analyze", 0.6, "B analyzing")

        event_a = q1.get_nowait()
        event_b = q2.get_nowait()

        assert event_a.stage == "fetch"
        assert event_a.message == "A fetching"
        assert event_b.stage == "analyze"
        assert event_b.message == "B analyzing"

        # Each queue only has its own event
        assert q1.empty()
        assert q2.empty()


class TestContextVarPropagation:
    def test_emit_progress_with_contextvar(self):
        bus = ProgressBus()
        queue = bus.subscribe("ctx-1")

        with patch("app.services.progress.progress_bus", bus):
            token = current_request_id.set("ctx-1")
            try:
                emit_progress("fetch", 0.3, "Fetching")
            finally:
                current_request_id.reset(token)

        event = queue.get_nowait()
        assert event.stage == "fetch"
        bus.unsubscribe("ctx-1")

    def test_emit_progress_without_contextvar(self):
        """emit_progress is a no-op when no request_id is set."""
        # Should not raise
        emit_progress("fetch", 0.3, "Fetching")


class TestWebSocketEndpoint:
    @staticmethod
    def _receive_non_heartbeat(ws):
        """Receive the next WS JSON message, skipping heartbeats."""
        while True:
            msg = ws.receive_json()
            if msg.get("stage") != "heartbeat":
                return msg

    def test_connect_and_receive(self):
        """Connect via WS, subscribe, emit, receive."""
        client = TestClient(app)

        with client.websocket_connect("/api/ws/progress") as ws:
            ws.send_json({"request_id": "ws-test-1"})

            # Wait for the WS handler to process the subscribe message.
            # The handler runs in a separate thread; without this the
            # emit() calls below can fire before subscribe() is called,
            # causing the events to be lost.
            deadline = time.monotonic() + 2.0
            while "ws-test-1" not in progress_bus._subscribers:
                if time.monotonic() > deadline:
                    raise TimeoutError("WS handler did not subscribe in time")
                time.sleep(0.01)

            # Emit a progress event from the server side
            progress_bus.emit(
                "ws-test-1",
                "fetch",
                0.3,
                "Fetching data",
            )
            progress_bus.emit(
                "ws-test-1",
                "complete",
                1.0,
                "Done",
            )

            msg1 = self._receive_non_heartbeat(ws)
            assert msg1["stage"] == "fetch"
            assert msg1["progress"] == 0.3

            msg2 = self._receive_non_heartbeat(ws)
            assert msg2["stage"] == "complete"
            assert msg2["progress"] == 1.0

    def test_missing_request_id(self):
        """WS closes with 4000 if no request_id sent."""
        client = TestClient(app)

        with client.websocket_connect("/api/ws/progress") as ws:
            ws.send_json({})
            # Server should close the connection
            # The close will raise WebSocketDisconnect
            # on the next receive attempt — the test
            # just verifies no crash.


class TestProgressEmissionInRoutes:
    """Verify that the API endpoints emit progress events."""

    @pytest.mark.asyncio
    async def test_series_emits_progress(self):
        """GET /api/series should emit progress events."""
        events: list[ProgressEvent] = []
        original_emit = progress_bus.emit

        def capture_emit(request_id, stage, progress, message):
            events.append(ProgressEvent(stage, progress, message))
            original_emit(request_id, stage, progress, message)

        with patch.object(progress_bus, "emit", side_effect=capture_emit):
            import datetime

            from app.models.schemas import DataPoint, TimeSeries

            fake_ts = TimeSeries(
                source="pypi",
                query="fastapi",
                points=[
                    DataPoint(
                        date=datetime.date(2024, 1, 1),
                        value=100.0,
                    ),
                    DataPoint(
                        date=datetime.date(2024, 1, 2),
                        value=200.0,
                    ),
                ],
            )

            with (
                patch("app.routers.api.registry.get") as mock_get,
                patch("app.routers.api._cache") as mock_cache,
            ):
                from unittest.mock import AsyncMock, MagicMock

                mock_adapter = AsyncMock()
                mock_adapter.name = "pypi"
                mock_adapter.aggregation_method = "sum"
                mock_adapter.custom_resample_periods = MagicMock(return_value=[])
                mock_get.return_value = mock_adapter
                mock_cache.fetch = AsyncMock(return_value=fake_ts)

                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://test",
                ) as client:
                    response = await client.get(
                        "/api/series",
                        params={
                            "source": "pypi",
                            "query": "fastapi",
                        },
                    )

                assert response.status_code == 200
                stages = [e.stage for e in events]
                assert "cache_check" in stages
                assert "fetch" in stages
                assert "complete" in stages
