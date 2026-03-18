import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.analysis.causal_impact import analyze_causal_impact
from app.models.schemas import DataPoint, TimeSeries


def _make_ts(
    values: list[float],
    source: str = "test",
    query: str = "test",
    start: datetime.date = datetime.date(2024, 1, 1),
) -> TimeSeries:
    points = [
        DataPoint(date=start + datetime.timedelta(days=i), value=v)
        for i, v in enumerate(values)
    ]
    return TimeSeries(source=source, query=query, points=points)


class TestAnalyzeCausalImpact:
    @pytest.mark.asyncio
    async def test_step_series_detects_positive_impact(self):
        """Constant pre-period then a higher constant post-period."""
        pre = [10.0] * 50
        post = [20.0] * 20
        ts = _make_ts(pre + post)
        event_date = (
            datetime.date(2024, 1, 1) + datetime.timedelta(days=50)
        ).isoformat()

        result = await analyze_causal_impact(ts, event_date)

        assert result.significant is True
        assert result.cumulative_impact > 0
        assert result.relative_impact_pct > 0
        assert result.p_value < 0.05
        assert result.pre_period_length == 50
        assert result.post_period_length == 20
        assert len(result.pointwise) == 20

    @pytest.mark.asyncio
    async def test_constant_series_no_impact(self):
        """Same constant value before and after event: no significant impact."""
        values = [10.0] * 80
        ts = _make_ts(values)
        event_date = (
            datetime.date(2024, 1, 1) + datetime.timedelta(days=50)
        ).isoformat()

        result = await analyze_causal_impact(ts, event_date)

        assert result.significant is False
        assert abs(result.cumulative_impact) < 1.0
        assert result.p_value > 0.05

    @pytest.mark.asyncio
    async def test_pre_period_too_short_raises(self):
        """Pre-period with < 30 points raises ValueError."""
        values = [10.0] * 40
        ts = _make_ts(values)
        event_date = (
            datetime.date(2024, 1, 1) + datetime.timedelta(days=20)
        ).isoformat()

        with pytest.raises(ValueError, match="Pre-period must have >= 30"):
            await analyze_causal_impact(ts, event_date)

    @pytest.mark.asyncio
    async def test_event_date_outside_range_raises(self):
        """Event date before or after series range raises ValueError."""
        ts = _make_ts([10.0] * 50)

        with pytest.raises(ValueError, match="outside series range"):
            await analyze_causal_impact(ts, "2023-01-01")

        with pytest.raises(ValueError, match="outside series range"):
            await analyze_causal_impact(ts, "2025-01-01")

    @pytest.mark.asyncio
    async def test_pointwise_fields(self):
        """Each pointwise entry has all expected fields."""
        pre = [10.0] * 50
        post = [15.0] * 10
        ts = _make_ts(pre + post)
        event_date = (
            datetime.date(2024, 1, 1) + datetime.timedelta(days=50)
        ).isoformat()

        result = await analyze_causal_impact(ts, event_date)

        for p in result.pointwise:
            assert p.date is not None
            assert isinstance(p.actual, float)
            assert isinstance(p.predicted, float)
            assert p.lower_ci <= p.predicted <= p.upper_ci
            assert isinstance(p.impact, float)

    @pytest.mark.asyncio
    async def test_summary_contains_event_date(self):
        pre = [10.0] * 50
        post = [20.0] * 10
        ts = _make_ts(pre + post)
        event_date = (
            datetime.date(2024, 1, 1) + datetime.timedelta(days=50)
        ).isoformat()

        result = await analyze_causal_impact(ts, event_date)

        assert event_date in result.summary


class TestCausalImpactEndpoint:
    @pytest.mark.asyncio
    async def test_causal_impact_returns_result(self, client: AsyncClient):
        pre = [10.0] * 50
        post = [20.0] * 20
        ts = _make_ts(pre + post, source="crypto", query="bitcoin")

        with patch("app.routers.api.registry.get") as mock_get:
            mock_adapter = AsyncMock()
            mock_adapter.name = "crypto"
            mock_adapter.aggregation_method = "mean"
            mock_adapter.fetch.return_value = ts
            mock_get.return_value = mock_adapter

            event_date = (
                datetime.date(2024, 1, 1) + datetime.timedelta(days=50)
            ).isoformat()
            response = await client.post(
                "/api/causal-impact",
                json={
                    "source": "crypto",
                    "query": "bitcoin",
                    "event_date": event_date,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["significant"] is True
        assert data["cumulative_impact"] > 0
        assert "pointwise" in data
        assert len(data["pointwise"]) == 20

    @pytest.mark.asyncio
    async def test_causal_impact_unknown_source_returns_404(self, client: AsyncClient):
        response = await client.post(
            "/api/causal-impact",
            json={
                "source": "nope",
                "query": "test",
                "event_date": "2024-03-01",
            },
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_causal_impact_validation_error_returns_422(
        self, client: AsyncClient
    ):
        # Too few pre-period points
        ts = _make_ts([10.0] * 40, source="crypto", query="bitcoin")

        with patch("app.routers.api.registry.get") as mock_get:
            mock_adapter = AsyncMock()
            mock_adapter.name = "crypto"
            mock_adapter.aggregation_method = "mean"
            mock_adapter.fetch.return_value = ts
            mock_get.return_value = mock_adapter

            # Event at day 10 → only 10 pre-period points
            event_date = (
                datetime.date(2024, 1, 1) + datetime.timedelta(days=10)
            ).isoformat()
            response = await client.post(
                "/api/causal-impact",
                json={
                    "source": "crypto",
                    "query": "bitcoin",
                    "event_date": event_date,
                },
            )

        assert response.status_code == 422
