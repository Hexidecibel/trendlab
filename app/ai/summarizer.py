"""Summarizer: build prompts, call LLM, return InsightReport."""

from collections.abc import AsyncGenerator

from app.ai.client import LLMClient
from app.ai.prompts import build_messages
from app.config import settings
from app.logging_config import get_logger
from app.models.schemas import (
    ForecastComparison,
    InsightReport,
    TrendAnalysis,
)

logger = get_logger(__name__)


def _get_client(client: LLMClient | None) -> LLMClient:
    """Return the provided client or create one from settings."""
    if client is not None:
        return client
    if not settings.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY not configured")
    return LLMClient(api_key=settings.anthropic_api_key)


async def summarize(
    analysis: TrendAnalysis,
    forecast: ForecastComparison,
    prompt_version: str = "default",
    client: LLMClient | None = None,
) -> InsightReport:
    """Generate a narrative insight report from analysis and forecast data."""
    llm = _get_client(client)
    messages = build_messages(analysis, forecast, version=prompt_version)
    summary_text = await llm.generate(messages)

    return InsightReport(
        source=analysis.source,
        query=analysis.query,
        summary=summary_text,
        risk_flags=[],
        recommended_action=None,
        prompt_version=prompt_version,
        model_used=llm.model,
    )


async def summarize_stream(
    analysis: TrendAnalysis,
    forecast: ForecastComparison,
    prompt_version: str = "default",
    client: LLMClient | None = None,
) -> AsyncGenerator[str, None]:
    """Stream LLM-generated text chunks for the insight."""
    llm = _get_client(client)
    messages = build_messages(analysis, forecast, version=prompt_version)
    async for chunk in llm.stream(messages):
        yield chunk


async def summarize_compare_stream(
    analyses: list[TrendAnalysis],
    labels: list[str],
    client: LLMClient | None = None,
) -> AsyncGenerator[str, None]:
    """Stream LLM-generated comparison insight for multiple series."""
    llm = _get_client(client)

    series_descriptions = []
    for analysis, label in zip(analyses, labels):
        desc = f"""
**{label}**:
- Trend: {analysis.trend.direction} (momentum: {analysis.trend.momentum:.4f})
- Seasonality: {'Yes, ' + str(analysis.seasonality.period_days) + '-day period' if analysis.seasonality.detected else 'None detected'}
- Anomalies: {analysis.anomalies.anomaly_count} flagged
- Structural breaks: {len(analysis.structural_breaks)}
"""
        series_descriptions.append(desc)

    system_prompt = """You are a data analyst comparing time series trends.
Write a concise comparison (2-3 short paragraphs) that:
1. Compares the trend directions and momentum
2. Notes any differences in volatility or patterns
3. Concludes which series shows stronger performance

Refer to each series by its name (provided in the data). Be specific with numbers.
Keep it brief and actionable. Use markdown formatting."""

    user_prompt = f"""Compare these {len(analyses)} series:
{''.join(series_descriptions)}
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    async for chunk in llm.stream(messages):
        yield chunk
