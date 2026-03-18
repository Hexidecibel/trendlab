"""Analysis orchestrator — runs all detectors on a TimeSeries."""

from app.analysis.anomalies import analyze_anomalies
from app.analysis.regime_detection import detect_regimes
from app.analysis.seasonality import analyze_seasonality
from app.analysis.structural_breaks import analyze_structural_breaks
from app.analysis.trend_metrics import analyze_trend
from app.models.schemas import TimeSeries, TrendAnalysis


def analyze(ts: TimeSeries, anomaly_method: str = "zscore") -> TrendAnalysis:
    """Run all analysis modules and return a combined TrendAnalysis."""
    if len(ts.points) == 0:
        raise ValueError("Cannot analyze empty series")

    breaks = analyze_structural_breaks(ts)

    return TrendAnalysis(
        source=ts.source,
        query=ts.query,
        series_length=len(ts.points),
        trend=analyze_trend(ts),
        seasonality=analyze_seasonality(ts),
        anomalies=analyze_anomalies(ts, method=anomaly_method),
        structural_breaks=breaks,
        regimes=detect_regimes(ts, breaks),
    )
