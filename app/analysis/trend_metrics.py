"""Trend metrics: direction and momentum from the smoothed trend, plus MAs."""

import datetime

import numpy as np

from app.analysis.level_shift import (
    JUMP_MIN_PCT,
    format_short_date,
    jump_pct,
    largest_step_near,
)
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
    StructuralBreak,
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

# Break-aware momentum: when a structural break falls inside the recent span,
# the slope is measured from the break onward only if at least this many
# points (and at least two short seasonal cycles) have been seen since.
MIN_POST_BREAK_POINTS = 10
# Seasonal cycles longer than this (in days) are not used to trim/extend the
# post-break span -- a yearly cycle is trend, not noise.
MAX_CYCLE_TRIM_DAYS = 31.0


def compute_momentum(values: np.ndarray) -> np.ndarray:
    """Percentage change per step: (v[i+1] - v[i]) / v[i]."""
    with np.errstate(divide="ignore", invalid="ignore"):
        mom = np.diff(values) / values[:-1]
    # Replace NaN/inf (from division by zero) with 0
    mom = np.where(np.isfinite(mom), mom, 0.0)
    return mom


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


def recent_span_points(
    dates: list[datetime.date],
    n: int,
    seasonal_period: int | None = None,
) -> int:
    """Points in the "recent" span used for momentum.

    The last ~25% of points, at least two medium windows and at least 3
    points (capped at the whole series).
    """
    window = window_points("medium", median_spacing_days(dates), seasonal_period)
    k = max(
        MIN_RECENT_POINTS,
        int(np.ceil(n * RECENT_SPAN_FRACTION)),
        int(np.ceil(RECENT_SPAN_MIN_WINDOWS * window)),
    )
    return min(k, n)


def recent_slope_pct(
    dates: list[datetime.date],
    smoothed: np.ndarray,
    scale_values: np.ndarray | None = None,
    seasonal_period: int | None = None,
) -> float | None:
    """Slope (% / month) of the recent part of a medium-smoothed line."""
    n = len(smoothed)
    if n < 2:
        return None
    k = recent_span_points(dates, n, seasonal_period)
    return slope_pct_per_month(dates[-k:], smoothed[-k:], scale_values)


def _short_cycle(dates: list[datetime.date], seasonal_period: int | None) -> int | None:
    """The seasonal period in points if it is a short (<= ~month) cycle."""
    if not seasonal_period or seasonal_period <= 1:
        return None
    if seasonal_period * median_spacing_days(dates) > MAX_CYCLE_TRIM_DAYS:
        return None
    return seasonal_period


def cycle_adjusted_slope_pct(
    dates: list[datetime.date],
    values: np.ndarray,
    cycle: int | None,
) -> float | None:
    """Linear slope in % of level per month, with a short cycle factored out.

    A plain least-squares fit over a few weeks of daily data is tilted by the
    weekly pattern (weekend dips near one end pull the line), even over whole
    weeks. Fitting ``value ~ a + b*t + phase dummies`` removes that bias.
    Falls back to the plain fit without a cycle or with too few points.
    """
    n = len(values)
    if not cycle or n < 2 * cycle:
        return slope_pct_per_month(dates, values)
    x = day_numbers(dates)
    if float(np.ptp(x)) == 0.0:
        return None
    level = float(np.mean(values))
    if not np.isfinite(level) or level <= 0:
        return slope_pct_per_month(dates, values)
    phase = np.arange(n) % cycle
    design = np.column_stack(
        [x] + [(phase == j).astype(np.float64) for j in range(cycle)]
    )
    coef, *_ = np.linalg.lstsq(design, values, rcond=None)
    pct = float(coef[0]) * DAYS_PER_MONTH / level * 100.0
    return pct if np.isfinite(pct) else None


def post_break_momentum(
    dates: list[datetime.date],
    values: np.ndarray,
    breaks: list[StructuralBreak],
    seasonal_period: int | None = None,
) -> tuple[float | None, str] | None:
    """Momentum measured from the latest break inside the recent span.

    A medium-smoothed line bends through a step change for about a window
    after it, so after e.g. a sudden drop the "recent slope" reports a steep
    decline even once the series has been flat at its new level for weeks.
    When the most recent structural break lies inside the momentum span and
    enough points have been seen since, the slope is instead a least-squares
    fit of the raw values since the break, with a short seasonal cycle
    (e.g. weekly) factored out so it doesn't tilt the line.

    Returns ``(pct_per_month, label)`` or None when the regular trend-based
    momentum should be used. A large level shift across the break (>= 20%)
    is named in the label, e.g. "flat since drop on Aug 25", because it is
    the real story when the post-break regime itself is flat.
    """
    n = len(values)
    if n < MIN_POST_BREAK_POINTS or not breaks:
        return None
    span_start = n - recent_span_points(dates, n, seasonal_period)
    indices = sorted({b.index for b in breaks if 0 < b.index < n})
    in_span = [i for i in indices if i > span_start]
    if not in_span:
        return None
    idx = in_span[-1]
    earlier = [i for i in indices if i < idx]
    prev_idx = earlier[-1] if earlier else 0

    jump = jump_pct(values, idx, idx - prev_idx, n - idx)
    big_jump = jump is not None and abs(jump) >= JUMP_MIN_PCT
    if big_jump:
        idx = largest_step_near(values, idx, rising=jump > 0)

    cycle = _short_cycle(dates, seasonal_period)
    need = max(MIN_POST_BREAK_POINTS, 2 * cycle if cycle else 0)
    if n - idx < need:
        return None

    pct = cycle_adjusted_slope_pct(dates[idx:], values[idx:], cycle)
    rate = format_momentum_label(pct)
    if not big_jump:
        return pct, rate
    what = "drop" if jump < 0 else "jump"
    return pct, f"{rate} since {what} on {format_short_date(dates[idx])}"


def trend_acceleration(
    dates: list[datetime.date],
    smoothed: np.ndarray,
    scale_values: np.ndarray | None = None,
    seasonal_period: int | None = None,
) -> tuple[float, str | None]:
    """Change in the medium-smoothed line's slope: recent span vs the one before.

    Returns ``(recent - prior in % per month, label)``. The label is None
    unless the change is meaningful: at least ``STABLE_PCT_PER_MONTH`` and at
    least a quarter of the larger slope, with the recent trend not flat.
    """
    n = len(smoothed)
    k = recent_span_points(dates, n, seasonal_period) if n >= 2 else n
    if n < 2 * k or k < 2:
        return 0.0, None
    recent = slope_pct_per_month(dates[-k:], smoothed[-k:], scale_values)
    prior = slope_pct_per_month(
        dates[-2 * k : -k], smoothed[-2 * k : -k], scale_values
    )
    if recent is None or prior is None:
        return 0.0, None
    diff = recent - prior
    if abs(diff) < STABLE_PCT_PER_MONTH or abs(diff) < 0.25 * max(
        abs(recent), abs(prior)
    ):
        return diff, None
    kind = classify_direction(recent)
    if kind == "rising":
        return diff, "accelerating" if diff > 0 else "growth slowing"
    if kind == "falling":
        return diff, "decline speeding up" if diff < 0 else "decline easing"
    return diff, None


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
    breaks: list[StructuralBreak] | None = None,
) -> TrendSignal:
    """Analyze a TimeSeries and return trend metrics.

    Direction and momentum come from the recent slope of the medium-smoothed
    trend line (robust LOWESS, ~1 month window), expressed in % per month.
    If ``breaks`` are given and one falls inside that recent span, momentum
    is measured from the break onward instead (see ``post_break_momentum``).
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

    medium = np.array([p.value for p in smoothed.medium], dtype=np.float64)
    pct = recent_slope_pct(
        dates, medium, scale_values=values, seasonal_period=seasonal_period
    )
    label = format_momentum_label(pct)
    post = post_break_momentum(dates, values, breaks or [], seasonal_period)
    if post is not None:
        # Momentum comes from after a recent break; the smoothed line bends
        # through that step, so its slope change says nothing about pace.
        pct, label = post
        accel, accel_label = 0.0, None
    else:
        accel, accel_label = trend_acceleration(
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
        acceleration=accel,
        acceleration_label=accel_label,
        moving_averages=moving_averages,
        momentum_series=momentum_series,
        smoothed=smoothed,
        momentum_label=label,
        momentum_pct_per_month=pct,
    )
