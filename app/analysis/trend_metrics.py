"""Trend metrics: momentum, acceleration, and moving averages."""

import numpy as np

from app.models.schemas import DataPoint, MovingAverage, TimeSeries, TrendSignal

# Average daily percentage change threshold to distinguish stable from trending
DIRECTION_THRESHOLD = 0.01


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


def analyze_trend(ts: TimeSeries, windows: list[int] | None = None) -> TrendSignal:
    """Analyze a TimeSeries and return trend metrics."""
    if windows is None:
        windows = [7, 30]

    dates = [p.date for p in ts.points]
    values = np.array([p.value for p in ts.points], dtype=np.float64)

    if len(values) < 2:
        return TrendSignal(
            direction="stable",
            momentum=0.0,
            acceleration=0.0,
            moving_averages=[MovingAverage(window=w, values=[]) for w in windows],
            momentum_series=[],
        )

    mom = compute_momentum(values)
    accel = compute_acceleration(values)

    avg_momentum = float(np.mean(mom))
    avg_acceleration = float(np.mean(accel)) if len(accel) > 0 else 0.0

    if avg_momentum > DIRECTION_THRESHOLD:
        direction = "rising"
    elif avg_momentum < -DIRECTION_THRESHOLD:
        direction = "falling"
    else:
        direction = "stable"

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
    )
