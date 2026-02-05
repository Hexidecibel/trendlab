import datetime
import json
import logging

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.ai.query_parser import parse_and_resolve
from app.ai.summarizer import summarize_stream
from app.analysis.correlation import correlate as run_correlate
from app.analysis.engine import analyze
from app.config import settings
from app.data.registry import registry
from app.db import repository as repo
from app.forecasting.engine import forecast
from app.models.schemas import (
    CompareRequest,
    CompareResponse,
    CorrelateRequest,
    CorrelateResponse,
    DataSourceInfo,
    ForecastComparison,
    LookupItem,
    NaturalQueryError,
    NaturalQueryRequest,
    SavedViewResponse,
    SaveViewRequest,
    TimeSeries,
    TrendAnalysis,
)
from app.services.aggregation import resample_series
from app.services.cache import CachedFetcher
from app.services.transforms import apply_transforms

logger = logging.getLogger(__name__)

router = APIRouter()
_cache = CachedFetcher(ttl_seconds=settings.cache_ttl)


@router.get("/")
async def api_root():
    """API root endpoint."""
    return {"message": "API v1"}


@router.get("/sources", response_model=list[DataSourceInfo])
async def list_sources():
    """List all available data sources."""
    return registry.list_sources()


@router.get("/lookup", response_model=list[LookupItem])
async def lookup(
    source: str = Query(..., description="Data source name"),
    lookup_type: str = Query(..., description="Lookup type (e.g. teams, players)"),
    league: str = Query("", description="League filter"),
    season: str = Query("", description="Season filter"),
):
    """Return lookup items for autocomplete fields."""
    try:
        adapter = registry.get(source)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Source '{source}' not found")

    kwargs: dict[str, str] = {}
    if league:
        kwargs["league"] = league
    if season:
        kwargs["season"] = season

    return await adapter.lookup(lookup_type, **kwargs)


@router.get("/series", response_model=TimeSeries)
async def get_series(
    source: str = Query(..., description="Data source name"),
    query: str = Query(..., description="Query string (e.g. package name)"),
    start: datetime.date | None = Query(None, description="Start date filter"),
    end: datetime.date | None = Query(None, description="End date filter"),
    refresh: bool = Query(False, description="Bypass cache"),
    resample: str | None = Query(
        None, description="Resample frequency: week, month, quarter, season"
    ),
    apply: str | None = Query(
        None,
        description="Pipe-delimited transforms, e.g. normalize|rolling_avg_7d",
    ),
):
    """Fetch time-series data from a named source."""
    try:
        adapter = registry.get(source)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Source '{source}' not found")

    try:
        ts = await _cache.fetch(adapter, query, start=start, end=end, refresh=refresh)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if resample:
        ts = resample_series(ts, resample, method=adapter.aggregation_method)
    if apply:
        ts = apply_transforms(ts, apply)
    return ts


@router.get("/analyze", response_model=TrendAnalysis)
async def analyze_series(
    source: str = Query(..., description="Data source name"),
    query: str = Query(..., description="Query string (e.g. package name)"),
    start: datetime.date | None = Query(None, description="Start date filter"),
    end: datetime.date | None = Query(None, description="End date filter"),
    anomaly_method: str = Query(
        "zscore", description="Anomaly detection method: zscore or iqr"
    ),
    refresh: bool = Query(False, description="Bypass cache"),
    resample: str | None = Query(
        None, description="Resample frequency: week, month, quarter, season"
    ),
    apply: str | None = Query(
        None,
        description="Pipe-delimited transforms, e.g. normalize|rolling_avg_7d",
    ),
):
    """Fetch time-series data and run trend analysis."""
    try:
        adapter = registry.get(source)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Source '{source}' not found")

    try:
        ts = await _cache.fetch(adapter, query, start=start, end=end, refresh=refresh)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if resample:
        ts = resample_series(ts, resample, method=adapter.aggregation_method)
    if apply:
        ts = apply_transforms(ts, apply)

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
    refresh: bool = Query(False, description="Bypass cache"),
    resample: str | None = Query(
        None, description="Resample frequency: week, month, quarter, season"
    ),
    apply: str | None = Query(
        None,
        description="Pipe-delimited transforms, e.g. normalize|rolling_avg_7d",
    ),
):
    """Fetch time-series data and run forecasting with multiple models."""
    try:
        adapter = registry.get(source)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Source '{source}' not found")

    try:
        ts = await _cache.fetch(adapter, query, start=start, end=end, refresh=refresh)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if resample:
        ts = resample_series(ts, resample, method=adapter.aggregation_method)
    if apply:
        ts = apply_transforms(ts, apply)

    try:
        return forecast(ts, horizon=horizon)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/compare", response_model=CompareResponse)
async def compare_series(request: CompareRequest):
    """Fetch and return multiple series for side-by-side comparison."""
    result_series: list[TimeSeries] = []

    for item in request.items:
        try:
            adapter = registry.get(item.source)
        except KeyError:
            raise HTTPException(
                status_code=404, detail=f"Source '{item.source}' not found"
            )

        try:
            ts = await _cache.fetch(
                adapter,
                item.query,
                start=item.start,
                end=item.end,
                refresh=request.refresh,
            )
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

        if request.resample:
            ts = resample_series(
                ts, request.resample, method=adapter.aggregation_method
            )
        if request.apply:
            ts = apply_transforms(ts, request.apply)

        result_series.append(ts)

    return CompareResponse(series=result_series, count=len(result_series))


@router.post("/correlate", response_model=CorrelateResponse)
async def correlate_series(request: CorrelateRequest):
    """Compute correlation between two time series."""
    items = [request.series_a, request.series_b]
    series_list: list[TimeSeries] = []

    for item in items:
        try:
            adapter = registry.get(item.source)
        except KeyError:
            raise HTTPException(
                status_code=404,
                detail=f"Source '{item.source}' not found",
            )

        start = item.start or request.start
        end = item.end or request.end

        try:
            ts = await _cache.fetch(
                adapter,
                item.query,
                start=start,
                end=end,
                refresh=request.refresh,
            )
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

        if request.resample:
            ts = resample_series(
                ts, request.resample, method=adapter.aggregation_method
            )

        series_list.append(ts)

    try:
        return run_correlate(series_list[0], series_list[1])
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/views", response_model=SavedViewResponse, status_code=201)
async def create_view(request: SaveViewRequest):
    """Save a view configuration and return a shareable hash."""
    return await repo.save_view(
        name=request.name,
        source=request.source,
        query=request.query,
        horizon=request.horizon,
        start_date=request.start,
        end_date=request.end,
        resample=request.resample,
        apply=request.apply,
        anomaly_method=request.anomaly_method,
    )


@router.get("/views", response_model=list[SavedViewResponse])
async def get_views():
    """List all saved views."""
    return await repo.list_views()


@router.get("/views/{hash_id}", response_model=SavedViewResponse)
async def get_view(hash_id: str):
    """Get a saved view by its hash ID."""
    view = await repo.get_view_by_hash(hash_id)
    if view is None:
        raise HTTPException(status_code=404, detail="View not found")
    return view


@router.delete("/views/{hash_id}", status_code=204)
async def delete_view(hash_id: str):
    """Delete a saved view."""
    deleted = await repo.delete_view(hash_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="View not found")


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
        ts = await _cache.fetch(adapter, query, start=start, end=end)
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


@router.post("/natural-query")
async def natural_query(request: NaturalQueryRequest):
    """Parse natural language into structured query parameters."""
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY not configured",
        )

    result = await parse_and_resolve(request.text)

    if isinstance(result, NaturalQueryError):
        raise HTTPException(
            status_code=422,
            detail={
                "error": result.error,
                "suggestions": result.suggestions,
            },
        )

    return result
