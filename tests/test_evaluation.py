"""Tests for forecasting evaluation metrics and backtesting."""

import datetime

import numpy as np

from app.forecasting.baseline import forecast_naive
from app.forecasting.evaluation import MIN_TRAIN_SIZE, backtest, compute_metrics
from tests.helpers import make_constant_series, make_linear_series

BASE_DATE = datetime.date(2024, 1, 1)


def _extract(ts):
    dates = [p.date for p in ts.points]
    values = np.array([p.value for p in ts.points], dtype=np.float64)
    return dates, values


class TestComputeMetrics:
    def test_perfect_prediction(self):
        actual = np.array([1.0, 2.0, 3.0])
        predicted = np.array([1.0, 2.0, 3.0])
        m = compute_metrics(actual, predicted)
        assert m["mae"] == 0.0
        assert m["rmse"] == 0.0
        assert m["mape"] == 0.0

    def test_known_errors(self):
        actual = np.array([10.0, 20.0, 30.0])
        predicted = np.array([12.0, 18.0, 33.0])
        m = compute_metrics(actual, predicted)
        # MAE = mean(|2|, |2|, |3|) = 7/3
        assert abs(m["mae"] - 7.0 / 3.0) < 1e-10
        # RMSE = sqrt(mean(4, 4, 9)) = sqrt(17/3)
        assert abs(m["rmse"] - np.sqrt(17.0 / 3.0)) < 1e-10

    def test_mape_skips_zero_actuals(self):
        actual = np.array([0.0, 10.0, 20.0])
        predicted = np.array([5.0, 12.0, 22.0])
        m = compute_metrics(actual, predicted)
        # MAPE computed only on entries 1,2: |2/10|, |2/20| → mean(0.2, 0.1)*100 = 15
        assert abs(m["mape"] - 15.0) < 1e-10

    def test_all_zeros_mape(self):
        actual = np.array([0.0, 0.0, 0.0])
        predicted = np.array([1.0, 2.0, 3.0])
        m = compute_metrics(actual, predicted)
        assert m["mape"] == 0.0


class TestBacktest:
    def test_constant_series_perfect_naive(self):
        ts = make_constant_series(n=60, value=50.0)
        dates, values = _extract(ts)
        result = backtest(dates, values, forecast_naive, "naive")
        assert result is not None
        assert result.model_name == "naive"
        assert result.mae == 0.0
        assert result.rmse == 0.0
        assert result.train_size + result.test_size == 60

    def test_default_test_size_is_20_percent(self):
        ts = make_linear_series(n=100)
        dates, values = _extract(ts)
        result = backtest(dates, values, forecast_naive, "naive")
        assert result is not None
        assert result.test_size == 20

    def test_custom_test_size(self):
        ts = make_linear_series(n=60)
        dates, values = _extract(ts)
        result = backtest(dates, values, forecast_naive, "naive", test_size=10)
        assert result is not None
        assert result.test_size == 10
        assert result.train_size == 50

    def test_returns_none_when_train_too_small(self):
        ts = make_linear_series(n=12)
        dates, values = _extract(ts)
        # test_size=5 → train_size=7 < MIN_TRAIN_SIZE
        result = backtest(dates, values, forecast_naive, "naive", test_size=5)
        assert result is None

    def test_returns_none_at_boundary(self):
        # n=MIN_TRAIN_SIZE, test_size=1 → train=MIN_TRAIN_SIZE-1 → None
        # Actually train=MIN_TRAIN_SIZE-1 < MIN_TRAIN_SIZE
        n = MIN_TRAIN_SIZE
        ts = make_linear_series(n=n)
        dates, values = _extract(ts)
        result = backtest(dates, values, forecast_naive, "naive", test_size=1)
        # train_size = MIN_TRAIN_SIZE - 1 = 9 < 10 → None
        assert result is None

    def test_succeeds_at_min_train(self):
        # n=MIN_TRAIN_SIZE+1, test_size=1 → train=MIN_TRAIN_SIZE → ok
        n = MIN_TRAIN_SIZE + 1
        ts = make_linear_series(n=n)
        dates, values = _extract(ts)
        result = backtest(dates, values, forecast_naive, "naive", test_size=1)
        assert result is not None
        assert result.train_size == MIN_TRAIN_SIZE

    def test_naive_on_linear_has_nonzero_error(self):
        ts = make_linear_series(n=60, slope=2.0)
        dates, values = _extract(ts)
        result = backtest(dates, values, forecast_naive, "naive")
        assert result is not None
        assert result.mae > 0.0
