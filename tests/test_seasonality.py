import numpy as np

from app.analysis.seasonality import analyze_seasonality, compute_autocorrelation
from tests.helpers import make_constant_series, make_seasonal_series


class TestComputeAutocorrelation:
    def test_lag_zero_is_one(self):
        values = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
        acf = compute_autocorrelation(values)
        assert abs(acf[0] - 1.0) < 1e-10


class TestAnalyzeSeasonality:
    def test_detects_weekly_pattern(self):
        ts = make_seasonal_series(n=90, period=7, amplitude=10.0)
        result = analyze_seasonality(ts)
        assert result.detected is True
        assert result.period_days == 7
        assert result.strength is not None
        assert result.strength > 0.3

    def test_detects_monthly_pattern(self):
        ts = make_seasonal_series(n=180, period=30, amplitude=10.0)
        result = analyze_seasonality(ts)
        assert result.detected is True
        assert result.period_days == 30

    def test_constant_data_no_seasonality(self):
        ts = make_constant_series(n=60, value=100.0)
        result = analyze_seasonality(ts)
        assert result.detected is False

    def test_short_series_returns_not_detected(self):
        ts = make_constant_series(n=10)
        result = analyze_seasonality(ts)
        assert result.detected is False
        assert result.period_days is None
        assert result.strength is None

    def test_autocorrelation_list_populated(self):
        ts = make_seasonal_series(n=90, period=7)
        result = analyze_seasonality(ts)
        assert len(result.autocorrelation) > 0
