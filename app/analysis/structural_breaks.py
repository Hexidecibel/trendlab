"""Structural break detection using CUSUM and rolling variance."""

import datetime

import numpy as np

from app.models.schemas import StructuralBreak, TimeSeries

MIN_POINTS_CUSUM = 10


def detect_cusum(
    dates: list[datetime.date],
    values: np.ndarray,
    threshold: float = 1.0,
) -> list[StructuralBreak]:
    """Detect regime changes via cumulative sum of deviations from the mean.

    The CUSUM tracks how far the cumulative deviation wanders from zero.
    A break is signaled where |CUSUM| exceeds threshold * std * sqrt(n).
    """
    n = len(values)
    if n < MIN_POINTS_CUSUM:
        return []

    std = float(np.std(values))
    if std == 0:
        return []

    mean = float(np.mean(values))
    cusum = np.cumsum(values - mean)

    # Normalize for scale-independent thresholding
    critical = threshold * std * np.sqrt(n)
    abs_cusum = np.abs(cusum)
    max_cusum = float(np.max(abs_cusum))

    if max_cusum <= critical:
        return []

    # Find indices exceeding the threshold
    exceeding = np.where(abs_cusum > critical)[0]

    # Cluster nearby break points (within 5 indices) — take peak per cluster
    breaks = _cluster_peaks(exceeding, abs_cusum, dates, max_cusum, gap=5)
    return breaks


def _cluster_peaks(
    indices: np.ndarray,
    scores: np.ndarray,
    dates: list[datetime.date],
    max_score: float,
    gap: int = 5,
) -> list[StructuralBreak]:
    """Group nearby indices into clusters, pick the peak of each."""
    if len(indices) == 0:
        return []

    clusters: list[list[int]] = []
    current_cluster = [int(indices[0])]

    for idx in indices[1:]:
        if idx - current_cluster[-1] <= gap:
            current_cluster.append(int(idx))
        else:
            clusters.append(current_cluster)
            current_cluster = [int(idx)]
    clusters.append(current_cluster)

    breaks = []
    for cluster in clusters:
        # Find the index in the cluster with the highest score
        peak_idx = max(cluster, key=lambda i: scores[i])
        breaks.append(
            StructuralBreak(
                date=dates[peak_idx],
                index=peak_idx,
                method="cusum",
                confidence=float(scores[peak_idx] / max_score),
            )
        )

    return breaks


def detect_rolling_variance(
    dates: list[datetime.date],
    values: np.ndarray,
    window: int = 30,
    threshold: float = 2.0,
) -> list[StructuralBreak]:
    """Detect breaks where the variance ratio between adjacent windows spikes."""
    n = len(values)
    if n < 2 * window:
        return []

    # Compute rolling variance
    variances = np.array(
        [float(np.var(values[i : i + window])) for i in range(n - window + 1)]
    )

    if len(variances) < 2:
        return []

    # Avoid division by zero — add small epsilon
    eps = 1e-10
    ratios = variances[1:] / (variances[:-1] + eps)

    breaks = []
    max_ratio = float(np.max(np.maximum(ratios, 1.0 / (ratios + eps))))

    for i, ratio in enumerate(ratios):
        if ratio > threshold or (ratio > 0 and 1.0 / ratio > threshold):
            actual_ratio = max(ratio, 1.0 / (ratio + eps))
            confidence = min(float(actual_ratio / max_ratio), 1.0)
            # The break point is at the boundary between windows
            break_idx = i + window
            if break_idx < len(dates):
                breaks.append(
                    StructuralBreak(
                        date=dates[break_idx],
                        index=break_idx,
                        method="rolling_variance",
                        confidence=confidence,
                    )
                )

    return breaks


def analyze_structural_breaks(
    ts: TimeSeries,
    method: str = "cusum",
    **kwargs: float,
) -> list[StructuralBreak]:
    """Run structural break detection on a TimeSeries."""
    dates = [p.date for p in ts.points]
    values = np.array([p.value for p in ts.points], dtype=np.float64)

    if method == "cusum":
        return detect_cusum(dates, values, **kwargs)
    elif method == "rolling_variance":
        return detect_rolling_variance(dates, values, **kwargs)
    else:
        raise ValueError(f"Unknown structural break method: '{method}'")
