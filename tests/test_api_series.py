import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.models.schemas import DataPoint, TimeSeries

FAKE_TIMESERIES = TimeSeries(
    source="pypi",
    query="fastapi",
    points=[
        DataPoint(date=datetime.date(2024, 1, 1), value=1000.0),
        DataPoint(date=datetime.date(2024, 1, 2), value=1500.0),
    ],
)


class TestSourcesEndpoint:
    @pytest.mark.asyncio
    async def test_lists_sources(self, client: AsyncClient):
        response = await client.get("/api/sources")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2
        names = [s["name"] for s in data]
        assert "pypi" in names
        assert "crypto" in names

    @pytest.mark.asyncio
    async def test_source_has_description(self, client: AsyncClient):
        response = await client.get("/api/sources")
        pypi = [s for s in response.json() if s["name"] == "pypi"][0]
        assert "description" in pypi
        assert len(pypi["description"]) > 0


class TestSeriesEndpoint:
    @pytest.mark.asyncio
    async def test_returns_timeseries(self, client: AsyncClient):
        with patch("app.routers.api.registry.get") as mock_get:
            mock_adapter = AsyncMock()
            mock_adapter.fetch.return_value = FAKE_TIMESERIES
            mock_get.return_value = mock_adapter

            response = await client.get(
                "/api/series", params={"source": "pypi", "query": "fastapi"}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "pypi"
        assert data["query"] == "fastapi"
        assert len(data["points"]) == 2

    @pytest.mark.asyncio
    async def test_unknown_source_returns_404(self, client: AsyncClient):
        response = await client.get(
            "/api/series", params={"source": "nope", "query": "test"}
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_missing_query_returns_422(self, client: AsyncClient):
        response = await client.get("/api/series", params={"source": "pypi"})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_passes_date_params(self, client: AsyncClient):
        with patch("app.routers.api.registry.get") as mock_get:
            mock_adapter = AsyncMock()
            mock_adapter.fetch.return_value = FAKE_TIMESERIES
            mock_get.return_value = mock_adapter

            await client.get(
                "/api/series",
                params={
                    "source": "pypi",
                    "query": "fastapi",
                    "start": "2024-01-01",
                    "end": "2024-01-31",
                },
            )

            mock_adapter.fetch.assert_called_once_with(
                "fastapi",
                start=datetime.date(2024, 1, 1),
                end=datetime.date(2024, 1, 31),
            )

    @pytest.mark.asyncio
    async def test_adapter_value_error_returns_404(self, client: AsyncClient):
        with patch("app.routers.api.registry.get") as mock_get:
            mock_adapter = AsyncMock()
            mock_adapter.fetch.side_effect = ValueError("Package not found")
            mock_get.return_value = mock_adapter

            response = await client.get(
                "/api/series", params={"source": "pypi", "query": "nope"}
            )

        assert response.status_code == 404
