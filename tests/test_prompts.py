"""Tests for AI prompt templates and context formatting."""

import datetime

import pytest

from app.models.schemas import (
    AnomalyPoint,
    AnomalyReport,
    DataPoint,
    ForecastComparison,
    ForecastPoint,
    ModelEvaluation,
    ModelForecast,
    MovingAverage,
    SeasonalityResult,
    StructuralBreak,
    TrendAnalysis,
    TrendSignal,
)

BASE_DATE = datetime.date(2024, 1, 1)


def _make_analysis() -> TrendAnalysis:
    return TrendAnalysis(
        source="pypi",
        query="fastapi",
        series_length=60,
        trend=TrendSignal(
            direction="rising",
            momentum=0.05,
            acceleration=0.001,
            moving_averages=[
                MovingAverage(
                    window=7,
                    values=[DataPoint(date=BASE_DATE, value=100.0)],
                )
            ],
            momentum_series=[DataPoint(date=BASE_DATE, value=0.05)],
        ),
        seasonality=SeasonalityResult(
            detected=True,
            period_days=7,
            strength=0.6,
            autocorrelation=[1.0, 0.5, 0.3],
        ),
        anomalies=AnomalyReport(
            method="zscore",
            threshold=2.5,
            anomalies=[
                AnomalyPoint(date=BASE_DATE, value=500.0, score=3.2, method="zscore")
            ],
            total_points=60,
            anomaly_count=1,
        ),
        structural_breaks=[
            StructuralBreak(
                date=BASE_DATE,
                index=30,
                method="cusum",
                confidence=0.85,
            )
        ],
    )


def _make_forecast() -> ForecastComparison:
    return ForecastComparison(
        source="pypi",
        query="fastapi",
        series_length=60,
        horizon=14,
        forecasts=[
            ModelForecast(
                model_name="linear",
                points=[
                    ForecastPoint(
                        date=BASE_DATE + datetime.timedelta(days=i),
                        value=100.0 + i * 2.0,
                        lower_ci=90.0 + i * 2.0,
                        upper_ci=110.0 + i * 2.0,
                    )
                    for i in range(1, 15)
                ],
            ),
            ModelForecast(
                model_name="naive",
                points=[
                    ForecastPoint(
                        date=BASE_DATE + datetime.timedelta(days=i),
                        value=100.0,
                        lower_ci=90.0,
                        upper_ci=110.0,
                    )
                    for i in range(1, 15)
                ],
            ),
        ],
        evaluations=[
            ModelEvaluation(
                model_name="linear",
                mae=1.5,
                rmse=2.0,
                mape=3.0,
                train_size=48,
                test_size=12,
            ),
            ModelEvaluation(
                model_name="naive",
                mae=5.0,
                rmse=6.0,
                mape=10.0,
                train_size=48,
                test_size=12,
            ),
        ],
        recommended_model="linear",
    )


class TestFormatAnalysisContext:
    def test_produces_nonempty_string(self):
        from app.ai.prompts import format_analysis_context

        result = format_analysis_context(_make_analysis(), _make_forecast())
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_source_name(self):
        from app.ai.prompts import format_analysis_context

        result = format_analysis_context(_make_analysis(), _make_forecast())
        assert "pypi" in result

    def test_contains_direction(self):
        from app.ai.prompts import format_analysis_context

        result = format_analysis_context(_make_analysis(), _make_forecast())
        assert "rising" in result

    def test_contains_recommended_model(self):
        from app.ai.prompts import format_analysis_context

        result = format_analysis_context(_make_analysis(), _make_forecast())
        assert "linear" in result


class TestGetPrompt:
    def test_default_contains_context_placeholder(self):
        from app.ai.prompts import get_prompt

        result = get_prompt("default")
        assert "{context}" in result

    def test_concise_contains_context_placeholder(self):
        from app.ai.prompts import get_prompt

        result = get_prompt("concise")
        assert "{context}" in result

    def test_detailed_contains_context_placeholder(self):
        from app.ai.prompts import get_prompt

        result = get_prompt("detailed")
        assert "{context}" in result

    def test_unknown_raises_value_error(self):
        from app.ai.prompts import get_prompt

        with pytest.raises(ValueError, match="Unknown prompt version"):
            get_prompt("nonexistent_version")

    def test_all_registered_versions_valid(self):
        from app.ai.prompts import PROMPT_REGISTRY

        for version, template in PROMPT_REGISTRY.items():
            assert "{context}" in template, f"Version '{version}' missing {{context}}"


class TestBuildMessages:
    def test_returns_list_with_system_and_user(self):
        from app.ai.prompts import build_messages

        msgs = build_messages(_make_analysis(), _make_forecast())
        assert isinstance(msgs, list)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"

    def test_system_message_has_content(self):
        from app.ai.prompts import build_messages

        msgs = build_messages(_make_analysis(), _make_forecast())
        assert len(msgs[0]["content"]) > 0

    def test_user_message_contains_context(self):
        from app.ai.prompts import build_messages

        msgs = build_messages(_make_analysis(), _make_forecast())
        # Should contain formatted context data, not the raw placeholder
        assert "{context}" not in msgs[1]["content"]
        assert "pypi" in msgs[1]["content"]

    def test_respects_version_parameter(self):
        from app.ai.prompts import build_messages

        msgs_default = build_messages(
            _make_analysis(), _make_forecast(), version="default"
        )
        msgs_concise = build_messages(
            _make_analysis(), _make_forecast(), version="concise"
        )
        # Different prompts should produce different user messages
        assert msgs_default[1]["content"] != msgs_concise[1]["content"]
