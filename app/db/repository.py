import datetime
import hashlib
import json

from sqlalchemy import select

import app.db.engine as _engine_mod
from app.db.models import (
    AnalysisRecord,
    ForecastRecord,
    QueryConfig,
    SavedView,
    SeriesRecord,
)
from app.models.schemas import (
    DataPoint,
    ForecastComparison,
    SavedViewResponse,
    TimeSeries,
    TrendAnalysis,
)


def _serialize_points(points: list[DataPoint]) -> str:
    return json.dumps([{"date": str(p.date), "value": p.value} for p in points])


def _deserialize_points(raw: str) -> list[DataPoint]:
    return [DataPoint(date=d["date"], value=d["value"]) for d in json.loads(raw)]


async def save_series(
    ts: TimeSeries,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
) -> SeriesRecord:
    """Save or update a TimeSeries record. Returns the ORM record with id set."""
    async with _engine_mod.async_session() as session:
        # Check for existing record with same key
        stmt = select(SeriesRecord).where(
            SeriesRecord.source == ts.source,
            SeriesRecord.query == ts.query,
            SeriesRecord.start_date.is_(start_date)
            if start_date is None
            else SeriesRecord.start_date == start_date,
            SeriesRecord.end_date.is_(end_date)
            if end_date is None
            else SeriesRecord.end_date == end_date,
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.points_json = _serialize_points(ts.points)
            existing.metadata_json = json.dumps(ts.metadata) if ts.metadata else None
            existing.fetched_at = datetime.datetime.now(datetime.UTC)
            record = existing
        else:
            record = SeriesRecord(
                source=ts.source,
                query=ts.query,
                points_json=_serialize_points(ts.points),
                metadata_json=json.dumps(ts.metadata) if ts.metadata else None,
                fetched_at=datetime.datetime.now(datetime.UTC),
                start_date=start_date,
                end_date=end_date,
            )
            session.add(record)

        await session.commit()
        await session.refresh(record)
        return record


async def get_series(
    source: str,
    query: str,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
) -> TimeSeries | None:
    """Retrieve a cached TimeSeries or None if not found."""
    async with _engine_mod.async_session() as session:
        stmt = select(SeriesRecord).where(
            SeriesRecord.source == source,
            SeriesRecord.query == query,
            SeriesRecord.start_date.is_(start_date)
            if start_date is None
            else SeriesRecord.start_date == start_date,
            SeriesRecord.end_date.is_(end_date)
            if end_date is None
            else SeriesRecord.end_date == end_date,
        )
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if record is None:
            return None

        return TimeSeries(
            source=record.source,
            query=record.query,
            points=_deserialize_points(record.points_json),
            metadata=json.loads(record.metadata_json) if record.metadata_json else {},
        )


async def save_analysis(
    series_id: int,
    analysis: TrendAnalysis,
    anomaly_method: str = "zscore",
) -> AnalysisRecord:
    """Save an analysis result linked to a series record."""
    async with _engine_mod.async_session() as session:
        record = AnalysisRecord(
            series_id=series_id,
            result_json=analysis.model_dump_json(),
            anomaly_method=anomaly_method,
        )
        session.add(record)
        await session.commit()
        await session.refresh(record)
        return record


async def get_analysis(series_id: int) -> TrendAnalysis | None:
    """Retrieve the latest analysis for a series, or None."""
    async with _engine_mod.async_session() as session:
        stmt = (
            select(AnalysisRecord)
            .where(AnalysisRecord.series_id == series_id)
            .order_by(AnalysisRecord.created_at.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if record is None:
            return None

        return TrendAnalysis.model_validate_json(record.result_json)


async def save_forecast(
    series_id: int,
    forecast: ForecastComparison,
) -> ForecastRecord:
    """Save a forecast result linked to a series record."""
    async with _engine_mod.async_session() as session:
        record = ForecastRecord(
            series_id=series_id,
            result_json=forecast.model_dump_json(),
            horizon=forecast.horizon,
        )
        session.add(record)
        await session.commit()
        await session.refresh(record)
        return record


async def get_forecast(series_id: int, horizon: int) -> ForecastComparison | None:
    """Retrieve a forecast for a series with matching horizon, or None."""
    async with _engine_mod.async_session() as session:
        stmt = (
            select(ForecastRecord)
            .where(
                ForecastRecord.series_id == series_id,
                ForecastRecord.horizon == horizon,
            )
            .order_by(ForecastRecord.created_at.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if record is None:
            return None

        return ForecastComparison.model_validate_json(record.result_json)


async def save_query_config(
    source: str,
    query: str,
    horizon: int | None = None,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    params: dict | None = None,
) -> int:
    """Save a query config and return its id."""
    async with _engine_mod.async_session() as session:
        record = QueryConfig(
            source=source,
            query=query,
            horizon=horizon,
            start_date=start_date,
            end_date=end_date,
            params_json=json.dumps(params) if params else None,
        )
        session.add(record)
        await session.commit()
        await session.refresh(record)
        return record.id


async def get_query_config(config_id: int) -> dict | None:
    """Retrieve a query config by id, or None."""
    async with _engine_mod.async_session() as session:
        stmt = select(QueryConfig).where(QueryConfig.id == config_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if record is None:
            return None

        return {
            "id": record.id,
            "source": record.source,
            "query": record.query,
            "horizon": record.horizon,
            "start_date": record.start_date,
            "end_date": record.end_date,
            "params": json.loads(record.params_json) if record.params_json else {},
            "created_at": record.created_at,
        }


# --- Saved Views ---


def _generate_hash(source: str, query: str) -> str:
    """Generate a short hash ID from source, query, and current timestamp."""
    raw = f"{source}:{query}:{datetime.datetime.now(datetime.UTC).isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:8]


def _view_to_response(record: SavedView) -> SavedViewResponse:
    return SavedViewResponse(
        hash_id=record.hash_id,
        name=record.name,
        source=record.source,
        query=record.query,
        horizon=record.horizon,
        start=record.start_date,
        end=record.end_date,
        resample=record.resample,
        apply=record.apply,
        anomaly_method=record.anomaly_method,
        created_at=record.created_at,
    )


async def save_view(
    name: str,
    source: str,
    query: str,
    horizon: int = 14,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    resample: str | None = None,
    apply: str | None = None,
    anomaly_method: str = "zscore",
) -> SavedViewResponse:
    """Save a view config and return the response with hash_id."""
    hash_id = _generate_hash(source, query)

    async with _engine_mod.async_session() as session:
        record = SavedView(
            hash_id=hash_id,
            name=name,
            source=source,
            query=query,
            horizon=horizon,
            start_date=start_date,
            end_date=end_date,
            resample=resample,
            apply=apply,
            anomaly_method=anomaly_method,
        )
        session.add(record)
        await session.commit()
        await session.refresh(record)
        return _view_to_response(record)


async def get_view_by_hash(hash_id: str) -> SavedViewResponse | None:
    """Retrieve a saved view by hash_id, or None."""
    async with _engine_mod.async_session() as session:
        stmt = select(SavedView).where(SavedView.hash_id == hash_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()
        if record is None:
            return None
        return _view_to_response(record)


async def list_views() -> list[SavedViewResponse]:
    """List all saved views, newest first."""
    async with _engine_mod.async_session() as session:
        stmt = select(SavedView).order_by(SavedView.created_at.desc())
        result = await session.execute(stmt)
        records = result.scalars().all()
        return [_view_to_response(r) for r in records]


async def delete_view(hash_id: str) -> bool:
    """Delete a saved view by hash_id. Returns True if deleted."""
    async with _engine_mod.async_session() as session:
        stmt = select(SavedView).where(SavedView.hash_id == hash_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()
        if record is None:
            return False
        await session.delete(record)
        await session.commit()
        return True
