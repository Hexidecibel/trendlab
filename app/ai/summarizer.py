"""Summarizer: build prompts, call LLM, return InsightReport."""

import logging
from collections.abc import AsyncGenerator

from app.ai.client import LLMClient
from app.ai.prompts import build_messages
from app.config import settings
from app.models.schemas import (
    ForecastComparison,
    InsightReport,
    TrendAnalysis,
)

logger = logging.getLogger(__name__)


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
