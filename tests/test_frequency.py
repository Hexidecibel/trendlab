"""Frequency-aware forecasting: step inference, forecast dates, horizon cap."""

import datetime

import numpy as np

from app.forecasting.baseline import forecast_linear, forecast_naive
from app.forecasting.engine import forecast
from app.forecasting.frequency import Step, cap_horizon, future_dates, infer_step
from app.forecasting.statistical import effective_season_length, forecast_autoets
from app.models.schemas import DataPoint, TimeSeries

BASE = datetime.date(2023, 1, 1)


def _months(n, start=BASE):
    out = []
    for k in range(n):
        total = start.month - 1 + k
        out.append(datetime.date(start.year + total // 12, total % 12 + 1, 1))
    return out


def _monthly_ts(n=36) -> TimeSeries:
    dates = _months(n)
    values = 100 + 3 * np.arange(n) + 10 * np.sin(np.arange(n) / 2)
    return TimeSeries(
        source="test",
        query="monthly",
        points=[DataPoint(date=d, value=float(v)) for d, v in zip(dates, values)],
    )


class TestInferStep:
    def test_daily(self):
        dates = [BASE + datetime.timedelta(days=i) for i in range(10)]
        assert infer_step(dates) == Step(days=1)

    def test_weekly(self):
        dates = [BASE + datetime.timedelta(weeks=i) for i in range(10)]
        assert infer_step(dates) == Step(days=7)

    def test_monthly(self):
        assert infer_step(_months(12)) == Step(months=1)

    def test_quarterly_and_yearly(self):
        assert infer_step(_months(12)[::3]) == Step(months=3)
        years = [datetime.date(2000 + i, 1, 1) for i in range(6)]
        assert infer_step(years) == Step(months=12)

    def test_trading_days_are_daily(self):
        dates = [
            BASE + datetime.timedelta(days=i)
            for i in range(60)
            if (BASE + datetime.timedelta(days=i)).weekday() < 5
        ]
        assert infer_step(dates) == Step(days=1)

    def test_single_date(self):
        assert infer_step([BASE]) == Step(days=1)


class TestFutureDates:
    def test_month_steps_use_calendar(self):
        dates = [datetime.date(2024, 1, 31), datetime.date(2024, 2, 29)]
        out = future_dates(
            [datetime.date(2023, 12, 31), datetime.date(2024, 1, 31)], 3
        )
        assert out == [
            datetime.date(2024, 2, 29),
            datetime.date(2024, 3, 31),
            datetime.date(2024, 4, 30),
        ]
        assert future_dates(dates, 0) == []

    def test_weekly_steps(self):
        dates = [BASE + datetime.timedelta(weeks=i) for i in range(5)]
        out = future_dates(dates, 2)
        assert out == [dates[-1] + datetime.timedelta(weeks=k) for k in (1, 2)]


class TestHorizonCap:
    def test_cap(self):
        assert cap_horizon(14, 60) == 14
        assert cap_horizon(24, 36) == 18
        assert cap_horizon(14, 1) == 1
        assert cap_horizon(5, 5) == 2


class TestForecastDatesOnMonthlyData:
    def test_baselines_step_monthly(self):
        dates = _months(24)
        values = np.arange(24, dtype=float) + 50
        for fn in (forecast_naive, forecast_linear):
            pts = fn(dates, values, 3).points
            assert [p.date for p in pts] == [
                datetime.date(2025, 1, 1),
                datetime.date(2025, 2, 1),
                datetime.date(2025, 3, 1),
            ]

    def test_autoets_steps_monthly(self):
        dates = _months(24)
        values = np.arange(24, dtype=float) + 50
        pts = forecast_autoets(dates, values, 2).points
        assert [p.date for p in pts] == [
            datetime.date(2025, 1, 1),
            datetime.date(2025, 2, 1),
        ]

    def test_engine_forecast_dates_step_monthly(self):
        ts = _monthly_ts(36)
        result = forecast(ts, horizon=6)
        assert result.horizon == 6
        for f in result.forecasts:
            assert [p.date for p in f.points] == _months(42)[36:], f.model_name

    def test_engine_caps_horizon_by_length(self):
        ts = _monthly_ts(20)
        result = forecast(ts, horizon=100)
        assert result.horizon == 10
        for f in result.forecasts:
            assert len(f.points) == 10


class TestSeasonLength:
    def test_needs_two_seasons(self):
        assert effective_season_length(12, 20) == 1
        assert effective_season_length(12, 24) == 12
        assert effective_season_length(7, 60) == 7

    def test_missing_or_too_long(self):
        assert effective_season_length(None, 100) == 1
        assert effective_season_length(1, 100) == 1
        assert effective_season_length(365, 2000) == 1

    def test_engine_passes_detected_period_to_autoets(self, monkeypatch):
        import app.forecasting.engine as eng

        seen = {}
        real = eng.forecast_autoets

        def spy(dates, values, horizon, season_length=None):
            seen["season_length"] = season_length
            return real(dates, values, horizon, season_length=season_length)

        monkeypatch.setattr(eng, "forecast_autoets", spy)
        n = 84
        dates = [BASE + datetime.timedelta(days=i) for i in range(n)]
        values = 100 + 20 * np.sin(2 * np.pi * np.arange(n) / 7)
        ts = TimeSeries(
            source="t",
            query="q",
            points=[DataPoint(date=d, value=float(v)) for d, v in zip(dates, values)],
        )
        forecast(ts, horizon=7)
        assert seen["season_length"] == 7
