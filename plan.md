# Implementation Plans

> Phases 1-6 plans archived to FEATURES.md. This file is for active planning only.

---

## Tier 1: Data Foundation

### Item 1: SQLite Persistence
**Status:** planned
**Tier:** 1 — Data Foundation

#### Requirements
- Store raw TimeSeries data (source, query, points, metadata) so repeated queries hit the DB instead of external APIs
- Store analysis results (TrendAnalysis) and forecast results (ForecastComparison) keyed by series
- Store query configs (source, query, params, date range) for future shareable URLs
- Use SQLite via SQLAlchemy async (aiosqlite driver)
- Auto-create tables on app startup
- Alembic for migrations from day one — avoids painful retrofitting later

#### Files to Create/Modify
- `app/db/__init__.py` — package init
- `app/db/engine.py` — async SQLAlchemy engine, session factory, init_db()
- `app/db/models.py` — SQLAlchemy ORM models (SeriesRecord, AnalysisRecord, ForecastRecord, QueryRecord)
- `app/db/repository.py` — CRUD functions: save_series(), get_series(), save_analysis(), etc.
- `app/config.py` — add DATABASE_URL setting (default: `sqlite+aiosqlite:///./trendlab.db`)
- `app/main.py` — call init_db() in lifespan startup
- `alembic.ini` + `alembic/` — migration setup

#### DB Schema
```
series_records:
  id            INTEGER PRIMARY KEY
  source        TEXT NOT NULL
  query         TEXT NOT NULL
  points_json   TEXT NOT NULL        -- JSON serialized list[DataPoint]
  metadata_json TEXT
  fetched_at    DATETIME NOT NULL
  start_date    DATE
  end_date      DATE
  UNIQUE(source, query, start_date, end_date)

analysis_records:
  id            INTEGER PRIMARY KEY
  series_id     INTEGER FK → series_records.id
  result_json   TEXT NOT NULL        -- JSON serialized TrendAnalysis
  anomaly_method TEXT
  created_at    DATETIME NOT NULL

forecast_records:
  id            INTEGER PRIMARY KEY
  series_id     INTEGER FK → series_records.id
  result_json   TEXT NOT NULL        -- JSON serialized ForecastComparison
  horizon       INTEGER NOT NULL
  created_at    DATETIME NOT NULL

query_configs:
  id            INTEGER PRIMARY KEY
  source        TEXT NOT NULL
  query         TEXT NOT NULL
  horizon       INTEGER
  start_date    DATE
  end_date      DATE
  params_json   TEXT                 -- any extra params (resample, apply, etc.)
  created_at    DATETIME NOT NULL
```

Note: Complex nested models (TrendAnalysis, ForecastComparison) serialize to JSON columns rather than fully normalized tables. These are read-heavy, write-once results — JSON keeps it simple and avoids a dozen join tables for nested structures like MovingAverage → DataPoint.

#### Implementation Steps
1. Add dependencies: `sqlalchemy[asyncio]`, `aiosqlite`, `alembic`
2. Create `app/db/engine.py` with async engine + session factory
3. Create `app/db/models.py` with SQLAlchemy ORM models
4. Create `app/db/repository.py` with async CRUD functions
5. Add `DATABASE_URL` to `app/config.py`
6. Initialize Alembic, generate initial migration
7. Wire `init_db()` into FastAPI lifespan in `app/main.py`
8. Write tests

#### Dependencies to Add
- `sqlalchemy[asyncio]` — async ORM
- `aiosqlite` — async SQLite driver
- `alembic` — schema migrations

#### Tests Needed
- Test DB engine creation and table init
- Test save/retrieve TimeSeries round-trip (points survive JSON serialization)
- Test save/retrieve TrendAnalysis round-trip
- Test save/retrieve ForecastComparison round-trip
- Test unique constraint on series_records (source, query, date range)
- Test QueryConfig save/lookup

---

### Item 2: Caching Layer
**Status:** planned
**Tier:** 1 — Data Foundation

#### Requirements
- TTL-based cache: if a series was fetched within TTL, return from DB instead of hitting external API
- Configurable TTLs per source (crypto prices change faster than PyPI downloads)
- Cache-aware fetch: check DB first → if fresh, return cached → if stale or missing, fetch from adapter → save to DB → return
- Analysis and forecast results cached alongside their series (invalidated when series is re-fetched)
- Cache bypass option (`?refresh=true`) for forcing a fresh fetch

#### Files to Create/Modify
- `app/services/cache.py` — CachedFetcher class wrapping adapter.fetch() with DB lookup
- `app/config.py` — add default TTL and per-source TTL overrides
- `app/routers/api.py` — replace direct `adapter.fetch()` calls with `cached_fetch()`; add `refresh` query param
- `app/db/repository.py` — add `get_fresh_series(source, query, ttl)` that checks age

#### Cache Flow
```
Request → cached_fetch(source, query, start, end)
  ├─ DB lookup: series_records WHERE source=X AND query=Y AND date range matches
  ├─ If found AND (now - fetched_at) < TTL → return cached TimeSeries
  ├─ If stale or missing → adapter.fetch() → save to DB → return fresh
  └─ If refresh=true → skip cache, always fetch fresh
```

#### Default TTLs
- `crypto`: 15 minutes (prices move fast)
- `pypi`: 6 hours (daily aggregates, updated once/day)
- `asa`: 24 hours (game data doesn't change retroactively)
- `github_stars`: 1 hour
- `football`: 24 hours

#### Implementation Steps
1. Add TTL config to `app/config.py` (dict of source → seconds)
2. Add `get_fresh_series()` to repository (checks fetched_at vs TTL)
3. Create `app/services/cache.py` with `CachedFetcher` class
4. Update all endpoints in `api.py` to use CachedFetcher instead of raw adapter.fetch()
5. Add `refresh: bool = False` query param to series/analyze/forecast endpoints
6. When series is re-fetched, delete stale analysis/forecast records for that series
7. Write tests

#### Dependencies to Add
- None (uses persistence layer from Item 1)

#### Tests Needed
- Test cache hit: fetch once, fetch again within TTL → no second API call
- Test cache miss: fetch with expired TTL → triggers fresh fetch
- Test cache bypass with refresh=true
- Test stale analysis/forecast cleanup on re-fetch
- Test per-source TTL configuration
- Test cache behavior with date range variations

---

### Item 3: Time-Based Aggregation
**Status:** planned
**Tier:** 1 — Data Foundation

#### Requirements
- Optional `resample` query param on `/series`, `/analyze`, `/forecast` endpoints
- Supported frequencies: `day` (default/no-op), `week`, `month`, `quarter`, `season`
- Aggregation method: `sum` for counts (PyPI downloads), `mean` for rates/prices (crypto, xG)
- Adapter declares its preferred aggregation method (new field on DataAdapter)
- Applied between fetch and downstream consumers (analysis, forecast, response)
- "season" frequency is sport-specific: maps to calendar year for ASA (MLS season ≈ Feb-Nov)

#### Files to Create/Modify
- `app/services/aggregation.py` — `resample_series(ts: TimeSeries, freq: str) -> TimeSeries` utility
- `app/data/base.py` — add `aggregation_method: str = "mean"` to DataAdapter base
- `app/data/adapters/pypi.py` — override `aggregation_method = "sum"`
- `app/routers/api.py` — add `resample: str | None = None` param to series/analyze/forecast; apply after fetch
- `app/models/schemas.py` — add `resample` to metadata in returned TimeSeries so frontend knows the frequency

#### Aggregation Logic
```python
def resample_series(ts: TimeSeries, freq: str, method: str = "mean") -> TimeSeries:
    # Group points by period bucket (week start, month start, quarter start)
    # Apply method (sum or mean) to each bucket
    # Return new TimeSeries with one point per bucket
    # Use the bucket start date as the point date
```

Period buckets:
- `week`: ISO week start (Monday)
- `month`: 1st of month
- `quarter`: Jan 1, Apr 1, Jul 1, Oct 1
- `season`: full calendar year (Jan 1)

#### Implementation Steps
1. Create `app/services/aggregation.py` with `resample_series()` function
2. Add `aggregation_method` property to `DataAdapter` base class
3. Override to `"sum"` in PyPI adapter (downloads are additive)
4. Add `resample` query param to `/series`, `/analyze`, `/forecast` endpoints
5. Apply resampling in router between fetch and analysis/forecast
6. Include `resample` in TimeSeries metadata so frontend can label axes correctly
7. Write tests

#### Dependencies to Add
- None (uses numpy which is already a dependency for date/value grouping)

#### Tests Needed
- Test weekly aggregation: 14 daily points → 2 weekly points
- Test monthly aggregation: 60 daily points → 2 monthly points
- Test sum vs mean aggregation methods
- Test no-op when resample=day or resample=None
- Test sparse data (ASA games): aggregation fills period even with few points
- Test quarter and season bucketing
- Test that metadata includes resample frequency
- Test aggregation integrates correctly with analysis engine (no crashes on shorter series)

---
