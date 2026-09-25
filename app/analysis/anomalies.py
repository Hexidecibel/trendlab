"""Anomaly detection: residual-from-trend (default), z-score and IQR methods."""

import datetime

import numpy as np

from app.models.schemas import (
    AnomalyPoint,
    AnomalyReport,
    StructuralBreak,
    TimeSeries,
)


def detect_zscore(
    dates: list[datetime.date],
    values: np.ndarray,
    threshold: float = 2.5,
) -> AnomalyReport:
    """Flag points where |z-score| exceeds threshold."""
    std = float(np.std(values))
    if std == 0:
        return AnomalyReport(
            method="zscore",
            threshold=threshold,
            anomalies=[],
            total_points=len(values),
            anomaly_count=0,
        )

    mean = float(np.mean(values))
    z_scores = (values - mean) / std

    anomalies = []
    for i, z in enumerate(z_scores):
        if abs(z) > threshold:
            anomalies.append(
                AnomalyPoint(
                    date=dates[i],
                    value=float(values[i]),
                    score=float(abs(z)),
                    method="zscore",
                )
            )

    return AnomalyReport(
        method="zscore",
        threshold=threshold,
        anomalies=anomalies,
        total_points=len(values),
        anomaly_count=len(anomalies),
    )


def detect_iqr(
    dates: list[datetime.date],
    values: np.ndarray,
    k: float = 1.5,
) -> AnomalyReport:
    """Flag points outside [Q1 - k*IQR, Q3 + k*IQR]."""
    q1 = float(np.percentile(values, 25))
    q3 = float(np.percentile(values, 75))
    iqr = q3 - q1

    if iqr == 0:
        # All values in the IQR are identical — any value != median is anomalous
        median = float(np.median(values))
        anomalies = []
        for i, v in enumerate(values):
            if v != median:
                anomalies.append(
                    AnomalyPoint(
                        date=dates[i],
                        value=float(v),
                        score=float(abs(v - median)),
                        method="iqr",
                    )
                )
        return AnomalyReport(
            method="iqr",
            threshold=k,
            anomalies=anomalies,
            total_points=len(values),
            anomaly_count=len(anomalies),
        )

    lower = q1 - k * iqr
    upper = q3 + k * iqr

    anomalies = []
    for i, v in enumerate(values):
        if v < lower or v > upper:
            # Score = distance from nearest bound, normalized by IQR
            distance = max(lower - v, v - upper)
            score = float(distance / iqr)
            anomalies.append(
                AnomalyPoint(
                    date=dates[i],
                    value=float(v),
                    score=score,
                    method="iqr",
                )
            )

    return AnomalyReport(
        method="iqr",
        threshold=k,
        anomalies=anomalies,
        total_points=len(values),
        anomaly_count=len(anomalies),
    )


# Robust z-score threshold for residual anomalies (Iglewicz & Hoaglin)
RESIDUAL_THRESHOLD = 3.5

# 0.6745 = z-score of the 75th percentile; scales MAD to a std estimate
MAD_TO_Z = 0.6745

ANOMALY_METHODS = ("residual", "zscore", "iqr")


# Points either side of a level shift where residual anomalies are not
# reported: the days right at a step are part of the step (already reported
# as a structural break), not unusual values in their own right.
STEP_GUARD_POINTS = 2


def trend_boundaries(values: np.ndarray, break_indices: list[int]) -> list[int]:
    """Indices where the trend is allowed to jump (piecewise fit boundaries).

    Each structural break becomes a boundary. Breaks with a large level shift
    are pinned to where the step actually happens (CUSUM tends to land a
    point or two early), so the fit on either side sees only one level.
    """
    from app.analysis.level_shift import pin_step_indices

    n = len(values)
    return sorted({i for i in pin_step_indices(values, break_indices) if 0 < i < n})


def piecewise_trend(
    dates: list[datetime.date],
    values: np.ndarray,
    boundaries: list[int],
    seasonal_period: int | None = None,
) -> np.ndarray:
    """Medium-smoothed trend fitted separately between ``boundaries``.

    A single smooth line bends through a step change and lags it for about a
    window either side, so every point around the step looks "unusual".
    Fitting each segment on its own keeps the step sharp.
    """
    from app.analysis.smoothing import smooth_values

    n = len(values)
    cuts = [0, *[b for b in boundaries if 0 < b < n], n]
    trend = np.empty(n, dtype=np.float64)
    for lo, hi in zip(cuts, cuts[1:]):
        if hi <= lo:
            continue
        trend[lo:hi] = smooth_values(
            dates[lo:hi], values[lo:hi], "medium", seasonal_period
        )
    return trend


def detect_residual(
    dates: list[datetime.date],
    values: np.ndarray,
    threshold: float = RESIDUAL_THRESHOLD,
    seasonal_period: int | None = None,
    break_indices: list[int] | None = None,
) -> AnomalyReport:
    """Flag points whose deviation from the smoothed trend is extreme.

    Residuals are taken against the medium robust-LOWESS trend line plus any
    short seasonal cycle (in log space for strictly positive series), then
    scored with a robust z-score: 0.6745 * (r - median(r)) / MAD(r). Measuring
    against the trend means a steadily rising series doesn't get its recent
    tail flagged, while a genuine spike on top of the trend does.

    With ``break_indices`` (structural breaks), the trend is fitted piecewise
    between them and points within ``STEP_GUARD_POINTS`` of a break are not
    flagged, so a level shift is reported once (as a break) instead of as a
    run of "anomalies" where the smooth line lags the step.
    """
    from app.analysis.smoothing import remove_short_cycle, short_cycle_period

    n = len(values)
    if n < 3:
        return AnomalyReport(
            method="residual",
            threshold=threshold,
            anomalies=[],
            total_points=n,
            anomaly_count=0,
        )

    # Positive series (downloads, prices, views) usually grow and vary
    # multiplicatively; working in log space keeps a steep trend's tail from
    # looking anomalous just because the numbers got bigger.
    base = np.log(values) if np.all(values > 0) else values
    boundaries = trend_boundaries(values, break_indices or [])
    trend = piecewise_trend(dates, base, boundaries, seasonal_period)
    # Regular short cycles (weekend dips) are expected, not anomalous
    expected = base - remove_short_cycle(
        base, short_cycle_period(dates, seasonal_period)
    )
    residuals = base - trend - expected

    # Ignore float noise (e.g. a flat line fit to a flat series)
    tol = 1e-9 * max(1.0, float(np.median(np.abs(residuals))))
    residuals = np.where(np.abs(residuals) < tol, 0.0, residuals)

    med = float(np.median(residuals))
    dev = np.abs(residuals - med)
    mad = float(np.median(dev))
    if mad > tol:
        scores = MAD_TO_Z * dev / mad
    else:
        # More than half the residuals are identical: fall back to the mean
        # absolute deviation (scaled to a std estimate for normal data).
        meanad = float(np.mean(dev))
        if meanad <= tol:
            scores = np.zeros(n)
        else:
            scores = dev / (1.2533 * meanad)

    guarded = np.zeros(n, dtype=bool)
    for b in boundaries:
        guarded[max(0, b - STEP_GUARD_POINTS) : b + STEP_GUARD_POINTS] = True

    anomalies = [
        AnomalyPoint(
            date=dates[i],
            value=float(values[i]),
            score=float(scores[i]),
            method="residual",
        )
        for i in range(n)
        if np.isfinite(scores[i]) and scores[i] > threshold and not guarded[i]
    ]

    return AnomalyReport(
        method="residual",
        threshold=threshold,
        anomalies=anomalies,
        total_points=n,
        anomaly_count=len(anomalies),
    )


def analyze_anomalies(
    ts: TimeSeries,
    method: str = "residual",
    seasonal_period: int | None = None,
    breaks: list[StructuralBreak] | None = None,
    **kwargs: float,
) -> AnomalyReport:
    """Run anomaly detection on a TimeSeries.

    ``breaks`` (structural breaks) only affect the residual method: the trend
    is fitted piecewise between them so level shifts aren't flagged.

    ``method`` is one of ``residual`` (default: robust score of the
    deviation from the smoothed trend), ``zscore`` or ``iqr``.
    """
    if method not in ANOMALY_METHODS:
        raise ValueError(
            f"Unknown anomaly detection method: '{method}'. "
            f"Valid: {list(ANOMALY_METHODS)}"
        )
    if len(ts.points) == 0:
        return AnomalyReport(
            method=method,
            threshold=kwargs.get(
                "threshold",
                kwargs.get("k", RESIDUAL_THRESHOLD if method == "residual" else 2.5),
            ),
            anomalies=[],
            total_points=0,
            anomaly_count=0,
        )

    dates = [p.date for p in ts.points]
    values = np.array([p.value for p in ts.points], dtype=np.float64)

    if method == "residual":
        return detect_residual(
            dates,
            values,
            seasonal_period=seasonal_period,
            break_indices=[b.index for b in breaks or []],
            **kwargs,
        )
    if method == "zscore":
        return detect_zscore(dates, values, **kwargs)
    return detect_iqr(dates, values, **kwargs)
