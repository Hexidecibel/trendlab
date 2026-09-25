"""Tests for trend smoothing presets (robust LOWESS + fit line)."""

import datetime
import math

import numpy as np
import pytest

from app.analysis.smoothing import (
    DAYS_PER_MONTH,
    FRAC_MAX,
    FRAC_MIN,
    centered_rolling_mean,
    lowess_frac,
    smooth_presets,
    window_points,
)
from app.models.schemas import DataPoint, TimeSeries

BASE = datetime.date(2024, 1, 1)
PRESETS = ("light", "medium", "heavy", "line")


def _series(dates, values) -> TimeSeries:
    return TimeSeries(
        source="test",
        query="smooth",
        points=[DataPoint(date=d, value=float(v)) for d, v in zip(dates, values)],
    )


def _daily(n):
    return [BASE + datetime.timedelta(days=i) for i in range(n)]


def _add_months(d: datetime.date, k: int) -> datetime.date:
    total = d.month - 1 + k
    return datetime.date(d.year + total // 12, total % 12 + 1, 1)


def _assert_valid(result, n):
    for key in PRESETS:
        pts = result[key]
        assert len(pts) == n, key
        assert all(math.isfinite(p.value) for p in pts), key


def _vals(result, key):
    return np.array([p.value for p in result[key]])


class TestFrequencies:
    def test_daily_noisy_trend(self):
        rng = np.random.default_rng(0)
        n = 200
        values = 1000 + 5 * np.arange(n) + rng.normal(0, 80, n)
        result = smooth_presets(_series(_daily(n), values))
        _assert_valid(result, n)
        truth = 1000 + 5 * np.arange(n)
        # Heavier presets are smoother (smaller step-to-step roughness)
        rough = {k: np.std(np.diff(_vals(result, k), 2)) for k in PRESETS[:3]}
        assert rough["heavy"] < rough["medium"] < rough["light"]
        # Medium tracks the true trend far better than the raw noise does
        err = np.mean(np.abs(_vals(result, "medium") - truth))
        assert err < 40

    def test_weekly_series(self):
        n = 104
        dates = [BASE + datetime.timedelta(weeks=i) for i in range(n)]
        values = 50 + 0.5 * np.arange(n) + 5 * np.sin(np.arange(n))
        result = smooth_presets(_series(dates, values))
        _assert_valid(result, n)
        # Output dates line up with input dates
        assert [p.date for p in result["medium"]] == dates

    def test_monthly_series(self):
        n = 48
        dates = [_add_months(BASE, k) for k in range(n)]
        values = 100 * (1.02 ** np.arange(n))
        result = smooth_presets(_series(dates, values))
        _assert_valid(result, n)
        assert result["slope_pct_per_month"] > 0

    def test_window_is_defined_in_time(self):
        # ~1 month window: 30 points on daily data, ~4.3 on weekly
        assert window_points("medium", 1.0) == pytest.approx(30.0)
        assert window_points("heavy", 7.0) == pytest.approx(90 / 7)
        # Monthly data still gets a minimum window in points
        assert window_points("light", 30.0) >= 3

    def test_seasonal_period_floors_window(self):
        assert window_points("light", 1.0, seasonal_period=14) == pytest.approx(14)
        # A yearly cycle in daily data is signal, not noise: no floor
        assert window_points("light", 1.0, seasonal_period=365) == pytest.approx(7)

    def test_frac_is_clamped(self):
        assert lowess_frac(1, 1000) == FRAC_MIN
        assert lowess_frac(900, 1000) == FRAC_MAX
        assert lowess_frac(300, 1000) == pytest.approx(0.3)


class TestShortSeries:
    def test_under_15_points_uses_centered_rolling_mean(self):
        n = 10
        values = np.array([1, 5, 2, 6, 3, 7, 4, 8, 5, 9], dtype=float)
        result = smooth_presets(_series(_daily(n), values))
        _assert_valid(result, n)
        # Endpoints: the window shrinks symmetrically to the point itself
        assert result["medium"][0].value == pytest.approx(1.0)
        assert result["medium"][-1].value == pytest.approx(9.0)

    def test_centered_rolling_mean(self):
        out = centered_rolling_mean(np.array([0, 3, 6, 9, 12], dtype=float), 3)
        assert out.tolist() == pytest.approx([0, 3, 6, 9, 12])
        out = centered_rolling_mean(np.array([0, 9, 0, 9, 0], dtype=float), 3)
        assert out[2] == pytest.approx(6.0)

    @pytest.mark.parametrize("n", [1, 2])
    def test_one_and_two_points(self, n):
        values = [10.0, 20.0][:n]
        result = smooth_presets(_series(_daily(n), values))
        _assert_valid(result, n)
        assert [p.value for p in result["medium"]] == values

    def test_empty(self):
        result = smooth_presets(_series([], []))
        for key in PRESETS:
            assert result[key] == []
        assert result["slope_pct_per_month"] is None


class TestRobustness:
    def test_gaps_are_handled(self):
        # Two blocks of daily data with a 60-day hole
        later = [BASE + datetime.timedelta(days=100 + i) for i in range(40)]
        dates = _daily(40) + later
        x = np.array([(d - BASE).days for d in dates], dtype=float)
        values = 200 + 2 * x
        result = smooth_presets(_series(dates, values))
        _assert_valid(result, len(dates))
        # A linear trend in time survives the gap (smoothing uses day numbers)
        assert _vals(result, "medium") == pytest.approx(values, rel=1e-3)
        assert _vals(result, "line") == pytest.approx(values, rel=1e-6)

    def test_single_spike_is_resisted(self):
        n = 120
        values = np.full(n, 100.0) + np.sin(np.arange(n) / 5.0)
        values[60] = 5000.0
        result = smooth_presets(_series(_daily(n), values))
        for key in ("light", "medium", "heavy"):
            smoothed = _vals(result, key)
            # Robust LOWESS: the spike barely moves the trend
            assert smoothed[60] < 110, key
            assert np.max(smoothed) < 110, key

    def test_constant_series(self):
        n = 60
        result = smooth_presets(_series(_daily(n), [42.0] * n))
        _assert_valid(result, n)
        for key in PRESETS:
            assert all(p.value == pytest.approx(42.0) for p in result[key])
        assert result["slope_pct_per_month"] == 0.0

    def test_all_zero_series(self):
        n = 60
        result = smooth_presets(_series(_daily(n), [0.0] * n))
        _assert_valid(result, n)
        for key in PRESETS:
            assert all(p.value == 0.0 for p in result[key])
        # A zero level has no meaningful % slope
        assert result["slope_pct_per_month"] is None

    def test_negative_level_has_no_pct_slope(self):
        n = 60
        values = -100 - np.arange(n, dtype=float)
        result = smooth_presets(_series(_daily(n), values))
        _assert_valid(result, n)
        assert result["slope_pct_per_month"] is None


class TestLine:
    def test_linear_slope_pct_per_month(self):
        n = 60
        values = 100 + 1.0 * np.arange(n)
        result = smooth_presets(_series(_daily(n), values))
        # slope 1/day relative to mean level 129.5
        expected = 1.0 * DAYS_PER_MONTH / 129.5 * 100
        assert result["slope_pct_per_month"] == pytest.approx(expected, rel=1e-9)
        assert _vals(result, "line") == pytest.approx(values)

    def test_exponential_growth_is_positive_and_curved(self):
        # 3% per month compounding on monthly data
        n = 60
        dates = [_add_months(BASE, k) for k in range(n)]
        values = 100 * (1.03 ** np.arange(n))
        result = smooth_presets(_series(dates, values))
        slope = result["slope_pct_per_month"]
        # Linear slope relative to the mean level of an exponential ~ a few %
        assert 2.0 < slope < 5.0
        # Curvature is clearly better explained by the quadratic line
        line = _vals(result, "line")
        lin = np.polyval(np.polyfit(np.arange(n), values, 1), np.arange(n))
        assert np.sum((line - values) ** 2) < np.sum((lin - values) ** 2)

    def test_noisy_linear_stays_linear(self):
        rng = np.random.default_rng(1)
        n = 100
        values = 500 + 2 * np.arange(n) + rng.normal(0, 5, n)
        result = smooth_presets(_series(_daily(n), values))
        line = _vals(result, "line")
        # A straight line has constant second differences of ~0
        assert np.max(np.abs(np.diff(line, 2))) < 1e-6
