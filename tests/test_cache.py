import datetime
from unittest.mock import AsyncMock

import pytest

import app.db.engine as db_engine
from app.models.schemas import DataPoint, TimeSeries
from app.services.cache import CachedFetcher


def _make_series(value: float = 100.0) -> TimeSeries:
    return TimeSeries(
        source="pypi",
        query="fastapi",
        points=[DataPoint(date=datetime.date(2025, 1, 1), value=value)],
    )


@pytest.fixture
async def db():
    await db_engine.init_db("sqlite+aiosqlite://")
    yield


@pytest.fixture
def mock_adapter():
    adapter = AsyncMock()
    adapter.name = "pypi"
    adapter.fetch = AsyncMock(return_value=_make_series(100.0))
    return adapter


class TestCacheHit:
    async def test_second_fetch_uses_cache(self, db, mock_adapter):
        """Fetch twice within TTL — adapter.fetch called only once."""
        fetcher = CachedFetcher(ttl_seconds={"pypi": 3600})
        await fetcher.fetch(mock_adapter, "fastapi")
        result = await fetcher.fetch(mock_adapter, "fastapi")

        assert mock_adapter.fetch.call_count == 1
        assert result.points[0].value == 100.0

    async def test_cache_returns_correct_data(self, db, mock_adapter):
        """Cached result matches original data."""
        fetcher = CachedFetcher(ttl_seconds={"pypi": 3600})
        original = await fetcher.fetch(mock_adapter, "fastapi")
        cached = await fetcher.fetch(mock_adapter, "fastapi")

        assert original.source == cached.source
        assert original.query == cached.query
        assert len(original.points) == len(cached.points)


class TestCacheMiss:
    async def test_expired_ttl_triggers_fresh_fetch(self, db, mock_adapter):
        """After TTL expires, adapter.fetch is called again."""
        fetcher = CachedFetcher(ttl_seconds={"pypi": 0})  # 0 = always stale
        await fetcher.fetch(mock_adapter, "fastapi")
        await fetcher.fetch(mock_adapter, "fastapi")

        assert mock_adapter.fetch.call_count == 2

    async def test_different_queries_not_shared(self, db, mock_adapter):
        """Different query strings are cached independently."""
        fetcher = CachedFetcher(ttl_seconds={"pypi": 3600})
        await fetcher.fetch(mock_adapter, "fastapi")
        await fetcher.fetch(mock_adapter, "django")

        assert mock_adapter.fetch.call_count == 2


class TestCacheBypass:
    async def test_refresh_skips_cache(self, db, mock_adapter):
        """refresh=True always calls adapter.fetch."""
        fetcher = CachedFetcher(ttl_seconds={"pypi": 3600})
        await fetcher.fetch(mock_adapter, "fastapi")
        await fetcher.fetch(mock_adapter, "fastapi", refresh=True)

        assert mock_adapter.fetch.call_count == 2

    async def test_refresh_updates_cached_value(self, db, mock_adapter):
        """After refresh, subsequent reads get the new data."""
        fetcher = CachedFetcher(ttl_seconds={"pypi": 3600})
        await fetcher.fetch(mock_adapter, "fastapi")

        mock_adapter.fetch.return_value = _make_series(200.0)
        await fetcher.fetch(mock_adapter, "fastapi", refresh=True)

        result = await fetcher.fetch(mock_adapter, "fastapi")
        assert result.points[0].value == 200.0
        # 3 calls: initial, refresh, and NOT a third (cache hit)
        assert mock_adapter.fetch.call_count == 2


class TestDefaultTTL:
    async def test_uses_default_ttl_for_unknown_source(self, db, mock_adapter):
        """Sources not in ttl_seconds dict use the default TTL."""
        mock_adapter.name = "unknown_source"
        mock_adapter.fetch.return_value = TimeSeries(
            source="unknown_source",
            query="test",
            points=[DataPoint(date=datetime.date(2025, 1, 1), value=50.0)],
        )
        fetcher = CachedFetcher(ttl_seconds={"pypi": 3600}, default_ttl=7200)
        await fetcher.fetch(mock_adapter, "test")
        await fetcher.fetch(mock_adapter, "test")

        assert mock_adapter.fetch.call_count == 1


class TestDateRangeCache:
    async def test_different_date_ranges_cached_separately(self, db, mock_adapter):
        """Same source+query with different date ranges are separate entries."""
        fetcher = CachedFetcher(ttl_seconds={"pypi": 3600})
        await fetcher.fetch(
            mock_adapter,
            "fastapi",
            start=datetime.date(2025, 1, 1),
            end=datetime.date(2025, 1, 31),
        )
        await fetcher.fetch(
            mock_adapter,
            "fastapi",
            start=datetime.date(2025, 2, 1),
            end=datetime.date(2025, 2, 28),
        )

        assert mock_adapter.fetch.call_count == 2
