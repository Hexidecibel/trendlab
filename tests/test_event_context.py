"""Tests for the event context module."""

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.ai.event_context import (
    _MAX_DATES,
    _cache,
    _fetch_ddg,
    _fetch_wikipedia,
    fetch_event_context,
)
from app.models.schemas import EventContext


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the in-memory cache before each test."""
    _cache.clear()
    yield
    _cache.clear()


def _mock_response(json_data, status_code=200):
    """Build a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    if status_code >= 400:
        resp.raise_for_status.side_effect = (
            httpx.HTTPStatusError(
                "error",
                request=MagicMock(),
                response=resp,
            )
        )
    return resp


class TestFetchDDG:
    @pytest.mark.asyncio
    async def test_returns_event_context(self):
        ddg_data = {
            "Heading": "Bitcoin price surge in Jan 2024",
            "AbstractURL": "https://example.com/article",
            "AbstractSource": "DuckDuckGo",
            "AbstractText": "",
        }
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.return_value = _mock_response(ddg_data)

        result = await _fetch_ddg(
            client, "bitcoin", "2024-01-15"
        )
        assert result is not None
        assert isinstance(result, EventContext)
        assert result.date == "2024-01-15"
        assert "Bitcoin" in result.headline
        assert result.source_url == "https://example.com/article"

    @pytest.mark.asyncio
    async def test_falls_back_to_related_topics(self):
        ddg_data = {
            "Heading": "",
            "AbstractText": "",
            "RelatedTopics": [
                {"Text": "Related topic about bitcoin"}
            ],
        }
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.return_value = _mock_response(ddg_data)

        result = await _fetch_ddg(
            client, "bitcoin", "2024-01-15"
        )
        assert result is not None
        assert "bitcoin" in result.headline.lower()

    @pytest.mark.asyncio
    async def test_returns_none_on_empty(self):
        ddg_data = {
            "Heading": "",
            "AbstractText": "",
            "RelatedTopics": [],
        }
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.return_value = _mock_response(ddg_data)

        result = await _fetch_ddg(
            client, "bitcoin", "2024-01-15"
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_error(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.side_effect = httpx.TimeoutException(
            "timeout"
        )

        result = await _fetch_ddg(
            client, "bitcoin", "2024-01-15"
        )
        assert result is None


class TestFetchWikipedia:
    @pytest.mark.asyncio
    async def test_returns_event_context(self):
        wiki_data = {
            "events": [
                {
                    "text": "Historic event happened",
                    "pages": [
                        {
                            "content_urls": {
                                "desktop": {
                                    "page": "https://en.wikipedia.org/wiki/Event"
                                }
                            }
                        }
                    ],
                }
            ]
        }
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.return_value = _mock_response(wiki_data)

        result = await _fetch_wikipedia(
            client, "2024-01-15"
        )
        assert result is not None
        assert result.date == "2024-01-15"
        assert "Historic" in result.headline
        assert result.relevance == "Wikipedia: On this day"

    @pytest.mark.asyncio
    async def test_returns_none_on_empty_events(self):
        wiki_data = {"events": []}
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.return_value = _mock_response(wiki_data)

        result = await _fetch_wikipedia(
            client, "2024-01-15"
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_error(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.side_effect = httpx.TimeoutException(
            "timeout"
        )

        result = await _fetch_wikipedia(
            client, "2024-01-15"
        )
        assert result is None


class TestFetchEventContext:
    @pytest.mark.asyncio
    async def test_returns_events_from_ddg(self):
        ddg_data = {
            "Heading": "Price spike explanation",
            "AbstractURL": "https://example.com",
            "AbstractSource": "News",
        }

        async def mock_get(url, **kwargs):
            return _mock_response(ddg_data)

        with patch(
            "app.ai.event_context.httpx.AsyncClient"
        ) as mock_cls:
            ctx = AsyncMock()
            ctx.get = mock_get
            ctx.__aenter__ = AsyncMock(return_value=ctx)
            ctx.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = ctx

            result = await fetch_event_context(
                "bitcoin", ["2024-01-15"]
            )
            assert len(result) == 1
            assert result[0].headline == "Price spike explanation"

    @pytest.mark.asyncio
    async def test_empty_dates_returns_empty(self):
        result = await fetch_event_context("bitcoin", [])
        assert result == []

    @pytest.mark.asyncio
    async def test_cache_prevents_duplicate_requests(self):
        call_count = 0

        async def mock_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            return _mock_response(
                {
                    "Heading": "Cached result",
                    "AbstractURL": None,
                }
            )

        with patch(
            "app.ai.event_context.httpx.AsyncClient"
        ) as mock_cls:
            ctx = AsyncMock()
            ctx.get = mock_get
            ctx.__aenter__ = AsyncMock(return_value=ctx)
            ctx.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = ctx

            # First call
            r1 = await fetch_event_context(
                "bitcoin", ["2024-01-15"]
            )
            assert len(r1) == 1
            first_count = call_count

            # Second call - should use cache
            r2 = await fetch_event_context(
                "bitcoin", ["2024-01-15"]
            )
            assert len(r2) == 1
            # No additional HTTP calls
            assert call_count == first_count

    @pytest.mark.asyncio
    async def test_limits_to_max_dates(self):
        call_count = 0

        async def mock_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            return _mock_response(
                {"Heading": "", "RelatedTopics": []}
            )

        with patch(
            "app.ai.event_context.httpx.AsyncClient"
        ) as mock_cls:
            ctx = AsyncMock()
            ctx.get = mock_get
            ctx.__aenter__ = AsyncMock(return_value=ctx)
            ctx.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = ctx

            dates = [
                f"2024-01-{i:02d}" for i in range(1, 12)
            ]
            assert len(dates) > _MAX_DATES

            await fetch_event_context("bitcoin", dates)
            # DDG + Wikipedia fallback = up to 2 calls per date
            # But limited to MAX_DATES dates
            assert call_count <= _MAX_DATES * 2

    @pytest.mark.asyncio
    async def test_network_error_returns_empty(self):
        with patch(
            "app.ai.event_context.httpx.AsyncClient"
        ) as mock_cls:
            mock_cls.side_effect = Exception(
                "network down"
            )

            result = await fetch_event_context(
                "bitcoin", ["2024-01-15"]
            )
            assert result == []


class TestPromptIntegration:
    def test_event_context_in_formatted_prompt(self):
        from app.ai.prompts import format_event_context

        events = [
            EventContext(
                date="2024-01-15",
                headline="Major exchange hack reported",
                source_url="https://example.com",
                relevance="News",
            ),
            EventContext(
                date="2024-02-01",
                headline="Regulatory announcement",
                source_url=None,
                relevance=None,
            ),
        ]
        result = format_event_context(events)
        assert "2024-01-15" in result
        assert "Major exchange hack" in result
        assert "2024-02-01" in result
        assert "Regulatory announcement" in result
        assert "real-world events" in result.lower()

    def test_empty_events_returns_empty_string(self):
        from app.ai.prompts import format_event_context

        result = format_event_context([])
        assert result == ""

    def test_build_messages_includes_event_context(self):
        from app.ai.prompts import build_messages
        from app.models.schemas import (
            AnomalyPoint,
            AnomalyReport,
            DataPoint,
            ForecastComparison,
            ForecastPoint,
            ModelEvaluation,
            ModelForecast,
            MovingAverage,
            SeasonalityResult,
            TrendAnalysis,
            TrendSignal,
        )

        base_date = datetime.date(2024, 1, 1)
        analysis = TrendAnalysis(
            source="pypi",
            query="fastapi",
            series_length=60,
            trend=TrendSignal(
                direction="rising",
                momentum=0.05,
                acceleration=0.001,
                moving_averages=[
                    MovingAverage(
                        window=7,
                        values=[
                            DataPoint(
                                date=base_date, value=100.0
                            )
                        ],
                    )
                ],
                momentum_series=[
                    DataPoint(date=base_date, value=0.05)
                ],
            ),
            seasonality=SeasonalityResult(
                detected=False,
                period_days=None,
                strength=None,
                autocorrelation=[1.0],
            ),
            anomalies=AnomalyReport(
                method="zscore",
                threshold=2.5,
                anomalies=[
                    AnomalyPoint(
                        date=base_date,
                        value=500.0,
                        score=3.2,
                        method="zscore",
                    )
                ],
                total_points=60,
                anomaly_count=1,
            ),
            structural_breaks=[],
        )
        fc = ForecastComparison(
            source="pypi",
            query="fastapi",
            series_length=60,
            horizon=14,
            forecasts=[
                ModelForecast(
                    model_name="linear",
                    points=[
                        ForecastPoint(
                            date=base_date
                            + datetime.timedelta(days=1),
                            value=102.0,
                            lower_ci=90.0,
                            upper_ci=110.0,
                        )
                    ],
                )
            ],
            evaluations=[
                ModelEvaluation(
                    model_name="linear",
                    mae=1.5,
                    rmse=2.0,
                    mape=3.0,
                    train_size=48,
                    test_size=12,
                )
            ],
            recommended_model="linear",
        )
        events = [
            EventContext(
                date="2024-01-01",
                headline="Test headline for prompt",
                source_url=None,
                relevance="Test",
            )
        ]

        msgs = build_messages(
            analysis, fc, event_contexts=events
        )
        user_content = msgs[1]["content"]
        assert "Test headline for prompt" in user_content
        assert "real-world events" in user_content.lower()
