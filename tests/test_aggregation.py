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


class TestLegacySeasonAlias:
    def test_season_is_treated_as_year(self):
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
        assert result.metadata["resample"] == "year"

    def test_seasonal_alias_is_treated_as_year(self):
        points = [
            DataPoint(date=datetime.date(2024, 6, 1), value=10.0),
            DataPoint(date=datetime.date(2025, 3, 1), value=30.0),
        ]
        ts = TimeSeries(source="test", query="test", points=points)
        result = resample_series(ts, "seasonal", method="sum")
        assert [p.date for p in result.points] == [
            datetime.date(2024, 1, 1),
            datetime.date(2025, 1, 1),
        ]

    def test_season_not_listed_as_valid(self):
        ts = TimeSeries(source="test", query="test", points=[])
        with pytest.raises(ValueError) as exc:
            resample_series(ts, "biweekly")
        assert "season'" not in str(exc.value)


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


def _daily_between(
    start: datetime.date, end: datetime.date, value: float = 10.0
) -> TimeSeries:
    n = (end - start).days + 1
    points = [
        DataPoint(date=start + datetime.timedelta(days=i), value=value)
        for i in range(n)
    ]
    return TimeSeries(source="test", query="test", points=points)


class TestPartialEdgeBuckets:
    def test_sum_drops_sparse_first_and_last_month(self):
        # Jan 28 .. May 5: January has 4 days, May has 5 days
        ts = _daily_between(datetime.date(2025, 1, 28), datetime.date(2025, 5, 5))
        result = resample_series(ts, "month", method="sum")
        assert [p.date.month for p in result.points] == [2, 3, 4]
        assert result.points[0].value == pytest.approx(28 * 10.0)
        assert result.metadata["partial_buckets_dropped"] == [
            "2025-01-01",
            "2025-05-01",
        ]

    def test_sum_keeps_mostly_covered_edges(self):
        # Jan 3 .. Apr 28: both edges cover > 90% of their month
        ts = _daily_between(datetime.date(2025, 1, 3), datetime.date(2025, 4, 28))
        result = resample_series(ts, "month", method="sum")
        assert [p.date.month for p in result.points] == [1, 2, 3, 4]
        assert "partial_buckets_dropped" not in result.metadata

    def test_mean_never_drops(self):
        ts = _daily_between(datetime.date(2025, 1, 28), datetime.date(2025, 5, 5))
        result = resample_series(ts, "month", method="mean")
        assert len(result.points) == 5

    def test_sum_drops_majority_covered_but_incomplete_week(self):
        # A 4-of-7-day week would read as a 43% drop in a summed series
        ts = _daily_between(datetime.date(2025, 1, 6), datetime.date(2025, 1, 30))
        result = resample_series(ts, "week", method="sum")
        assert result.points[-1].date == datetime.date(2025, 1, 20)
        assert result.points[-1].value == pytest.approx(70.0)

    def test_sum_weekly_partial_last_week(self):
        # Mon Jan 6 .. Wed Jan 29: last ISO week (Jan 27) only has 3 days
        ts = _daily_between(datetime.date(2025, 1, 6), datetime.date(2025, 1, 29))
        result = resample_series(ts, "week", method="sum")
        assert [p.date for p in result.points] == [
            datetime.date(2025, 1, 6),
            datetime.date(2025, 1, 13),
            datetime.date(2025, 1, 20),
        ]

    def test_monthly_native_series_is_not_treated_as_partial(self):
        # Monthly data dated on the 1st covers its whole month
        points = [
            DataPoint(date=datetime.date(2025, m, 1), value=100.0)
            for m in range(1, 7)
        ]
        ts = TimeSeries(source="test", query="m", points=points)
        result = resample_series(ts, "quarter", method="sum")
        assert [p.value for p in result.points] == [300.0, 300.0]

    def test_sparse_counts_are_not_penalised_for_gaps(self):
        # Only a few days per month have data (e.g. GitHub stars), but the
        # series spans Jan 1 .. Apr 30 so every month is fully covered.
        days = [
            datetime.date(2025, m, d) for m in range(1, 5) for d in (1, 15)
        ] + [datetime.date(2025, 4, 30)]
        points = [DataPoint(date=d, value=1.0) for d in days]
        ts = TimeSeries(source="test", query="gh", points=points)
        result = resample_series(ts, "month", method="sum")
        assert len(result.points) == 4

    def test_keeps_edges_when_too_few_buckets_would_remain(self):
        ts = _daily_between(datetime.date(2025, 1, 28), datetime.date(2025, 2, 3))
        result = resample_series(ts, "month", method="sum")
        assert len(result.points) == 2

    def test_year_bucket_partial(self):
        ts = _daily_between(datetime.date(2023, 12, 1), datetime.date(2026, 2, 1))
        result = resample_series(ts, "year", method="sum")
        assert [p.date.year for p in result.points] == [2024, 2025]
