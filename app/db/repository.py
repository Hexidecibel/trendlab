import datetime
import hashlib
import json

from sqlalchemy import select

import app.db.engine as _engine_mod
from app.db.models import (
    AnalysisRecord,
    ForecastRecord,
    ForecastSnapshot,
    NotificationConfig,
    QueryConfig,
    SavedView,
    SeriesRecord,
    WatchlistItem,
)
from app.models.schemas import (
    DataPoint,
    ForecastComparison,
    SavedViewResponse,
    TimeSeries,
    TrendAnalysis,
    WatchlistItemResponse,
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


# --- Forecast Snapshots ---


async def save_forecast_snapshot(
    source: str,
    query: str,
    model_name: str,
    horizon: int,
    predictions: list[dict],
) -> int:
    """Save a forecast snapshot and return its id."""
    async with _engine_mod.async_session() as session:
        record = ForecastSnapshot(
            source=source,
            query=query,
            forecast_date=datetime.date.today(),
            horizon=horizon,
            model_name=model_name,
            predictions_json=json.dumps(predictions),
        )
        session.add(record)
        await session.commit()
        await session.refresh(record)
        return record.id


async def get_forecast_snapshots(
    source: str,
    query: str,
    limit: int = 10,
) -> list[dict]:
    """Get recent forecast snapshots for a source/query combination."""
    async with _engine_mod.async_session() as session:
        stmt = (
            select(ForecastSnapshot)
            .where(
                ForecastSnapshot.source == source,
                ForecastSnapshot.query == query,
            )
            .order_by(ForecastSnapshot.forecast_date.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        records = result.scalars().all()

        return [
            {
                "id": r.id,
                "source": r.source,
                "query": r.query,
                "forecast_date": r.forecast_date.isoformat(),
                "horizon": r.horizon,
                "model_name": r.model_name,
                "predictions": json.loads(r.predictions_json),
                "created_at": r.created_at.isoformat(),
            }
            for r in records
        ]


async def calculate_forecast_accuracy(
    snapshot_id: int,
    actual_points: list[DataPoint],
) -> dict | None:
    """Calculate accuracy metrics for a forecast snapshot against actual values."""
    async with _engine_mod.async_session() as session:
        stmt = select(ForecastSnapshot).where(ForecastSnapshot.id == snapshot_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if record is None:
            return None

        predictions = json.loads(record.predictions_json)
        actual_by_date = {str(p.date): p.value for p in actual_points}

        # Match predictions to actuals
        matched = []
        for pred in predictions:
            pred_date = pred["date"]
            if pred_date in actual_by_date:
                matched.append({
                    "date": pred_date,
                    "predicted": pred["value"],
                    "actual": actual_by_date[pred_date],
                    "lower_ci": pred.get("lower_ci"),
                    "upper_ci": pred.get("upper_ci"),
                })

        if not matched:
            return {
                "snapshot_id": snapshot_id,
                "matched_points": 0,
                "mae": None,
                "rmse": None,
                "within_ci_pct": None,
            }

        # Calculate metrics
        errors = [abs(m["predicted"] - m["actual"]) for m in matched]
        mae = sum(errors) / len(errors)
        rmse = (sum(e**2 for e in errors) / len(errors)) ** 0.5

        # Check how many actuals fell within CI
        within_ci = 0
        for m in matched:
            if m["lower_ci"] is not None and m["upper_ci"] is not None:
                if m["lower_ci"] <= m["actual"] <= m["upper_ci"]:
                    within_ci += 1

        within_ci_pct = (within_ci / len(matched) * 100) if matched else None

        return {
            "snapshot_id": snapshot_id,
            "forecast_date": record.forecast_date.isoformat(),
            "model_name": record.model_name,
            "matched_points": len(matched),
            "mae": round(mae, 4),
            "rmse": round(rmse, 4),
            "within_ci_pct": round(within_ci_pct, 1) if within_ci_pct else None,
            "details": matched,
        }


# --- Watchlist ---


def _watchlist_to_response(record: WatchlistItem) -> WatchlistItemResponse:
    """Convert DB record to response model."""
    return WatchlistItemResponse(
        id=record.id,
        name=record.name,
        source=record.source,
        query=record.query,
        resample=record.resample,
        threshold_direction=record.threshold_direction,
        threshold_value=(
            float(record.threshold_value) if record.threshold_value else None
        ),
        last_value=float(record.last_value) if record.last_value else None,
        last_checked_at=record.last_checked_at,
        created_at=record.created_at,
    )


async def add_watchlist_item(
    name: str,
    source: str,
    query: str,
    resample: str | None = None,
    threshold_direction: str | None = None,
    threshold_value: float | None = None,
) -> WatchlistItemResponse:
    """Add a new item to the watchlist."""
    async with _engine_mod.async_session() as session:
        record = WatchlistItem(
            name=name,
            source=source,
            query=query,
            resample=resample,
            threshold_direction=threshold_direction,
            threshold_value=int(threshold_value) if threshold_value else None,
        )
        session.add(record)
        await session.commit()
        await session.refresh(record)
        return _watchlist_to_response(record)


async def list_watchlist() -> list[WatchlistItemResponse]:
    """List all watchlist items, newest first."""
    async with _engine_mod.async_session() as session:
        stmt = select(WatchlistItem).order_by(WatchlistItem.created_at.desc())
        result = await session.execute(stmt)
        records = result.scalars().all()
        return [_watchlist_to_response(r) for r in records]


async def get_watchlist_item(item_id: int) -> WatchlistItemResponse | None:
    """Get a single watchlist item by ID."""
    async with _engine_mod.async_session() as session:
        stmt = select(WatchlistItem).where(WatchlistItem.id == item_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()
        if record is None:
            return None
        return _watchlist_to_response(record)


async def update_watchlist_item(
    item_id: int,
    last_value: float | None = None,
    last_checked_at: datetime.datetime | None = None,
) -> WatchlistItemResponse | None:
    """Update a watchlist item with new values."""
    async with _engine_mod.async_session() as session:
        stmt = select(WatchlistItem).where(WatchlistItem.id == item_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()
        if record is None:
            return None

        if last_value is not None:
            record.last_value = int(last_value)
        if last_checked_at is not None:
            record.last_checked_at = last_checked_at

        await session.commit()
        await session.refresh(record)
        return _watchlist_to_response(record)


async def delete_watchlist_item(item_id: int) -> bool:
    """Delete a watchlist item. Returns True if deleted."""
    async with _engine_mod.async_session() as session:
        stmt = select(WatchlistItem).where(WatchlistItem.id == item_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()
        if record is None:
            return False
        await session.delete(record)
        await session.commit()
        return True


# --- Notification Config ---


class NotificationConfigResponse:
    """Lightweight response object for notification config."""

    def __init__(
        self,
        webhook_url: str,
        channel: str,
        enabled: bool,
        created_at: datetime.datetime,
    ):
        self.webhook_url = webhook_url
        self.channel = channel
        self.enabled = enabled
        self.created_at = created_at


async def get_notification_config() -> NotificationConfigResponse | None:
    """Return the first (and only) notification config, or None."""
    async with _engine_mod.async_session() as session:
        stmt = select(NotificationConfig).limit(1)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()
        if record is None:
            return None
        return NotificationConfigResponse(
            webhook_url=record.webhook_url,
            channel=record.channel or "generic",
            enabled=bool(record.enabled),
            created_at=record.created_at,
        )


async def save_notification_config(
    webhook_url: str,
    channel: str = "generic",
    enabled: bool = True,
) -> NotificationConfigResponse:
    """Upsert the single notification config row."""
    async with _engine_mod.async_session() as session:
        stmt = select(NotificationConfig).limit(1)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if record:
            record.webhook_url = webhook_url
            record.channel = channel
            record.enabled = enabled
        else:
            record = NotificationConfig(
                webhook_url=webhook_url,
                channel=channel,
                enabled=enabled,
            )
            session.add(record)

        await session.commit()
        await session.refresh(record)
        return NotificationConfigResponse(
            webhook_url=record.webhook_url,
            channel=record.channel or "generic",
            enabled=bool(record.enabled),
            created_at=record.created_at,
        )
