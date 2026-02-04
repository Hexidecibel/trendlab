import datetime
import json

from sqlalchemy import select

import app.db.engine as _engine_mod
from app.db.models import SeriesRecord
from app.db.repository import _deserialize_points, save_series
from app.models.schemas import TimeSeries


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

        if not refresh and _engine_mod.async_session is not None:
            cached = await self._get_fresh(source, query, start, end)
            if cached is not None:
                return cached

        # Cache miss, stale, or forced refresh
        ts = await adapter.fetch(query, start=start, end=end)
        if _engine_mod.async_session is not None:
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
            stmt = select(SeriesRecord).where(
                SeriesRecord.source == source,
                SeriesRecord.query == query,
                SeriesRecord.start_date.is_(start)
                if start is None
                else SeriesRecord.start_date == start,
                SeriesRecord.end_date.is_(end)
                if end is None
                else SeriesRecord.end_date == end,
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

            return TimeSeries(
                source=record.source,
                query=record.query,
                points=_deserialize_points(record.points_json),
                metadata=json.loads(record.metadata_json)
                if record.metadata_json
                else {},
            )
