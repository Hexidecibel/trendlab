from app.analysis.structural_breaks import analyze_structural_breaks
from app.models.schemas import TimeSeries
from tests.helpers import make_constant_series, make_step_series


class TestCUSUM:
    def test_detects_step_change(self):
        ts = make_step_series(n=100, break_at=50, val_before=10.0, val_after=50.0)
        result = analyze_structural_breaks(ts, method="cusum")
        assert len(result) >= 1
        # The detected break should be near index 50 (+/- tolerance)
        break_indices = [b.index for b in result]
        assert any(abs(idx - 50) <= 5 for idx in break_indices)

    def test_constant_data_no_breaks(self):
        ts = make_constant_series(n=100, value=42.0)
        result = analyze_structural_breaks(ts, method="cusum")
        assert len(result) == 0

    def test_break_has_correct_method(self):
        ts = make_step_series(n=100, break_at=50)
        result = analyze_structural_breaks(ts, method="cusum")
        for b in result:
            assert b.method == "cusum"

    def test_break_confidence_between_0_and_1(self):
        ts = make_step_series(n=100, break_at=50)
        result = analyze_structural_breaks(ts, method="cusum")
        for b in result:
            assert 0.0 <= b.confidence <= 1.0


class TestRollingVariance:
    def test_detects_variance_shift(self):
        """Create data where variance changes dramatically."""
        import datetime
        import math

        from app.models.schemas import DataPoint

        points = []
        base = datetime.date(2024, 1, 1)
        # Low-variance segment: values near 100
        for i in range(50):
            points.append(
                DataPoint(
                    date=base + datetime.timedelta(days=i),
                    value=100.0 + (i % 2),  # tiny oscillation
                )
            )
        # High-variance segment: values swing wildly
        for i in range(50, 100):
            points.append(
                DataPoint(
                    date=base + datetime.timedelta(days=i),
                    value=100.0 + 30.0 * math.sin(i),
                )
            )
        ts = TimeSeries(source="test", query="variance_shift", points=points)
        result = analyze_structural_breaks(ts, method="rolling_variance", window=15)
        assert len(result) >= 1

    def test_break_has_correct_method(self):
        ts = make_step_series(n=100, break_at=50)
        result = analyze_structural_breaks(ts, method="rolling_variance", window=15)
        for b in result:
            assert b.method == "rolling_variance"


class TestEdgeCases:
    def test_short_series_returns_empty(self):
        ts = make_constant_series(n=5)
        result = analyze_structural_breaks(ts, method="cusum")
        assert result == []

    def test_short_series_rolling_variance(self):
        ts = make_constant_series(n=5)
        result = analyze_structural_breaks(ts, method="rolling_variance", window=30)
        assert result == []
