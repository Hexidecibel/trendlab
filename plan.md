# Implementation Plans

> Phases 1-6 plans archived to FEATURES.md. This file is for active planning only.

---

## Tier 1: Data Foundation

### Item 1: SQLite Persistence
**Status:** done
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
**Status:** done
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
**Status:** done
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

## Tier 2: Core Features

### Item 4: Multi-Series Comparison
**Status:** done
**Tier:** 2 — Core Features

#### Requirements
- Compare 2–3 entities on the same chart (e.g. two MLS teams' xG, or Bitcoin vs Ethereum)
- API endpoint accepts multiple series specs, returns all series in one response
- Frontend overlays multiple series with distinct colors and legend
- Each series can come from a different source (cross-source comparison)
- Resample param applies uniformly to all series
- NL parser support deferred to later — this is API + Frontend only

#### API Design
New endpoint: `POST /api/compare`

Request body:
```json
{
  "items": [
    {"source": "crypto", "query": "bitcoin", "start": "2024-01-01", "end": "2024-12-31"},
    {"source": "crypto", "query": "ethereum", "start": "2024-01-01", "end": "2024-12-31"}
  ],
  "resample": "week",
  "apply": "normalize"
}
```

Response model:
```json
{
  "series": [
    {"source": "crypto", "query": "bitcoin", "points": [...], "metadata": {...}},
    {"source": "crypto", "query": "ethereum", "points": [...], "metadata": {...}}
  ],
  "count": 2
}
```

POST because the request is structured (list of objects with optional fields). Max 3 items enforced server-side.

#### Schemas (Pydantic)
```python
class CompareItem(BaseModel):
    source: str
    query: str
    start: datetime.date | None = None
    end: datetime.date | None = None

class CompareRequest(BaseModel):
    items: list[CompareItem]  # 2-3 items
    resample: str | None = None
    apply: str | None = None   # from Item 5 (derived metrics)
    refresh: bool = False

class CompareResponse(BaseModel):
    series: list[TimeSeries]
    count: int
```

#### Files to Create/Modify
- `app/models/schemas.py` — add CompareItem, CompareRequest, CompareResponse
- `app/routers/api.py` — add `POST /compare` endpoint
- `frontend/src/api/types.ts` — add CompareItem, CompareRequest, CompareResponse
- `frontend/src/api/client.ts` — add `fetchCompare()` function
- `frontend/src/components/charts/ForecastChart.tsx` — support multi-series overlay mode
- `frontend/src/components/CompareForm.tsx` — new component: 2-3 query inputs side by side
- `frontend/src/components/Dashboard.tsx` — add comparison mode toggle, wire up CompareForm
- `frontend/src/hooks/useApi.ts` — add `loadCompare()` function and `compareResult` state

#### Frontend Color Palette
Series 1: blue (#3B82F6), Series 2: orange (#F97316), Series 3: green (#10B981). Each gets solid line for actual data. Use existing Chart.js multi-dataset support (already proven by actual + forecast + CI rendering).

#### Implementation Steps
1. Add Pydantic schemas for compare request/response
2. Add `POST /compare` endpoint — validate 2-3 items, fetch all via CachedFetcher, apply resample/transforms, return
3. Write backend tests (compare 2 series, compare 3 series, max items validation, mixed sources, resample applies to all)
4. Add TypeScript types for compare
5. Add `fetchCompare()` to API client
6. Create CompareForm component with 2-3 query input rows
7. Modify ForecastChart to accept optional `compareSeries` prop — renders multiple line datasets
8. Wire comparison mode into Dashboard with toggle
9. Write frontend smoke tests if applicable

#### Tests Needed
- Test compare with 2 same-source series
- Test compare with 2 different-source series (cross-source)
- Test compare with 3 series (max)
- Test compare rejects >3 items or <2 items
- Test resample applies to all series
- Test refresh=true bypasses cache for all series
- Test missing source returns 404
- Test invalid query returns appropriate error

---

### Item 5: Derived Metrics / Computed Series
**Status:** done
**Tier:** 2 — Core Features

#### Requirements
- Transform series with `?apply=rolling_avg_7d|pct_change|cumulative|normalize` query param
- Pipe-delimited chain of transforms, applied left to right
- Applied after fetch + resample, before analysis/forecast
- Essential for cross-source comparison (normalize puts different scales on [0,1])
- No new adapters needed — pure data transformations

#### Supported Transforms
| Transform | Description | Example |
|-----------|-------------|---------|
| `rolling_avg_Nd` | N-day rolling average | `rolling_avg_7d`, `rolling_avg_30d` |
| `pct_change` | Period-over-period % change | `(v[i] - v[i-1]) / v[i-1] * 100` |
| `cumulative` | Running cumulative sum | Good for total downloads |
| `normalize` | Min-max scale to [0, 1] | Required for cross-source comparison |
| `diff` | First difference | `v[i] - v[i-1]` |

#### Pipeline Design
```python
def apply_transforms(ts: TimeSeries, apply_str: str) -> TimeSeries:
    """Parse pipe-delimited transform string and apply in order."""
    for name in apply_str.split("|"):
        ts = TRANSFORMS[name](ts)
    return ts
```

Each transform is a pure function `(TimeSeries) -> TimeSeries`. Transforms that reduce length (rolling avg, pct_change, diff) drop leading NaN points.

#### Files to Create/Modify
- `app/services/transforms.py` — transform functions + `apply_transforms()` pipeline
- `app/routers/api.py` — add `apply: str | None = Query(None)` to `/series`, `/analyze`, `/forecast`; apply after resample
- `app/models/schemas.py` — (no changes needed; transforms go in metadata)

#### Implementation Steps
1. Create `app/services/transforms.py` with individual transform functions
2. Implement `apply_transforms()` pipeline parser
3. Add `apply` query param to `/series`, `/analyze`, `/forecast` endpoints
4. Apply transforms in router: fetch → resample → apply → analyze/forecast
5. Include applied transforms in metadata for frontend labeling
6. Write tests

#### Tests Needed
- Test rolling_avg_7d: 14 points → 8 points (7 dropped), values are correct
- Test rolling_avg_30d on short series: raises or returns empty gracefully
- Test pct_change: known values produce correct percentages
- Test pct_change handles zero values (division by zero → NaN dropped)
- Test cumulative: known values produce running sum
- Test normalize: output range is [0, 1], min maps to 0, max maps to 1
- Test normalize with constant series (all same value) → handle gracefully
- Test diff: first differences are correct
- Test pipeline chaining: `normalize|rolling_avg_7d` applies both in order
- Test empty apply string is no-op
- Test unknown transform name raises ValueError
- Test metadata includes applied transforms

---

### Item 6: Annotation Layer
**Status:** done
**Tier:** 2 — Core Features

#### Requirements
- Surface structural breaks and anomalies as visual annotations on the chart
- Vertical lines at structural break dates with labels
- Anomaly points highlighted with distinct markers
- Use chartjs-plugin-annotation for vertical lines
- Data comes from existing TrendAnalysis response — no new backend endpoint needed initially
- Optional: manual annotations endpoint (deferred)

#### Design Decisions
- **No new backend endpoint** for v1 — structural breaks and anomalies are already in the TrendAnalysis response
- Frontend reads `analysis.structural_breaks` and `analysis.anomalies.anomalies` to build annotations
- chartjs-plugin-annotation draws vertical lines at break dates
- Anomaly points get distinct markers (red circles) on the existing line
- User can toggle annotations on/off

#### Files to Create/Modify
- `frontend/package.json` — add `chartjs-plugin-annotation` dependency
- `frontend/src/main.tsx` — register annotation plugin with Chart.js
- `frontend/src/components/charts/ForecastChart.tsx` — accept optional `analysis` prop, build annotation config from structural breaks + anomalies
- `frontend/src/components/Dashboard.tsx` — pass analysis data to ForecastChart
- `frontend/src/components/AnnotationToggle.tsx` — new small component: checkboxes for "Show breaks" / "Show anomalies"

#### Chart.js Annotation Config
```typescript
// Structural break → vertical line
{
  type: 'line',
  xMin: breakDate,
  xMax: breakDate,
  borderColor: 'rgba(239, 68, 68, 0.7)',  // red
  borderWidth: 2,
  borderDash: [6, 4],
  label: {
    display: true,
    content: `Break (${method})`,
    position: 'start'
  }
}

// Anomaly → point annotation
{
  type: 'point',
  xValue: anomalyDate,
  yValue: anomalyValue,
  radius: 6,
  backgroundColor: 'rgba(239, 68, 68, 0.5)',
  borderColor: 'rgb(239, 68, 68)'
}
```

#### Implementation Steps
1. Install `chartjs-plugin-annotation` in frontend
2. Register plugin in `main.tsx`
3. Add `analysis` prop to ForecastChart component
4. Build annotation config from structural breaks (vertical lines)
5. Build annotation config from anomaly points (highlighted markers)
6. Add AnnotationToggle component with show/hide state
7. Wire toggle state into Dashboard → ForecastChart
8. Test visual rendering

#### Tests Needed
- Test annotation config generation from structural breaks
- Test annotation config generation from anomalies
- Test toggle state hides/shows annotations
- Test empty analysis (no breaks, no anomalies) renders chart without errors
- Visual smoke test: chart renders with annotations enabled

---

### Item 7: Cross-Source Correlation
**Status:** done
**Tier:** 2 — Core Features

#### Requirements
- Endpoint that takes two series, aligns them by date, and computes correlation statistics
- Returns: Pearson r, Spearman ρ, p-values, lag analysis, and scatter plot data
- "Does Bitcoin price correlate with crypto library downloads?"
- Both series must be aligned to the same date range — inner join on dates
- Supports optional resample to align series with different granularities

#### API Design
New endpoint: `POST /api/correlate`

Request body:
```json
{
  "series_a": {"source": "crypto", "query": "bitcoin"},
  "series_b": {"source": "pypi", "query": "web3"},
  "start": "2024-01-01",
  "end": "2024-12-31",
  "resample": "week"
}
```

Response model:
```json
{
  "series_a": {"source": "crypto", "query": "bitcoin"},
  "series_b": {"source": "pypi", "query": "web3"},
  "aligned_points": 52,
  "pearson": {"r": 0.73, "p_value": 0.001},
  "spearman": {"rho": 0.68, "p_value": 0.003},
  "lag_analysis": [
    {"lag": -7, "correlation": 0.45},
    {"lag": 0, "correlation": 0.73},
    {"lag": 7, "correlation": 0.61}
  ],
  "scatter": [
    {"x": 42000.0, "y": 15234.0},
    {"x": 43500.0, "y": 16100.0}
  ]
}
```

#### Schemas (Pydantic)
```python
class CorrelateRequest(BaseModel):
    series_a: CompareItem
    series_b: CompareItem
    start: datetime.date | None = None
    end: datetime.date | None = None
    resample: str | None = None
    refresh: bool = False

class CorrelationCoefficient(BaseModel):
    r: float        # or rho for Spearman
    p_value: float

class LagCorrelation(BaseModel):
    lag: int         # positive = A leads B
    correlation: float

class ScatterPoint(BaseModel):
    x: float         # series A value
    y: float         # series B value

class CorrelateResponse(BaseModel):
    series_a_label: str   # "crypto:bitcoin"
    series_b_label: str   # "pypi:web3"
    aligned_points: int
    pearson: CorrelationCoefficient
    spearman: CorrelationCoefficient
    lag_analysis: list[LagCorrelation]
    scatter: list[ScatterPoint]
```

#### Correlation Engine
```python
def correlate(
    ts_a: TimeSeries, ts_b: TimeSeries, max_lag: int = 30
) -> CorrelateResponse:
    # 1. Align: inner join on date
    # 2. Pearson r via scipy.stats.pearsonr
    # 3. Spearman ρ via scipy.stats.spearmanr
    # 4. Lag analysis: shift one series by -max_lag..+max_lag, compute r at each
    # 5. Scatter: zip aligned values
```

#### Files to Create/Modify
- `app/models/schemas.py` — add CorrelateRequest, CorrelateResponse, CorrelationCoefficient, LagCorrelation, ScatterPoint
- `app/analysis/correlation.py` — new module: `align_series()`, `correlate()`
- `app/routers/api.py` — add `POST /correlate` endpoint
- `frontend/src/api/types.ts` — add correlation types
- `frontend/src/api/client.ts` — add `fetchCorrelation()` function
- `frontend/src/components/charts/ScatterChart.tsx` — new chart component for scatter plot
- `frontend/src/components/CorrelationPanel.tsx` — new component displaying r-values, lag chart, scatter

#### Dependencies to Add
- `scipy` — for `pearsonr`, `spearmanr` (check if already installed)

#### Implementation Steps
1. Check if scipy is available (may need to add to deps)
2. Add Pydantic schemas for correlation request/response
3. Create `app/analysis/correlation.py` with `align_series()` and `correlate()` functions
4. Add `POST /correlate` endpoint to router
5. Write backend tests
6. Add TypeScript types and API client function
7. Create ScatterChart component (Chart.js scatter type)
8. Create CorrelationPanel component (stats display + lag chart)
9. Wire into Dashboard (new tab or section)

#### Tests Needed
- Test align_series with overlapping date ranges
- Test align_series with non-overlapping ranges (should error or return 0 points)
- Test Pearson r on perfectly correlated data (r ≈ 1.0)
- Test Pearson r on uncorrelated data (r ≈ 0.0)
- Test Spearman ρ on monotonic data
- Test lag analysis finds correct peak lag for shifted data
- Test scatter output has correct x/y mapping
- Test with resampled data (weekly alignment)
- Test endpoint rejects if <2 aligned points
- Test correlation with identical series (r = 1.0, ρ = 1.0)

---

## Tier 3: UX & Polish

### Item 8: Saved Views / Shareable URLs
**Status:** planned
**Tier:** 3 — UX & Polish

#### Requirements
- Save current query config + params to DB, generate a short hash ID
- Load full view from `/view/{hash}` URL — re-fetches data and renders chart/analysis/forecast
- List saved views, delete views
- Hash-based sharing: no auth, anyone with the link can load the view
- Frontend needs react-router-dom for URL routing

#### DB Model
```python
class SavedView(Base):
    __tablename__ = "saved_views"
    id = Column(Integer, primary_key=True)
    hash_id = Column(String(12), unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    source = Column(String, nullable=False)
    query = Column(String, nullable=False)
    horizon = Column(Integer, default=14)
    start_date = Column(Date)
    end_date = Column(Date)
    resample = Column(String)
    apply = Column(String)
    anomaly_method = Column(String, default="zscore")
    created_at = Column(DateTime, nullable=False, default=_utcnow)
```

Hash generated from `hashlib.sha256(f"{source}:{query}:{timestamp}")[:8]` — short, URL-safe.

#### API Endpoints
- `POST /api/views` — save view, returns `{hash_id, name, ...}`
- `GET /api/views` — list all saved views
- `GET /api/views/{hash_id}` — get view config by hash
- `DELETE /api/views/{hash_id}` — delete view

#### Files to Create/Modify
- `app/db/models.py` — add SavedView model
- `app/db/repository.py` — add save_view, get_view_by_hash, list_views, delete_view
- `app/models/schemas.py` — add SaveViewRequest, SavedViewResponse
- `app/routers/api.py` — add 4 view endpoints
- `frontend/package.json` — add react-router-dom
- `frontend/src/main.tsx` — add BrowserRouter
- `frontend/src/App.tsx` — add routes (/ and /view/:hash)
- `frontend/src/api/client.ts` — add saveView, getView, listViews, deleteView
- `frontend/src/api/types.ts` — add SavedView type
- `frontend/src/components/Dashboard.tsx` — add save button, load from URL param
- `frontend/src/components/SavedViewsList.tsx` — new component: list/load/delete views

#### Implementation Steps
1. Add SavedView ORM model with hash_id generation
2. Add repository CRUD functions
3. Add Pydantic request/response schemas
4. Add API endpoints
5. Write backend tests
6. Install react-router-dom in frontend
7. Add routing to App.tsx
8. Add save/load/list UI components
9. Wire Dashboard to load view from URL

#### Tests Needed
- Test save view returns hash_id
- Test get view by hash returns correct config
- Test list views returns all saved
- Test delete view removes record
- Test duplicate saves get different hashes
- Test 404 for unknown hash
- Test endpoint validation (name required, source required)

---

### Item 9: Structured Error Handling
**Status:** done
**Tier:** 3 — UX & Polish

#### Requirements
- Standardized error response model across all endpoints
- Global exception handler for unhandled errors
- Consistent HTTP status codes (400 for bad input, 404 for not found, 422 for validation, 503 for external service failure)
- Fix ASA adapter missing try/except on HTTP calls
- Fix ValueError → 404 mapping (should be 422 for validation errors)

#### Error Response Model
```python
class ErrorResponse(BaseModel):
    error: str           # Machine-readable error type
    detail: str          # Human-readable message
    status_code: int     # HTTP status code
```

#### Status Code Mapping
| Scenario | Current | Correct |
|----------|---------|---------|
| Unknown source | 404 | 404 ✓ |
| Adapter ValueError (bad query) | 404 | 422 |
| Empty series | 404 | 422 |
| Too few correlation points | 422 | 422 ✓ |
| External API down | 500 (unhandled) | 503 |
| Invalid transform name | 500 (unhandled) | 422 |
| Missing API key | 503 | 503 ✓ |

#### Files to Create/Modify
- `app/models/schemas.py` — add ErrorResponse model
- `app/main.py` — add global exception handlers (ValueError, httpx errors, catch-all)
- `app/routers/api.py` — fix status codes for ValueError (404 → 422)
- `app/data/adapters/asa.py` — add try/except around HTTP calls

#### Implementation Steps
1. Add ErrorResponse schema
2. Add global exception handlers in main.py
3. Fix ValueError status codes in api.py (404 → 422 for validation errors, keep 404 for "not found")
4. Add error handling to ASA adapter HTTP calls
5. Write tests for error responses
6. Verify existing tests still pass

#### Tests Needed
- Test global handler catches unhandled exceptions → 500 with ErrorResponse format
- Test ValueError from adapter → 422 (not 404)
- Test unknown source → 404
- Test ASA adapter HTTP error → proper ValueError
- Test invalid transform → 422
- Test invalid resample frequency → 422

---

### Item 10: Frontend Redesign (MUI)
**Status:** planned
**Tier:** 3 — UX & Polish

#### Requirements
- Migrate from raw Tailwind to Material UI (MUI) component library
- Better visual hierarchy and layout
- Less dense — currently all info on one screen
- Consistent theme (colors, typography, spacing)
- Keep all existing functionality intact

#### Design Approach
- MUI v6 (latest) with Emotion styling
- Tabbed layout: "Explore" (single query), "Compare" (multi-series), "Correlate"
- Sidebar for analysis details (collapsible)
- Card-based layout for chart, model selector, evaluation
- AppBar with title, theme toggle (light/dark)
- Snackbar for errors/success messages

#### Files to Create/Modify
- `frontend/package.json` — add @mui/material, @mui/icons-material, @emotion/react, @emotion/styled
- `frontend/src/App.tsx` — MUI ThemeProvider, CssBaseline
- `frontend/src/components/Dashboard.tsx` — rewrite with MUI Grid, Tabs, Cards
- `frontend/src/components/QueryForm.tsx` — MUI TextField, Select, Autocomplete
- `frontend/src/components/NaturalQueryInput.tsx` — MUI TextField, Alert
- `frontend/src/components/charts/ForecastChart.tsx` — wrap in MUI Card
- `frontend/src/components/AnalysisPanel.tsx` — MUI Accordion, List, Chip
- `frontend/src/components/ModelSelector.tsx` — MUI ToggleButtonGroup
- `frontend/src/components/EvaluationTable.tsx` — MUI Table with sorting
- `frontend/src/components/InsightPanel.tsx` — MUI Card, LinearProgress

#### Implementation Steps
1. Install MUI dependencies
2. Set up ThemeProvider and CssBaseline in App.tsx
3. Migrate components one at a time (start with layout → forms → panels → chart wrapper)
4. Remove Tailwind CSS (or keep for minor utility; MUI handles layout)
5. Test each component visually after migration
6. Verify build passes

#### Tests Needed
- Frontend build compiles without errors
- Visual smoke test of each major view

---

### Item 11: Player-Level ASA Queries
**Status:** done
**Tier:** 3 — UX & Polish

#### Requirements
- Add "players" option to ASA entity_type field
- Implement player lookup per league
- Player-level xgoals and xpass metrics via ASA API
- Query format: `league:players:player_id:metric[:home_away:stage]`

#### ASA Player API
- Lookup: `GET /api/v1/{league}/players` → returns player_id, player_name
- Metrics: `GET /api/v1/{league}/players/xgoals?player_id=X&split_by_games=true`
- Metrics: `GET /api/v1/{league}/players/xpass?player_id=X&split_by_games=true`

#### Files to Create/Modify
- `app/data/adapters/asa.py` — add "players" to entity_type options, add `_lookup_players()`, update fetch to handle player_id param

#### Implementation Steps
1. Add "players" to entity_type form field options
2. Implement `_lookup_players(league)` method
3. Update `lookup()` to dispatch to `_lookup_players` when lookup_type == "players"
4. Update `_fetch_metric_data()` — already uses player_id param when entity_type is players (line 280)
5. Update form_fields entity placeholder based on entity_type
6. Write tests

#### Tests Needed
- Test player lookup returns list of players
- Test player query format is parsed correctly
- Test player xgoals metric fetches and returns TimeSeries
- Test player xpass metric fetches and returns TimeSeries
- Test entity field depends_on entity_type change

---

### Item 12: Enhance Current Adapters
**Status:** planned
**Tier:** 3 — UX & Polish

#### Requirements
- Football adapter: add team/competition lookup and select fields
- GitHub adapter: add form_fields() with proper text input
- Review other adapters for enhancement opportunities

#### Football Adapter Enhancements
- Add `form_fields()` with competition select (Premier League, La Liga, etc.) and team autocomplete
- Add `lookup()` for teams within a competition
- Query format already works: `competition_id:team_id`

#### GitHub Adapter Enhancements
- Already has a text field via default form_fields()
- Could add description/placeholder: "owner/repo format"

#### Files to Create/Modify
- `app/data/adapters/football.py` — add form_fields(), lookup()
- `app/data/adapters/github.py` — override form_fields() for better placeholder

#### Implementation Steps
1. Add competition select and team autocomplete to football adapter form_fields()
2. Implement football adapter lookup() for teams
3. Update github adapter form_fields() with better placeholder
4. Write tests

#### Tests Needed
- Test football form_fields returns competition and team fields
- Test football lookup returns teams for a competition
- Test github form_fields has descriptive placeholder
