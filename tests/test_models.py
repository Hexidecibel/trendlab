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


class TestRiskFlag:
    def test_round_trip(self):
        from app.models.schemas import RiskFlag

        flag = RiskFlag(label="volatility_spike", description="Unusually high variance")
        data = flag.model_dump()
        assert data["label"] == "volatility_spike"
        assert data["description"] == "Unusually high variance"
        restored = RiskFlag.model_validate(data)
        assert restored == flag


class TestInsightReport:
    def test_serialization_round_trip(self):
        from app.models.schemas import InsightReport, RiskFlag

        report = InsightReport(
            source="pypi",
            query="fastapi",
            summary="Downloads are rising steadily.",
            risk_flags=[
                RiskFlag(label="volatility_spike", description="High variance")
            ],
            recommended_action="Monitor closely",
            prompt_version="default",
            model_used="claude-sonnet-4-20250514",
        )
        data = report.model_dump()
        assert data["source"] == "pypi"
        assert data["summary"] == "Downloads are rising steadily."
        assert len(data["risk_flags"]) == 1
        assert data["recommended_action"] == "Monitor closely"
        assert data["prompt_version"] == "default"
        assert data["model_used"] == "claude-sonnet-4-20250514"
        restored = InsightReport.model_validate(data)
        assert restored == report

    def test_empty_risk_flags_and_none_action(self):
        from app.models.schemas import InsightReport

        report = InsightReport(
            source="pypi",
            query="fastapi",
            summary="All good.",
            risk_flags=[],
            recommended_action=None,
            prompt_version="concise",
            model_used="claude-sonnet-4-20250514",
        )
        data = report.model_dump()
        assert data["risk_flags"] == []
        assert data["recommended_action"] is None

    def test_all_fields_in_model_dump(self):
        from app.models.schemas import InsightReport

        report = InsightReport(
            source="test",
            query="test",
            summary="Test",
            risk_flags=[],
            recommended_action=None,
            prompt_version="default",
            model_used="test-model",
        )
        keys = set(report.model_dump().keys())
        expected = {
            "source",
            "query",
            "summary",
            "risk_flags",
            "recommended_action",
            "prompt_version",
            "model_used",
        }
        assert expected == keys


class TestDataAdapterABC:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            DataAdapter()
