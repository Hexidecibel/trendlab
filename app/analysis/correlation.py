import datetime
import math

import numpy as np
from scipy.stats import pearsonr, spearmanr

from app.models.schemas import (
    CorrelateResponse,
    CorrelationCoefficient,
    LagCorrelation,
    ScatterPoint,
    TimeSeries,
)


def align_series(
    ts_a: TimeSeries, ts_b: TimeSeries
) -> tuple[list[float], list[float], list[datetime.date]]:
    """Inner-join two series by date, returning aligned values."""
    b_map = {p.date: p.value for p in ts_b.points}

    a_vals: list[float] = []
    b_vals: list[float] = []
    dates: list[datetime.date] = []

    for p in ts_a.points:
        if p.date in b_map:
            a_vals.append(p.value)
            b_vals.append(b_map[p.date])
            dates.append(p.date)

    return a_vals, b_vals, dates


def _safe_corr(fn, a: np.ndarray, b: np.ndarray) -> CorrelationCoefficient:
    """Compute correlation, handling NaN/constant cases."""
    try:
        r, p = fn(a, b)
    except Exception:
        r, p = 0.0, 1.0

    if math.isnan(r):
        r = 0.0
    if math.isnan(p):
        p = 1.0

    return CorrelationCoefficient(r=float(r), p_value=float(p))


def _lag_analysis(a: np.ndarray, b: np.ndarray, max_lag: int) -> list[LagCorrelation]:
    """Cross-correlation at different lag offsets."""
    results: list[LagCorrelation] = []
    n = len(a)

    for lag in range(-max_lag, max_lag + 1):
        if lag >= 0:
            a_slice = a[: n - lag] if lag > 0 else a
            b_slice = b[lag:] if lag > 0 else b
        else:
            a_slice = a[-lag:]
            b_slice = b[: n + lag]

        if len(a_slice) < 3:
            continue

        coeff = _safe_corr(pearsonr, a_slice, b_slice)
        results.append(LagCorrelation(lag=lag, correlation=coeff.r))

    return results


def correlate(
    ts_a: TimeSeries,
    ts_b: TimeSeries,
    max_lag: int = 14,
) -> CorrelateResponse:
    """Compute correlation statistics between two time series."""
    a_vals, b_vals, dates = align_series(ts_a, ts_b)

    if len(a_vals) < 3:
        raise ValueError(f"Need at least 3 aligned points, got {len(a_vals)}")

    a = np.array(a_vals)
    b = np.array(b_vals)

    pearson_coeff = _safe_corr(pearsonr, a, b)
    spearman_coeff = _safe_corr(spearmanr, a, b)

    lag_results = _lag_analysis(a, b, max_lag)

    scatter = [ScatterPoint(x=av, y=bv) for av, bv in zip(a_vals, b_vals)]

    return CorrelateResponse(
        series_a_label=f"{ts_a.source}:{ts_a.query}",
        series_b_label=f"{ts_b.source}:{ts_b.query}",
        aligned_points=len(a_vals),
        pearson=pearson_coeff,
        spearman=spearman_coeff,
        lag_analysis=lag_results,
        scatter=scatter,
    )
