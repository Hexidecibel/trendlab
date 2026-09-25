import datetime

import pytest

from app.analysis.trend_metrics import analyze_trend
from app.models.schemas import DataPoint, StructuralBreak, TimeSeries
from tests.helpers import make_constant_series, make_linear_series


class TestAnalyzeTrend:
    def test_rising_linear_data(self):
        ts = make_linear_series(n=60, slope=2.0, intercept=100.0)
        result = analyze_trend(ts)
        assert result.direction == "rising"
        assert result.momentum > 0

    def test_falling_linear_data(self):
        ts = make_linear_series(n=60, slope=-2.0, intercept=200.0)
        result = analyze_trend(ts)
        assert result.direction == "falling"
        assert result.momentum < 0

    def test_constant_data_is_stable(self):
        ts = make_constant_series(n=60, value=100.0)
        result = analyze_trend(ts)
        assert result.direction == "stable"
        assert result.momentum == 0.0
        assert result.acceleration == 0.0

    def test_moving_average_window_3(self):
        """Verify exact MA values with a tiny known series."""
        points = [
            DataPoint(date=datetime.date(2024, 1, i + 1), value=float(v))
            for i, v in enumerate([10, 20, 30, 40, 50])
        ]
        ts = TimeSeries(source="test", query="ma", points=points)
        result = analyze_trend(ts, windows=[3])

        ma = result.moving_averages[0]
        assert ma.window == 3
        # End-aligned: MA[2]=avg(10,20,30)=20, MA[3]=30, MA[4]=40
        assert len(ma.values) == 3
        assert ma.values[0].value == pytest.approx(20.0)
        assert ma.values[1].value == pytest.approx(30.0)
        assert ma.values[2].value == pytest.approx(40.0)
        # Dates should be end-aligned
        assert ma.values[0].date == datetime.date(2024, 1, 3)
        assert ma.values[2].date == datetime.date(2024, 1, 5)

    def test_single_point_returns_stable(self):
        ts = TimeSeries(
            source="test",
            query="single",
            points=[DataPoint(date=datetime.date(2024, 1, 1), value=42.0)],
        )
        result = analyze_trend(ts)
        assert result.direction == "stable"
        assert result.momentum == 0.0
        assert result.acceleration == 0.0
        assert result.momentum_series == []
        assert all(ma.values == [] for ma in result.moving_averages)

    def test_series_shorter_than_window(self):
        ts = make_linear_series(n=5, slope=1.0)
        result = analyze_trend(ts, windows=[7, 30])
        # Window 7 needs 7 points — we only have 5, so empty
        assert result.moving_averages[0].values == []
        # Window 30 also empty
        assert result.moving_averages[1].values == []

    def test_momentum_series_length(self):
        ts = make_linear_series(n=10)
        result = analyze_trend(ts)
        # momentum_series should be len(points) - 1
        assert len(result.momentum_series) == 9


def _weekday_cycle_series(n=180, monthly_growth=0.06, seed=3) -> TimeSeries:
    """Daily data with a strong weekend dip, noise and a real uptrend."""
    import numpy as np

    rng = np.random.default_rng(seed)
    t = np.arange(n)
    daily_growth = monthly_growth / 30.4375
    base = 1000 * (1 + daily_growth * t)
    weekday = np.where(t % 7 >= 5, 0.55, 1.0)
    values = base * weekday * (1 + rng.normal(0, 0.05, n))
    start = datetime.date(2025, 1, 1)
    return TimeSeries(
        source="test",
        query="weekday",
        points=[
            DataPoint(date=start + datetime.timedelta(days=int(i)), value=float(v))
            for i, v in zip(t, values)
        ],
    )


class TestTrendFromSmoothedLine:
    def test_noisy_weekday_cycle_uptrend_is_rising(self):
        ts = _weekday_cycle_series()
        # Per-step % changes swing wildly with the weekly cycle...
        result = analyze_trend(ts, seasonal_period=7)
        # ...but the smoothed trend's recent slope says rising
        assert result.direction == "rising"
        assert result.momentum_pct_per_month > 2.0
        assert result.momentum == pytest.approx(result.momentum_pct_per_month / 100)
        assert result.momentum_label.startswith("+")
        assert result.momentum_label.endswith("% / month")

    def test_weekday_cycle_uptrend_rising_without_period(self):
        ts = _weekday_cycle_series(seed=4)
        assert analyze_trend(ts).direction == "rising"

    def test_flat_noisy_weekday_cycle_is_stable(self):
        ts = _weekday_cycle_series(monthly_growth=0.0, seed=5)
        result = analyze_trend(ts, seasonal_period=7)
        assert result.direction == "stable"
        assert result.momentum_label == "flat"

    def test_momentum_is_pct_per_month_fraction(self):
        # +1/day; the recent span is 2 medium windows = the last 60 points
        ts = make_linear_series(n=90, slope=1.0, intercept=100.0)
        result = analyze_trend(ts)
        recent_level = 100 + 1.0 * (30 + 89) / 2  # mean of the last 60 points
        expected = 30.4375 / recent_level * 100
        assert result.momentum_pct_per_month == pytest.approx(expected, rel=0.02)
        assert result.momentum == pytest.approx(expected / 100, rel=0.02)

    def test_smoothed_presets_attached(self):
        ts = make_linear_series(n=60)
        result = analyze_trend(ts)
        assert result.smoothed is not None
        assert len(result.smoothed.medium) == 60
        assert result.smoothed.slope_pct_per_month is not None

    def test_constant_label_flat(self):
        result = analyze_trend(make_constant_series(n=60))
        assert result.momentum_label == "flat"
        assert result.momentum_pct_per_month == 0.0

    def test_single_point_has_no_pct(self):
        ts = TimeSeries(
            source="t",
            query="q",
            points=[DataPoint(date=datetime.date(2024, 1, 1), value=5.0)],
        )
        result = analyze_trend(ts)
        assert result.momentum_pct_per_month is None
        assert result.momentum_label == "flat"


def _weekly_cycle(i: int) -> float:
    """Multiplicative weekday pattern: weekends ~35% lower."""
    return 0.65 if i % 7 in (5, 6) else 1.0


def _step_series(
    n_before: int, n_after: int, before: float, after: float, after_slope: float = 0.0
) -> TimeSeries:
    """Daily series with a weekly cycle and a level step at ``n_before``."""
    start = datetime.date(2026, 3, 2)  # a Monday
    points = []
    for i in range(n_before + n_after):
        if i < n_before:
            level = before
        else:
            level = after + after_slope * (i - n_before)
        points.append(
            DataPoint(
                date=start + datetime.timedelta(days=i),
                value=level * _weekly_cycle(i),
            )
        )
    return TimeSeries(source="test", query="step", points=points)


def _break_at(ts: TimeSeries, idx: int) -> StructuralBreak:
    return StructuralBreak(
        date=ts.points[idx].date, index=idx, method="cusum", confidence=0.9
    )


class TestBreakAwareMomentum:
    def test_flat_after_drop_is_not_falling(self):
        # 150 days at 60, then a 30% drop and 25 days flat at 42
        ts = _step_series(150, 25, before=60.0, after=42.0)
        naive = analyze_trend(ts, seasonal_period=7)
        assert naive.direction == "falling"  # the smooth bends through the step

        result = analyze_trend(ts, seasonal_period=7, breaks=[_break_at(ts, 150)])
        assert result.direction == "stable"
        assert result.momentum_pct_per_month is not None
        assert abs(result.momentum_pct_per_month) < 2.0
        drop_day = ts.points[150].date
        assert result.momentum_label == (
            f"flat since drop on {drop_day:%b} {drop_day.day}"
        )

    def test_break_pinned_to_actual_step(self):
        # CUSUM often reports the point before the shift
        ts = _step_series(150, 25, before=60.0, after=42.0)
        result = analyze_trend(ts, seasonal_period=7, breaks=[_break_at(ts, 149)])
        drop_day = ts.points[150].date
        assert result.momentum_label.endswith(f"{drop_day:%b} {drop_day.day}")

    def test_growth_after_jump_reports_post_break_slope(self):
        # Jump from 40 to 60, then +0.4/day (~+20%/month at level ~65)
        ts = _step_series(150, 28, before=40.0, after=60.0, after_slope=0.4)
        result = analyze_trend(ts, seasonal_period=7, breaks=[_break_at(ts, 150)])
        assert result.direction == "rising"
        assert result.momentum_label.startswith("+")
        assert "since jump on" in result.momentum_label
        assert 12.0 < result.momentum_pct_per_month < 25.0

    def test_too_few_points_since_break_keeps_trend_momentum(self):
        ts = _step_series(150, 8, before=60.0, after=42.0)
        naive = analyze_trend(ts, seasonal_period=7)
        result = analyze_trend(ts, seasonal_period=7, breaks=[_break_at(ts, 150)])
        assert result.momentum_label == naive.momentum_label
        assert result.direction == naive.direction

    def test_break_outside_recent_span_is_ignored(self):
        ts = make_linear_series(n=200, slope=1.0, intercept=100.0)
        naive = analyze_trend(ts)
        result = analyze_trend(ts, breaks=[_break_at(ts, 20)])
        assert result.momentum_label == naive.momentum_label

    def test_small_shift_uses_plain_rate_label(self):
        # 5% step: not a notable level shift, label is just the rate
        ts = _step_series(150, 30, before=60.0, after=63.0)
        result = analyze_trend(ts, seasonal_period=7, breaks=[_break_at(ts, 150)])
        assert "since" not in result.momentum_label
        assert result.direction == "stable"

    def test_weekly_cycle_does_not_tilt_post_break_slope(self):
        # Flat post-break level starting on a Saturday (weekend dip first)
        ts = _step_series(152, 26, before=60.0, after=42.0)
        result = analyze_trend(ts, seasonal_period=7, breaks=[_break_at(ts, 152)])
        assert abs(result.momentum_pct_per_month) < 1.0


class TestAccelerationLabel:
    @staticmethod
    def _series(fn, n=180):
        start = datetime.date(2024, 1, 1)
        return TimeSeries(
            source="t",
            query="q",
            points=[
                DataPoint(date=start + datetime.timedelta(days=i), value=fn(i))
                for i in range(n)
            ],
        )

    def test_steady_linear_growth_has_no_label(self):
        ts = make_linear_series(n=180, slope=0.5, intercept=100.0)
        result = analyze_trend(ts)
        assert result.acceleration_label is None

    def test_speeding_up_growth_is_accelerating(self):
        import math

        # Growth rate itself rises over time (in % of level, like the label)
        ts = self._series(lambda i: 100.0 * math.exp(0.00005 * i**2))
        result = analyze_trend(ts)
        assert result.direction == "rising"
        assert result.acceleration_label == "accelerating"
        assert result.acceleration > 0

    def test_slowing_growth(self):
        import math

        ts = self._series(lambda i: 100.0 + 400.0 * (1 - math.exp(-i / 90.0)))
        result = analyze_trend(ts)
        assert result.direction == "rising"
        assert result.acceleration_label == "growth slowing"

    def test_noise_does_not_create_a_label(self):
        """Raw second differences of noise used to report 'accelerating'."""
        import numpy as np

        rng = np.random.default_rng(3)
        noise = rng.normal(0, 5, 180)
        ts = self._series(lambda i: 1000.0 + float(noise[i]))
        result = analyze_trend(ts)
        assert result.acceleration_label is None
