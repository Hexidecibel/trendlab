"""API endpoint tests for GET /api/forecast."""

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
            value=100.0 + i * 2.0 + (10.0 if i == 30 else 0.0),
        )
        for i in range(60)
    ],
)


class TestForecastEndpoint:
    @pytest.mark.asyncio
    async def test_successful_response_shape(self, client: AsyncClient):
        with patch("app.routers.api.registry.get") as mock_get:
            mock_adapter = AsyncMock()
            mock_adapter.fetch.return_value = FAKE_TIMESERIES
            mock_get.return_value = mock_adapter

            response = await client.get(
                "/api/forecast",
                params={"source": "pypi", "query": "fastapi"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "pypi"
        assert data["query"] == "fastapi"
        assert data["series_length"] == 60
        assert data["horizon"] == 14  # default

    @pytest.mark.asyncio
    async def test_custom_horizon(self, client: AsyncClient):
        with patch("app.routers.api.registry.get") as mock_get:
            mock_adapter = AsyncMock()
            mock_adapter.fetch.return_value = FAKE_TIMESERIES
            mock_get.return_value = mock_adapter

            response = await client.get(
                "/api/forecast",
                params={"source": "pypi", "query": "fastapi", "horizon": 7},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["horizon"] == 7
        for f in data["forecasts"]:
            assert len(f["points"]) == 7

    @pytest.mark.asyncio
    async def test_forecasts_list(self, client: AsyncClient):
        with patch("app.routers.api.registry.get") as mock_get:
            mock_adapter = AsyncMock()
            mock_adapter.fetch.return_value = FAKE_TIMESERIES
            mock_get.return_value = mock_adapter

            response = await client.get(
                "/api/forecast",
                params={"source": "pypi", "query": "fastapi"},
            )

        data = response.json()
        assert isinstance(data["forecasts"], list)
        assert len(data["forecasts"]) >= 3
        for f in data["forecasts"]:
            assert "model_name" in f
            assert "points" in f
            for pt in f["points"]:
                assert "date" in pt
                assert "value" in pt
                assert "lower_ci" in pt
                assert "upper_ci" in pt

    @pytest.mark.asyncio
    async def test_evaluations_list(self, client: AsyncClient):
        with patch("app.routers.api.registry.get") as mock_get:
            mock_adapter = AsyncMock()
            mock_adapter.fetch.return_value = FAKE_TIMESERIES
            mock_get.return_value = mock_adapter

            response = await client.get(
                "/api/forecast",
                params={"source": "pypi", "query": "fastapi"},
            )

        data = response.json()
        assert isinstance(data["evaluations"], list)
        for e in data["evaluations"]:
            assert "model_name" in e
            assert "mae" in e
            assert "rmse" in e
            assert "mape" in e
            assert "train_size" in e
            assert "test_size" in e

    @pytest.mark.asyncio
    async def test_recommended_model_present(self, client: AsyncClient):
        with patch("app.routers.api.registry.get") as mock_get:
            mock_adapter = AsyncMock()
            mock_adapter.fetch.return_value = FAKE_TIMESERIES
            mock_get.return_value = mock_adapter

            response = await client.get(
                "/api/forecast",
                params={"source": "pypi", "query": "fastapi"},
            )

        data = response.json()
        assert "recommended_model" in data
        model_names = {f["model_name"] for f in data["forecasts"]}
        assert data["recommended_model"] in model_names

    @pytest.mark.asyncio
    async def test_unknown_source_returns_404(self, client: AsyncClient):
        response = await client.get(
            "/api/forecast",
            params={"source": "nope", "query": "test"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_missing_query_returns_422(self, client: AsyncClient):
        response = await client.get("/api/forecast", params={"source": "pypi"})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_horizon_validation_too_low(self, client: AsyncClient):
        response = await client.get(
            "/api/forecast",
            params={"source": "pypi", "query": "fastapi", "horizon": 0},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_horizon_validation_too_high(self, client: AsyncClient):
        response = await client.get(
            "/api/forecast",
            params={"source": "pypi", "query": "fastapi", "horizon": 400},
        )
        assert response.status_code == 422
