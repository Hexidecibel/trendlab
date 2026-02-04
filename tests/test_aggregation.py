import datetime

import pytest

from app.models.schemas import DataPoint, TimeSeries
from app.services.aggregation import resample_series


def _daily_series(
    n: int, start: datetime.date = datetime.date(2025, 1, 1)
) -> TimeSeries:
    """Generate n consecutive daily points starting from start."""
    points = [
        DataPoint(date=start + datetime.timedelta(days=i), value=float(i + 1))
        for i in range(n)
    ]
    return TimeSeries(source="test", query="test", points=points)


class TestWeeklyAggregation:
    def test_14_days_yields_2_weeks(self):
        # Start on a Monday so 14 days = exactly 2 ISO weeks
        ts = _daily_series(14, start=datetime.date(2025, 1, 6))
        result = resample_series(ts, "week", method="mean")
        assert len(result.points) == 2

    def test_week_bucket_dates_are_mondays(self):
        ts = _daily_series(14, start=datetime.date(2025, 1, 6))
        result = resample_series(ts, "week", method="mean")
        for p in result.points:
            assert p.date.weekday() == 0  # Monday

    def test_mean_aggregation(self):
        # Start on Monday, 7 days = 1 full week
        ts = _daily_series(7, start=datetime.date(2025, 1, 6))  # values 1..7
        result = resample_series(ts, "week", method="mean")
        assert len(result.points) == 1
        assert result.points[0].value == pytest.approx(4.0)  # mean of 1..7

    def test_sum_aggregation(self):
        ts = _daily_series(7, start=datetime.date(2025, 1, 6))  # values 1..7
        result = resample_series(ts, "week", method="sum")
        assert len(result.points) == 1
        assert result.points[0].value == pytest.approx(28.0)  # sum of 1..7


class TestMonthlyAggregation:
    def test_60_days_yields_2_or_3_months(self):
        ts = _daily_series(60)
        result = resample_series(ts, "month", method="mean")
        # Jan 1 - Mar 1: Jan has 31 points, Feb has 28, Mar has 1
        assert len(result.points) == 3

    def test_bucket_dates_are_first_of_month(self):
        ts = _daily_series(60)
        result = resample_series(ts, "month", method="mean")
        for p in result.points:
            assert p.date.day == 1


class TestQuarterAggregation:
    def test_quarter_bucketing(self):
        # Create points spanning Q1 and Q2
        points = [
            DataPoint(date=datetime.date(2025, 2, 15), value=10.0),
            DataPoint(date=datetime.date(2025, 3, 15), value=20.0),
            DataPoint(date=datetime.date(2025, 4, 15), value=30.0),
            DataPoint(date=datetime.date(2025, 5, 15), value=40.0),
        ]
        ts = TimeSeries(source="test", query="test", points=points)
        result = resample_series(ts, "quarter", method="mean")
        assert len(result.points) == 2
        # Q1 bucket
        assert result.points[0].date == datetime.date(2025, 1, 1)
        assert result.points[0].value == pytest.approx(15.0)  # mean(10, 20)
        # Q2 bucket
        assert result.points[1].date == datetime.date(2025, 4, 1)
        assert result.points[1].value == pytest.approx(35.0)  # mean(30, 40)


class TestSeasonAggregation:
    def test_season_groups_by_year(self):
        points = [
            DataPoint(date=datetime.date(2024, 6, 1), value=10.0),
            DataPoint(date=datetime.date(2024, 12, 1), value=20.0),
            DataPoint(date=datetime.date(2025, 3, 1), value=30.0),
        ]
        ts = TimeSeries(source="test", query="test", points=points)
        result = resample_series(ts, "season", method="mean")
        assert len(result.points) == 2
        assert result.points[0].date == datetime.date(2024, 1, 1)
        assert result.points[0].value == pytest.approx(15.0)
        assert result.points[1].date == datetime.date(2025, 1, 1)
        assert result.points[1].value == pytest.approx(30.0)


class TestNoOp:
    def test_day_is_noop(self):
        ts = _daily_series(5)
        result = resample_series(ts, "day", method="mean")
        assert len(result.points) == 5

    def test_none_returns_original(self):
        ts = _daily_series(5)
        result = resample_series(ts, None, method="mean")
        assert len(result.points) == 5


class TestSparseData:
    def test_sparse_points_aggregate_correctly(self):
        """ASA-like data: games every few days."""
        points = [
            DataPoint(date=datetime.date(2025, 1, 3), value=2.0),
            DataPoint(date=datetime.date(2025, 1, 10), value=1.0),
            DataPoint(date=datetime.date(2025, 1, 20), value=3.0),
            DataPoint(date=datetime.date(2025, 1, 28), value=0.0),
        ]
        ts = TimeSeries(source="asa", query="test", points=points)
        result = resample_series(ts, "month", method="mean")
        assert len(result.points) == 1
        assert result.points[0].value == pytest.approx(1.5)  # mean(2,1,3,0)


class TestMetadata:
    def test_resample_in_metadata(self):
        ts = _daily_series(14)
        result = resample_series(ts, "week", method="mean")
        assert result.metadata.get("resample") == "week"

    def test_no_resample_metadata_for_noop(self):
        ts = _daily_series(5)
        result = resample_series(ts, "day", method="mean")
        assert "resample" not in result.metadata


class TestEmptySeries:
    def test_empty_points_returns_empty(self):
        ts = TimeSeries(source="test", query="test", points=[])
        result = resample_series(ts, "week", method="mean")
        assert len(result.points) == 0
