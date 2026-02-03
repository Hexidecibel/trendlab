import pytest

from app.analysis.anomalies import analyze_anomalies
from app.models.schemas import TimeSeries
from tests.helpers import make_constant_series, make_series_with_outliers


class TestZScoreDetection:
    def test_detects_spike(self):
        ts = make_series_with_outliers(
            n=60, base_value=100.0, outlier_indices=[25], outlier_value=500.0
        )
        result = analyze_anomalies(ts, method="zscore")
        assert result.anomaly_count >= 1
        anomaly_dates = {a.date for a in result.anomalies}
        assert ts.points[25].date in anomaly_dates

    def test_constant_data_no_anomalies(self):
        ts = make_constant_series(n=60, value=100.0)
        result = analyze_anomalies(ts, method="zscore")
        assert result.anomaly_count == 0

    def test_anomaly_count_matches_list(self):
        ts = make_series_with_outliers(
            n=60, outlier_indices=[10, 40], outlier_value=999.0
        )
        result = analyze_anomalies(ts)
        assert result.anomaly_count == len(result.anomalies)

    def test_method_label_is_zscore(self):
        ts = make_constant_series(n=30)
        result = analyze_anomalies(ts, method="zscore")
        assert result.method == "zscore"


class TestIQRDetection:
    def test_detects_outlier(self):
        ts = make_series_with_outliers(
            n=60, base_value=100.0, outlier_indices=[30], outlier_value=500.0
        )
        result = analyze_anomalies(ts, method="iqr")
        assert result.anomaly_count >= 1
        assert result.method == "iqr"

    def test_method_dispatch(self):
        ts = make_constant_series(n=30)
        result = analyze_anomalies(ts, method="iqr")
        assert result.method == "iqr"


class TestEdgeCases:
    def test_unknown_method_raises(self):
        ts = make_constant_series(n=30)
        with pytest.raises(ValueError, match="Unknown"):
            analyze_anomalies(ts, method="bogus")

    def test_empty_series(self):
        ts = TimeSeries(source="test", query="empty", points=[])
        result = analyze_anomalies(ts)
        assert result.anomaly_count == 0
        assert result.total_points == 0

    def test_total_points_correct(self):
        ts = make_constant_series(n=42)
        result = analyze_anomalies(ts)
        assert result.total_points == 42
