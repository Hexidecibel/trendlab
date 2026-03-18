"""Tests for the Google Trends adapter."""

import datetime
from unittest.mock import patch

import pandas as pd
import pytest

from app.data.adapters.google_trends import GoogleTrendsAdapter


@pytest.fixture
def adapter():
    return GoogleTrendsAdapter()


def _mock_dataframe(keyword: str, dates: list[str], values: list[float]):
    """Build a pandas DataFrame mimicking pytrends output."""
    index = pd.DatetimeIndex([pd.Timestamp(d) for d in dates], name="date")
    data = {keyword: values, "isPartial": [False] * len(values)}
    df = pd.DataFrame(data, index=index)
    return df


class TestGoogleTrendsAdapter:
    def test_adapter_metadata(self, adapter):
        assert adapter.name == "google_trends"
        assert "Google Trends" in adapter.description

    def test_form_fields(self, adapter):
        fields = adapter.form_fields()
        names = [f.name for f in fields]
        assert "keyword" in names
        assert "timeframe" in names
        assert "geo" in names

        keyword_field = next(f for f in fields if f.name == "keyword")
        assert keyword_field.field_type == "text"

        timeframe_field = next(f for f in fields if f.name == "timeframe")
        assert timeframe_field.field_type == "select"
        assert len(timeframe_field.options) > 0

        geo_field = next(f for f in fields if f.name == "geo")
        assert geo_field.field_type == "text"

    @pytest.mark.asyncio
    async def test_fetch_basic(self, adapter):
        mock_df = _mock_dataframe(
            "python",
            ["2024-01-07", "2024-01-14", "2024-01-21"],
            [75.0, 80.0, 85.0],
        )

        with patch(
            "app.data.adapters.google_trends.GoogleTrendsAdapter._fetch_sync",
            return_value=mock_df,
        ):
            ts = await adapter.fetch("python:today 12-m:US")

        assert ts.source == "google_trends"
        assert len(ts.points) == 3
        assert ts.points[0].date == datetime.date(2024, 1, 7)
        assert ts.points[0].value == 75.0
        assert ts.points[2].value == 85.0

    @pytest.mark.asyncio
    async def test_fetch_keyword_only(self, adapter):
        """Query with only a keyword should use defaults."""
        mock_df = _mock_dataframe(
            "fastapi",
            ["2024-06-01"],
            [50.0],
        )

        with patch(
            "app.data.adapters.google_trends.GoogleTrendsAdapter._fetch_sync",
            return_value=mock_df,
        ) as mock_fetch:
            ts = await adapter.fetch("fastapi")

        mock_fetch.assert_called_once_with("fastapi", "today 12-m", "")
        assert ts.metadata["keyword"] == "fastapi"
        assert ts.metadata["timeframe"] == "today 12-m"
        assert ts.metadata["geo"] == "worldwide"

    @pytest.mark.asyncio
    async def test_fetch_keyword_and_timeframe(self, adapter):
        """Query with keyword:timeframe should default geo to empty."""
        mock_df = _mock_dataframe(
            "react",
            ["2020-01-01"],
            [90.0],
        )

        with patch(
            "app.data.adapters.google_trends.GoogleTrendsAdapter._fetch_sync",
            return_value=mock_df,
        ) as mock_fetch:
            ts = await adapter.fetch("react:today 5-y:")

        mock_fetch.assert_called_once_with("react", "today 5-y", "")
        assert ts.metadata["geo"] == "worldwide"

    @pytest.mark.asyncio
    async def test_fetch_full_query(self, adapter):
        """Query with all three parts should parse correctly."""
        mock_df = _mock_dataframe(
            "machine learning",
            ["2024-01-01"],
            [60.0],
        )

        with patch(
            "app.data.adapters.google_trends.GoogleTrendsAdapter._fetch_sync",
            return_value=mock_df,
        ) as mock_fetch:
            ts = await adapter.fetch("machine learning:today 12-m:US")

        mock_fetch.assert_called_once_with("machine learning", "today 12-m", "US")
        assert ts.metadata["keyword"] == "machine learning"
        assert ts.metadata["geo"] == "US"

    @pytest.mark.asyncio
    async def test_fetch_date_filtering(self, adapter):
        mock_df = _mock_dataframe(
            "python",
            ["2024-01-07", "2024-01-14", "2024-01-21", "2024-01-28"],
            [70.0, 75.0, 80.0, 85.0],
        )

        with patch(
            "app.data.adapters.google_trends.GoogleTrendsAdapter._fetch_sync",
            return_value=mock_df,
        ):
            ts = await adapter.fetch(
                "python:today 12-m:",
                start=datetime.date(2024, 1, 10),
                end=datetime.date(2024, 1, 25),
            )

        assert len(ts.points) == 2
        assert ts.points[0].date == datetime.date(2024, 1, 14)
        assert ts.points[1].date == datetime.date(2024, 1, 21)

    @pytest.mark.asyncio
    async def test_fetch_missing_keyword(self, adapter):
        with pytest.raises(ValueError, match="Missing keyword"):
            await adapter.fetch("")

    @pytest.mark.asyncio
    async def test_fetch_empty_keyword_with_colon(self, adapter):
        with pytest.raises(ValueError, match="Missing keyword"):
            await adapter.fetch(":today 12-m:US")

    @pytest.mark.asyncio
    async def test_fetch_invalid_timeframe(self, adapter):
        with pytest.raises(ValueError, match="Invalid timeframe"):
            await adapter.fetch("python:invalid_timeframe:US")

    @pytest.mark.asyncio
    async def test_fetch_rate_limit_error(self, adapter):
        """TooManyRequestsError should raise a user-friendly ValueError."""

        class TooManyRequestsError(Exception):
            pass

        with patch(
            "app.data.adapters.google_trends.GoogleTrendsAdapter._fetch_sync",
            side_effect=TooManyRequestsError("429 Too Many Requests"),
        ):
            with pytest.raises(ValueError, match="rate limit exceeded"):
                await adapter.fetch("python:today 12-m:US")

    @pytest.mark.asyncio
    async def test_fetch_429_in_message(self, adapter):
        """Generic exception with '429' in message should be caught as rate limit."""
        with patch(
            "app.data.adapters.google_trends.GoogleTrendsAdapter._fetch_sync",
            side_effect=Exception("Response error: 429"),
        ):
            with pytest.raises(ValueError, match="rate limit exceeded"):
                await adapter.fetch("python:today 12-m:US")

    @pytest.mark.asyncio
    async def test_points_sorted_by_date(self, adapter):
        # Provide dates out of order to verify sorting
        mock_df = _mock_dataframe(
            "python",
            ["2024-01-21", "2024-01-07", "2024-01-14"],
            [85.0, 75.0, 80.0],
        )

        with patch(
            "app.data.adapters.google_trends.GoogleTrendsAdapter._fetch_sync",
            return_value=mock_df,
        ):
            ts = await adapter.fetch("python:today 12-m:")

        dates = [p.date for p in ts.points]
        assert dates == sorted(dates)

    @pytest.mark.asyncio
    async def test_metadata_content(self, adapter):
        mock_df = _mock_dataframe(
            "AI",
            ["2024-01-01"],
            [100.0],
        )

        with patch(
            "app.data.adapters.google_trends.GoogleTrendsAdapter._fetch_sync",
            return_value=mock_df,
        ):
            ts = await adapter.fetch("AI:today 3-m:GB")

        assert ts.metadata["keyword"] == "AI"
        assert ts.metadata["timeframe"] == "today 3-m"
        assert ts.metadata["geo"] == "GB"
