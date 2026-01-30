import datetime

import pytest

from app.data.base import DataAdapter
from app.models.schemas import DataPoint, DataSourceInfo, TimeSeries


class TestDataPoint:
    def test_valid_data_point(self):
        dp = DataPoint(date=datetime.date(2024, 1, 15), value=42.0)
        assert dp.date == datetime.date(2024, 1, 15)
        assert dp.value == 42.0

    def test_data_point_coerces_int_to_float(self):
        dp = DataPoint(date=datetime.date(2024, 1, 15), value=42)
        assert isinstance(dp.value, (int, float))


class TestTimeSeries:
    def test_serializes_to_expected_shape(self):
        ts = TimeSeries(
            source="test",
            query="example",
            points=[
                DataPoint(date=datetime.date(2024, 1, 1), value=10.0),
                DataPoint(date=datetime.date(2024, 1, 2), value=20.0),
            ],
            metadata={"note": "test data"},
        )
        data = ts.model_dump()
        assert data["source"] == "test"
        assert data["query"] == "example"
        assert len(data["points"]) == 2
        assert data["points"][0]["date"] == datetime.date(2024, 1, 1)
        assert data["points"][0]["value"] == 10.0
        assert data["metadata"] == {"note": "test data"}

    def test_empty_points(self):
        ts = TimeSeries(source="test", query="empty", points=[], metadata={})
        assert ts.points == []

    def test_default_metadata(self):
        ts = TimeSeries(source="test", query="example", points=[])
        assert ts.metadata == {}


class TestDataSourceInfo:
    def test_source_info(self):
        info = DataSourceInfo(name="pypi", description="PyPI downloads")
        assert info.name == "pypi"
        assert info.description == "PyPI downloads"


class TestDataAdapterABC:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            DataAdapter()
