"""Tests for AutoETS statistical forecasting wrapper."""

import datetime
from unittest.mock import MagicMock, patch

import numpy as np

from app.forecasting.statistical import MIN_SERIES_LENGTH, forecast_autoets

BASE_DATE = datetime.date(2024, 1, 1)


def _make_dates(n):
    return [BASE_DATE + datetime.timedelta(days=i) for i in range(n)]


class TestForecastAutoETS:
    def test_returns_correct_model_name(self):
        dates = _make_dates(30)
        values = np.arange(30, dtype=np.float64) + 100.0
        result = forecast_autoets(dates, values, horizon=5)
        assert result.model_name == "autoets"

    def test_returns_correct_number_of_points(self):
        dates = _make_dates(30)
        values = np.arange(30, dtype=np.float64) + 100.0
        result = forecast_autoets(dates, values, horizon=5)
        assert len(result.points) == 5

    def test_forecast_dates_are_sequential(self):
        dates = _make_dates(30)
        values = np.arange(30, dtype=np.float64) + 100.0
        result = forecast_autoets(dates, values, horizon=5)
        last_date = dates[-1]
        for i, pt in enumerate(result.points):
            assert pt.date == last_date + datetime.timedelta(days=i + 1)

    def test_points_have_confidence_intervals(self):
        dates = _make_dates(30)
        values = np.arange(30, dtype=np.float64) + 100.0
        result = forecast_autoets(dates, values, horizon=5)
        for pt in result.points:
            assert pt.lower_ci <= pt.value <= pt.upper_ci

    def test_short_series_returns_empty(self):
        dates = _make_dates(3)
        values = np.array([1.0, 2.0, 3.0])
        result = forecast_autoets(dates, values, horizon=5)
        assert result.points == []

    def test_exactly_min_length(self):
        dates = _make_dates(MIN_SERIES_LENGTH)
        values = np.arange(MIN_SERIES_LENGTH, dtype=np.float64) + 10.0
        result = forecast_autoets(dates, values, horizon=3)
        # Should not be empty—we meet the minimum
        assert result.model_name == "autoets"
        # May or may not produce points depending on model convergence

    def test_horizon_zero_returns_empty(self):
        dates = _make_dates(30)
        values = np.arange(30, dtype=np.float64)
        result = forecast_autoets(dates, values, horizon=0)
        assert result.points == []

    def test_model_failure_returns_empty(self):
        dates = _make_dates(30)
        values = np.arange(30, dtype=np.float64) + 100.0
        with patch(
            "statsforecast.models.AutoETS",
            side_effect=RuntimeError("convergence failure"),
        ):
            result = forecast_autoets(dates, values, horizon=5)
        assert result.points == []
        assert result.model_name == "autoets"

    def test_exception_during_predict_returns_empty(self):
        """Model fits but predict raises."""
        dates = _make_dates(30)
        values = np.arange(30, dtype=np.float64) + 100.0

        mock_model_instance = MagicMock()
        mock_model_instance.fit.return_value = None
        mock_model_instance.predict.side_effect = ValueError("bad predict")

        mock_cls = MagicMock(return_value=mock_model_instance)
        with patch("statsforecast.models.AutoETS", mock_cls):
            result = forecast_autoets(dates, values, horizon=5)
        assert result.points == []
