import pytest

from app.analysis.engine import analyze
from app.models.schemas import (
    AnomalyReport,
    SeasonalityResult,
    TimeSeries,
    TrendAnalysis,
    TrendSignal,
)
from tests.helpers import make_linear_series


class TestAnalyzeOrchestrator:
    def test_returns_trend_analysis(self):
        ts = make_linear_series(n=60, slope=1.0)
        result = analyze(ts)
        assert isinstance(result, TrendAnalysis)

    def test_all_subresults_present(self):
        ts = make_linear_series(n=60)
        result = analyze(ts)
        assert isinstance(result.trend, TrendSignal)
        assert isinstance(result.seasonality, SeasonalityResult)
        assert isinstance(result.anomalies, AnomalyReport)
        assert isinstance(result.structural_breaks, list)

    def test_source_and_query_propagated(self):
        ts = make_linear_series(n=60)
        result = analyze(ts)
        assert result.source == "test"
        assert result.query == "linear"
        assert result.series_length == 60

    def test_empty_series_raises(self):
        ts = TimeSeries(source="test", query="empty", points=[])
        with pytest.raises(ValueError, match="empty"):
            analyze(ts)

    def test_anomaly_method_passed_through(self):
        ts = make_linear_series(n=60)
        result = analyze(ts, anomaly_method="iqr")
        assert result.anomalies.method == "iqr"

    def test_default_anomaly_method_is_zscore(self):
        ts = make_linear_series(n=60)
        result = analyze(ts)
        assert result.anomalies.method == "zscore"
