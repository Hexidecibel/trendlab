"""Regime detection using structural break boundaries."""

import numpy as np

from app.analysis.trend_metrics import DIRECTION_THRESHOLD
from app.models.schemas import Regime, StructuralBreak, TimeSeries


def detect_regimes(
    ts: TimeSeries, breaks: list[StructuralBreak]
) -> list[Regime]:
    """Segment the series at structural breaks and classify each regime.

    For each segment between consecutive breaks the function computes:
    - mean value
    - mean return (average pct change per step)
    - volatility (std of returns)

    Direction is classified against ``DIRECTION_THRESHOLD`` from
    ``trend_metrics``.
    """
    if len(ts.points) < 2:
        return []

    dates = [p.date for p in ts.points]
    values = np.array([p.value for p in ts.points], dtype=np.float64)

    # Build ordered boundary indices from breaks
    sorted_breaks = sorted(breaks, key=lambda b: b.index)
    boundaries = [b.index for b in sorted_breaks]

    # Build segment ranges: [(start, end), ...]
    segments: list[tuple[int, int]] = []
    prev = 0
    for b in boundaries:
        if b > prev:
            segments.append((prev, b))
        prev = b
    # Final segment from last break to end
    if prev < len(values):
        segments.append((prev, len(values)))

    regimes: list[Regime] = []
    for start, end in segments:
        seg_values = values[start:end]
        mean_value = float(np.mean(seg_values))

        # Compute returns (pct change)
        if len(seg_values) >= 2:
            with np.errstate(divide="ignore", invalid="ignore"):
                returns = np.diff(seg_values) / seg_values[:-1]
            returns = np.where(np.isfinite(returns), returns, 0.0)
            mean_return = float(np.mean(returns))
            volatility = float(np.std(returns))
        else:
            mean_return = 0.0
            volatility = 0.0

        # Classify direction
        if mean_return > DIRECTION_THRESHOLD:
            label = "rising"
        elif mean_return < -DIRECTION_THRESHOLD:
            label = "falling"
        else:
            label = "stable"

        regimes.append(
            Regime(
                start_date=str(dates[start]),
                end_date=str(dates[end - 1]),
                label=label,
                mean_value=mean_value,
                mean_return=mean_return,
                volatility=volatility,
            )
        )

    return regimes
