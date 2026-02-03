import datetime

from app.models.schemas import (
    AnomalyPoint,
    AnomalyReport,
    DataPoint,
    MovingAverage,
    SeasonalityResult,
    StructuralBreak,
    TrendAnalysis,
    TrendSignal,
)


class TestTrendSignal:
    def test_basic_creation(self):
        sig = TrendSignal(
            direction="rising",
            momentum=0.05,
            acceleration=0.01,
            moving_averages=[],
            momentum_series=[],
        )
        assert sig.direction == "rising"
        assert sig.momentum == 0.05

    def test_with_moving_averages(self):
        ma = MovingAverage(
            window=7,
            values=[DataPoint(date=datetime.date(2024, 1, 7), value=100.0)],
        )
        sig = TrendSignal(
            direction="stable",
            momentum=0.0,
            acceleration=0.0,
            moving_averages=[ma],
            momentum_series=[],
        )
        assert len(sig.moving_averages) == 1
        assert sig.moving_averages[0].window == 7


class TestSeasonalityResult:
    def test_no_seasonality(self):
        res = SeasonalityResult(
            detected=False,
            period_days=None,
            strength=None,
            autocorrelation=[],
        )
        assert res.detected is False
        assert res.period_days is None

    def test_with_seasonality(self):
        res = SeasonalityResult(
            detected=True,
            period_days=7,
            strength=0.85,
            autocorrelation=[1.0, 0.5, 0.2, 0.1, 0.05, 0.1, 0.2, 0.85],
        )
        assert res.period_days == 7
        assert res.strength == 0.85


class TestAnomalyReport:
    def test_round_trip(self):
        ap = AnomalyPoint(
            date=datetime.date(2024, 1, 5),
            value=999.0,
            score=4.2,
            method="zscore",
        )
        report = AnomalyReport(
            method="zscore",
            threshold=2.5,
            anomalies=[ap],
            total_points=100,
            anomaly_count=1,
        )
        data = report.model_dump()
        restored = AnomalyReport.model_validate(data)
        assert restored.anomaly_count == 1
        assert restored.anomalies[0].score == 4.2

    def test_empty_report(self):
        report = AnomalyReport(
            method="zscore",
            threshold=2.5,
            anomalies=[],
            total_points=50,
            anomaly_count=0,
        )
        assert report.anomaly_count == 0


class TestTrendAnalysis:
    def test_full_serialization(self):
        analysis = TrendAnalysis(
            source="pypi",
            query="fastapi",
            series_length=90,
            trend=TrendSignal(
                direction="rising",
                momentum=0.03,
                acceleration=0.001,
                moving_averages=[],
                momentum_series=[],
            ),
            seasonality=SeasonalityResult(
                detected=False,
                period_days=None,
                strength=None,
                autocorrelation=[],
            ),
            anomalies=AnomalyReport(
                method="zscore",
                threshold=2.5,
                anomalies=[],
                total_points=90,
                anomaly_count=0,
            ),
            structural_breaks=[],
        )
        data = analysis.model_dump()
        assert data["source"] == "pypi"
        assert data["series_length"] == 90
        assert data["trend"]["direction"] == "rising"
        assert data["seasonality"]["detected"] is False
        assert data["anomalies"]["method"] == "zscore"
        assert data["structural_breaks"] == []

    def test_with_structural_breaks(self):
        sb = StructuralBreak(
            date=datetime.date(2024, 3, 15),
            index=50,
            method="cusum",
            confidence=0.9,
        )
        analysis = TrendAnalysis(
            source="crypto",
            query="bitcoin",
            series_length=180,
            trend=TrendSignal(
                direction="falling",
                momentum=-0.02,
                acceleration=-0.001,
                moving_averages=[],
                momentum_series=[],
            ),
            seasonality=SeasonalityResult(
                detected=True,
                period_days=7,
                strength=0.6,
                autocorrelation=[1.0, 0.3, 0.1],
            ),
            anomalies=AnomalyReport(
                method="iqr",
                threshold=1.5,
                anomalies=[],
                total_points=180,
                anomaly_count=0,
            ),
            structural_breaks=[sb],
        )
        assert len(analysis.structural_breaks) == 1
        assert analysis.structural_breaks[0].confidence == 0.9
