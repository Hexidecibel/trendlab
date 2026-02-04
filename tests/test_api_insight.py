"""API endpoint tests for GET /api/insight (SSE streaming)."""

import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.models.schemas import DataPoint, TimeSeries

FAKE_TIMESERIES = TimeSeries(
    source="pypi",
    query="fastapi",
    points=[
        DataPoint(
            date=datetime.date(2024, 1, 1) + datetime.timedelta(days=i),
            value=100.0 + i * 2.0,
        )
        for i in range(60)
    ],
)


class TestInsightEndpoint:
    @pytest.mark.asyncio
    async def test_returns_sse_content_type(self, client: AsyncClient):
        with (
            patch("app.routers.api.registry.get") as mock_get,
            patch("app.routers.api.settings") as mock_settings,
            patch("app.routers.api.summarize_stream") as mock_stream,
        ):
            mock_settings.anthropic_api_key = "sk-test"
            mock_adapter = AsyncMock()
            mock_adapter.fetch.return_value = FAKE_TIMESERIES
            mock_get.return_value = mock_adapter

            async def fake_stream(*args, **kwargs):
                yield "Hello "
                yield "world!"

            mock_stream.return_value = fake_stream()

            response = await client.get(
                "/api/insight",
                params={"source": "pypi", "query": "fastapi"},
            )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

    @pytest.mark.asyncio
    async def test_sse_contains_delta_events(self, client: AsyncClient):
        with (
            patch("app.routers.api.registry.get") as mock_get,
            patch("app.routers.api.settings") as mock_settings,
            patch("app.routers.api.summarize_stream") as mock_stream,
        ):
            mock_settings.anthropic_api_key = "sk-test"
            mock_adapter = AsyncMock()
            mock_adapter.fetch.return_value = FAKE_TIMESERIES
            mock_get.return_value = mock_adapter

            async def fake_stream(*args, **kwargs):
                yield "chunk1"
                yield "chunk2"

            mock_stream.return_value = fake_stream()

            response = await client.get(
                "/api/insight",
                params={"source": "pypi", "query": "fastapi"},
            )

        body = response.text
        assert "event: delta" in body

    @pytest.mark.asyncio
    async def test_sse_contains_complete_event(self, client: AsyncClient):
        with (
            patch("app.routers.api.registry.get") as mock_get,
            patch("app.routers.api.settings") as mock_settings,
            patch("app.routers.api.summarize_stream") as mock_stream,
        ):
            mock_settings.anthropic_api_key = "sk-test"
            mock_adapter = AsyncMock()
            mock_adapter.fetch.return_value = FAKE_TIMESERIES
            mock_get.return_value = mock_adapter

            async def fake_stream(*args, **kwargs):
                yield "done"

            mock_stream.return_value = fake_stream()

            response = await client.get(
                "/api/insight",
                params={"source": "pypi", "query": "fastapi"},
            )

        body = response.text
        assert "event: complete" in body

    @pytest.mark.asyncio
    async def test_missing_api_key_returns_503(self, client: AsyncClient):
        with patch("app.routers.api.settings") as mock_settings:
            mock_settings.anthropic_api_key = None

            response = await client.get(
                "/api/insight",
                params={"source": "pypi", "query": "fastapi"},
            )

        assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_unknown_source_returns_404(self, client: AsyncClient):
        with patch("app.routers.api.settings") as mock_settings:
            mock_settings.anthropic_api_key = "sk-test"

            response = await client.get(
                "/api/insight",
                params={"source": "nope", "query": "test"},
            )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_missing_query_returns_422(self, client: AsyncClient):
        with patch("app.routers.api.settings") as mock_settings:
            mock_settings.anthropic_api_key = "sk-test"

            response = await client.get("/api/insight", params={"source": "pypi"})

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_prompt_version_accepted(self, client: AsyncClient):
        with (
            patch("app.routers.api.registry.get") as mock_get,
            patch("app.routers.api.settings") as mock_settings,
            patch("app.routers.api.summarize_stream") as mock_stream,
        ):
            mock_settings.anthropic_api_key = "sk-test"
            mock_adapter = AsyncMock()
            mock_adapter.fetch.return_value = FAKE_TIMESERIES
            mock_get.return_value = mock_adapter

            async def fake_stream(*args, **kwargs):
                yield "ok"

            mock_stream.return_value = fake_stream()

            response = await client.get(
                "/api/insight",
                params={
                    "source": "pypi",
                    "query": "fastapi",
                    "prompt_version": "concise",
                },
            )

        assert response.status_code == 200
