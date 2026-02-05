import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.models.schemas import DataPoint, TimeSeries


def _fake_ts(source: str, query: str) -> TimeSeries:
    return TimeSeries(
        source=source,
        query=query,
        points=[
            DataPoint(date=datetime.date(2024, 1, 1), value=10.0),
            DataPoint(date=datetime.date(2024, 1, 2), value=20.0),
        ],
    )


class TestCompareEndpoint:
    @pytest.mark.asyncio
    async def test_compare_two_series(self, client: AsyncClient):
        with patch("app.routers.api.registry.get") as mock_get:
            mock_adapter = AsyncMock()
            mock_adapter.name = "crypto"
            mock_adapter.aggregation_method = "mean"
            mock_adapter.fetch.side_effect = [
                _fake_ts("crypto", "bitcoin"),
                _fake_ts("crypto", "ethereum"),
            ]
            mock_get.return_value = mock_adapter

            response = await client.post(
                "/api/compare",
                json={
                    "items": [
                        {"source": "crypto", "query": "bitcoin"},
                        {"source": "crypto", "query": "ethereum"},
                    ]
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert len(data["series"]) == 2
        assert data["series"][0]["source"] == "crypto"
        assert data["series"][0]["query"] == "bitcoin"
        assert data["series"][1]["query"] == "ethereum"

    @pytest.mark.asyncio
    async def test_compare_three_series(self, client: AsyncClient):
        with patch("app.routers.api.registry.get") as mock_get:
            mock_adapter = AsyncMock()
            mock_adapter.name = "crypto"
            mock_adapter.aggregation_method = "mean"
            mock_adapter.fetch.side_effect = [
                _fake_ts("crypto", "bitcoin"),
                _fake_ts("crypto", "ethereum"),
                _fake_ts("crypto", "solana"),
            ]
            mock_get.return_value = mock_adapter

            response = await client.post(
                "/api/compare",
                json={
                    "items": [
                        {"source": "crypto", "query": "bitcoin"},
                        {"source": "crypto", "query": "ethereum"},
                        {"source": "crypto", "query": "solana"},
                    ]
                },
            )

        assert response.status_code == 200
        assert response.json()["count"] == 3

    @pytest.mark.asyncio
    async def test_compare_rejects_more_than_three(self, client: AsyncClient):
        response = await client.post(
            "/api/compare",
            json={
                "items": [{"source": "crypto", "query": f"coin{i}"} for i in range(4)]
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_compare_rejects_fewer_than_two(self, client: AsyncClient):
        response = await client.post(
            "/api/compare",
            json={"items": [{"source": "crypto", "query": "bitcoin"}]},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_compare_cross_source(self, client: AsyncClient):
        """Two different sources in the same comparison."""
        with patch("app.routers.api.registry.get") as mock_get:
            crypto_adapter = AsyncMock()
            crypto_adapter.name = "crypto"
            crypto_adapter.aggregation_method = "mean"
            crypto_adapter.fetch.return_value = _fake_ts("crypto", "bitcoin")

            pypi_adapter = AsyncMock()
            pypi_adapter.name = "pypi"
            pypi_adapter.aggregation_method = "sum"
            pypi_adapter.fetch.return_value = _fake_ts("pypi", "web3")

            def get_adapter(name):
                return {"crypto": crypto_adapter, "pypi": pypi_adapter}[name]

            mock_get.side_effect = get_adapter

            response = await client.post(
                "/api/compare",
                json={
                    "items": [
                        {"source": "crypto", "query": "bitcoin"},
                        {"source": "pypi", "query": "web3"},
                    ]
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["series"][0]["source"] == "crypto"
        assert data["series"][1]["source"] == "pypi"

    @pytest.mark.asyncio
    async def test_compare_unknown_source_returns_404(self, client: AsyncClient):
        response = await client.post(
            "/api/compare",
            json={
                "items": [
                    {"source": "nope", "query": "a"},
                    {"source": "crypto", "query": "b"},
                ]
            },
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_compare_with_resample(self, client: AsyncClient):
        # 14 daily points starting on a Monday
        points = [
            DataPoint(
                date=datetime.date(2024, 1, 8) + datetime.timedelta(days=i),
                value=float(i + 1),
            )
            for i in range(14)
        ]
        ts1 = TimeSeries(source="crypto", query="bitcoin", points=points)
        ts2 = TimeSeries(source="crypto", query="ethereum", points=points)

        with patch("app.routers.api.registry.get") as mock_get:
            mock_adapter = AsyncMock()
            mock_adapter.name = "crypto"
            mock_adapter.aggregation_method = "mean"
            mock_adapter.fetch.side_effect = [ts1, ts2]
            mock_get.return_value = mock_adapter

            response = await client.post(
                "/api/compare",
                json={
                    "items": [
                        {"source": "crypto", "query": "bitcoin"},
                        {"source": "crypto", "query": "ethereum"},
                    ],
                    "resample": "week",
                },
            )

        assert response.status_code == 200
        data = response.json()
        # 14 daily points → 2 weekly points per series
        assert len(data["series"][0]["points"]) == 2
        assert len(data["series"][1]["points"]) == 2

    @pytest.mark.asyncio
    async def test_compare_with_date_range(self, client: AsyncClient):
        with patch("app.routers.api.registry.get") as mock_get:
            mock_adapter = AsyncMock()
            mock_adapter.name = "crypto"
            mock_adapter.aggregation_method = "mean"
            mock_adapter.fetch.side_effect = [
                _fake_ts("crypto", "bitcoin"),
                _fake_ts("crypto", "ethereum"),
            ]
            mock_get.return_value = mock_adapter

            response = await client.post(
                "/api/compare",
                json={
                    "items": [
                        {
                            "source": "crypto",
                            "query": "bitcoin",
                            "start": "2024-01-01",
                            "end": "2024-06-30",
                        },
                        {
                            "source": "crypto",
                            "query": "ethereum",
                            "start": "2024-01-01",
                            "end": "2024-06-30",
                        },
                    ]
                },
            )

        assert response.status_code == 200
        # Verify date params were passed through to adapter
        call_args = mock_adapter.fetch.call_args_list
        assert call_args[0].kwargs["start"] == datetime.date(2024, 1, 1)
        assert call_args[0].kwargs["end"] == datetime.date(2024, 6, 30)
