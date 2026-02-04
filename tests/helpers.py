"""Synthetic data factories for analysis tests.

Each generator produces deterministic TimeSeries with mathematically
known properties so test assertions can be exact, not probabilistic.
"""

import datetime
import math

from app.models.schemas import DataPoint, TimeSeries

BASE_DATE = datetime.date(2024, 1, 1)


def make_linear_series(
    n: int = 60,
    slope: float = 1.0,
    intercept: float = 100.0,
    start_date: datetime.date = BASE_DATE,
) -> TimeSeries:
    """Create a series with linearly increasing/decreasing values."""
    points = [
        DataPoint(
            date=start_date + datetime.timedelta(days=i),
            value=intercept + slope * i,
        )
        for i in range(n)
    ]
    return TimeSeries(source="test", query="linear", points=points)


def make_constant_series(
    n: int = 60,
    value: float = 100.0,
    start_date: datetime.date = BASE_DATE,
) -> TimeSeries:
    """Create a flat series where every point has the same value."""
    points = [
        DataPoint(
            date=start_date + datetime.timedelta(days=i),
            value=value,
        )
        for i in range(n)
    ]
    return TimeSeries(source="test", query="constant", points=points)


def make_seasonal_series(
    n: int = 90,
    period: int = 7,
    amplitude: float = 10.0,
    baseline: float = 100.0,
    start_date: datetime.date = BASE_DATE,
) -> TimeSeries:
    """Create a sine wave series with a known period."""
    points = [
        DataPoint(
            date=start_date + datetime.timedelta(days=i),
            value=baseline + amplitude * math.sin(2 * math.pi * i / period),
        )
        for i in range(n)
    ]
    return TimeSeries(source="test", query="seasonal", points=points)


def make_step_series(
    n: int = 100,
    break_at: int = 50,
    val_before: float = 10.0,
    val_after: float = 50.0,
    start_date: datetime.date = BASE_DATE,
) -> TimeSeries:
    """Create a step function with a known break point."""
    points = [
        DataPoint(
            date=start_date + datetime.timedelta(days=i),
            value=val_before if i < break_at else val_after,
        )
        for i in range(n)
    ]
    return TimeSeries(source="test", query="step", points=points)


def make_trending_series_with_noise(
    n: int = 60,
    slope: float = 1.0,
    intercept: float = 100.0,
    noise_std: float = 5.0,
    seed: int = 42,
    start_date: datetime.date = BASE_DATE,
) -> TimeSeries:
    """Create a linear trend with Gaussian noise for forecast testing."""
    rng = __import__("numpy").random.default_rng(seed)
    noise = rng.normal(0, noise_std, n)
    points = [
        DataPoint(
            date=start_date + datetime.timedelta(days=i),
            value=intercept + slope * i + noise[i],
        )
        for i in range(n)
    ]
    return TimeSeries(source="test", query="noisy_trend", points=points)


def make_series_with_outliers(
    n: int = 60,
    base_value: float = 100.0,
    outlier_indices: list[int] | None = None,
    outlier_value: float = 500.0,
    start_date: datetime.date = BASE_DATE,
) -> TimeSeries:
    """Create a flat series with spikes at known positions."""
    if outlier_indices is None:
        outlier_indices = [25]
    points = [
        DataPoint(
            date=start_date + datetime.timedelta(days=i),
            value=outlier_value if i in outlier_indices else base_value,
        )
        for i in range(n)
    ]
    return TimeSeries(source="test", query="outliers", points=points)
