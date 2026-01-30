import datetime

from fastapi import APIRouter, HTTPException, Query

from app.data.registry import registry
from app.models.schemas import DataSourceInfo, TimeSeries

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
