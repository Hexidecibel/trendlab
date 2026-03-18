import datetime

from app.analysis.regime_detection import detect_regimes
from app.models.schemas import DataPoint, StructuralBreak, TimeSeries
from tests.helpers import make_constant_series, make_step_series

BASE_DATE = datetime.date(2024, 1, 1)


def _make_v_series(n: int = 100, trough_at: int = 50) -> TimeSeries:
    """Create a V-shape: falling to trough_at then rising."""
    points = []
    for i in range(n):
        if i < trough_at:
            value = 100.0 - 2.0 * i  # falling
        else:
            value = 100.0 - 2.0 * trough_at + 2.0 * (i - trough_at)  # rising
        points.append(
            DataPoint(date=BASE_DATE + datetime.timedelta(days=i), value=value)
        )
    return TimeSeries(source="test", query="v_shape", points=points)


class TestRegimeDetection:
    def test_step_series_detects_regimes(self):
        """Step series with a break should produce at least two regimes."""
        ts = make_step_series(n=100, break_at=50, val_before=10.0, val_after=50.0)
        brk = StructuralBreak(
            date=BASE_DATE + datetime.timedelta(days=50),
            index=50,
            method="cusum",
            confidence=0.9,
        )
        regimes = detect_regimes(ts, [brk])
        assert len(regimes) == 2
        # First regime should be stable (flat at 10), second stable (flat at 50)
        assert regimes[0].label == "stable"
        assert regimes[1].label == "stable"
        assert regimes[0].mean_value < regimes[1].mean_value

    def test_v_shape_falling_then_rising(self):
        """V-shape with break at trough should detect falling + rising."""
        ts = _make_v_series(n=100, trough_at=50)
        brk = StructuralBreak(
            date=BASE_DATE + datetime.timedelta(days=50),
            index=50,
            method="cusum",
            confidence=0.8,
        )
        regimes = detect_regimes(ts, [brk])
        assert len(regimes) == 2
        assert regimes[0].label == "falling"
        assert regimes[1].label == "rising"

    def test_constant_series_single_stable(self):
        """Constant series with no breaks → single stable regime."""
        ts = make_constant_series(n=60, value=42.0)
        regimes = detect_regimes(ts, [])
        assert len(regimes) == 1
        assert regimes[0].label == "stable"
        assert regimes[0].mean_value == 42.0
        assert regimes[0].volatility == 0.0

    def test_no_breaks_single_regime(self):
        """Any series without breaks produces exactly one regime."""
        ts = make_step_series(n=100, break_at=50)
        regimes = detect_regimes(ts, [])
        assert len(regimes) == 1
        # Covers full date range
        assert regimes[0].start_date == str(ts.points[0].date)
        assert regimes[0].end_date == str(ts.points[-1].date)

    def test_empty_series_returns_empty(self):
        """Empty series edge case."""
        ts = TimeSeries(source="test", query="empty", points=[])
        regimes = detect_regimes(ts, [])
        assert regimes == []

    def test_single_point_returns_empty(self):
        """A single-point series cannot compute returns."""
        ts = TimeSeries(
            source="test",
            query="single",
            points=[DataPoint(date=BASE_DATE, value=10.0)],
        )
        regimes = detect_regimes(ts, [])
        assert regimes == []

    def test_regime_fields_populated(self):
        """All fields on a Regime object are populated correctly."""
        ts = make_constant_series(n=60, value=100.0)
        regimes = detect_regimes(ts, [])
        r = regimes[0]
        assert r.start_date == str(BASE_DATE)
        assert r.end_date == str(BASE_DATE + datetime.timedelta(days=59))
        assert r.mean_value == 100.0
        assert r.mean_return == 0.0
        assert r.volatility == 0.0

    def test_multiple_breaks_produce_multiple_regimes(self):
        """Two breaks should produce three regimes."""
        points = []
        for i in range(90):
            if i < 30:
                value = 10.0
            elif i < 60:
                value = 50.0
            else:
                value = 10.0
            points.append(
                DataPoint(
                    date=BASE_DATE + datetime.timedelta(days=i), value=value
                )
            )
        ts = TimeSeries(source="test", query="multi_step", points=points)
        breaks = [
            StructuralBreak(
                date=BASE_DATE + datetime.timedelta(days=30),
                index=30,
                method="cusum",
                confidence=0.9,
            ),
            StructuralBreak(
                date=BASE_DATE + datetime.timedelta(days=60),
                index=60,
                method="cusum",
                confidence=0.9,
            ),
        ]
        regimes = detect_regimes(ts, breaks)
        assert len(regimes) == 3
