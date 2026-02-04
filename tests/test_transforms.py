import datetime

import pytest

from app.models.schemas import DataPoint, TimeSeries
from app.services.transforms import apply_transforms


def _make_ts(values: list[float], start: datetime.date = datetime.date(2025, 1, 1)):
    points = [
        DataPoint(date=start + datetime.timedelta(days=i), value=v)
        for i, v in enumerate(values)
    ]
    return TimeSeries(source="test", query="test", points=points)


class TestRollingAverage:
    def test_rolling_avg_7d(self):
        ts = _make_ts([float(i) for i in range(14)])  # 0..13
        result = apply_transforms(ts, "rolling_avg_7d")
        # Window of 7: first valid at index 6 → 8 output points
        assert len(result.points) == 8
        # Mean of 0..6 = 3.0
        assert result.points[0].value == pytest.approx(3.0)
        # Mean of 7..13 = 10.0
        assert result.points[-1].value == pytest.approx(10.0)

    def test_rolling_avg_30d_on_short_series(self):
        ts = _make_ts([1.0] * 10)
        result = apply_transforms(ts, "rolling_avg_30d")
        # 10 points, window 30 → no complete windows → empty
        assert len(result.points) == 0

    def test_rolling_avg_3d(self):
        ts = _make_ts([1.0, 2.0, 3.0, 4.0, 5.0])
        result = apply_transforms(ts, "rolling_avg_3d")
        assert len(result.points) == 3
        assert result.points[0].value == pytest.approx(2.0)  # mean(1,2,3)
        assert result.points[1].value == pytest.approx(3.0)  # mean(2,3,4)
        assert result.points[2].value == pytest.approx(4.0)  # mean(3,4,5)


class TestPctChange:
    def test_basic_pct_change(self):
        ts = _make_ts([100.0, 110.0, 99.0])
        result = apply_transforms(ts, "pct_change")
        assert len(result.points) == 2
        assert result.points[0].value == pytest.approx(10.0)  # (110-100)/100*100
        assert result.points[1].value == pytest.approx(-10.0)  # (99-110)/110*100

    def test_pct_change_drops_zero_division(self):
        ts = _make_ts([0.0, 10.0, 20.0])
        result = apply_transforms(ts, "pct_change")
        # First change: 0→10, division by zero → dropped
        # Second change: 10→20 = 100%
        assert len(result.points) == 1
        assert result.points[0].value == pytest.approx(100.0)


class TestCumulative:
    def test_cumulative_sum(self):
        ts = _make_ts([1.0, 2.0, 3.0, 4.0])
        result = apply_transforms(ts, "cumulative")
        assert len(result.points) == 4
        assert [p.value for p in result.points] == [1.0, 3.0, 6.0, 10.0]


class TestNormalize:
    def test_normalize_range(self):
        ts = _make_ts([10.0, 20.0, 30.0, 40.0, 50.0])
        result = apply_transforms(ts, "normalize")
        assert len(result.points) == 5
        assert result.points[0].value == pytest.approx(0.0)
        assert result.points[-1].value == pytest.approx(1.0)
        assert result.points[2].value == pytest.approx(0.5)

    def test_normalize_constant_series(self):
        ts = _make_ts([5.0, 5.0, 5.0])
        result = apply_transforms(ts, "normalize")
        # All same → all 0.0 (min == max, avoid division by zero)
        assert all(p.value == 0.0 for p in result.points)


class TestDiff:
    def test_first_difference(self):
        ts = _make_ts([10.0, 13.0, 11.0, 15.0])
        result = apply_transforms(ts, "diff")
        assert len(result.points) == 3
        assert result.points[0].value == pytest.approx(3.0)
        assert result.points[1].value == pytest.approx(-2.0)
        assert result.points[2].value == pytest.approx(4.0)


class TestPipeline:
    def test_chain_two_transforms(self):
        ts = _make_ts([10.0, 20.0, 30.0, 40.0, 50.0])
        result = apply_transforms(ts, "normalize|diff")
        # normalize: [0, 0.25, 0.5, 0.75, 1.0]
        # diff: [0.25, 0.25, 0.25, 0.25]
        assert len(result.points) == 4
        for p in result.points:
            assert p.value == pytest.approx(0.25)

    def test_empty_apply_is_noop(self):
        ts = _make_ts([1.0, 2.0, 3.0])
        result = apply_transforms(ts, "")
        assert len(result.points) == 3

    def test_unknown_transform_raises(self):
        ts = _make_ts([1.0, 2.0])
        with pytest.raises(ValueError, match="Unknown transform"):
            apply_transforms(ts, "bogus_transform")


class TestMetadata:
    def test_transforms_recorded_in_metadata(self):
        ts = _make_ts([1.0, 2.0, 3.0, 4.0])
        result = apply_transforms(ts, "cumulative")
        assert result.metadata.get("transforms") == ["cumulative"]

    def test_pipeline_metadata(self):
        ts = _make_ts([10.0, 20.0, 30.0, 40.0, 50.0])
        result = apply_transforms(ts, "normalize|diff")
        assert result.metadata.get("transforms") == ["normalize", "diff"]
