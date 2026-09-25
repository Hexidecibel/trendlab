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


class TestResidualMethod:
    def _exp_trend(self, n=120, spike_at=None, spike_mult=3.0, seed=7):
        import datetime

        import numpy as np

        from app.models.schemas import DataPoint, TimeSeries

        rng = np.random.default_rng(seed)
        t = np.arange(n)
        values = 100 * np.exp(0.035 * t) * (1 + rng.normal(0, 0.02, n))
        if spike_at is not None:
            values[spike_at] *= spike_mult
        start = datetime.date(2024, 1, 1)
        return TimeSeries(
            source="test",
            query="exp",
            points=[
                DataPoint(date=start + datetime.timedelta(days=int(i)), value=float(v))
                for i, v in zip(t, values)
            ],
        )

    def test_default_method_is_residual(self):
        ts = make_series_with_outliers(n=60, outlier_indices=[30])
        result = analyze_anomalies(ts)
        assert result.method == "residual"

    def test_catches_spike_on_trending_series(self):
        ts = self._exp_trend(spike_at=70)
        result = analyze_anomalies(ts, method="residual")
        flagged = {a.date for a in result.anomalies}
        assert ts.points[70].date in flagged

    def test_does_not_flag_trend_tail(self):
        ts = self._exp_trend(spike_at=70)
        result = analyze_anomalies(ts, method="residual")
        tail = {p.date for p in ts.points[-20:]}
        assert not (tail & {a.date for a in result.anomalies})
        # Raw z-score, by contrast, mistakes the exponential tail for anomalies
        z = analyze_anomalies(ts, method="zscore")
        assert tail & {a.date for a in z.anomalies}

    def test_flat_series_spike(self):
        ts = make_series_with_outliers(n=60, outlier_indices=[25])
        result = analyze_anomalies(ts, method="residual")
        assert [a.date for a in result.anomalies] == [ts.points[25].date]

    def test_constant_series_no_anomalies(self):
        ts = make_constant_series(n=60)
        result = analyze_anomalies(ts, method="residual")
        assert result.anomaly_count == 0

    def test_short_series(self):
        ts = make_series_with_outliers(n=2, outlier_indices=[1])
        result = analyze_anomalies(ts, method="residual")
        assert result.anomaly_count == 0
        assert result.total_points == 2

    def test_weekly_cycle_is_not_anomalous(self):
        import datetime

        import numpy as np

        from app.models.schemas import DataPoint, TimeSeries

        rng = np.random.default_rng(11)
        n = 140
        t = np.arange(n)
        values = 1000 * np.where(t % 7 >= 5, 0.6, 1.0) * (1 + rng.normal(0, 0.03, n))
        values[90] *= 2.5
        start = datetime.date(2024, 1, 1)
        ts = TimeSeries(
            source="test",
            query="weekly",
            points=[
                DataPoint(date=start + datetime.timedelta(days=int(i)), value=float(v))
                for i, v in zip(t, values)
            ],
        )
        result = analyze_anomalies(ts, method="residual", seasonal_period=7)
        assert [a.date for a in result.anomalies] == [ts.points[90].date]
