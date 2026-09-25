"""Analysis orchestrator — runs all detectors on a TimeSeries."""

import numpy as np

from app.analysis.anomalies import analyze_anomalies
from app.analysis.level_shift import JUMP_MIN_PCT, jump_pct, pin_step_indices
from app.analysis.regime_detection import detect_regimes
from app.analysis.seasonality import analyze_seasonality
from app.analysis.structural_breaks import analyze_structural_breaks
from app.analysis.summary import build_summary_lines
from app.analysis.trend_metrics import analyze_trend
from app.models.schemas import StructuralBreak, TimeSeries, TrendAnalysis


def pin_level_shifts(
    ts: TimeSeries, breaks: list[StructuralBreak]
) -> list[StructuralBreak]:
    """Put breaks that are big level shifts on the day the step happens.

    CUSUM tends to land on the last point before a step; the break lines,
    regime bands, momentum ("since drop on ...") and the anomaly fit should
    all agree on the step date.
    """
    if not breaks:
        return breaks
    values = np.array([p.value for p in ts.points], dtype=np.float64)
    pinned = pin_step_indices(values, [b.index for b in breaks])
    out: list[StructuralBreak] = []
    seen: set[int] = set()
    for b, idx in zip(breaks, pinned):
        if idx in seen:
            continue
        seen.add(idx)
        if idx != b.index:
            b = b.model_copy(update={"index": idx, "date": ts.points[idx].date})
        out.append(b)
    return out


# Level changes smaller than this (%) across a break read as a change in
# the trend rather than a shift in level
SHIFT_MIN_PCT = 5.0


def describe_breaks(
    ts: TimeSeries, breaks: list[StructuralBreak]
) -> list[StructuralBreak]:
    """Fill each break's plain-English ``label`` and ``change_pct``."""
    values = np.array([p.value for p in ts.points], dtype=np.float64)
    n = len(values)
    idxs = sorted(b.index for b in breaks)
    out = []
    for b in breaks:
        k = idxs.index(b.index)
        prev_idx = idxs[k - 1] if k > 0 else 0
        next_idx = idxs[k + 1] if k + 1 < len(idxs) else n
        pct = jump_pct(values, b.index, b.index - prev_idx, next_idx - b.index)
        if pct is None:
            label = "change"
        elif abs(pct) >= JUMP_MIN_PCT:
            label = "big drop" if pct < 0 else "big jump"
        elif abs(pct) >= SHIFT_MIN_PCT:
            label = "shift down" if pct < 0 else "shift up"
        else:
            label = "trend change"
        out.append(b.model_copy(update={"label": label, "change_pct": pct}))
    return out


def analyze(ts: TimeSeries, anomaly_method: str = "residual") -> TrendAnalysis:
    """Run all analysis modules and return a combined TrendAnalysis.

    Seasonality runs first so its period can floor the smoothing window used
    for the trend line and for residual-based anomaly detection. Structural
    breaks run before the trend so momentum can be measured from the most
    recent break rather than through a step change.
    """
    if len(ts.points) == 0:
        raise ValueError("Cannot analyze empty series")

    seasonality = analyze_seasonality(ts)
    period = seasonality.period_days if seasonality.detected else None

    breaks = describe_breaks(ts, pin_level_shifts(ts, analyze_structural_breaks(ts)))
    regimes = detect_regimes(ts, breaks)

    return TrendAnalysis(
        source=ts.source,
        query=ts.query,
        series_length=len(ts.points),
        trend=analyze_trend(ts, seasonal_period=period, breaks=breaks),
        seasonality=seasonality,
        anomalies=analyze_anomalies(
            ts, method=anomaly_method, seasonal_period=period, breaks=breaks
        ),
        structural_breaks=breaks,
        regimes=regimes,
        summary_lines=build_summary_lines(ts, breaks, regimes),
    )
