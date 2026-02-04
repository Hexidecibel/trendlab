import datetime
import json
import logging

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.ai.summarizer import summarize_stream
from app.analysis.engine import analyze
from app.config import settings
from app.data.registry import registry
from app.forecasting.engine import forecast
from app.models.schemas import (
    DataSourceInfo,
    ForecastComparison,
    TimeSeries,
    TrendAnalysis,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/")
async def api_root():
    """API root endpoint."""
    return {"message": "API v1"}


@router.get("/sources", response_model=list[DataSourceInfo])
async def list_sources():
    """List all available data sources."""
    return registry.list_sources()


@router.get("/series", response_model=TimeSeries)
async def get_series(
    source: str = Query(..., description="Data source name"),
    query: str = Query(..., description="Query string (e.g. package name)"),
    start: datetime.date | None = Query(None, description="Start date filter"),
    end: datetime.date | None = Query(None, description="End date filter"),
):
    """Fetch time-series data from a named source."""
    try:
        adapter = registry.get(source)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Source '{source}' not found")

    try:
        return await adapter.fetch(query, start=start, end=end)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/analyze", response_model=TrendAnalysis)
async def analyze_series(
    source: str = Query(..., description="Data source name"),
    query: str = Query(..., description="Query string (e.g. package name)"),
    start: datetime.date | None = Query(None, description="Start date filter"),
    end: datetime.date | None = Query(None, description="End date filter"),
    anomaly_method: str = Query(
        "zscore", description="Anomaly detection method: zscore or iqr"
    ),
):
    """Fetch time-series data and run trend analysis."""
    try:
        adapter = registry.get(source)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Source '{source}' not found")

    try:
        ts = await adapter.fetch(query, start=start, end=end)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    try:
        return analyze(ts, anomaly_method=anomaly_method)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/forecast", response_model=ForecastComparison)
async def forecast_series(
    source: str = Query(..., description="Data source name"),
    query: str = Query(..., description="Query string (e.g. package name)"),
    horizon: int = Query(14, ge=1, le=365, description="Forecast horizon in days"),
    start: datetime.date | None = Query(None, description="Start date filter"),
    end: datetime.date | None = Query(None, description="End date filter"),
):
    """Fetch time-series data and run forecasting with multiple models."""
    try:
        adapter = registry.get(source)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Source '{source}' not found")

    try:
        ts = await adapter.fetch(query, start=start, end=end)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    try:
        return forecast(ts, horizon=horizon)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/insight")
async def insight_stream(
    source: str = Query(..., description="Data source name"),
    query: str = Query(..., description="Query string"),
    horizon: int = Query(14, ge=1, le=365, description="Forecast horizon"),
    start: datetime.date | None = Query(None),
    end: datetime.date | None = Query(None),
    prompt_version: str = Query("default", description="Prompt version"),
):
    """Stream AI commentary via SSE: fetch → analyze → forecast → LLM."""
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY not configured",
        )

    try:
        adapter = registry.get(source)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Source '{source}' not found")

    try:
        ts = await adapter.fetch(query, start=start, end=end)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    analysis = analyze(ts)
    forecast_result = forecast(ts, horizon=horizon)

    async def event_generator():
        accumulated = []
        try:
            async for chunk in summarize_stream(
                analysis,
                forecast_result,
                prompt_version=prompt_version,
            ):
                accumulated.append(chunk)
                yield f"event: delta\ndata: {json.dumps(chunk)}\n\n"

            full_text = "".join(accumulated)
            complete_data = {
                "source": analysis.source,
                "query": analysis.query,
                "summary": full_text,
                "prompt_version": prompt_version,
            }
            yield (f"event: complete\ndata: {json.dumps(complete_data)}\n\n")
        except Exception as e:
            logger.warning("Insight stream error", exc_info=True)
            yield f"event: error\ndata: {json.dumps(str(e))}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
