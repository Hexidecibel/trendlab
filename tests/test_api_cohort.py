import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.analysis.cohort import (
    _max_drawdown,
    _normalize_points,
    _total_return,
    _volatility,
    analyze_cohort,
)
from app.models.schemas import DataPoint, TimeSeries


def _make_ts(source: str, query: str, values: list[float]) -> TimeSeries:
    points = [
        DataPoint(
            date=datetime.date(2024, 1, 1) + datetime.timedelta(days=i),
            value=v,
        )
        for i, v in enumerate(values)
    ]
    return TimeSeries(source=source, query=query, points=points)


class TestNormalization:
    def test_normalize_percentage_change(self):
        points = [
            DataPoint(date=datetime.date(2024, 1, 1), value=100.0),
            DataPoint(date=datetime.date(2024, 1, 2), value=110.0),
            DataPoint(date=datetime.date(2024, 1, 3), value=90.0),
        ]
        result = _normalize_points(points)
        assert result[0].value == 0.0  # Day 1 = 0%
        assert result[1].value == pytest.approx(10.0)  # +10%
        assert result[2].value == pytest.approx(-10.0)  # -10%

    def test_normalize_with_zero_first(self):
        """When first value is zero, return points unchanged."""
        points = [
            DataPoint(date=datetime.date(2024, 1, 1), value=0.0),
            DataPoint(date=datetime.date(2024, 1, 2), value=10.0),
        ]
        result = _normalize_points(points)
        assert result[0].value == 0.0
        assert result[1].value == 10.0


class TestTotalReturn:
    def test_positive_return(self):
        ts = _make_ts("test", "a", [100.0, 110.0, 120.0])
        assert _total_return(ts.points) == pytest.approx(20.0)

    def test_negative_return(self):
        ts = _make_ts("test", "a", [100.0, 90.0, 80.0])
        assert _total_return(ts.points) == pytest.approx(-20.0)

    def test_zero_first_value(self):
        ts = _make_ts("test", "a", [0.0, 10.0])
        assert _total_return(ts.points) == 0.0


class TestMaxDrawdown:
    def test_simple_drawdown(self):
        # Peak at 200, trough at 100 => -50%
        ts = _make_ts("test", "a", [100.0, 200.0, 100.0])
        assert _max_drawdown(ts.points) == pytest.approx(-50.0)

    def test_no_drawdown(self):
        # Monotonically increasing
        ts = _make_ts("test", "a", [100.0, 110.0, 120.0])
        assert _max_drawdown(ts.points) == pytest.approx(0.0)

    def test_multiple_drawdowns(self):
        # Two drawdowns: 100->50 (-50%), then 80->20 (-75%)
        ts = _make_ts("test", "a", [100.0, 50.0, 80.0, 20.0])
        assert _max_drawdown(ts.points) == pytest.approx(-80.0)  # 100->20

    def test_single_point(self):
        ts = _make_ts("test", "a", [100.0])
        assert _max_drawdown(ts.points) == 0.0


class TestVolatility:
    def test_constant_values(self):
        ts = _make_ts("test", "a", [100.0, 100.0, 100.0, 100.0])
        assert _volatility(ts.points) == pytest.approx(0.0)

    def test_volatile_series(self):
        ts = _make_ts("test", "a", [100.0, 110.0, 90.0, 120.0])
        vol = _volatility(ts.points)
        assert vol > 0

    def test_single_point(self):
        ts = _make_ts("test", "a", [100.0])
        assert _volatility(ts.points) == 0.0


class TestAnalyzeCohort:
    def test_ranking_order(self):
        """Highest total return should be rank 1."""
        ts_a = _make_ts("test", "winner", [100.0, 200.0])  # +100%
        ts_b = _make_ts("test", "loser", [100.0, 50.0])  # -50%
        ts_c = _make_ts("test", "mid", [100.0, 120.0])  # +20%

        members = analyze_cohort([ts_a, ts_b, ts_c])
        assert members[0].query == "winner"
        assert members[0].rank == 1
        assert members[1].query == "mid"
        assert members[1].rank == 2
        assert members[2].query == "loser"
        assert members[2].rank == 3

    def test_normalized_points_in_result(self):
        ts_a = _make_ts("test", "a", [100.0, 150.0])
        ts_b = _make_ts("test", "b", [200.0, 250.0])

        members = analyze_cohort([ts_a, ts_b], normalize=True)
        # Both should start at 0%
        for m in members:
            assert m.normalized_points[0].value == pytest.approx(0.0)

    def test_no_normalize(self):
        ts_a = _make_ts("test", "a", [100.0, 150.0])
        members = analyze_cohort([ts_a], normalize=False)
        # Points should be original values
        assert members[0].normalized_points[0].value == pytest.approx(100.0)
        assert members[0].normalized_points[1].value == pytest.approx(150.0)


class TestCohortEndpoint:
    @pytest.mark.asyncio
    async def test_cohort_happy_path(self, client: AsyncClient):
        with patch("app.routers.api.registry.get") as mock_get:
            mock_adapter = AsyncMock()
            mock_adapter.name = "crypto"
            mock_adapter.aggregation_method = "mean"
            mock_adapter.fetch.side_effect = [
                _make_ts("crypto", "bitcoin", [100.0, 200.0, 150.0]),
                _make_ts("crypto", "ethereum", [50.0, 60.0, 55.0]),
                _make_ts("crypto", "solana", [10.0, 5.0, 8.0]),
            ]
            mock_get.return_value = mock_adapter

            response = await client.post(
                "/api/cohort",
                json={
                    "source": "crypto",
                    "queries": ["bitcoin", "ethereum", "solana"],
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "crypto"
        assert len(data["members"]) == 3
        # Bitcoin has highest return (+50%), should be rank 1
        assert data["members"][0]["query"] == "bitcoin"
        assert data["members"][0]["rank"] == 1
        # Ethereum is second (+10%)
        assert data["members"][1]["query"] == "ethereum"
        assert data["members"][1]["rank"] == 2
        # Solana is last (-20%)
        assert data["members"][2]["query"] == "solana"
        assert data["members"][2]["rank"] == 3
        # Period bounds
        assert data["period_start"] is not None
        assert data["period_end"] is not None

    @pytest.mark.asyncio
    async def test_cohort_normalization_math(self, client: AsyncClient):
        with patch("app.routers.api.registry.get") as mock_get:
            mock_adapter = AsyncMock()
            mock_adapter.name = "crypto"
            mock_adapter.aggregation_method = "mean"
            mock_adapter.fetch.side_effect = [
                _make_ts("crypto", "a", [100.0, 150.0]),
                _make_ts("crypto", "b", [200.0, 250.0]),
            ]
            mock_get.return_value = mock_adapter

            response = await client.post(
                "/api/cohort",
                json={
                    "source": "crypto",
                    "queries": ["a", "b"],
                    "normalize": True,
                },
            )

        assert response.status_code == 200
        data = response.json()
        for member in data["members"]:
            # First normalized point should be 0%
            assert member["normalized_points"][0]["value"] == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_cohort_too_few_queries(self, client: AsyncClient):
        response = await client.post(
            "/api/cohort",
            json={"source": "crypto", "queries": ["bitcoin"]},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_cohort_unknown_source(self, client: AsyncClient):
        response = await client.post(
            "/api/cohort",
            json={"source": "nonexistent", "queries": ["a", "b"]},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_cohort_with_dates(self, client: AsyncClient):
        with patch("app.routers.api.registry.get") as mock_get:
            mock_adapter = AsyncMock()
            mock_adapter.name = "crypto"
            mock_adapter.aggregation_method = "mean"
            mock_adapter.fetch.side_effect = [
                _make_ts("crypto", "bitcoin", [100.0, 120.0]),
                _make_ts("crypto", "ethereum", [50.0, 55.0]),
            ]
            mock_get.return_value = mock_adapter

            response = await client.post(
                "/api/cohort",
                json={
                    "source": "crypto",
                    "queries": ["bitcoin", "ethereum"],
                    "start_date": "2024-01-01",
                    "end_date": "2024-06-30",
                },
            )

        assert response.status_code == 200
        # Verify date params were passed through
        call_args = mock_adapter.fetch.call_args_list
        assert call_args[0].kwargs["start"] == datetime.date(2024, 1, 1)
        assert call_args[0].kwargs["end"] == datetime.date(2024, 6, 30)

    @pytest.mark.asyncio
    async def test_cohort_stats_correctness(self, client: AsyncClient):
        """Verify that returned stats match expected calculations."""
        with patch("app.routers.api.registry.get") as mock_get:
            mock_adapter = AsyncMock()
            mock_adapter.name = "test"
            mock_adapter.aggregation_method = "mean"
            # Series: 100 -> 200 -> 100 -> 150
            mock_adapter.fetch.side_effect = [
                _make_ts("test", "a", [100.0, 200.0, 100.0, 150.0]),
                _make_ts("test", "b", [100.0, 110.0, 120.0, 130.0]),
            ]
            mock_get.return_value = mock_adapter

            response = await client.post(
                "/api/cohort",
                json={"source": "test", "queries": ["a", "b"]},
            )

        data = response.json()
        member_a = next(m for m in data["members"] if m["query"] == "a")
        member_b = next(m for m in data["members"] if m["query"] == "b")

        # Total return: (150/100 - 1) * 100 = 50%
        assert member_a["total_return"] == pytest.approx(50.0)
        # Total return: (130/100 - 1) * 100 = 30%
        assert member_b["total_return"] == pytest.approx(30.0)

        # Max drawdown for a: peak at 200, trough at 100 => -50%
        assert member_a["max_drawdown"] == pytest.approx(-50.0)
        # Max drawdown for b: monotonically increasing => 0%
        assert member_b["max_drawdown"] == pytest.approx(0.0)

        # Volatility should be positive for a (varying returns)
        assert member_a["volatility"] > 0
        # Volatility for b should be lower (steady growth)
        assert member_b["volatility"] < member_a["volatility"]
