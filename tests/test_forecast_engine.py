"""Integration tests for the forecast engine orchestrator."""

import pytest

from app.forecasting.engine import forecast
from app.models.schemas import (
    ForecastComparison,
    ModelEvaluation,
    ModelForecast,
    TimeSeries,
)
from tests.helpers import make_constant_series, make_linear_series


class TestForecastEngine:
    def test_returns_forecast_comparison(self):
        ts = make_linear_series(n=60, slope=1.0)
        result = forecast(ts, horizon=7)
        assert isinstance(result, ForecastComparison)

    def test_source_and_query_propagated(self):
        ts = make_linear_series(n=60)
        result = forecast(ts, horizon=7)
        assert result.source == "test"
        assert result.query == "linear"
        assert result.series_length == 60
        assert result.horizon == 7

    def test_contains_multiple_forecasts(self):
        ts = make_linear_series(n=60)
        result = forecast(ts, horizon=7)
        assert len(result.forecasts) >= 3  # at least the 3 baselines
        for f in result.forecasts:
            assert isinstance(f, ModelForecast)
            assert len(f.points) == 7

    def test_contains_evaluations(self):
        ts = make_linear_series(n=60)
        result = forecast(ts, horizon=7)
        assert len(result.evaluations) >= 1
        for e in result.evaluations:
            assert isinstance(e, ModelEvaluation)
            assert e.mae >= 0
            assert e.rmse >= 0

    def test_recommended_model_is_valid(self):
        ts = make_linear_series(n=60)
        result = forecast(ts, horizon=7)
        model_names = {f.model_name for f in result.forecasts}
        assert result.recommended_model in model_names

    def test_linear_has_low_mae_on_linear_data(self):
        ts = make_linear_series(n=60, slope=2.0, intercept=100.0)
        result = forecast(ts, horizon=7)
        # Linear model should have near-zero MAE on perfect linear data
        linear_evals = [e for e in result.evaluations if e.model_name == "linear"]
        assert len(linear_evals) == 1
        assert linear_evals[0].mae < 1.0

    def test_empty_series_raises(self):
        ts = TimeSeries(source="test", query="empty", points=[])
        with pytest.raises(ValueError, match="empty"):
            forecast(ts)

    def test_short_series_still_works(self):
        # 5 points: too short for backtest (MIN_TRAIN_SIZE=10)
        # but baselines should still produce forecasts
        ts = make_linear_series(n=5)
        result = forecast(ts, horizon=3)
        assert isinstance(result, ForecastComparison)
        assert len(result.forecasts) >= 1

    def test_constant_series(self):
        ts = make_constant_series(n=60, value=100.0)
        result = forecast(ts, horizon=5)
        # All baseline models should produce forecasts
        assert len(result.forecasts) >= 3

    def test_default_horizon(self):
        ts = make_linear_series(n=60)
        result = forecast(ts)
        assert result.horizon == 14
        for f in result.forecasts:
            assert len(f.points) == 14

    def test_evaluation_model_names_match_forecasts(self):
        ts = make_linear_series(n=60)
        result = forecast(ts, horizon=7)
        eval_names = {e.model_name for e in result.evaluations}
        forecast_names = {f.model_name for f in result.forecasts}
        # Every evaluated model should also have a forecast
        assert eval_names.issubset(forecast_names)
