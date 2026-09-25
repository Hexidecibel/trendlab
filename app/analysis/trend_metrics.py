"""Trend metrics: direction and momentum from the smoothed trend, plus MAs."""

import datetime

import numpy as np

from app.analysis.smoothing import (
    DAYS_PER_MONTH,
    day_numbers,
    median_spacing_days,
    smooth_presets,
    window_points,
)
from app.models.schemas import (
    DataPoint,
    MovingAverage,
    SmoothedSeries,
    TimeSeries,
    TrendSignal,
)

# Average per-step percentage change threshold used for regime labels
DIRECTION_THRESHOLD = 0.01

# |slope| of the medium-smoothed trend (in % per month) below which a series
# is "stable"
STABLE_PCT_PER_MONTH = 2.0

# Momentum is measured over the most recent share of the series, but never
# less than two medium-smoothing windows: the smooth's final ~window is fit
# one-sidedly and too noisy on its own to call a direction.
RECENT_SPAN_FRACTION = 0.25
RECENT_SPAN_MIN_WINDOWS = 2
MIN_RECENT_POINTS = 3


def compute_momentum(values: np.ndarray) -> np.ndarray:
    """Percentage change per step: (v[i+1] - v[i]) / v[i]."""
    with np.errstate(divide="ignore", invalid="ignore"):
        mom = np.diff(values) / values[:-1]
    # Replace NaN/inf (from division by zero) with 0
    mom = np.where(np.isfinite(mom), mom, 0.0)
    return mom


def compute_acceleration(values: np.ndarray) -> np.ndarray:
    """Second differences of the raw values."""
    return np.diff(values, n=2)


def compute_moving_average(
    dates: list, values: np.ndarray, window: int
) -> list[DataPoint]:
    """Trailing (end-aligned) moving average."""
    if len(values) < window:
        return []
    kernel = np.ones(window) / window
    ma = np.convolve(values, kernel, mode="valid")
    # End-aligned: MA[i] uses values[i-window+1 : i+1]
    # The first MA value corresponds to date[window-1]
    return [
        DataPoint(date=dates[window - 1 + i], value=float(ma[i]))
        for i in range(len(ma))
    ]


def slope_pct_per_month(
    dates: list[datetime.date],
    values: np.ndarray,
    scale_values: np.ndarray | None = None,
) -> float | None:
    """Least-squares slope of ``values`` over time, in % of level per month.

    The level is the mean of ``values``; when that is zero/negative the mean
    absolute value of ``scale_values`` (default ``values``) is used instead,
    so the sign stays meaningful. Returns None if no scale is available.
    """
    if len(values) < 2:
        return None
    x = day_numbers(dates)
    if float(np.ptp(x)) == 0.0:
        return None
    if float(np.ptp(values)) == 0.0:
        return 0.0
    slope = float(np.polyfit(x, values, 1)[0])
    level = float(np.mean(values))
    if not np.isfinite(level) or level <= 0:
        ref = values if scale_values is None else scale_values
        level = float(np.mean(np.abs(ref)))
    if not np.isfinite(level) or level == 0:
        return None if slope != 0 else 0.0
    pct = slope * DAYS_PER_MONTH / level * 100.0
    return pct if np.isfinite(pct) else None


def recent_slope_pct(
    dates: list[datetime.date],
    smoothed: np.ndarray,
    scale_values: np.ndarray | None = None,
    seasonal_period: int | None = None,
) -> float | None:
    """Slope (% / month) of the recent part of a medium-smoothed line.

    The span is the last ~25% of points, at least two medium windows and at
    least 3 points (capped at the whole series).
    """
    n = len(smoothed)
    if n < 2:
        return None
    window = window_points("medium", median_spacing_days(dates), seasonal_period)
    k = max(
        MIN_RECENT_POINTS,
        int(np.ceil(n * RECENT_SPAN_FRACTION)),
        int(np.ceil(RECENT_SPAN_MIN_WINDOWS * window)),
    )
    k = min(k, n)
    return slope_pct_per_month(dates[-k:], smoothed[-k:], scale_values)


def format_momentum_label(pct: float | None) -> str:
    """Human-readable momentum, e.g. "+3.2% / month" or "flat"."""
    if pct is None or abs(pct) < STABLE_PCT_PER_MONTH:
        return "flat"
    if abs(pct) >= 100:
        return f"{pct:+.0f}% / month"
    return f"{pct:+.1f}% / month"


def classify_direction(pct: float | None) -> str:
    if pct is None:
        return "stable"
    if pct >= STABLE_PCT_PER_MONTH:
        return "rising"
    if pct <= -STABLE_PCT_PER_MONTH:
        return "falling"
    return "stable"


def analyze_trend(
    ts: TimeSeries,
    windows: list[int] | None = None,
    seasonal_period: int | None = None,
) -> TrendSignal:
    """Analyze a TimeSeries and return trend metrics.

    Direction and momentum come from the recent slope of the medium-smoothed
    trend line (robust LOWESS, ~1 month window), expressed in % per month.
    """
    if windows is None:
        windows = [7, 30]

    dates = [p.date for p in ts.points]
    values = np.array([p.value for p in ts.points], dtype=np.float64)

    presets = smooth_presets(ts, seasonal_period=seasonal_period)
    smoothed = SmoothedSeries(**presets)

    if len(values) < 2:
        return TrendSignal(
            direction="stable",
            momentum=0.0,
            acceleration=0.0,
            moving_averages=[MovingAverage(window=w, values=[]) for w in windows],
            momentum_series=[],
            smoothed=smoothed,
            momentum_label="flat",
            momentum_pct_per_month=None,
        )

    mom = compute_momentum(values)
    accel = compute_acceleration(values)
    avg_acceleration = float(np.mean(accel)) if len(accel) > 0 else 0.0

    medium = np.array([p.value for p in smoothed.medium], dtype=np.float64)
    pct = recent_slope_pct(
        dates, medium, scale_values=values, seasonal_period=seasonal_period
    )
    direction = classify_direction(pct)
    avg_momentum = (pct / 100.0) if pct is not None else 0.0

    momentum_series = [
        DataPoint(date=dates[i + 1], value=float(mom[i])) for i in range(len(mom))
    ]

    moving_averages = [
        MovingAverage(
            window=w,
            values=compute_moving_average(dates, values, w),
        )
        for w in windows
    ]

    return TrendSignal(
        direction=direction,
        momentum=avg_momentum,
        acceleration=avg_acceleration,
        moving_averages=moving_averages,
        momentum_series=momentum_series,
        smoothed=smoothed,
        momentum_label=format_momentum_label(pct),
        momentum_pct_per_month=pct,
    )
