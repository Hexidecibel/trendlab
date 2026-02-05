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
    """Wraps adapter.fetch() with DB-backed TTL caching and request deduplication."""

    DEFAULT_TTL = 3600  # 1 hour

    def __init__(
        self,
        ttl_seconds: dict[str, int] | None = None,
        default_ttl: int = DEFAULT_TTL,
    ):
        self.ttl_seconds = ttl_seconds or {}
        self.default_ttl = default_ttl
        # In-flight request deduplication: key -> Future
        self._inflight: dict[str, asyncio.Future[TimeSeries]] = {}

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

        # Check for in-flight request with same parameters
        cache_key = f"{source}:{query}:{start}:{end}"
        if cache_key in self._inflight:
            log.info("Waiting for in-flight request")
            return await self._inflight[cache_key]

        # Create a future for this request so others can wait on it
        loop = asyncio.get_event_loop()
        future: asyncio.Future[TimeSeries] = loop.create_future()
        self._inflight[cache_key] = future

        try:
            # Cache miss, stale, or forced refresh
            log.with_fields(cache_hit=False, refresh=refresh).info("Cache miss, fetching")
            start_time = time.perf_counter()
            ts = await adapter.fetch(query, start=start, end=end)
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            # Retry up to 3 times if empty (ASA API needs longer delays)
            retries = 0
            while not ts.points and retries < 3:
                retries += 1
                delay = retries * 1.0  # 1s, 2s, 3s
                log.info("Empty response, retry %d after %.1fs", retries, delay)
                await asyncio.sleep(delay)
                ts = await adapter.fetch(query, start=start, end=end)
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            log.with_fields(fetch_ms=round(elapsed_ms, 2), data_points=len(ts.points)).info(
                "Fetched from source"
            )

            # Only cache non-empty series to avoid caching transient API failures
            if _engine_mod.async_session is not None and ts.points:
                await save_series(ts, start_date=start, end_date=end)

            # Resolve the future so waiting requests get the result
            future.set_result(ts)
            return ts
        except Exception as e:
            future.set_exception(e)
            raise
        finally:
            # Clean up in-flight tracker
            self._inflight.pop(cache_key, None)

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
