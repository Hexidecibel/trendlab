import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.models.schemas import DataPoint, TimeSeries

# Need enough points for all analysis modules to work
FAKE_TIMESERIES = TimeSeries(
    source="pypi",
    query="fastapi",
    points=[
        DataPoint(
            date=datetime.date(2024, 1, 1) + datetime.timedelta(days=i),
            value=100.0 + i * 2.0 + (10.0 if i == 30 else 0.0),
        )
        for i in range(60)
    ],
)


class TestAnalyzeEndpoint:
    @pytest.mark.asyncio
    async def test_successful_response_shape(self, client: AsyncClient):
        with patch("app.routers.api.registry.get") as mock_get:
            mock_adapter = AsyncMock()
            mock_adapter.fetch.return_value = FAKE_TIMESERIES
            mock_get.return_value = mock_adapter

            response = await client.get(
                "/api/analyze",
                params={"source": "pypi", "query": "fastapi"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "pypi"
        assert data["query"] == "fastapi"
        assert data["series_length"] == 60

    @pytest.mark.asyncio
    async def test_trend_subobject(self, client: AsyncClient):
        with patch("app.routers.api.registry.get") as mock_get:
            mock_adapter = AsyncMock()
            mock_adapter.fetch.return_value = FAKE_TIMESERIES
            mock_get.return_value = mock_adapter

            response = await client.get(
                "/api/analyze",
                params={"source": "pypi", "query": "fastapi"},
            )

        trend = response.json()["trend"]
        assert "direction" in trend
        assert "momentum" in trend
        assert "acceleration" in trend
        assert "moving_averages" in trend

    @pytest.mark.asyncio
    async def test_seasonality_subobject(self, client: AsyncClient):
        with patch("app.routers.api.registry.get") as mock_get:
            mock_adapter = AsyncMock()
            mock_adapter.fetch.return_value = FAKE_TIMESERIES
            mock_get.return_value = mock_adapter

            response = await client.get(
                "/api/analyze",
                params={"source": "pypi", "query": "fastapi"},
            )

        seasonality = response.json()["seasonality"]
        assert "detected" in seasonality
        assert "period_days" in seasonality
        assert "strength" in seasonality

    @pytest.mark.asyncio
    async def test_anomalies_subobject(self, client: AsyncClient):
        with patch("app.routers.api.registry.get") as mock_get:
            mock_adapter = AsyncMock()
            mock_adapter.fetch.return_value = FAKE_TIMESERIES
            mock_get.return_value = mock_adapter

            response = await client.get(
                "/api/analyze",
                params={"source": "pypi", "query": "fastapi"},
            )

        anomalies = response.json()["anomalies"]
        assert "method" in anomalies
        assert "threshold" in anomalies
        assert "anomalies" in anomalies
        assert "total_points" in anomalies

    @pytest.mark.asyncio
    async def test_structural_breaks_is_list(self, client: AsyncClient):
        with patch("app.routers.api.registry.get") as mock_get:
            mock_adapter = AsyncMock()
            mock_adapter.fetch.return_value = FAKE_TIMESERIES
            mock_get.return_value = mock_adapter

            response = await client.get(
                "/api/analyze",
                params={"source": "pypi", "query": "fastapi"},
            )

        assert isinstance(response.json()["structural_breaks"], list)

    @pytest.mark.asyncio
    async def test_unknown_source_returns_404(self, client: AsyncClient):
        response = await client.get(
            "/api/analyze",
            params={"source": "nope", "query": "test"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_missing_query_returns_422(self, client: AsyncClient):
        response = await client.get("/api/analyze", params={"source": "pypi"})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_anomaly_method_iqr_accepted(self, client: AsyncClient):
        with patch("app.routers.api.registry.get") as mock_get:
            mock_adapter = AsyncMock()
            mock_adapter.fetch.return_value = FAKE_TIMESERIES
            mock_get.return_value = mock_adapter

            response = await client.get(
                "/api/analyze",
                params={
                    "source": "pypi",
                    "query": "fastapi",
                    "anomaly_method": "iqr",
                },
            )

        assert response.status_code == 200
        assert response.json()["anomalies"]["method"] == "iqr"
