import datetime

import pytest

from app.analysis.correlation import align_series, correlate
from app.models.schemas import DataPoint, TimeSeries


def _make_ts(
    values: list[float],
    source: str = "test",
    query: str = "test",
    start: datetime.date = datetime.date(2025, 1, 1),
) -> TimeSeries:
    points = [
        DataPoint(date=start + datetime.timedelta(days=i), value=v)
        for i, v in enumerate(values)
    ]
    return TimeSeries(source=source, query=query, points=points)


class TestAlignSeries:
    def test_overlapping_dates(self):
        ts_a = _make_ts([1.0, 2.0, 3.0, 4.0, 5.0])
        ts_b = _make_ts(
            [10.0, 20.0, 30.0],
            start=datetime.date(2025, 1, 3),
        )
        a_vals, b_vals, dates = align_series(ts_a, ts_b)
        assert len(a_vals) == 3
        assert len(b_vals) == 3
        assert a_vals == [3.0, 4.0, 5.0]
        assert b_vals == [10.0, 20.0, 30.0]

    def test_no_overlap_returns_empty(self):
        ts_a = _make_ts([1.0, 2.0], start=datetime.date(2025, 1, 1))
        ts_b = _make_ts([3.0, 4.0], start=datetime.date(2025, 6, 1))
        a_vals, b_vals, dates = align_series(ts_a, ts_b)
        assert len(a_vals) == 0

    def test_identical_dates(self):
        ts_a = _make_ts([1.0, 2.0, 3.0])
        ts_b = _make_ts([4.0, 5.0, 6.0])
        a_vals, b_vals, dates = align_series(ts_a, ts_b)
        assert len(a_vals) == 3


class TestCorrelate:
    def test_perfect_positive_correlation(self):
        ts_a = _make_ts([1.0, 2.0, 3.0, 4.0, 5.0])
        ts_b = _make_ts([2.0, 4.0, 6.0, 8.0, 10.0])
        result = correlate(ts_a, ts_b)
        assert result.pearson.r == pytest.approx(1.0)
        assert result.spearman.r == pytest.approx(1.0)
        assert result.aligned_points == 5

    def test_perfect_negative_correlation(self):
        ts_a = _make_ts([1.0, 2.0, 3.0, 4.0, 5.0])
        ts_b = _make_ts([10.0, 8.0, 6.0, 4.0, 2.0])
        result = correlate(ts_a, ts_b)
        assert result.pearson.r == pytest.approx(-1.0)

    def test_uncorrelated_data(self):
        # Alternating pattern vs constant → low correlation
        ts_a = _make_ts([1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0])
        ts_b = _make_ts([5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0])
        result = correlate(ts_a, ts_b)
        # Constant series → correlation is NaN, we clamp to 0
        assert abs(result.pearson.r) < 0.01

    def test_lag_analysis_finds_peak(self):
        # A leads B by 2 days
        a_vals = [0.0] * 5 + [10.0] * 5 + [0.0] * 10
        b_vals = [0.0] * 7 + [10.0] * 5 + [0.0] * 8
        ts_a = _make_ts(a_vals)
        ts_b = _make_ts(b_vals)
        result = correlate(ts_a, ts_b, max_lag=5)
        # Find lag with highest correlation
        best_lag = max(result.lag_analysis, key=lambda lc: lc.correlation)
        assert best_lag.lag == 2  # A leads B by 2

    def test_scatter_output(self):
        ts_a = _make_ts([1.0, 2.0, 3.0])
        ts_b = _make_ts([4.0, 5.0, 6.0])
        result = correlate(ts_a, ts_b)
        assert len(result.scatter) == 3
        assert result.scatter[0].x == 1.0
        assert result.scatter[0].y == 4.0

    def test_labels(self):
        ts_a = _make_ts([1.0, 2.0, 3.0], source="crypto", query="bitcoin")
        ts_b = _make_ts([4.0, 5.0, 6.0], source="pypi", query="web3")
        result = correlate(ts_a, ts_b)
        assert result.series_a_label == "crypto:bitcoin"
        assert result.series_b_label == "pypi:web3"

    def test_too_few_aligned_points_raises(self):
        ts_a = _make_ts([1.0], start=datetime.date(2025, 1, 1))
        ts_b = _make_ts([2.0], start=datetime.date(2025, 1, 1))
        with pytest.raises(ValueError, match="at least 3"):
            correlate(ts_a, ts_b)

    def test_identical_series(self):
        ts = _make_ts([1.0, 2.0, 3.0, 4.0, 5.0])
        result = correlate(ts, ts)
        assert result.pearson.r == pytest.approx(1.0)
        assert result.spearman.r == pytest.approx(1.0)
