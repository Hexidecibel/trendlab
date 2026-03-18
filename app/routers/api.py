import datetime
import json

from fastapi import APIRouter, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from app.ai.query_parser import parse_and_resolve
from app.ai.summarizer import (
    generate_headline,
    summarize_compare_stream,
    summarize_stream,
)
from app.analysis.causal_impact import analyze_causal_impact
from app.analysis.correlation import correlate as run_correlate
from app.analysis.engine import analyze
from app.config import settings
from app.data.adapters.csv_upload import (
    delete_upload,
    list_uploads,
    parse_csv_content,
    store_upload,
)
from app.data.registry import registry
from app.db import repository as repo
from app.forecasting.engine import forecast
from app.logging_config import get_logger
from app.middleware.auth import generate_session_token
from app.models.plugin_schemas import PluginInfo
from app.models.schemas import (
    CausalImpactResponse,
    CohortRequest,
    CohortResponse,
    CompareInsightFollowupRequest,
    CompareRequest,
    CompareResponse,
    CorrelateRequest,
    CorrelateResponse,
    DataSourceInfo,
    EventContext,
    ForecastComparison,
    InsightFollowupRequest,
    LookupItem,
    NaturalQueryError,
    NaturalQueryRequest,
    NotificationConfigRequest,
    NotificationConfigResponse,
    NotificationStatusResponse,
    SavedViewResponse,
    SaveViewRequest,
    TimeSeries,
    TrendAnalysis,
    WatchlistAddRequest,
    WatchlistCheckResponse,
    WatchlistItemResponse,
)
from app.plugins import reload_plugins, scan_plugins
from app.services.aggregation import resample_series
from app.services.cache import CachedFetcher
from app.services.pdf_export import generate_pdf_report
from app.services.progress import current_request_id, emit_progress
from app.services.transforms import apply_transforms
from app.services.watchlist_checker import (
    check_watchlist as run_watchlist_check,
)

logger = get_logger(__name__)

router = APIRouter()
_cache = CachedFetcher(ttl_seconds=settings.cache_ttl)


def friendly_http_error(
    status_code: int,
    detail: str,
    hint: str | None = None,
    error_code: str | None = None,
) -> HTTPException:
    """Raise an HTTPException with a structured detail dict
    for friendly error display."""
    return HTTPException(
        status_code=status_code,
        detail={"detail": detail, "hint": hint, "error_code": error_code},
    )


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
        raise friendly_http_error(
            401,
            "Invalid phrase",
            hint="Enter the correct access phrase to unlock the app.",
            error_code="INVALID_PHRASE",
        )

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
        raise friendly_http_error(
            404,
            f"Source '{source}' not found",
            hint="Check /api/sources for available data sources.",
            error_code="SOURCE_NOT_FOUND",
        )

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


class CSVUploadResponse(BaseModel):
    upload_id: str
    name: str
    points_count: int


@router.post("/upload-csv", response_model=CSVUploadResponse, tags=["Data"])
async def upload_csv(
    file: UploadFile,
    name: str = Form(..., description="Name for the uploaded dataset"),
):
    """
    Upload a CSV file for analysis.

    The CSV should have at least two columns: one for dates and one for values.
    The adapter will auto-detect common column names like 'date', 'value', 'count', etc.

    **Supported date formats:**
    - YYYY-MM-DD (preferred)
    - YYYY/MM/DD
    - MM/DD/YYYY
    - DD/MM/YYYY

    Returns an upload_id that can be used with source='csv' in other endpoints.
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise friendly_http_error(
            400,
            "Please upload a CSV file",
            hint="Make sure the file is a .csv file with UTF-8 encoding.",
            error_code="INVALID_FILE_TYPE",
        )

    try:
        content = await file.read()
        content_str = content.decode("utf-8")
    except UnicodeDecodeError:
        raise friendly_http_error(
            400,
            "Could not decode file",
            hint="Make sure the file is UTF-8 encoded CSV with a date column.",
            error_code="FILE_DECODE_ERROR",
        )

    try:
        series = parse_csv_content(content_str, name)
    except ValueError as e:
        raise friendly_http_error(
            400,
            str(e),
            hint="Make sure the file is UTF-8 encoded CSV with a date column.",
            error_code="CSV_PARSE_ERROR",
        )

    upload_id = store_upload(name, series)
    return CSVUploadResponse(
        upload_id=upload_id,
        name=name,
        points_count=len(series.points),
    )


class CSVListItem(BaseModel):
    upload_id: str
    name: str
    points_count: int
    created_at: datetime.datetime


@router.get("/uploads", response_model=list[CSVListItem], tags=["Data"])
async def get_uploads():
    """
    List all uploaded CSV datasets.

    Returns metadata about each upload including ID, name, and point count.
    """
    uploads = list_uploads()
    return [
        CSVListItem(
            upload_id=u.upload_id,
            name=u.name,
            points_count=len(u.series.points),
            created_at=u.created_at,
        )
        for u in uploads
    ]


@router.delete("/uploads/{upload_id}", status_code=204, tags=["Data"])
async def remove_upload(upload_id: str):
    """
    Delete an uploaded CSV dataset.

    Permanently removes the uploaded data. Returns 204 on success.
    """
    if not delete_upload(upload_id):
        raise friendly_http_error(
            404,
            "Upload not found",
            hint="The uploaded dataset may have expired. Try uploading again.",
            error_code="UPLOAD_NOT_FOUND",
        )


@router.get("/series", response_model=TimeSeries, tags=["Data"])
async def get_series(
    request: Request,
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
    req_id = getattr(request.state, "request_id", None)
    token = current_request_id.set(req_id)
    try:
        try:
            adapter = registry.get(source)
        except KeyError:
            raise friendly_http_error(
                404,
                f"Source '{source}' not found",
                hint="Check /api/sources for available data sources.",
                error_code="SOURCE_NOT_FOUND",
            )

        emit_progress("cache_check", 0.1, "Checking cache")
        try:
            emit_progress("fetch", 0.3, f"Fetching from {source}")
            ts = await _cache.fetch(
                adapter, query, start=start, end=end, refresh=refresh
            )
        except ValueError as e:
            raise friendly_http_error(
                404,
                str(e),
                hint="Double-check the spelling, or try searching with /api/lookup.",
                error_code="ENTITY_NOT_FOUND",
            )

        if resample:
            ts = resample_series(
                ts,
                resample,
                method=adapter.aggregation_method,
                adapter=adapter,
            )
        if apply:
            ts = apply_transforms(ts, apply)

        emit_progress("complete", 1.0, "Done")
        return ts
    finally:
        current_request_id.reset(token)


@router.get("/analyze", response_model=TrendAnalysis, tags=["Analysis"])
async def analyze_series(
    request: Request,
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
    req_id = getattr(request.state, "request_id", None)
    token = current_request_id.set(req_id)
    try:
        try:
            adapter = registry.get(source)
        except KeyError:
            raise friendly_http_error(
                404,
                f"Source '{source}' not found",
                hint="Check /api/sources for available data sources.",
                error_code="SOURCE_NOT_FOUND",
            )

        emit_progress("cache_check", 0.1, "Checking cache")
        try:
            emit_progress("fetch", 0.3, f"Fetching from {source}")
            ts = await _cache.fetch(
                adapter, query, start=start, end=end, refresh=refresh
            )
        except ValueError as e:
            raise friendly_http_error(
                404,
                str(e),
                hint="Double-check the spelling, or try searching with /api/lookup.",
                error_code="ENTITY_NOT_FOUND",
            )

        if resample:
            ts = resample_series(
                ts,
                resample,
                method=adapter.aggregation_method,
                adapter=adapter,
            )
        if apply:
            ts = apply_transforms(ts, apply)

        emit_progress("analyze", 0.6, "Running analysis")
        try:
            result = analyze(ts, anomaly_method=anomaly_method)
        except ValueError as e:
            raise friendly_http_error(
                404,
                str(e),
                hint="Double-check the spelling, or try searching with /api/lookup.",
                error_code="ENTITY_NOT_FOUND",
            )

        emit_progress("complete", 1.0, "Done")
        return result
    finally:
        current_request_id.reset(token)


@router.get("/forecast", response_model=ForecastComparison, tags=["Analysis"])
async def forecast_series(
    request: Request,
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
    req_id = getattr(request.state, "request_id", None)
    token = current_request_id.set(req_id)
    try:
        try:
            adapter = registry.get(source)
        except KeyError:
            raise friendly_http_error(
                404,
                f"Source '{source}' not found",
                hint="Check /api/sources for available data sources.",
                error_code="SOURCE_NOT_FOUND",
            )

        emit_progress("cache_check", 0.1, "Checking cache")
        try:
            emit_progress("fetch", 0.3, f"Fetching from {source}")
            ts = await _cache.fetch(
                adapter, query, start=start, end=end, refresh=refresh
            )
        except ValueError as e:
            raise friendly_http_error(
                404,
                str(e),
                hint="Double-check the spelling, or try searching with /api/lookup.",
                error_code="ENTITY_NOT_FOUND",
            )

        if resample:
            ts = resample_series(
                ts,
                resample,
                method=adapter.aggregation_method,
                adapter=adapter,
            )
        if apply:
            ts = apply_transforms(ts, apply)

        emit_progress("forecast", 0.9, "Running forecast models")
        try:
            result = forecast(ts, horizon=horizon)
        except ValueError as e:
            raise friendly_http_error(
                404,
                str(e),
                hint="Double-check the spelling, or try searching with /api/lookup.",
                error_code="ENTITY_NOT_FOUND",
            )

        emit_progress("complete", 1.0, "Done")
        return result
    finally:
        current_request_id.reset(token)


class ForecastSnapshotResponse(BaseModel):
    id: int
    source: str
    query: str
    forecast_date: str
    horizon: int
    model_name: str
    predictions: list[dict]
    created_at: str


class AccuracyResponse(BaseModel):
    snapshot_id: int
    forecast_date: str | None = None
    model_name: str | None = None
    matched_points: int
    mae: float | None
    rmse: float | None
    within_ci_pct: float | None
    details: list[dict] | None = None


@router.post("/forecast-snapshot", tags=["Analysis"])
async def save_forecast_snapshot_endpoint(
    source: str = Query(..., description="Data source name"),
    query: str = Query(..., description="Query string"),
    model_name: str = Query(..., description="Model name (e.g. arima, ets)"),
    horizon: int = Query(14, ge=1, le=365, description="Forecast horizon in days"),
):
    """
    Save a forecast snapshot for later accuracy tracking.

    Stores the current forecast predictions so they can be compared
    against actual values once that data becomes available.
    """
    try:
        adapter = registry.get(source)
    except KeyError:
        raise friendly_http_error(
            404,
            f"Source '{source}' not found",
            hint="Check /api/sources for available data sources.",
            error_code="SOURCE_NOT_FOUND",
        )

    try:
        ts = await _cache.fetch(adapter, query)
    except ValueError as e:
        raise friendly_http_error(
            404,
            str(e),
            hint="Double-check the spelling, or try searching with /api/lookup.",
            error_code="ENTITY_NOT_FOUND",
        )

    forecast_result = forecast(ts, horizon=horizon)

    # Find the requested model
    model_forecast = next(
        (f for f in forecast_result.forecasts if f.model_name == model_name),
        None,
    )
    if model_forecast is None:
        raise HTTPException(
            status_code=400,
            detail=f"Model '{model_name}' not found in forecast results",
        )

    # Save snapshot
    predictions = [
        {
            "date": str(p.date),
            "value": p.value,
            "lower_ci": p.lower_ci,
            "upper_ci": p.upper_ci,
        }
        for p in model_forecast.points
    ]

    snapshot_id = await repo.save_forecast_snapshot(
        source=source,
        query=query,
        model_name=model_name,
        horizon=horizon,
        predictions=predictions,
    )

    return {"snapshot_id": snapshot_id, "message": "Forecast snapshot saved"}


@router.get(
    "/forecast-snapshots",
    response_model=list[ForecastSnapshotResponse],
    tags=["Analysis"],
)
async def get_forecast_snapshots(
    source: str = Query(..., description="Data source name"),
    query: str = Query(..., description="Query string"),
    limit: int = Query(10, ge=1, le=50, description="Max results to return"),
):
    """
    Get saved forecast snapshots for a source/query combination.

    Returns past forecast predictions that can be compared against
    actual values for accuracy tracking.
    """
    snapshots = await repo.get_forecast_snapshots(source, query, limit=limit)
    return snapshots


@router.get("/forecast-accuracy", response_model=AccuracyResponse, tags=["Analysis"])
async def get_forecast_accuracy(
    snapshot_id: int = Query(..., description="Forecast snapshot ID"),
    source: str = Query(..., description="Data source name"),
    query: str = Query(..., description="Query string"),
):
    """
    Calculate accuracy metrics for a past forecast.

    Compares the saved forecast predictions against actual values
    and returns error metrics (MAE, RMSE) and confidence interval coverage.
    """
    try:
        adapter = registry.get(source)
    except KeyError:
        raise friendly_http_error(
            404,
            f"Source '{source}' not found",
            hint="Check /api/sources for available data sources.",
            error_code="SOURCE_NOT_FOUND",
        )

    # Fetch current (actual) data
    try:
        ts = await _cache.fetch(adapter, query)
    except ValueError as e:
        raise friendly_http_error(
            404,
            str(e),
            hint="Double-check the spelling, or try searching with /api/lookup.",
            error_code="ENTITY_NOT_FOUND",
        )

    # Calculate accuracy
    accuracy = await repo.calculate_forecast_accuracy(snapshot_id, ts.points)

    if accuracy is None:
        raise friendly_http_error(
            404,
            "Snapshot not found",
            hint="This forecast snapshot may have expired or been deleted.",
            error_code="SNAPSHOT_NOT_FOUND",
        )

    return accuracy


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
            raise friendly_http_error(
                404,
                f"Source '{item.source}' not found",
                hint="Check /api/sources for available data sources.",
                error_code="SOURCE_NOT_FOUND",
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
            raise friendly_http_error(
                404,
                str(e),
                hint="Double-check the spelling, or try searching with /api/lookup.",
                error_code="ENTITY_NOT_FOUND",
            )

        if request.resample:
            ts = resample_series(
                ts, request.resample, method=adapter.aggregation_method, adapter=adapter
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
        raise friendly_http_error(
            503,
            "AI features are not available",
            hint="The AI features require an API key. Contact the administrator.",
            error_code="AI_NOT_CONFIGURED",
        )

    analyses: list[TrendAnalysis] = []
    labels: list[str] = []

    for item in request.items:
        try:
            adapter = registry.get(item.source)
        except KeyError:
            raise friendly_http_error(
                404,
                f"Source '{item.source}' not found",
                hint="Check /api/sources for available data sources.",
                error_code="SOURCE_NOT_FOUND",
            )

        ts = await _cache.fetch(
            adapter, item.query, start=item.start, end=item.end, refresh=request.refresh
        )

        if request.resample:
            ts = resample_series(
                ts, request.resample, method=adapter.aggregation_method, adapter=adapter
            )
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


@router.post("/cohort", response_model=CohortResponse, tags=["Comparison"])
async def cohort_comparison(request: CohortRequest):
    """
    Compare a cohort of series from the same source.

    Normalizes each series to percentage change from day 1, computes
    per-member stats (total return, max drawdown, volatility), and ranks
    members by total return.
    """
    import asyncio
    import datetime as dt

    from app.analysis.cohort import analyze_cohort

    try:
        adapter = registry.get(request.source)
    except KeyError:
        raise friendly_http_error(
            404,
            f"Source '{request.source}' not found",
            hint="Check /api/sources for available data sources.",
            error_code="SOURCE_NOT_FOUND",
        )

    start = dt.date.fromisoformat(request.start_date) if request.start_date else None
    end = dt.date.fromisoformat(request.end_date) if request.end_date else None

    async def fetch_one(query: str) -> TimeSeries:
        return await _cache.fetch(adapter, query, start=start, end=end)

    try:
        all_series = await asyncio.gather(*(fetch_one(q) for q in request.queries))
    except ValueError as e:
        raise friendly_http_error(
            404,
            str(e),
            hint="Double-check the spelling, or try searching with /api/lookup.",
            error_code="ENTITY_NOT_FOUND",
        )

    members = analyze_cohort(list(all_series), normalize=request.normalize)

    # Determine period bounds from actual data
    all_dates = [p.date for ts in all_series for p in ts.points]
    period_start = str(min(all_dates)) if all_dates else None
    period_end = str(max(all_dates)) if all_dates else None

    return CohortResponse(
        source=request.source,
        members=members,
        period_start=period_start,
        period_end=period_end,
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
            raise friendly_http_error(
                404,
                f"Source '{item.source}' not found",
                hint="Check /api/sources for available data sources.",
                error_code="SOURCE_NOT_FOUND",
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
            raise friendly_http_error(
                404,
                str(e),
                hint="Double-check the spelling, or try searching with /api/lookup.",
                error_code="ENTITY_NOT_FOUND",
            )

        if request.resample:
            ts = resample_series(
                ts, request.resample, method=adapter.aggregation_method, adapter=adapter
            )

        series_list.append(ts)

    try:
        return run_correlate(series_list[0], series_list[1])
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


class CausalImpactRequest(BaseModel):
    source: str
    query: str
    event_date: str
    start: datetime.date | None = None
    end: datetime.date | None = None
    resample: str | None = None
    apply: str | None = None
    refresh: bool = False


@router.post(
    "/causal-impact",
    response_model=CausalImpactResponse,
    tags=["Analysis"],
)
async def causal_impact(request: CausalImpactRequest):
    """
    Estimate the causal impact of an event on a time series.

    Splits the series at the event date, builds a counterfactual forecast
    from the pre-period, and measures how far the post-period deviates.

    Returns:
    - **pointwise**: Actual vs predicted for each post-period point with CI
    - **cumulative_impact**: Total deviation from the counterfactual
    - **relative_impact_pct**: Cumulative impact as a percentage of predicted
    - **p_value**: Statistical significance of the impact
    - **significant**: Whether p < 0.05
    """
    try:
        adapter = registry.get(request.source)
    except KeyError:
        raise friendly_http_error(
            404,
            f"Source '{request.source}' not found",
            hint="Check /api/sources for available data sources.",
            error_code="SOURCE_NOT_FOUND",
        )

    try:
        ts = await _cache.fetch(
            adapter,
            request.query,
            start=request.start,
            end=request.end,
            refresh=request.refresh,
        )
    except ValueError as e:
        raise friendly_http_error(
            404,
            str(e),
            hint="Double-check the spelling, or try searching with /api/lookup.",
            error_code="ENTITY_NOT_FOUND",
        )

    if request.resample:
        ts = resample_series(
            ts, request.resample, method=adapter.aggregation_method, adapter=adapter
        )
    if request.apply:
        ts = apply_transforms(ts, request.apply)

    try:
        return await analyze_causal_impact(ts, request.event_date)
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
        raise friendly_http_error(
            404,
            "View not found",
            hint="This saved view may have been deleted.",
            error_code="VIEW_NOT_FOUND",
        )
    return view


@router.delete("/views/{hash_id}", status_code=204, tags=["Views"])
async def delete_view(hash_id: str):
    """
    Delete a saved view.

    Permanently removes a view configuration. Returns 204 on success.
    """
    deleted = await repo.delete_view(hash_id)
    if not deleted:
        raise friendly_http_error(
            404,
            "View not found",
            hint="This saved view may have been deleted.",
            error_code="VIEW_NOT_FOUND",
        )


# --- Watchlist Endpoints ---


@router.post("/watchlist", response_model=WatchlistItemResponse, tags=["Watchlist"])
async def add_to_watchlist(request: WatchlistAddRequest):
    """
    Add a trend to the watchlist.

    Watch a specific source/query combination and optionally set a threshold
    to be notified when the value crosses it.

    **Threshold options:**
    - `threshold_direction`: "above" or "below"
    - `threshold_value`: The numeric threshold to watch for
    """
    return await repo.add_watchlist_item(
        name=request.name,
        source=request.source,
        query=request.query,
        resample=request.resample,
        threshold_direction=request.threshold_direction,
        threshold_value=request.threshold_value,
    )


@router.get("/watchlist", tags=["Watchlist"])
async def list_watchlist() -> list[WatchlistItemResponse]:
    """
    List all watchlist items.

    Returns all watched trends, newest first.
    """
    return await repo.list_watchlist()


@router.get("/watchlist/check", tags=["Watchlist"])
async def check_watchlist() -> WatchlistCheckResponse:
    """
    Refresh and check all watchlist items.

    Fetches the latest value for each watched trend and checks if any
    thresholds have been crossed. Returns all items with their current
    status and a list of triggered alerts.
    """
    return await run_watchlist_check(cache=_cache)


@router.get(
    "/watchlist/{item_id}", response_model=WatchlistItemResponse, tags=["Watchlist"]
)
async def get_watchlist_item(item_id: int):
    """
    Get a single watchlist item by ID.
    """
    item = await repo.get_watchlist_item(item_id)
    if item is None:
        raise friendly_http_error(
            404,
            "Watchlist item not found",
            hint="This watchlist item may have been deleted.",
            error_code="WATCHLIST_ITEM_NOT_FOUND",
        )
    return item


@router.delete("/watchlist/{item_id}", status_code=204, tags=["Watchlist"])
async def delete_from_watchlist(item_id: int):
    """
    Remove a trend from the watchlist.
    """
    deleted = await repo.delete_watchlist_item(item_id)
    if not deleted:
        raise friendly_http_error(
            404,
            "Watchlist item not found",
            hint="This watchlist item may have been deleted.",
            error_code="WATCHLIST_ITEM_NOT_FOUND",
        )


# --- Notification endpoints ---


@router.get(
    "/notifications/config",
    response_model=NotificationConfigResponse | None,
    tags=["Notifications"],
)
async def get_notification_config():
    """Return the current notification config, or null."""
    cfg = await repo.get_notification_config()
    if cfg is None:
        return None
    return NotificationConfigResponse(
        webhook_url=cfg.webhook_url,
        channel=cfg.channel,
        enabled=cfg.enabled,
        created_at=cfg.created_at,
    )


@router.post(
    "/notifications/config",
    response_model=NotificationConfigResponse,
    tags=["Notifications"],
)
async def save_notification_config(
    request: NotificationConfigRequest,
):
    """Save or update the notification webhook config."""
    cfg = await repo.save_notification_config(
        webhook_url=request.webhook_url,
        channel=request.channel,
        enabled=request.enabled,
    )
    return NotificationConfigResponse(
        webhook_url=cfg.webhook_url,
        channel=cfg.channel,
        enabled=cfg.enabled,
        created_at=cfg.created_at,
    )


@router.get(
    "/notifications/status",
    response_model=NotificationStatusResponse,
    tags=["Notifications"],
)
async def get_notification_status():
    """Return the notification scheduler status."""
    from app.notifications.scheduler import notification_scheduler

    return NotificationStatusResponse(
        running=notification_scheduler.running,
        last_check=(
            notification_scheduler.last_check.isoformat()
            if notification_scheduler.last_check
            else None
        ),
        next_check=(
            notification_scheduler.next_check.isoformat()
            if notification_scheduler.next_check
            else None
        ),
        interval=settings.notification_check_interval,
    )


@router.post("/notifications/test", tags=["Notifications"])
async def test_notification():
    """Send a test webhook with dummy alert data."""
    cfg = await repo.get_notification_config()
    if cfg is None:
        raise friendly_http_error(
            400,
            "No notification config found",
            hint="Save a webhook URL first.",
            error_code="NO_NOTIFICATION_CONFIG",
        )

    from app.notifications.webhook import send_webhook

    dummy_alert = WatchlistItemResponse(
        id=0,
        name="Test Alert",
        source="test",
        query="test_query",
        threshold_direction="above",
        threshold_value=100.0,
        last_value=150.0,
        created_at=datetime.datetime.now(datetime.UTC),
        triggered=True,
        trend_direction="rising",
    )

    ok = await send_webhook(cfg.webhook_url, cfg.channel, [dummy_alert])
    if ok:
        return {"status": "ok", "message": "Test webhook sent"}
    raise friendly_http_error(
        502,
        "Webhook delivery failed",
        hint="Check that the URL is correct and reachable.",
        error_code="WEBHOOK_FAILED",
    )


@router.get("/export-pdf", tags=["Analysis"])
async def export_pdf(
    source: str = Query(..., description="Data source name"),
    query: str = Query(..., description="Query string"),
    horizon: int = Query(14, ge=1, le=365, description="Forecast horizon in days"),
    start: datetime.date | None = Query(None, description="Start date filter"),
    end: datetime.date | None = Query(None, description="End date filter"),
    resample: str | None = Query(None, description="Resample frequency"),
    apply: str | None = Query(None, description="Transforms to apply"),
):
    """
    Export analysis as a PDF report.

    Generates a comprehensive PDF document including:
    - Summary statistics
    - Trend analysis results
    - Time series chart with forecast
    - Model evaluation metrics

    Returns a downloadable PDF file.
    """
    try:
        adapter = registry.get(source)
    except KeyError:
        raise friendly_http_error(
            404,
            f"Source '{source}' not found",
            hint="Check /api/sources for available data sources.",
            error_code="SOURCE_NOT_FOUND",
        )

    try:
        ts = await _cache.fetch(adapter, query, start=start, end=end)
    except ValueError as e:
        raise friendly_http_error(
            404,
            str(e),
            hint="Double-check the spelling, or try searching with /api/lookup.",
            error_code="ENTITY_NOT_FOUND",
        )

    if resample:
        ts = resample_series(
            ts, resample, method=adapter.aggregation_method, adapter=adapter
        )
    if apply:
        ts = apply_transforms(ts, apply)

    analysis = analyze(ts)
    forecast_result = forecast(ts, horizon=horizon)

    # Generate PDF
    pdf_buffer = generate_pdf_report(ts, analysis, forecast_result)

    filename = f"trendlab-{source}-{query}-{datetime.date.today()}.pdf"

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
        raise friendly_http_error(
            404,
            f"Source '{source}' not found",
            hint="Check /api/sources for available data sources.",
            error_code="SOURCE_NOT_FOUND",
        )

    try:
        ts = await _cache.fetch(adapter, query, start=start, end=end)
    except ValueError as e:
        raise friendly_http_error(
            404,
            str(e),
            hint="Double-check the spelling, or try searching with /api/lookup.",
            error_code="ENTITY_NOT_FOUND",
        )

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


class InsightFeedItem(BaseModel):
    source: str
    query: str
    headline: str
    trend_direction: str
    momentum: float


@router.get("/insights-feed", response_model=list[InsightFeedItem], tags=["AI"])
async def insights_feed(
    limit: int = Query(5, ge=1, le=10, description="Number of insights to return"),
):
    """
    Get AI-generated headline summaries for trending data.

    Analyzes recent/popular queries and generates one-sentence headlines
    describing key trends. Useful for "What's interesting today?" dashboards.

    Requires `ANTHROPIC_API_KEY` environment variable.
    """
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY not configured",
        )

    # Predefined interesting queries to analyze
    sample_queries = [
        ("pypi", "fastapi"),
        ("pypi", "requests"),
        ("coingecko", "bitcoin"),
        ("coingecko", "ethereum"),
        ("npm", "react"),
        ("npm", "express"),
    ]

    insights: list[InsightFeedItem] = []

    for source, query in sample_queries[:limit]:
        try:
            adapter = registry.get(source)
            ts = await _cache.fetch(adapter, query)

            if not ts.points:
                continue

            analysis = analyze(ts)

            # Generate AI headline
            label = ts.metadata.get("package") or ts.metadata.get("coin") or query
            headline = await generate_headline(analysis, label)

            insights.append(
                InsightFeedItem(
                    source=source,
                    query=query,
                    headline=headline.strip(),
                    trend_direction=analysis.trend.direction,
                    momentum=analysis.trend.momentum,
                )
            )
        except Exception as e:
            logger.warning("Failed to generate insight for %s:%s: %s", source, query, e)
            continue

        if len(insights) >= limit:
            break

    return insights


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
- Seasonality: {
            "Yes, " + str(ctx.seasonality_period) + "-day period"
            if ctx.seasonality_detected
            else "None detected"
        }
- Anomalies: {ctx.anomaly_count} flagged
- Structural breaks: {len(ctx.structural_breaks)}

Recent values: {
            ", ".join(f"{v['date']}: {v['value']:.2f}" for v in ctx.recent_values[-5:])
        }
"""
        if ctx.anomalies:
            anomaly_dates = ", ".join(
                a["date"] for a in ctx.anomalies[:5]
            )
            data_section += (
                f"Anomaly dates: {anomaly_dates}\n"
            )
        if ctx.forecast_values:
            forecast_str = ", ".join(
                f"{v['date']}: {v['value']:.2f}"
                for v in ctx.forecast_values[:5]
            )
            data_section += (
                f"Forecast ({ctx.forecast_horizon}d):"
                f" {forecast_str}\n"
            )

    # Fetch event context for anomaly dates
    event_section = ""
    if request.data_context and request.data_context.anomalies:
        try:
            from app.ai.event_context import (
                fetch_event_context,
            )

            dates = [
                a["date"]
                for a in request.data_context.anomalies[:5]
            ]
            topic = f"{request.source} {request.query}"
            events = await fetch_event_context(
                topic, dates
            )
            if events:
                lines = []
                for ev in events:
                    src = (
                        f" ({ev.source_url})"
                        if ev.source_url
                        else ""
                    )
                    lines.append(
                        f"- {ev.date}: "
                        f'"{ev.headline}"{src}'
                    )
                event_section = (
                    "\nRELEVANT EVENTS:\n"
                    + "\n".join(lines)
                    + "\n"
                )
                data_section += event_section
        except Exception:
            logger.debug(
                "Event context fetch failed for "
                "followup: %s",
                request.query,
            )

    # Build messages with system context
    has_events = bool(event_section)
    event_instruction = (
        " You also have real-world event context"
        " for anomaly dates - reference these events"
        " when explaining data movements or spikes."
        if has_events
        else ""
    )
    system_prompt = (
        f"You are a helpful data analyst assistant."
        f" You previously provided an analysis"
        f" of time series data for {request.source}"
        f" - {request.query}.\n\n"
        f"Your initial analysis was:\n"
        f"{request.context_summary}\n"
        f"{data_section}\n"
        f"Now answer the user's follow-up questions"
        f" about this data. Be concise but thorough.\n"
        f"Use markdown formatting. You have access to"
        f" the actual data details above - use them"
        f" to give specific answers."
        f"{event_instruction}"
    )

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
    series_desc = ", ".join(f"{item.source}:{item.query}" for item in request.items)

    # Build data context section for each series
    data_section = ""
    if request.data_contexts:
        for i, ctx in enumerate(request.data_contexts):
            item = request.items[i] if i < len(request.items) else None
            label = f"{item.source}:{item.query}" if item else f"Series {i + 1}"
            data_section += f"""
{label}:
- Date range: {ctx.date_range} ({ctx.data_points_count} points)
- Values: min={ctx.min_value:.2f}, max={ctx.max_value:.2f}, mean={ctx.mean_value:.2f}
- Trend: {ctx.trend_direction} (momentum: {ctx.trend_momentum:.4f})
- Anomalies: {ctx.anomaly_count} flagged
"""
            if ctx.anomalies:
                anomaly_str = ", ".join(
                    a["date"]
                    for a in ctx.anomalies[:3]
                )
                data_section += (
                    f"  Anomaly dates: {anomaly_str}\n"
                )

    # Fetch event context for anomaly dates
    event_section = ""
    if request.data_contexts:
        try:
            from app.ai.event_context import (
                fetch_event_context,
            )

            all_dates: list[str] = []
            topic_parts: list[str] = []
            for i, ctx in enumerate(
                request.data_contexts
            ):
                if ctx.anomalies:
                    all_dates.extend(
                        a["date"]
                        for a in ctx.anomalies[:3]
                    )
                item = (
                    request.items[i]
                    if i < len(request.items)
                    else None
                )
                if item:
                    topic_parts.append(
                        f"{item.source} {item.query}"
                    )
            if all_dates:
                topic = (
                    topic_parts[0]
                    if topic_parts
                    else series_desc
                )
                # Deduplicate dates
                unique_dates = list(
                    dict.fromkeys(all_dates)
                )
                events = await fetch_event_context(
                    topic, unique_dates
                )
                if events:
                    lines = []
                    for ev in events:
                        src = (
                            f" ({ev.source_url})"
                            if ev.source_url
                            else ""
                        )
                        lines.append(
                            f"- {ev.date}: "
                            f'"{ev.headline}"{src}'
                        )
                    event_section = (
                        "\nRELEVANT EVENTS:\n"
                        + "\n".join(lines)
                        + "\n"
                    )
                    data_section += event_section
        except Exception:
            logger.debug(
                "Event context fetch failed for "
                "compare followup"
            )

    has_events = bool(event_section)
    event_instruction = (
        " You also have real-world event context"
        " for anomaly dates - reference these events"
        " when explaining data movements or spikes."
        if has_events
        else ""
    )
    system_prompt = (
        f"You are a helpful data analyst assistant."
        f" You previously provided a comparison"
        f" analysis of multiple time series:"
        f" {series_desc}\n\n"
        f"Your initial comparison was:\n"
        f"{request.context_summary}\n"
        f"{data_section}\n"
        f"Now answer the user's follow-up questions"
        f" about this comparison. Be concise but"
        f" thorough.\n"
        f"Use markdown formatting. You have access to"
        f" the actual data details above - use them"
        f" to give specific answers."
        f"{event_instruction}"
    )

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


@router.get(
    "/event-context",
    response_model=list[EventContext],
    tags=["AI"],
)
async def event_context(
    source: str = Query(..., description="Data source name"),
    query: str = Query(..., description="Query string"),
    dates: str = Query(
        ...,
        description="Comma-separated dates (YYYY-MM-DD)",
    ),
):
    """
    Fetch real-world event context for specific dates.

    Queries DuckDuckGo and Wikipedia to find events
    that may explain anomalies or spikes in the data.
    Best-effort: returns empty list on failure.
    """
    from app.ai.event_context import fetch_event_context

    date_list = [d.strip() for d in dates.split(",") if d.strip()]
    topic = f"{source} {query}"
    return await fetch_event_context(topic, date_list)


# --- Plugin management ---


@router.get(
    "/plugins",
    response_model=list[PluginInfo],
    tags=["System"],
)
async def list_plugins():
    """
    List all discovered plugins with their status.

    Scans the plugins/ directory for flat .py files and
    directory plugins with plugin.json manifests.
    """
    return scan_plugins()


@router.post(
    "/plugins/reload",
    response_model=list[PluginInfo],
    tags=["System"],
)
async def reload_plugins_endpoint():
    """
    Re-scan and re-load all plugins.

    Unregisters existing plugin adapters and re-imports them.
    Returns the updated plugin list.
    """
    return reload_plugins()
