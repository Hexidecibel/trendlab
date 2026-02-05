import datetime
import json

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from app.ai.query_parser import parse_and_resolve
from app.ai.summarizer import summarize_compare_stream, summarize_stream
from app.analysis.correlation import correlate as run_correlate
from app.analysis.engine import analyze
from app.config import settings
from app.data.registry import registry
from app.db import repository as repo
from app.forecasting.engine import forecast
from app.logging_config import get_logger
from app.middleware.auth import generate_session_token
from app.models.schemas import (
    CompareInsightFollowupRequest,
    CompareRequest,
    CompareResponse,
    CorrelateRequest,
    CorrelateResponse,
    DataSourceInfo,
    ForecastComparison,
    InsightFollowupRequest,
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

logger = get_logger(__name__)

router = APIRouter()
_cache = CachedFetcher(ttl_seconds=settings.cache_ttl)


class UnlockRequest(BaseModel):
    phrase: str


@router.get("/auth-status", tags=["System"])
async def auth_status():
    """Check if authentication is required."""
    return {"auth_required": settings.secret_phrase is not None}


@router.post("/unlock", tags=["System"])
async def unlock(request: UnlockRequest):
    """
    Unlock the app with the secret phrase.

    Returns a session cookie if the phrase is correct.
    """
    if not settings.secret_phrase:
        return {"status": "ok", "message": "No authentication required"}

    if request.phrase != settings.secret_phrase:
        raise HTTPException(status_code=401, detail="Invalid phrase")

    token = generate_session_token(settings.secret_phrase)
    response = JSONResponse({"status": "ok"})
    response.set_cookie(
        key="trendlab_session",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,  # 30 days
    )
    return response


@router.get("/", tags=["System"])
async def api_root():
    """API root endpoint with version information."""
    return {"message": "API v1"}


@router.get("/sources", response_model=list[DataSourceInfo], tags=["Data"])
async def list_sources():
    """
    List all available data sources.

    Returns metadata about each registered adapter including its name,
    description, and form fields for building queries.
    """
    return registry.list_sources()


@router.get("/lookup", response_model=list[LookupItem], tags=["Data"])
async def lookup(
    source: str = Query(..., description="Data source name"),
    lookup_type: str = Query(..., description="Lookup type (e.g. teams, players)"),
    league: str = Query("", description="League filter"),
    season: str = Query("", description="Season filter"),
    project: str = Query("", description="Wikipedia project (e.g. en.wikipedia)"),
    search: str = Query("", description="Search term for lookups"),
):
    """
    Get lookup values for autocomplete fields.

    Returns available options for dynamic form fields like team names,
    player names, or leagues. Used to populate dropdowns and autocomplete
    inputs in the UI.
    """
    try:
        adapter = registry.get(source)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Source '{source}' not found")

    kwargs: dict[str, str] = {}
    if league:
        kwargs["league"] = league
    if project:
        kwargs["project"] = project
    if search:
        kwargs["search"] = search
    if season:
        kwargs["season"] = season

    return await adapter.lookup(lookup_type, **kwargs)


@router.get("/series", response_model=TimeSeries, tags=["Data"])
async def get_series(
    source: str = Query(..., description="Data source name (e.g. pypi, coingecko)"),
    query: str = Query(..., description="Query string (e.g. package name, coin ID)"),
    start: datetime.date | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end: datetime.date | None = Query(None, description="End date (YYYY-MM-DD)"),
    refresh: bool = Query(False, description="Bypass cache and fetch fresh data"),
    resample: str | None = Query(
        None, description="Resample frequency: week, month, quarter, season"
    ),
    apply: str | None = Query(
        None,
        description="Pipe-delimited transforms: normalize, rolling_avg_Nd, etc.",
    ),
):
    """
    Fetch time-series data from a data source.

    Retrieves historical data points with optional date filtering, resampling
    to different time periods, and mathematical transforms for derived metrics.

    **Transforms available:**
    - `normalize` - Scale values to 0-1 range
    - `rolling_avg_7d` - 7-day rolling average (adjust N for other windows)
    - `pct_change` - Percent change from previous value
    - `cumulative` - Running total
    - `diff` - Difference from previous value

    Chain multiple transforms with pipes: `normalize|rolling_avg_7d`
    """
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


@router.get("/analyze", response_model=TrendAnalysis, tags=["Analysis"])
async def analyze_series(
    source: str = Query(..., description="Data source name"),
    query: str = Query(..., description="Query string (e.g. package name)"),
    start: datetime.date | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end: datetime.date | None = Query(None, description="End date (YYYY-MM-DD)"),
    anomaly_method: str = Query(
        "zscore", description="Anomaly detection method: zscore or iqr"
    ),
    refresh: bool = Query(False, description="Bypass cache and fetch fresh data"),
    resample: str | None = Query(
        None, description="Resample frequency: week, month, quarter, season"
    ),
    apply: str | None = Query(
        None,
        description="Pipe-delimited transforms: normalize, rolling_avg_Nd, etc.",
    ),
):
    """
    Analyze a time series for trends, seasonality, and anomalies.

    Performs comprehensive statistical analysis including:
    - **Trend detection**: Direction, momentum, acceleration, moving averages
    - **Seasonality**: Autocorrelation-based period detection
    - **Anomalies**: Outlier detection using z-score or IQR method
    - **Structural breaks**: Regime change detection using PELT algorithm
    """
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


@router.get("/forecast", response_model=ForecastComparison, tags=["Analysis"])
async def forecast_series(
    source: str = Query(..., description="Data source name"),
    query: str = Query(..., description="Query string (e.g. package name)"),
    horizon: int = Query(14, ge=1, le=365, description="Forecast horizon in days"),
    start: datetime.date | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end: datetime.date | None = Query(None, description="End date (YYYY-MM-DD)"),
    refresh: bool = Query(False, description="Bypass cache and fetch fresh data"),
    resample: str | None = Query(
        None, description="Resample frequency: week, month, quarter, season"
    ),
    apply: str | None = Query(
        None,
        description="Pipe-delimited transforms: normalize, rolling_avg_Nd, etc.",
    ),
):
    """
    Generate forecasts using multiple statistical models.

    Runs several forecasting models in parallel and returns predictions
    with confidence intervals:
    - **Naive**: Last value baseline
    - **Drift**: Linear extrapolation
    - **ETS**: Exponential smoothing (when sufficient data)
    - **ARIMA**: Auto-regressive integrated moving average

    Each model is evaluated on a holdout set with MAE, RMSE, and MAPE metrics.
    The response includes a recommended model based on evaluation scores.
    """
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


@router.post("/compare", response_model=CompareResponse, tags=["Comparison"])
async def compare_series(request: CompareRequest):
    """
    Compare 2-3 time series side by side.

    Fetches multiple series and returns them aligned for overlay visualization.
    Use `resample` to align series with different frequencies, and `apply`
    transforms like `normalize` to compare series with different scales.
    Includes trend analysis for each series (when data is available).
    """
    result_series: list[TimeSeries] = []
    result_analyses: list[TrendAnalysis] = []

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

        # Run trend analysis on each series (skip if empty)
        if ts.points:
            analysis = analyze(ts)
            result_analyses.append(analysis)

    return CompareResponse(
        series=result_series,
        analyses=result_analyses if result_analyses else None,
        count=len(result_series),
    )


@router.post("/compare-insight", tags=["Comparison"])
async def compare_insight_stream(request: CompareRequest):
    """
    Stream AI-generated comparison insights via Server-Sent Events (SSE).

    Fetches multiple series, analyzes each, then streams LLM commentary
    comparing trends, patterns, and performance across the series.

    Requires `ANTHROPIC_API_KEY` environment variable.
    """
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=503, detail="AI not configured")

    analyses: list[TrendAnalysis] = []
    labels: list[str] = []

    for item in request.items:
        try:
            adapter = registry.get(item.source)
        except KeyError:
            raise HTTPException(
                status_code=404, detail=f"Source '{item.source}' not found"
            )

        ts = await _cache.fetch(
            adapter, item.query, start=item.start, end=item.end, refresh=request.refresh
        )

        if request.resample:
            ts = resample_series(ts, request.resample, method=adapter.aggregation_method)
        if request.apply:
            ts = apply_transforms(ts, request.apply)

        # Skip empty series
        if not ts.points:
            continue

        analysis = analyze(ts)
        analyses.append(analysis)

        # Build friendly label from metadata
        meta = ts.metadata or {}
        label = (
            meta.get("article")
            or meta.get("team")
            or meta.get("player")
            or meta.get("package")
            or meta.get("coin")
            or meta.get("symbol")
            or meta.get("location")
            or item.query
        )
        # Add metric info for ASA
        if item.source == "asa" and meta.get("metric_label"):
            label = f"{label} - {meta.get('metric_label')}"
        labels.append(label)

    async def generate():
        try:
            async for chunk in summarize_compare_stream(analyses, labels):
                yield f"event: delta\ndata: {json.dumps(chunk)}\n\n"
            yield "event: complete\ndata: {}\n\n"
        except Exception as e:
            logger.error("Compare insight streaming failed: %s", e)
            yield f"event: error\ndata: {json.dumps(str(e))}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/correlate", response_model=CorrelateResponse, tags=["Comparison"])
async def correlate_series(request: CorrelateRequest):
    """
    Compute correlation between two time series.

    Returns:
    - **Pearson correlation**: Linear relationship strength (-1 to 1)
    - **Spearman correlation**: Monotonic relationship (rank-based)
    - **Lag analysis**: Correlations at different time offsets
    - **Scatter points**: Aligned (x, y) pairs for visualization

    Useful for answering questions like "Does Bitcoin price correlate
    with crypto library downloads?"
    """
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


@router.post(
    "/views", response_model=SavedViewResponse, status_code=201, tags=["Views"]
)
async def create_view(request: SaveViewRequest):
    """
    Save a view configuration for sharing.

    Persists the query parameters (source, query, date range, transforms, etc.)
    and returns a unique hash ID that can be used to recreate the exact view.
    """
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


@router.get("/views", response_model=list[SavedViewResponse], tags=["Views"])
async def get_views():
    """
    List all saved views.

    Returns all persisted view configurations sorted by creation date.
    """
    return await repo.list_views()


@router.get("/views/{hash_id}", response_model=SavedViewResponse, tags=["Views"])
async def get_view(hash_id: str):
    """
    Get a saved view by its hash ID.

    Use this to load a previously saved configuration from a shared link.
    """
    view = await repo.get_view_by_hash(hash_id)
    if view is None:
        raise HTTPException(status_code=404, detail="View not found")
    return view


@router.delete("/views/{hash_id}", status_code=204, tags=["Views"])
async def delete_view(hash_id: str):
    """
    Delete a saved view.

    Permanently removes a view configuration. Returns 204 on success.
    """
    deleted = await repo.delete_view(hash_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="View not found")


@router.get("/insight", tags=["AI"])
async def insight_stream(
    source: str = Query(..., description="Data source name"),
    query: str = Query(..., description="Query string"),
    horizon: int = Query(14, ge=1, le=365, description="Forecast horizon in days"),
    start: datetime.date | None = Query(None, description="Start date filter"),
    end: datetime.date | None = Query(None, description="End date filter"),
    prompt_version: str = Query("default", description="Prompt template version"),
):
    """
    Stream AI-generated insights via Server-Sent Events (SSE).

    Fetches data, runs analysis and forecasting, then streams LLM commentary
    explaining the trends, anomalies, and predictions in plain English.

    **Event types:**
    - `delta`: Incremental text chunk
    - `complete`: Full response with metadata
    - `error`: Error message if generation fails

    Requires `ANTHROPIC_API_KEY` environment variable.
    """
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
            logger.with_fields(
                source=source, query=query, error_type=type(e).__name__
            ).warning("Insight stream error", exc_info=True)
            yield f"event: error\ndata: {json.dumps(str(e))}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/natural-query", tags=["AI"])
async def natural_query(request: NaturalQueryRequest):
    """
    Parse natural language into structured query parameters.

    Converts plain English queries like "Show me PyPI downloads for requests
    over the last 90 days" into the appropriate source, query string, and
    date filters.

    Also supports multi-series comparison queries like "Compare Bitcoin and
    Ethereum prices this year".

    Requires `ANTHROPIC_API_KEY` environment variable.
    """
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


@router.post("/insight-followup", tags=["AI"])
async def insight_followup_stream(request: InsightFollowupRequest):
    """
    Stream AI response to a follow-up question about the data analysis.

    Takes the conversation history and streams a response that continues
    the discussion about the time series data.

    **Event types:**
    - `delta`: Incremental text chunk
    - `complete`: End of response
    - `error`: Error message if generation fails

    Requires `ANTHROPIC_API_KEY` environment variable.
    """
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY not configured",
        )

    from app.ai.client import LLMClient

    llm = LLMClient(api_key=settings.anthropic_api_key)

    # Build data context section if available
    data_section = ""
    if request.data_context:
        ctx = request.data_context
        data_section = f"""

DATA DETAILS:
- Date range: {ctx.date_range} ({ctx.data_points_count} points)
- Values: min={ctx.min_value:.2f}, max={ctx.max_value:.2f}, mean={ctx.mean_value:.2f}
- Trend: {ctx.trend_direction} (momentum: {ctx.trend_momentum:.4f})
- Seasonality: {"Yes, " + str(ctx.seasonality_period) + "-day period" if ctx.seasonality_detected else "None detected"}
- Anomalies: {ctx.anomaly_count} flagged
- Structural breaks: {len(ctx.structural_breaks)}

Recent values: {", ".join(f"{v['date']}: {v['value']:.2f}" for v in ctx.recent_values[-5:])}
"""
        if ctx.anomalies:
            anomaly_dates = ", ".join(a["date"] for a in ctx.anomalies[:5])
            data_section += f"Anomaly dates: {anomaly_dates}\n"
        if ctx.forecast_values:
            forecast_str = ", ".join(
                f"{v['date']}: {v['value']:.2f}" for v in ctx.forecast_values[:5]
            )
            data_section += f"Forecast ({ctx.forecast_horizon}d): {forecast_str}\n"

    # Build messages with system context
    system_prompt = f"""You are a helpful data analyst assistant. You previously provided an analysis
of time series data for {request.source} - {request.query}.

Your initial analysis was:
{request.context_summary}
{data_section}
Now answer the user's follow-up questions about this data. Be concise but thorough.
Use markdown formatting. You have access to the actual data details above - use them to give specific answers."""

    messages = [{"role": "system", "content": system_prompt}]
    for msg in request.messages:
        messages.append({"role": msg.role, "content": msg.content})

    async def generate():
        try:
            async for chunk in llm.stream(messages):
                yield f"event: delta\ndata: {json.dumps(chunk)}\n\n"
            yield "event: complete\ndata: {}\n\n"
        except Exception as e:
            logger.error("Insight followup streaming failed: %s", e)
            yield f"event: error\ndata: {json.dumps(str(e))}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/compare-insight-followup", tags=["AI"])
async def compare_insight_followup_stream(request: CompareInsightFollowupRequest):
    """
    Stream AI response to a follow-up question about the series comparison.

    Takes the conversation history and streams a response that continues
    the discussion about the compared time series.

    Requires `ANTHROPIC_API_KEY` environment variable.
    """
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY not configured",
        )

    from app.ai.client import LLMClient

    llm = LLMClient(api_key=settings.anthropic_api_key)

    # Build series descriptions for context
    series_desc = ", ".join(
        f"{item.source}:{item.query}" for item in request.items
    )

    # Build data context section for each series
    data_section = ""
    if request.data_contexts:
        for i, ctx in enumerate(request.data_contexts):
            item = request.items[i] if i < len(request.items) else None
            label = f"{item.source}:{item.query}" if item else f"Series {i+1}"
            data_section += f"""
{label}:
- Date range: {ctx.date_range} ({ctx.data_points_count} points)
- Values: min={ctx.min_value:.2f}, max={ctx.max_value:.2f}, mean={ctx.mean_value:.2f}
- Trend: {ctx.trend_direction} (momentum: {ctx.trend_momentum:.4f})
- Anomalies: {ctx.anomaly_count} flagged
"""
            if ctx.anomalies:
                data_section += f"  Anomaly dates: {', '.join(a['date'] for a in ctx.anomalies[:3])}\n"

    system_prompt = f"""You are a helpful data analyst assistant. You previously provided a comparison
analysis of multiple time series: {series_desc}

Your initial comparison was:
{request.context_summary}
{data_section}
Now answer the user's follow-up questions about this comparison. Be concise but thorough.
Use markdown formatting. You have access to the actual data details above - use them to give specific answers."""

    messages = [{"role": "system", "content": system_prompt}]
    for msg in request.messages:
        messages.append({"role": msg.role, "content": msg.content})

    async def generate():
        try:
            async for chunk in llm.stream(messages):
                yield f"event: delta\ndata: {json.dumps(chunk)}\n\n"
            yield "event: complete\ndata: {}\n\n"
        except Exception as e:
            logger.error("Compare insight followup streaming failed: %s", e)
            yield f"event: error\ndata: {json.dumps(str(e))}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
