import datetime

import pytest

from app.analysis.trend_metrics import analyze_trend
from app.models.schemas import DataPoint, TimeSeries
from tests.helpers import make_constant_series, make_linear_series


class TestAnalyzeTrend:
    def test_rising_linear_data(self):
        ts = make_linear_series(n=60, slope=2.0, intercept=100.0)
        result = analyze_trend(ts)
        assert result.direction == "rising"
        assert result.momentum > 0

    def test_falling_linear_data(self):
        ts = make_linear_series(n=60, slope=-2.0, intercept=200.0)
        result = analyze_trend(ts)
        assert result.direction == "falling"
        assert result.momentum < 0

    def test_constant_data_is_stable(self):
        ts = make_constant_series(n=60, value=100.0)
        result = analyze_trend(ts)
        assert result.direction == "stable"
        assert result.momentum == 0.0
        assert result.acceleration == 0.0

    def test_moving_average_window_3(self):
        """Verify exact MA values with a tiny known series."""
        points = [
            DataPoint(date=datetime.date(2024, 1, i + 1), value=float(v))
            for i, v in enumerate([10, 20, 30, 40, 50])
        ]
        ts = TimeSeries(source="test", query="ma", points=points)
        result = analyze_trend(ts, windows=[3])

        ma = result.moving_averages[0]
        assert ma.window == 3
        # End-aligned: MA[2]=avg(10,20,30)=20, MA[3]=30, MA[4]=40
        assert len(ma.values) == 3
        assert ma.values[0].value == pytest.approx(20.0)
        assert ma.values[1].value == pytest.approx(30.0)
        assert ma.values[2].value == pytest.approx(40.0)
        # Dates should be end-aligned
        assert ma.values[0].date == datetime.date(2024, 1, 3)
        assert ma.values[2].date == datetime.date(2024, 1, 5)

    def test_single_point_returns_stable(self):
        ts = TimeSeries(
            source="test",
            query="single",
            points=[DataPoint(date=datetime.date(2024, 1, 1), value=42.0)],
        )
        result = analyze_trend(ts)
        assert result.direction == "stable"
        assert result.momentum == 0.0
        assert result.acceleration == 0.0
        assert result.momentum_series == []
        assert all(ma.values == [] for ma in result.moving_averages)

    def test_series_shorter_than_window(self):
        ts = make_linear_series(n=5, slope=1.0)
        result = analyze_trend(ts, windows=[7, 30])
        # Window 7 needs 7 points — we only have 5, so empty
        assert result.moving_averages[0].values == []
        # Window 30 also empty
        assert result.moving_averages[1].values == []

    def test_momentum_series_length(self):
        ts = make_linear_series(n=10)
        result = analyze_trend(ts)
        # momentum_series should be len(points) - 1
        assert len(result.momentum_series) == 9
