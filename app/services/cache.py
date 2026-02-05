import asyncio
import datetime
import json
import time

from sqlalchemy import select

import app.db.engine as _engine_mod
from app.db.models import SeriesRecord
from app.db.repository import _deserialize_points, save_series
from app.logging_config import get_logger
from app.models.schemas import TimeSeries

logger = get_logger(__name__)


class CachedFetcher:
    """Wraps adapter.fetch() with DB-backed TTL caching."""

    DEFAULT_TTL = 3600  # 1 hour

    def __init__(
        self,
        ttl_seconds: dict[str, int] | None = None,
        default_ttl: int = DEFAULT_TTL,
    ):
        self.ttl_seconds = ttl_seconds or {}
        self.default_ttl = default_ttl

    def _get_ttl(self, source: str) -> int:
        return self.ttl_seconds.get(source, self.default_ttl)

    async def fetch(
        self,
        adapter,
        query: str,
        start: datetime.date | None = None,
        end: datetime.date | None = None,
        refresh: bool = False,
    ) -> TimeSeries:
        source = adapter.name
        log = logger.with_fields(source=source, query=query)

        if not refresh and _engine_mod.async_session is not None:
            cached = await self._get_fresh(source, query, start, end)
            if cached is not None:
                log.with_fields(cache_hit=True, data_points=len(cached.points)).info(
                    "Cache hit"
                )
                return cached

        # Cache miss, stale, or forced refresh
        log.with_fields(cache_hit=False, refresh=refresh).info("Cache miss, fetching")
        start_time = time.perf_counter()
        ts = await adapter.fetch(query, start=start, end=end)
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # Retry once if empty (API may have transient issues)
        if not ts.points:
            log.info("Empty response, retrying once")
            await asyncio.sleep(0.5)
            ts = await adapter.fetch(query, start=start, end=end)
            elapsed_ms = (time.perf_counter() - start_time) * 1000

        log.with_fields(fetch_ms=round(elapsed_ms, 2), data_points=len(ts.points)).info(
            "Fetched from source"
        )

        # Only cache non-empty series to avoid caching transient API failures
        if _engine_mod.async_session is not None and ts.points:
            await save_series(ts, start_date=start, end_date=end)
        return ts

    async def _get_fresh(
        self,
        source: str,
        query: str,
        start: datetime.date | None,
        end: datetime.date | None,
    ) -> TimeSeries | None:
        """Return cached TimeSeries if fresh, else None."""
        async with _engine_mod.async_session() as session:
            stmt = (
                select(SeriesRecord)
                .where(
                    SeriesRecord.source == source,
                    SeriesRecord.query == query,
                    SeriesRecord.start_date.is_(start)
                    if start is None
                    else SeriesRecord.start_date == start,
                    SeriesRecord.end_date.is_(end)
                    if end is None
                    else SeriesRecord.end_date == end,
                )
                .order_by(SeriesRecord.fetched_at.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()

            if record is None:
                return None

            ttl = self._get_ttl(source)
            fetched_at = record.fetched_at
            if fetched_at.tzinfo is None:
                fetched_at = fetched_at.replace(tzinfo=datetime.UTC)
            age = datetime.datetime.now(datetime.UTC) - fetched_at

            if age.total_seconds() >= ttl:
                return None

            # Reject empty cached series - they're likely stale/invalid
            points = _deserialize_points(record.points_json)
            if not points:
                return None

            return TimeSeries(
                source=record.source,
                query=record.query,
                points=points,
                metadata=json.loads(record.metadata_json)
                if record.metadata_json
                else {},
            )
