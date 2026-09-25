"""Trend smoothing presets: robust LOWESS at time-based windows plus a fit line.

Each preset's window is defined in *time* (days), not points, so a "medium"
smooth means roughly one month whether the series is daily, weekly or monthly.
LOWESS runs on day-number x values, so gaps in the data are handled naturally,
and its robustness iterations (``it=3``) keep single spikes from dragging the
trend line.
"""

from __future__ import annotations

import datetime

import numpy as np

from app.models.schemas import DataPoint, TimeSeries

DAYS_PER_MONTH = 365.25 / 12

# Target smoothing window per preset, in days
PRESET_WINDOW_DAYS: dict[str, float] = {"light": 7.0, "medium": 30.0, "heavy": 90.0}

# Minimum window per preset, in points, so presets stay distinct on coarse
# (e.g. monthly) series where a 7-day window would be under one point.
PRESET_MIN_POINTS: dict[str, int] = {"light": 3, "medium": 5, "heavy": 9}

# Below this many points LOWESS is unreliable; use a centered rolling mean.
MIN_LOWESS_POINTS = 15

FRAC_MIN = 0.1
FRAC_MAX = 0.6

# Robustness iterations for LOWESS (down-weights outliers such as spikes)
LOWESS_ITERATIONS = 3

# Quadratic line only wins when its AIC beats linear by more than this
AIC_IMPROVEMENT = 2.0

# A seasonal period only floors the window when the cycle is short relative to
# the heaviest window (e.g. a weekly cycle in daily data). Long cycles such as
# a yearly cycle in daily weather data are signal, not noise.
MAX_SEASONAL_FLOOR_DAYS = 90.0


def day_numbers(dates: list[datetime.date]) -> np.ndarray:
    """Days since the first date, as float64."""
    if not dates:
        return np.array([], dtype=np.float64)
    first = dates[0]
    return np.array([(d - first).days for d in dates], dtype=np.float64)


def median_spacing_days(dates: list[datetime.date]) -> float:
    """Median gap between consecutive dates in days (1.0 if undefined)."""
    if len(dates) < 2:
        return 1.0
    gaps = np.diff(day_numbers(dates))
    gaps = gaps[gaps > 0]
    if len(gaps) == 0:
        return 1.0
    return float(np.median(gaps))


def window_points(
    preset: str,
    spacing_days: float,
    seasonal_period: int | None = None,
) -> float:
    """Smoothing window for a preset, in points."""
    pts = PRESET_WINDOW_DAYS[preset] / max(spacing_days, 1e-9)
    pts = max(pts, float(PRESET_MIN_POINTS[preset]))
    if (
        seasonal_period
        and seasonal_period > 1
        and seasonal_period * spacing_days <= MAX_SEASONAL_FLOOR_DAYS
    ):
        pts = max(pts, float(seasonal_period))
    return pts


def lowess_frac(points: float, n: int) -> float:
    """Convert a window in points to a LOWESS fraction, clamped to [0.1, 0.6]."""
    if n <= 0:
        return FRAC_MAX
    return float(min(FRAC_MAX, max(FRAC_MIN, points / n)))


def centered_rolling_mean(values: np.ndarray, window: int) -> np.ndarray:
    """Centered rolling mean whose window shrinks symmetrically at the edges."""
    n = len(values)
    half = max(0, int(window) // 2)
    out = np.empty(n, dtype=np.float64)
    for i in range(n):
        h = min(half, i, n - 1 - i)
        out[i] = float(np.mean(values[i - h : i + h + 1]))
    return out


# Hampel pre-filter: isolated points this many robust SDs from the local
# median are replaced by that median before LOWESS. LOWESS robustness alone
# fails for narrow windows, where a spike's neighbours are pulled up in the
# first pass and every robustness weight near it collapses to zero.
HAMPEL_HALF_WINDOW = 3
HAMPEL_THRESHOLD = 6.0


def _robust_scale(resid: np.ndarray) -> float:
    scale = 1.4826 * float(np.nanmedian(np.abs(resid)))
    if scale == 0.0:
        scale = 1.2533 * float(np.nanmean(np.abs(resid)))
    return scale


def hampel_filter(values: np.ndarray, period: int | None = None) -> np.ndarray:
    """Replace isolated extreme outliers with the local rolling median.

    With a short seasonal ``period`` (e.g. a weekly cycle in daily data), a
    point must *also* be extreme against same-phase values (i +/- k*period),
    so regular weekend dips are never mistaken for outliers.
    """
    n = len(values)
    h = HAMPEL_HALF_WINDOW
    if n < 2 * h + 1:
        return values.copy()
    from numpy.lib.stride_tricks import sliding_window_view

    padded = np.pad(values, h, mode="edge")
    windows = sliding_window_view(padded, 2 * h + 1)
    med = np.median(windows, axis=1)
    resid = values - med
    local = 1.4826 * np.median(np.abs(windows - med[:, None]), axis=1)
    glob = _robust_scale(resid)
    if glob == 0.0:
        return values.copy()
    mask = np.abs(resid) > HAMPEL_THRESHOLD * np.maximum(local, glob)

    if period and 2 <= period <= n // 3 and mask.any():
        shifted = []
        for k in (1, 2, 3):
            for sign in (-1, 1):
                off = sign * k * period
                col = np.full(n, np.nan)
                if off > 0:
                    col[:-off] = values[off:]
                else:
                    col[-off:] = values[:off]
                shifted.append(col)
        phase_med = np.nanmedian(np.vstack(shifted), axis=0)
        phase_resid = values - phase_med
        phase_scale = _robust_scale(phase_resid)
        if phase_scale > 0:
            mask &= np.abs(phase_resid) > HAMPEL_THRESHOLD * phase_scale
        else:
            mask &= phase_resid != 0

    out = values.copy()
    out[mask] = med[mask]
    return out


def remove_short_cycle(values: np.ndarray, period: int | None) -> np.ndarray:
    """Subtract a short seasonal cycle (e.g. weekday/weekend) from ``values``.

    Rough trend = centered moving average over one full cycle; the seasonal
    component is the per-phase median of the detrended values, centered to
    zero. Without this, LOWESS robustness weights treat regular weekend dips
    as outliers and the trend sits at the weekday level instead of the
    weekly average.
    """
    n = len(values)
    if not period or period < 2 or n < 3 * period:
        return values
    kernel = np.ones(period) / period
    if period % 2 == 0:  # 2 x period MA keeps an even window centered
        kernel = np.convolve(kernel, [0.5, 0.5])
    half = len(kernel) // 2
    padded = np.pad(values, half, mode="edge")
    rough = np.convolve(padded, kernel, mode="valid")[:n]
    detrended = values - rough
    phase = np.arange(n) % period
    seasonal = np.array(
        [float(np.median(detrended[phase == p])) for p in range(period)]
    )
    seasonal -= seasonal.mean()
    return values - seasonal[phase]


def short_cycle_period(
    dates: list[datetime.date], seasonal_period: int | None
) -> int | None:
    """The seasonal period if it's a short cycle worth removing, else None."""
    if not seasonal_period or seasonal_period < 2:
        return None
    if seasonal_period * median_spacing_days(dates) > MAX_SEASONAL_FLOOR_DAYS:
        return None
    return int(seasonal_period)


def _lowess(x: np.ndarray, y: np.ndarray, frac: float) -> np.ndarray:
    from statsmodels.nonparametric.smoothers_lowess import lowess

    span = float(x[-1] - x[0]) if len(x) else 0.0
    # delta speeds up long series by interpolating between nearby x values
    delta = 0.005 * span if len(x) > 500 else 0.0
    fitted = lowess(
        y,
        x,
        frac=frac,
        it=LOWESS_ITERATIONS,
        delta=delta,
        return_sorted=False,
    )
    return np.asarray(fitted, dtype=np.float64)


def smooth_values(
    dates: list[datetime.date],
    values: np.ndarray,
    preset: str,
    seasonal_period: int | None = None,
) -> np.ndarray:
    """Smooth ``values`` with the given preset. Always returns finite values."""
    n = len(values)
    if n == 0:
        return np.array([], dtype=np.float64)
    if n <= 2 or float(np.ptp(values)) == 0.0:
        return values.astype(np.float64).copy()

    spacing = median_spacing_days(dates)
    pts = window_points(preset, spacing, seasonal_period)

    fallback = centered_rolling_mean(values, int(round(min(pts, n))))
    if n < MIN_LOWESS_POINTS:
        return fallback

    x = day_numbers(dates)
    short_cycle = short_cycle_period(dates, seasonal_period)
    try:
        adjusted = remove_short_cycle(values, short_cycle)
        cleaned = hampel_filter(adjusted, short_cycle)
        fitted = _lowess(x, cleaned, lowess_frac(pts, n))
    except Exception:
        return fallback

    if fitted.shape != values.shape:
        return fallback
    bad = ~np.isfinite(fitted)
    if bad.any():
        fitted[bad] = fallback[bad]
    return fitted


def _aic(rss: float, n: int, k: int) -> float:
    return n * float(np.log(max(rss / n, 1e-300))) + 2 * k


def fit_line(
    dates: list[datetime.date], values: np.ndarray
) -> tuple[np.ndarray, float | None]:
    """Least-squares trend line (quadratic only if AIC is clearly better).

    Returns ``(fitted_values, slope_pct_per_month)``. The slope always comes
    from the *linear* fit, relative to the fitted mean level; it is ``None``
    when the level is zero/negative or the slope is undefined.
    """
    n = len(values)
    if n == 0:
        return np.array([], dtype=np.float64), None
    if n == 1:
        return values.astype(np.float64).copy(), None

    x = day_numbers(dates)
    if float(np.ptp(x)) == 0.0:
        return np.full(n, float(np.mean(values))), None
    if float(np.ptp(values)) == 0.0:
        level0 = float(values[0])
        return values.astype(np.float64).copy(), (0.0 if level0 > 0 else None)

    lin = np.polyfit(x, values, 1)
    lin_fit = np.polyval(lin, x)
    fitted = lin_fit

    if n >= 5:
        rss_lin = float(np.sum((values - lin_fit) ** 2))
        scale = float(np.sum(values**2)) or 1.0
        if rss_lin > 1e-12 * scale:
            quad = np.polyfit(x, values, 2)
            quad_fit = np.polyval(quad, x)
            rss_quad = float(np.sum((values - quad_fit) ** 2))
            if _aic(rss_quad, n, 3) < _aic(rss_lin, n, 2) - AIC_IMPROVEMENT:
                fitted = quad_fit

    level = float(np.mean(lin_fit))
    slope_pct: float | None = None
    if np.isfinite(level) and level > 0:
        slope_pct = float(lin[0]) * DAYS_PER_MONTH / level * 100.0
        if not np.isfinite(slope_pct):
            slope_pct = None

    fitted = np.where(np.isfinite(fitted), fitted, float(np.mean(values)))
    return fitted, slope_pct


def smooth_presets(ts: TimeSeries, seasonal_period: int | None = None) -> dict:
    """Compute all smoothing presets for a series.

    Returns ``{"light", "medium", "heavy", "line": list[DataPoint],
    "slope_pct_per_month": float | None}``.
    """
    dates = [p.date for p in ts.points]
    values = np.array([p.value for p in ts.points], dtype=np.float64)

    def to_points(arr: np.ndarray) -> list[DataPoint]:
        return [DataPoint(date=d, value=float(v)) for d, v in zip(dates, arr)]

    result: dict = {}
    for preset in PRESET_WINDOW_DAYS:
        smoothed = smooth_values(dates, values, preset, seasonal_period)
        result[preset] = to_points(smoothed)

    line, slope = fit_line(dates, values)
    result["line"] = to_points(line)
    result["slope_pct_per_month"] = slope
    return result
