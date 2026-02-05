import datetime
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.schemas import DataPoint, TimeSeries

FAKE_TS = TimeSeries(
    source="pypi",
    query="fastapi",
    points=[
        DataPoint(date=datetime.date(2024, 1, 1), value=100.0),
        DataPoint(date=datetime.date(2024, 1, 2), value=200.0),
    ],
)


class TestErrorResponseFormat:
    @pytest.mark.asyncio
    async def test_unknown_source_404(self, client: AsyncClient):
        response = await client.get(
            "/api/series", params={"source": "nope", "query": "test"}
        )
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_adapter_not_found_returns_404(self, client: AsyncClient):
        """ValueError from adapter (entity not found) stays 404."""
        with patch("app.routers.api.registry.get") as mock_get:
            mock_adapter = AsyncMock()
            mock_adapter.name = "pypi"
            mock_adapter.fetch.side_effect = ValueError("Package 'nope' not found")
            mock_get.return_value = mock_adapter

            response = await client.get(
                "/api/series", params={"source": "pypi", "query": "nope"}
            )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_invalid_resample_returns_422(self, client: AsyncClient):
        with patch("app.routers.api.registry.get") as mock_get:
            mock_adapter = AsyncMock()
            mock_adapter.name = "pypi"
            mock_adapter.aggregation_method = "sum"
            mock_adapter.fetch.return_value = FAKE_TS
            mock_get.return_value = mock_adapter

            response = await client.get(
                "/api/series",
                params={
                    "source": "pypi",
                    "query": "fastapi",
                    "resample": "biweekly",
                },
            )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_transform_returns_422(self, client: AsyncClient):
        with patch("app.routers.api.registry.get") as mock_get:
            mock_adapter = AsyncMock()
            mock_adapter.name = "pypi"
            mock_adapter.aggregation_method = "sum"
            mock_adapter.fetch.return_value = FAKE_TS
            mock_get.return_value = mock_adapter

            response = await client.get(
                "/api/series",
                params={
                    "source": "pypi",
                    "query": "fastapi",
                    "apply": "bogus_transform",
                },
            )

        assert response.status_code == 422


class TestGlobalExceptionHandlers:
    """Tests that need raise_app_exceptions=False to verify
    server-side error handling for non-HTTP exceptions."""

    @pytest.mark.asyncio
    async def test_external_api_failure_returns_503(self):
        """httpx errors from external APIs should return 503."""
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with (
                patch("app.routers.api.registry.get") as mock_get,
                patch("app.routers.api._cache") as mock_cache,
            ):
                mock_cache.fetch.side_effect = httpx.ConnectError("Connection refused")
                mock_adapter = AsyncMock()
                mock_adapter.name = "pypi"
                mock_get.return_value = mock_adapter

                response = await client.get(
                    "/api/series",
                    params={"source": "pypi", "query": "fastapi"},
                )

        assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_unhandled_exception_returns_500(self):
        """Unexpected errors should return 500 with structured response."""
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with (
                patch("app.routers.api.registry.get") as mock_get,
                patch("app.routers.api._cache") as mock_cache,
            ):
                mock_cache.fetch.side_effect = RuntimeError("Unexpected")
                mock_adapter = AsyncMock()
                mock_adapter.name = "pypi"
                mock_get.return_value = mock_adapter

                response = await client.get(
                    "/api/series",
                    params={"source": "pypi", "query": "fastapi"},
                )

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
