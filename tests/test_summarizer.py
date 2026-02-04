"""Tests for the AI summarizer module (mocked LLM client)."""

import datetime
from unittest.mock import AsyncMock, patch

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
            detected=False,
            period_days=None,
            strength=None,
            autocorrelation=[1.0, 0.5],
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
        structural_breaks=[],
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
                        lower_ci=90.0,
                        upper_ci=110.0,
                    )
                    for i in range(1, 15)
                ],
            )
        ],
        evaluations=[
            ModelEvaluation(
                model_name="linear",
                mae=1.5,
                rmse=2.0,
                mape=3.0,
                train_size=48,
                test_size=12,
            )
        ],
        recommended_model="linear",
    )


class TestSummarize:
    @pytest.mark.asyncio
    async def test_returns_insight_report(self):
        from app.ai.summarizer import summarize
        from app.models.schemas import InsightReport

        mock_client = AsyncMock()
        mock_client.generate.return_value = (
            "Downloads for fastapi are rising steadily. "
            "The linear model forecasts continued growth."
        )
        mock_client.model = "claude-sonnet-4-20250514"

        result = await summarize(_make_analysis(), _make_forecast(), client=mock_client)
        assert isinstance(result, InsightReport)
        assert result.source == "pypi"
        assert result.query == "fastapi"
        assert "rising" in result.summary.lower() or len(result.summary) > 0

    @pytest.mark.asyncio
    async def test_populates_prompt_version(self):
        from app.ai.summarizer import summarize

        mock_client = AsyncMock()
        mock_client.generate.return_value = "Summary text."
        mock_client.model = "claude-sonnet-4-20250514"

        result = await summarize(
            _make_analysis(),
            _make_forecast(),
            prompt_version="concise",
            client=mock_client,
        )
        assert result.prompt_version == "concise"

    @pytest.mark.asyncio
    async def test_populates_model_used(self):
        from app.ai.summarizer import summarize

        mock_client = AsyncMock()
        mock_client.generate.return_value = "Summary text."
        mock_client.model = "test-model-v1"

        result = await summarize(_make_analysis(), _make_forecast(), client=mock_client)
        assert result.model_used == "test-model-v1"

    @pytest.mark.asyncio
    async def test_missing_api_key_raises(self):
        from app.ai.summarizer import summarize

        with patch("app.ai.summarizer.settings") as mock_settings:
            mock_settings.anthropic_api_key = None
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                await summarize(_make_analysis(), _make_forecast(), client=None)


class TestSummarizeStream:
    @pytest.mark.asyncio
    async def test_yields_chunks(self):
        from app.ai.summarizer import summarize_stream

        chunks = ["Hello ", "world", "!"]

        mock_client = AsyncMock()

        async def mock_stream(*args, **kwargs):
            for chunk in chunks:
                yield chunk

        mock_client.stream = mock_stream

        collected = []
        async for text in summarize_stream(
            _make_analysis(), _make_forecast(), client=mock_client
        ):
            collected.append(text)

        assert collected == chunks

    @pytest.mark.asyncio
    async def test_stream_missing_api_key_raises(self):
        from app.ai.summarizer import summarize_stream

        with patch("app.ai.summarizer.settings") as mock_settings:
            mock_settings.anthropic_api_key = None
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                async for _ in summarize_stream(
                    _make_analysis(), _make_forecast(), client=None
                ):
                    pass
