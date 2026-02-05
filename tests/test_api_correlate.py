import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.models.schemas import DataPoint, TimeSeries


def _make_ts(source: str, query: str, n: int = 10) -> TimeSeries:
    points = [
        DataPoint(
            date=datetime.date(2024, 1, 1) + datetime.timedelta(days=i),
            value=float(i + 1),
        )
        for i in range(n)
    ]
    return TimeSeries(source=source, query=query, points=points)


class TestCorrelateEndpoint:
    @pytest.mark.asyncio
    async def test_correlate_returns_result(self, client: AsyncClient):
        with patch("app.routers.api.registry.get") as mock_get:
            crypto_adapter = AsyncMock()
            crypto_adapter.name = "crypto"
            crypto_adapter.aggregation_method = "mean"
            crypto_adapter.fetch.return_value = _make_ts("crypto", "bitcoin")

            pypi_adapter = AsyncMock()
            pypi_adapter.name = "pypi"
            pypi_adapter.aggregation_method = "sum"
            pypi_adapter.fetch.return_value = _make_ts("pypi", "web3")

            def get_adapter(name):
                return {"crypto": crypto_adapter, "pypi": pypi_adapter}[name]

            mock_get.side_effect = get_adapter

            response = await client.post(
                "/api/correlate",
                json={
                    "series_a": {"source": "crypto", "query": "bitcoin"},
                    "series_b": {"source": "pypi", "query": "web3"},
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "pearson" in data
        assert "spearman" in data
        assert "lag_analysis" in data
        assert "scatter" in data
        assert data["aligned_points"] == 10

    @pytest.mark.asyncio
    async def test_correlate_unknown_source_returns_404(self, client: AsyncClient):
        response = await client.post(
            "/api/correlate",
            json={
                "series_a": {"source": "nope", "query": "a"},
                "series_b": {"source": "crypto", "query": "b"},
            },
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_correlate_with_resample(self, client: AsyncClient):
        # 28 daily points starting on a Monday → 4 weekly points
        points = [
            DataPoint(
                date=datetime.date(2024, 1, 8) + datetime.timedelta(days=i),
                value=float(i + 1),
            )
            for i in range(28)
        ]
        ts = TimeSeries(source="crypto", query="bitcoin", points=points)

        with patch("app.routers.api.registry.get") as mock_get:
            mock_adapter = AsyncMock()
            mock_adapter.name = "crypto"
            mock_adapter.aggregation_method = "mean"
            mock_adapter.fetch.return_value = ts
            mock_get.return_value = mock_adapter

            response = await client.post(
                "/api/correlate",
                json={
                    "series_a": {"source": "crypto", "query": "bitcoin"},
                    "series_b": {"source": "crypto", "query": "bitcoin"},
                    "resample": "week",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["aligned_points"] == 4

    @pytest.mark.asyncio
    async def test_correlate_too_few_points_returns_422(self, client: AsyncClient):
        points = [DataPoint(date=datetime.date(2024, 1, 1), value=1.0)]
        ts = TimeSeries(source="crypto", query="bitcoin", points=points)

        with patch("app.routers.api.registry.get") as mock_get:
            mock_adapter = AsyncMock()
            mock_adapter.name = "crypto"
            mock_adapter.aggregation_method = "mean"
            mock_adapter.fetch.return_value = ts
            mock_get.return_value = mock_adapter

            response = await client.post(
                "/api/correlate",
                json={
                    "series_a": {"source": "crypto", "query": "bitcoin"},
                    "series_b": {"source": "crypto", "query": "bitcoin"},
                },
            )

        assert response.status_code == 422
