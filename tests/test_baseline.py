"""Tests for baseline forecasting models."""

import datetime

import numpy as np

from app.forecasting.baseline import (
    forecast_linear,
    forecast_moving_average,
    forecast_naive,
)
from app.models.schemas import TimeSeries
from tests.helpers import make_constant_series, make_linear_series

BASE_DATE = datetime.date(2024, 1, 1)


def _extract(ts: TimeSeries):
    dates = [p.date for p in ts.points]
    values = np.array([p.value for p in ts.points], dtype=np.float64)
    return dates, values


class TestForecastNaive:
    def test_repeats_last_value(self):
        ts = make_linear_series(n=30, slope=1.0, intercept=100.0)
        dates, values = _extract(ts)
        result = forecast_naive(dates, values, horizon=5)
        assert result.model_name == "naive"
        assert len(result.points) == 5
        expected = 100.0 + 29.0  # last value
        for pt in result.points:
            assert pt.value == expected

    def test_ci_widens_over_horizon(self):
        # Use noisy data so diff std > 0 and CIs actually widen
        from tests.helpers import make_trending_series_with_noise

        ts = make_trending_series_with_noise(n=30, slope=1.0, noise_std=5.0)
        dates, values = _extract(ts)
        result = forecast_naive(dates, values, horizon=5)
        widths = [pt.upper_ci - pt.lower_ci for pt in result.points]
        for i in range(1, len(widths)):
            assert widths[i] > widths[i - 1]

    def test_dates_are_sequential(self):
        ts = make_linear_series(n=30)
        dates, values = _extract(ts)
        result = forecast_naive(dates, values, horizon=3)
        last_date = dates[-1]
        for i, pt in enumerate(result.points):
            assert pt.date == last_date + datetime.timedelta(days=i + 1)

    def test_empty_series(self):
        result = forecast_naive([], np.array([]), horizon=5)
        assert result.points == []

    def test_single_point(self):
        dates = [BASE_DATE]
        values = np.array([42.0])
        result = forecast_naive(dates, values, horizon=3)
        assert len(result.points) == 3
        for pt in result.points:
            assert pt.value == 42.0
            # Zero CI for single point (no diff to compute std)
            assert pt.lower_ci == pt.upper_ci == 42.0

    def test_horizon_zero(self):
        ts = make_linear_series(n=10)
        dates, values = _extract(ts)
        result = forecast_naive(dates, values, horizon=0)
        assert result.points == []

    def test_constant_series_zero_ci(self):
        ts = make_constant_series(n=30, value=50.0)
        dates, values = _extract(ts)
        result = forecast_naive(dates, values, horizon=3)
        for pt in result.points:
            assert pt.value == 50.0
            # std of diff of constant series is 0
            assert pt.lower_ci == pt.upper_ci == 50.0


class TestForecastMovingAverage:
    def test_uses_trailing_window(self):
        ts = make_linear_series(n=30, slope=1.0, intercept=0.0)
        dates, values = _extract(ts)
        result = forecast_moving_average(dates, values, horizon=3, window=7)
        # MA of last 7 values: 23,24,25,26,27,28,29 → mean=26
        expected = np.mean([23.0, 24.0, 25.0, 26.0, 27.0, 28.0, 29.0])
        for pt in result.points:
            assert abs(pt.value - expected) < 1e-10

    def test_fallback_when_series_shorter_than_window(self):
        ts = make_linear_series(n=3, slope=1.0, intercept=0.0)
        dates, values = _extract(ts)
        result = forecast_moving_average(dates, values, horizon=2, window=7)
        # Falls back to mean of all 3 values: 0, 1, 2 → 1.0
        for pt in result.points:
            assert abs(pt.value - 1.0) < 1e-10

    def test_empty_series(self):
        result = forecast_moving_average([], np.array([]), horizon=5)
        assert result.points == []

    def test_horizon_zero(self):
        ts = make_linear_series(n=30)
        dates, values = _extract(ts)
        result = forecast_moving_average(dates, values, horizon=0)
        assert result.points == []

    def test_model_name(self):
        ts = make_linear_series(n=30)
        dates, values = _extract(ts)
        result = forecast_moving_average(dates, values, horizon=3)
        assert result.model_name == "moving_average"


class TestForecastLinear:
    def test_extrapolates_linear_trend(self):
        ts = make_linear_series(n=30, slope=2.0, intercept=10.0)
        dates, values = _extract(ts)
        result = forecast_linear(dates, values, horizon=5)
        assert result.model_name == "linear"
        assert len(result.points) == 5
        # Perfect linear data: forecast should continue the line
        for i, pt in enumerate(result.points):
            expected = 10.0 + 2.0 * (30 + i)
            assert abs(pt.value - expected) < 1e-6

    def test_perfect_linear_has_zero_ci(self):
        ts = make_linear_series(n=30, slope=2.0, intercept=10.0)
        dates, values = _extract(ts)
        result = forecast_linear(dates, values, horizon=3)
        # Perfect fit means residual std ≈ 0
        for pt in result.points:
            assert abs(pt.upper_ci - pt.lower_ci) < 1e-6

    def test_empty_series(self):
        result = forecast_linear([], np.array([]), horizon=5)
        assert result.points == []

    def test_single_point(self):
        dates = [BASE_DATE]
        values = np.array([42.0])
        result = forecast_linear(dates, values, horizon=3)
        assert len(result.points) == 3
        for pt in result.points:
            assert pt.value == 42.0

    def test_horizon_zero(self):
        ts = make_linear_series(n=10)
        dates, values = _extract(ts)
        result = forecast_linear(dates, values, horizon=0)
        assert result.points == []
