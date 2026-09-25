"""Analysis orchestrator — runs all detectors on a TimeSeries."""

from app.analysis.anomalies import analyze_anomalies
from app.analysis.regime_detection import detect_regimes
from app.analysis.seasonality import analyze_seasonality
from app.analysis.structural_breaks import analyze_structural_breaks
from app.analysis.summary import build_summary_lines
from app.analysis.trend_metrics import analyze_trend
from app.models.schemas import TimeSeries, TrendAnalysis


def analyze(ts: TimeSeries, anomaly_method: str = "residual") -> TrendAnalysis:
    """Run all analysis modules and return a combined TrendAnalysis.

    Seasonality runs first so its period can floor the smoothing window used
    for the trend line and for residual-based anomaly detection.
    """
    if len(ts.points) == 0:
        raise ValueError("Cannot analyze empty series")

    seasonality = analyze_seasonality(ts)
    period = seasonality.period_days if seasonality.detected else None

    breaks = analyze_structural_breaks(ts)
    regimes = detect_regimes(ts, breaks)

    return TrendAnalysis(
        source=ts.source,
        query=ts.query,
        series_length=len(ts.points),
        trend=analyze_trend(ts, seasonal_period=period),
        seasonality=seasonality,
        anomalies=analyze_anomalies(
            ts, method=anomaly_method, seasonal_period=period
        ),
        structural_breaks=breaks,
        regimes=regimes,
        summary_lines=build_summary_lines(ts, breaks, regimes),
    )
