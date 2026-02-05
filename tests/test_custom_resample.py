"""Tests for custom adapter resample periods."""

import datetime

import pytest

from app.data.adapters.asa import ASAAdapter
from app.data.adapters.weather import WeatherAdapter
from app.models.schemas import DataPoint, TimeSeries
from app.services.aggregation import resample_series


class TestASACustomResample:
    """Tests for ASA adapter custom resample periods."""

    def test_custom_resample_periods_returns_mls_season(self):
        """Should return mls_season as a custom period."""
        adapter = ASAAdapter()
        periods = adapter.custom_resample_periods()

        assert len(periods) == 1
        assert periods[0].value == "mls_season"
        assert periods[0].label == "MLS Season"

    def test_custom_resample_sums_goals_by_season(self):
        """Should sum goal metrics by calendar year."""
        adapter = ASAAdapter()
        series = TimeSeries(
            source="asa",
            query="mls:team1:goals_for",
            points=[
                DataPoint(date=datetime.date(2023, 3, 15), value=2.0),
                DataPoint(date=datetime.date(2023, 5, 20), value=1.0),
                DataPoint(date=datetime.date(2023, 8, 10), value=3.0),
                DataPoint(date=datetime.date(2024, 4, 5), value=2.0),
                DataPoint(date=datetime.date(2024, 6, 15), value=1.0),
            ],
            metadata={"metric": "goals_for"},
        )

        resampled = adapter.custom_resample(series, "mls_season")

        assert len(resampled.points) == 2
        # Feb 1 used as season marker (MLS starts late Feb)
        assert resampled.points[0].date == datetime.date(2023, 2, 1)
        assert resampled.points[0].value == 6.0  # 2+1+3
        assert resampled.points[1].date == datetime.date(2024, 2, 1)
        assert resampled.points[1].value == 3.0  # 2+1
        assert resampled.metadata["resample"] == "mls_season"

    def test_custom_resample_averages_xg_by_season(self):
        """Should average xG metrics by calendar year."""
        adapter = ASAAdapter()
        series = TimeSeries(
            source="asa",
            query="mls:team1:xgoals_for",
            points=[
                DataPoint(date=datetime.date(2023, 3, 15), value=1.5),
                DataPoint(date=datetime.date(2023, 5, 20), value=2.0),
                DataPoint(date=datetime.date(2023, 8, 10), value=1.0),
            ],
            metadata={"metric": "xgoals_for"},
        )

        resampled = adapter.custom_resample(series, "mls_season")

        assert len(resampled.points) == 1
        # Feb 1 used as season marker (MLS starts late Feb)
        assert resampled.points[0].date == datetime.date(2023, 2, 1)
        assert resampled.points[0].value == pytest.approx(1.5)  # (1.5+2.0+1.0)/3

    def test_custom_resample_empty_series(self):
        """Should handle empty series."""
        adapter = ASAAdapter()
        series = TimeSeries(
            source="asa",
            query="mls:team1:goals_for",
            points=[],
            metadata={"metric": "goals_for"},
        )

        resampled = adapter.custom_resample(series, "mls_season")

        assert len(resampled.points) == 0
        assert resampled.metadata["resample"] == "mls_season"

    def test_custom_resample_unknown_period_raises(self):
        """Should raise for unknown custom period."""
        adapter = ASAAdapter()
        series = TimeSeries(
            source="asa",
            query="mls:team1:goals_for",
            points=[],
            metadata={},
        )

        with pytest.raises(NotImplementedError, match="Unknown custom period"):
            adapter.custom_resample(series, "unknown_period")


class TestWeatherCustomResample:
    """Tests for Weather adapter custom resample periods."""

    def test_custom_resample_periods_returns_meteorological_season(self):
        """Should return meteorological_season as a custom period."""
        adapter = WeatherAdapter()
        periods = adapter.custom_resample_periods()

        assert len(periods) == 1
        assert periods[0].value == "meteorological_season"
        assert periods[0].label == "Meteorological Season"

    def test_custom_resample_groups_by_meteorological_season(self):
        """Should group data by meteorological seasons."""
        adapter = WeatherAdapter()
        series = TimeSeries(
            source="weather",
            query="40.7,-74.0:temperature_2m_mean:celsius:kmh:mm",
            points=[
                # Winter 2024 (Dec 2023 + Jan/Feb 2024)
                DataPoint(date=datetime.date(2023, 12, 15), value=2.0),
                DataPoint(date=datetime.date(2024, 1, 15), value=0.0),
                DataPoint(date=datetime.date(2024, 2, 15), value=4.0),
                # Spring 2024
                DataPoint(date=datetime.date(2024, 3, 15), value=10.0),
                DataPoint(date=datetime.date(2024, 4, 15), value=15.0),
                # Summer 2024
                DataPoint(date=datetime.date(2024, 6, 15), value=25.0),
                DataPoint(date=datetime.date(2024, 7, 15), value=28.0),
            ],
            metadata={"metric": "temperature_2m_mean"},
        )

        resampled = adapter.custom_resample(series, "meteorological_season")

        assert len(resampled.points) == 3
        # Winter 2024 (Jan 1, 2024) - avg of 2, 0, 4 = 2.0
        assert resampled.points[0].date == datetime.date(2024, 1, 1)
        assert resampled.points[0].value == pytest.approx(2.0)
        # Spring 2024 (Mar 1, 2024) - avg of 10, 15 = 12.5
        assert resampled.points[1].date == datetime.date(2024, 3, 1)
        assert resampled.points[1].value == pytest.approx(12.5)
        # Summer 2024 (Jun 1, 2024) - avg of 25, 28 = 26.5
        assert resampled.points[2].date == datetime.date(2024, 6, 1)
        assert resampled.points[2].value == pytest.approx(26.5)

    def test_custom_resample_empty_series(self):
        """Should handle empty series."""
        adapter = WeatherAdapter()
        series = TimeSeries(
            source="weather",
            query="test",
            points=[],
            metadata={},
        )

        resampled = adapter.custom_resample(series, "meteorological_season")

        assert len(resampled.points) == 0
        assert resampled.metadata["resample"] == "meteorological_season"


class TestResampleServiceWithAdapter:
    """Tests for resample_series with adapter custom periods."""

    def test_resample_with_standard_freq_ignores_adapter(self):
        """Standard frequencies should work without adapter."""
        series = TimeSeries(
            source="test",
            query="test",
            points=[
                DataPoint(date=datetime.date(2024, 1, 15), value=1.0),
                DataPoint(date=datetime.date(2024, 1, 20), value=2.0),
                DataPoint(date=datetime.date(2024, 2, 5), value=3.0),
            ],
            metadata={},
        )

        resampled = resample_series(series, "month", method="sum")

        assert len(resampled.points) == 2
        assert resampled.points[0].value == 3.0  # Jan: 1+2
        assert resampled.points[1].value == 3.0  # Feb: 3

    def test_resample_with_custom_freq_uses_adapter(self):
        """Custom frequencies should delegate to adapter."""
        adapter = ASAAdapter()
        series = TimeSeries(
            source="asa",
            query="mls:team1:goals_for",
            points=[
                DataPoint(date=datetime.date(2023, 3, 15), value=2.0),
                DataPoint(date=datetime.date(2023, 5, 20), value=1.0),
            ],
            metadata={"metric": "goals_for"},
        )

        resampled = resample_series(series, "mls_season", adapter=adapter)

        assert len(resampled.points) == 1
        assert resampled.points[0].value == 3.0  # 2+1

    def test_resample_unknown_freq_without_adapter_raises(self):
        """Unknown frequency without adapter should raise."""
        series = TimeSeries(
            source="test",
            query="test",
            points=[],
            metadata={},
        )

        with pytest.raises(ValueError, match="Unknown resample frequency"):
            resample_series(series, "mls_season")

    def test_resample_unknown_freq_with_adapter_raises_if_not_supported(self):
        """Unknown frequency should raise even with adapter if not supported."""
        from app.data.adapters.pypi import PyPIAdapter

        adapter = PyPIAdapter()
        series = TimeSeries(
            source="pypi",
            query="requests",
            points=[],
            metadata={},
        )

        with pytest.raises(ValueError, match="Unknown resample frequency"):
            resample_series(series, "mls_season", adapter=adapter)
