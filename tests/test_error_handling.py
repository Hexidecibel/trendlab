import datetime
from unittest.mock import AsyncMock, MagicMock, patch

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


def assert_error_shape(data: dict):
    """Assert that response matches the ErrorResponse schema."""
    assert "detail" in data
    assert "request_id" in data
    # hint and error_code may be None but should be present
    assert "hint" in data
    assert "error_code" in data


class TestErrorResponseFormat:
    @pytest.mark.asyncio
    async def test_unknown_source_404(self, client: AsyncClient):
        response = await client.get(
            "/api/series", params={"source": "nope", "query": "test"}
        )
        assert response.status_code == 404
        data = response.json()
        assert_error_shape(data)
        assert "nope" in data["detail"]
        assert data["error_code"] == "SOURCE_NOT_FOUND"
        assert data["hint"] is not None

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
        data = response.json()
        assert_error_shape(data)
        assert data["error_code"] == "ENTITY_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_invalid_resample_returns_422(self, client: AsyncClient):
        with patch("app.routers.api.registry.get") as mock_get:
            mock_adapter = AsyncMock()
            mock_adapter.name = "pypi"
            mock_adapter.aggregation_method = "sum"
            mock_adapter.fetch.return_value = FAKE_TS
            mock_adapter.custom_resample_periods = MagicMock(return_value=[])
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
            mock_adapter.custom_resample_periods = MagicMock(return_value=[])
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

    @pytest.mark.asyncio
    async def test_http_exception_string_detail_wrapped(self, client: AsyncClient):
        """HTTPException with string detail gets wrapped in ErrorResponse shape."""
        response = await client.get(
            "/api/series", params={"source": "nope", "query": "test"}
        )
        assert response.status_code == 404
        data = response.json()
        assert_error_shape(data)
        assert isinstance(data["detail"], str)


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
        data = response.json()
        assert_error_shape(data)
        assert data["error_code"] == "EXTERNAL_UNAVAILABLE"
        assert data["hint"] is not None

    @pytest.mark.asyncio
    async def test_timeout_returns_503(self):
        """Timeout errors should return 503 with friendly message."""
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with (
                patch("app.routers.api.registry.get") as mock_get,
                patch("app.routers.api._cache") as mock_cache,
            ):
                mock_cache.fetch.side_effect = httpx.ReadTimeout("Timed out")
                mock_adapter = AsyncMock()
                mock_adapter.name = "pypi"
                mock_get.return_value = mock_adapter

                response = await client.get(
                    "/api/series",
                    params={"source": "pypi", "query": "fastapi"},
                )

        assert response.status_code == 503
        data = response.json()
        assert_error_shape(data)
        assert data["error_code"] == "EXTERNAL_TIMEOUT"

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
        assert_error_shape(data)
        assert data["error_code"] == "INTERNAL_ERROR"
        assert "unexpected" in data["detail"].lower()
        assert data["hint"] is not None
