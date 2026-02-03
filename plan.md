# Implementation Plan

## Item: DataAdapter ABC & Core Models
**Status:** done
**Phase:** 1

### Requirements
- Abstract base class with async `fetch()` method
- All adapters return a common `TimeSeries` model
- `fetch(query, start, end)` signature — `start`/`end` are optional date bounds
- Each adapter declares its `name` and `description` (for the `/api/sources` listing)

### Files to Create/Modify
- `app/data/__init__.py` — make it a package
- `app/data/base.py` — `DataAdapter` ABC
- `app/models/schemas.py` — add `DataPoint`, `TimeSeries`, `DataSourceInfo`

### Implementation Steps
1. Define `DataPoint` model: `date: datetime.date`, `value: float`
2. Define `TimeSeries` model: `source: str`, `query: str`, `points: list[DataPoint]`, `metadata: dict`
3. Define `DataSourceInfo` model: `name: str`, `description: str`
4. Define `DataAdapter` ABC with:
   - `name: str` class attribute
   - `description: str` class attribute
   - `async def fetch(self, query: str, start: date | None, end: date | None) -> TimeSeries`

### Dependencies to Add
- None (uses stdlib `abc` and existing `pydantic`)

### Tests Needed
- Test that `DataAdapter` cannot be instantiated directly (is abstract)
- Test that `TimeSeries` serializes to expected JSON shape
- Test that `DataPoint` validates date and value types

---

## Item: Project Directory Structure
**Status:** done
**Phase:** 1

### Requirements
- Create the skeleton directories for all future phases now
- Each directory gets an `__init__.py`

### Files to Create/Modify
- `app/data/__init__.py`
- `app/data/adapters/__init__.py`
- `app/analysis/__init__.py`
- `app/forecasting/__init__.py`
- `app/ai/__init__.py`

### Implementation Steps
1. Create each directory
2. Add empty `__init__.py` files
3. Verify imports work

### Dependencies to Add
- None

### Tests Needed
- None (structural only — verified by import in other tests)

---

## Item: PyPI Download Adapter
**Status:** done
**Phase:** 1

### Requirements
- Hit `https://pypistats.org/api/packages/{package}/overall?mirrors=false` to get daily download counts
- Parse the JSON response into `TimeSeries`
- Data goes back 180 days max (API limitation)
- Aggregate across categories (the API returns "with_mirrors" / "without_mirrors" rows per date — we sum per date)
- Handle missing package (404) gracefully with a clear error
- Respect optional `start`/`end` date filters by slicing the returned data

### Files to Create/Modify
- `app/data/adapters/pypi.py` — `PyPIAdapter(DataAdapter)`

### Implementation Steps
1. Implement `PyPIAdapter` inheriting from `DataAdapter`
2. Set `name = "pypi"`, `description = "PyPI package download counts (last 180 days)"`
3. In `fetch()`: build URL from `query` (the package name)
4. Use `httpx.AsyncClient` to GET the URL
5. Parse `response.json()["data"]` — each item has `date`, `category`, `downloads`
6. Group by date and sum downloads across categories
7. Sort by date ascending
8. Apply `start`/`end` filters if provided
9. Return `TimeSeries`
10. Raise `ValueError` with descriptive message on 404 or unexpected response

### Dependencies to Add
- `httpx` — promote from dev to main dependency

### Tests Needed
- Test with mocked successful response (known JSON fixture) — verify correct `TimeSeries` output
- Test date filtering — pass `start`/`end` and verify points are sliced
- Test 404 handling — mock a 404 response, assert `ValueError` raised
- Test aggregation — mock response with multiple categories per date, verify summing

---

## Item: Adapter Registry
**Status:** done
**Phase:** 1

### Requirements
- Simple dict-based registry mapping adapter name → adapter instance
- Singleton pattern or module-level instance
- Methods: `register(adapter)`, `get(name)`, `list_sources()`
- Pre-register the PyPI adapter on app startup

### Files to Create/Modify
- `app/data/registry.py` — `AdapterRegistry` class
- `app/main.py` — register adapters on startup (lifespan or module-level)

### Implementation Steps
1. Create `AdapterRegistry` with `_adapters: dict[str, DataAdapter]`
2. `register(adapter: DataAdapter)` — stores by `adapter.name`
3. `get(name: str) -> DataAdapter` — returns adapter or raises `KeyError`
4. `list_sources() -> list[DataSourceInfo]` — returns name + description of all registered adapters
5. Create a module-level `registry` instance in `app/data/registry.py`
6. In `app/main.py`, import and register `PyPIAdapter` on startup

### Dependencies to Add
- None

### Tests Needed
- Test register and retrieve an adapter
- Test `get()` with unknown name raises `KeyError`
- Test `list_sources()` returns correct info after registration

---

## Item: API Endpoints — `/api/sources` and `/api/series`
**Status:** done
**Phase:** 1

### Requirements
- `GET /api/sources` — list all registered data sources (name + description)
- `GET /api/series?source=pypi&query=fastapi` — fetch time-series from a named adapter
  - Optional query params: `start` (date), `end` (date)
  - Returns `TimeSeries` JSON
  - Returns 404 if source name not found
  - Returns 400/422 if query missing or invalid

### Files to Create/Modify
- `app/routers/api.py` — add the two new route handlers
- `app/models/schemas.py` — add any response models needed (e.g., `SourcesResponse`)

### Implementation Steps
1. Add `GET /sources` — calls `registry.list_sources()`, returns list of `DataSourceInfo`
2. Add `GET /series` — accepts `source: str`, `query: str`, `start: date | None`, `end: date | None`
3. Resolve adapter via `registry.get(source)` — catch `KeyError`, return 404
4. Call `adapter.fetch(query, start, end)`
5. Catch `ValueError` from adapter (e.g., package not found) and return 404
6. Return `TimeSeries` response

### Dependencies to Add
- None

### Tests Needed
- Test `/api/sources` returns list with PyPI entry
- Test `/api/series?source=pypi&query=fastapi` returns valid `TimeSeries` shape (mock the adapter)
- Test `/api/series` with unknown source returns 404
- Test `/api/series` without required `query` param returns 422
- Test `/api/series` with `start`/`end` passes dates through to adapter

---

## Item: Promote httpx to Main Dependency
**Status:** done
**Phase:** 1

### Requirements
- `httpx` is currently in `[project.optional-dependencies] dev` only
- It's needed at runtime for the PyPI adapter

### Files to Create/Modify
- `pyproject.toml` — add `httpx>=0.27.0` to main `dependencies`

### Implementation Steps
1. Add `httpx>=0.27.0` to the `[project] dependencies` list
2. Run `uv sync` to update the lockfile

### Dependencies to Add
- `httpx>=0.27.0` (move from dev to main)

### Tests Needed
- None (verified by adapter tests importing httpx)

---

## Item: Integration & API Tests
**Status:** done
**Phase:** 1

### Requirements
- PyPI adapter tests use mocked HTTP (no real network calls in CI)
- API tests use the existing `AsyncClient` fixture from `test_main.py`
- Tests cover the happy path and error cases listed above

### Files to Create/Modify
- `tests/test_pypi_adapter.py` — unit/integration tests for `PyPIAdapter`
- `tests/test_registry.py` — unit tests for `AdapterRegistry`
- `tests/test_api_series.py` — API endpoint tests for `/api/sources` and `/api/series`
- `tests/conftest.py` — shared fixtures (mock adapter, async client)

### Implementation Steps
1. Create `tests/conftest.py` with shared `client` fixture (move from `test_main.py`)
2. Create JSON fixture data for a mocked PyPI response
3. Write adapter tests using `unittest.mock.patch` on `httpx.AsyncClient.get`
4. Write registry tests (pure unit tests, no mocking needed)
5. Write API tests — mock the registry to return a fake adapter so tests don't hit the network
6. Run full suite, verify all pass

### Dependencies to Add
- None (pytest, httpx already in dev deps)

### Tests Needed
- (This item IS the tests)

---

## Execution Order

1. Promote httpx to main dependency
2. Create directory structure
3. DataAdapter ABC & core Pydantic models
4. PyPI adapter implementation
5. Adapter registry
6. API endpoints
7. All tests

Items 3-5 can overlap but should be committed in this order for clean git history.

---
---

# Phase 2: Second Adapter & Adapter Registry

> Registry and endpoints already exist from Phase 1. Phase 2 adds two new
> adapters and .env-based configuration to prove the plugin pattern works.

---

## Item: Environment config for API keys
**Status:** done
**Phase:** 2

### Requirements
- Load `GITHUB_TOKEN` from `.env` at startup (required for GitHub adapter)
- Create a small config module so adapters can access settings without importing dotenv everywhere
- Update `.env.example` with the new variable

### Files to Create/Modify
- `app/config.py` — settings loader using `pydantic-settings` or plain `os.environ` + `dotenv`
- `.env.example` — add `GITHUB_TOKEN=`
- `.env` — (not committed) user adds their token here

### Implementation Steps
1. Create `app/config.py` with a `Settings` class that reads `GITHUB_TOKEN` from env
2. Use `python-dotenv` (already a dependency) to load `.env` on import
3. Export a module-level `settings` instance
4. Update `.env.example` with `GITHUB_TOKEN=your_token_here`

### Dependencies to Add
- None (`python-dotenv` is already in main deps)

### Tests Needed
- Test that `Settings` reads from environment variables
- Test that missing `GITHUB_TOKEN` raises a clear error or returns None

---

## Item: GitHub stargazers adapter
**Status:** done
**Phase:** 2

### Requirements
- Fetch stargazer timestamps from `GET /repos/{owner}/{repo}/stargazers`
- Requires `Accept: application/vnd.github.star+json` header for timestamps
- Requires `Authorization: Bearer {GITHUB_TOKEN}` header (token is mandatory)
- Paginate with `per_page=100` — follow `Link` header or increment page until empty response
- Bucket `starred_at` timestamps into daily counts
- Query format: `"owner/repo"` (e.g. `"tiangolo/fastapi"`)
- Handle 404 (repo not found) as `ValueError`
- Handle 403/rate-limit as a descriptive error
- Respect optional `start`/`end` date filters

### Files to Create/Modify
- `app/data/adapters/github.py` — `GitHubStarsAdapter(DataAdapter)`
- `app/main.py` — register `GitHubStarsAdapter` on startup

### Implementation Steps
1. Import `settings` from `app/config.py` to get `GITHUB_TOKEN`
2. Set `name = "github_stars"`, `description = "GitHub repo stargazers over time"`
3. In `fetch()`:
   - Parse `query` as `"owner/repo"`
   - Build URL: `https://api.github.com/repos/{owner}/{repo}/stargazers`
   - Set headers: `Accept: application/vnd.github.star+json`, `Authorization: Bearer {token}`
   - Paginate: request `per_page=100`, increment page until response is empty list
   - Collect all `starred_at` timestamps
4. Bucket timestamps into daily counts using `collections.Counter` on `date()`
5. Convert to sorted `DataPoint` list
6. Apply `start`/`end` filters
7. Return `TimeSeries` with `metadata={"total_stars": len(all_stargazers)}`
8. Handle 404 → `ValueError`, 403 → descriptive error about rate limits

### Dependencies to Add
- None (uses `httpx` already in main deps)

### Tests Needed
- Test with mocked paginated response (2 pages) — verify correct daily bucketing
- Test single-page repo — verify no over-pagination
- Test 404 handling → `ValueError`
- Test 403/rate-limit handling → descriptive error
- Test date filtering with `start`/`end`
- Test adapter metadata (`name`, `description`)
- Test `total_stars` appears in metadata

---

## Item: CoinGecko crypto prices adapter
**Status:** done
**Phase:** 2

### Requirements
- Fetch daily price history from `GET https://api.coingecko.com/api/v3/coins/{id}/market_chart`
- Free tier, no API key needed
- Query format: coin ID string (e.g. `"bitcoin"`, `"ethereum"`)
- Params: `vs_currency=usd`, `days=180` (match PyPI's window)
- Response shape: `{"prices": [[timestamp_ms, price], ...], ...}`
- Convert millisecond timestamps to dates, use closing price per day
- Handle unknown coin (400/404) as `ValueError`
- Respect optional `start`/`end` date filters

### Files to Create/Modify
- `app/data/adapters/coingecko.py` — `CoinGeckoAdapter(DataAdapter)`
- `app/main.py` — register `CoinGeckoAdapter` on startup

### Implementation Steps
1. Set `name = "crypto"`, `description = "Cryptocurrency price history (USD, last 180 days)"`
2. In `fetch()`:
   - Build URL with `query` as the coin ID
   - GET with params `vs_currency=usd`, `days=180`, `interval=daily`
   - Parse `response.json()["prices"]` — list of `[timestamp_ms, price]`
   - Convert each `timestamp_ms` to `datetime.date` via `datetime.fromtimestamp(ts/1000)`
   - Deduplicate dates (take last value per date if duplicates exist)
   - Sort by date ascending
3. Apply `start`/`end` filters
4. Return `TimeSeries`
5. Handle error responses → `ValueError`

### Dependencies to Add
- None (uses `httpx`)

### Tests Needed
- Test with mocked response — verify correct date conversion and values
- Test deduplication — mock response with two entries on same date
- Test error handling — mock 400/404, assert `ValueError`
- Test date filtering
- Test adapter metadata

---

## Item: Register new adapters in main.py
**Status:** done
**Phase:** 2

### Requirements
- Import and register `GitHubStarsAdapter` and `CoinGeckoAdapter` on startup
- GitHub adapter should only register if `GITHUB_TOKEN` is configured
- CoinGecko registers unconditionally (no auth needed)

### Files to Create/Modify
- `app/main.py` — add registration calls

### Implementation Steps
1. Import both adapter classes
2. Import `settings` from `app/config.py`
3. Always register `CoinGeckoAdapter()`
4. Conditionally register `GitHubStarsAdapter(settings.github_token)` only if token is set
5. Log a warning if GitHub token is missing (adapter won't be available)

### Dependencies to Add
- None

### Tests Needed
- Test `/api/sources` now lists all registered adapters
- Test that app starts without `GITHUB_TOKEN` (crypto + pypi still work)

---

## Phase 2 Execution Order

1. Environment config module
2. CoinGecko adapter (simpler — no auth, no pagination)
3. GitHub stargazers adapter (pagination + auth)
4. Register both in main.py
5. Full test suite pass + lint

---
---

# Phase 3: Trend Detection Engine

> Build the analysis layer that turns raw `TimeSeries` data into structured
> trend signals, seasonality patterns, anomaly reports, and structural break
> detection.

---

## Item: Add numpy dependency
**Status:** planned
**Phase:** 3

### Requirements
- All analysis modules need vectorized math: differences, rolling windows, FFT, standard deviation
- numpy covers every algorithm in Phase 3 without needing scipy
- Keep scipy out for now — revisit in Phase 4 if forecasting models need it

### Files to Create/Modify
- `pyproject.toml` — add `numpy>=1.26.0` to main `dependencies`

### Implementation Steps
1. Add `"numpy>=1.26.0"` to the `[project] dependencies` list in `pyproject.toml`
2. Run `uv sync` to update the lockfile
3. Verify import works: `python -c "import numpy; print(numpy.__version__)"`

### Dependencies to Add
- `numpy>=1.26.0`

### Tests Needed
- None (verified by analysis module imports)

---

## Item: Analysis Pydantic models
**Status:** planned
**Phase:** 3

### Requirements
- Define output models for each analysis sub-module and a combined result
- `TrendSignal` — captures momentum, acceleration, moving averages, and an overall direction label
- `SeasonalityResult` — captures detected period, strength, and autocorrelation values
- `AnomalyReport` — list of flagged anomaly points with scores and method used
- `StructuralBreak` — a single detected regime change point with metadata
- `TrendAnalysis` — combined model that aggregates all of the above for a single `TimeSeries`
- All models must be JSON-serializable via Pydantic for the API response

### Files to Create/Modify
- `app/models/schemas.py` — add new models alongside existing `DataPoint`, `TimeSeries`, etc.

### Implementation Steps
1. Define `MovingAverage` model:
   - `window: int` (e.g. 7, 30)
   - `values: list[DataPoint]` (date + smoothed value)
2. Define `TrendSignal` model:
   - `direction: str` — one of `"rising"`, `"falling"`, `"stable"`
   - `momentum: float` — average rate of change over the series
   - `acceleration: float` — average second derivative
   - `moving_averages: list[MovingAverage]`
   - `momentum_series: list[DataPoint]` — per-point rate of change
3. Define `SeasonalityResult` model:
   - `detected: bool`
   - `period_days: int | None` — dominant period in days (e.g. 7 for weekly)
   - `strength: float | None` — normalized autocorrelation peak (0.0-1.0)
   - `autocorrelation: list[float]` — raw autocorrelation values for inspection
4. Define `AnomalyPoint` model:
   - `date: datetime.date`
   - `value: float`
   - `score: float` — z-score or IQR distance
   - `method: str` — `"zscore"` or `"iqr"`
5. Define `AnomalyReport` model:
   - `method: str`
   - `threshold: float`
   - `anomalies: list[AnomalyPoint]`
   - `total_points: int`
   - `anomaly_count: int`
6. Define `StructuralBreak` model:
   - `date: datetime.date`
   - `index: int` — position in the series
   - `method: str` — `"cusum"` or `"rolling_variance"`
   - `confidence: float` — signal strength (0.0-1.0)
7. Define `TrendAnalysis` model:
   - `source: str`
   - `query: str`
   - `series_length: int`
   - `trend: TrendSignal`
   - `seasonality: SeasonalityResult`
   - `anomalies: AnomalyReport`
   - `structural_breaks: list[StructuralBreak]`

### Dependencies to Add
- None (uses existing Pydantic)

### Tests Needed
- Test `TrendAnalysis` serializes to expected JSON shape with all nested models
- Test `TrendSignal` validates `direction` values
- Test `AnomalyReport` round-trips through `model_dump()` / `model_validate()`
- Test default values and optional fields

---

## Item: Trend metrics module (`trend_metrics.py`)
**Status:** planned
**Phase:** 3

### Requirements
- Compute momentum: rate of change (first differences divided by value, i.e. percentage change per step)
- Compute acceleration: second derivative (diff of diffs)
- Compute moving averages with configurable windows (default 7d and 30d)
- Determine overall direction label: `"rising"` / `"falling"` / `"stable"` based on sign of average momentum
- Accept a `TimeSeries` and return a `TrendSignal`
- Handle edge cases: series too short for a given window returns empty moving average; series with < 2 points returns zero momentum/acceleration

### Files to Create/Modify
- `app/analysis/trend_metrics.py`

### Implementation Steps
1. Create function `compute_momentum(values: numpy.ndarray) -> numpy.ndarray`:
   - Use `numpy.diff(values) / values[:-1]` (percentage change)
   - Handle division by zero: replace NaN/inf with 0.0
2. Create function `compute_acceleration(values: numpy.ndarray) -> numpy.ndarray`:
   - `numpy.diff(values, n=2)` — raw second differences
3. Create function `compute_moving_average(dates: list[date], values: numpy.ndarray, window: int) -> list[DataPoint]`:
   - Use `numpy.convolve(values, numpy.ones(window)/window, mode='valid')`
   - End-aligned: the MA value on day N uses days N-window+1 through N
4. Create main function `analyze_trend(ts: TimeSeries, windows: list[int] | None = None) -> TrendSignal`:
   - Default `windows = [7, 30]`
   - Extract values as numpy array from `ts.points`
   - Compute momentum, acceleration, moving averages
   - Determine direction: if mean(momentum) > 0.01 → `"rising"`, < -0.01 → `"falling"`, else `"stable"`
   - Build and return `TrendSignal`
5. Guard against short series: if `len(points) < 2`, return a `TrendSignal` with zeros and `"stable"`

### Dependencies to Add
- None (uses numpy added in previous item)

### Tests Needed
- Test with linear increasing data → `direction == "rising"`, positive momentum
- Test with linear decreasing data → `direction == "falling"`, negative momentum
- Test with constant data → `direction == "stable"`, zero momentum, zero acceleration
- Test moving average with window=3 on known data → verify exact output values
- Test edge case: series with 1 point → returns stable with zero values
- Test edge case: series shorter than window → moving average list is empty for that window
- Test that momentum_series length == len(points) - 1

---

## Item: Seasonality detection module (`seasonality.py`)
**Status:** planned
**Phase:** 3

### Requirements
- Detect periodic patterns in a `TimeSeries`
- Use autocorrelation via FFT (efficient O(n log n) approach using numpy)
- Identify the dominant period (lag with highest autocorrelation peak, excluding lag 0)
- Report whether seasonality was detected based on a strength threshold
- Handle short series gracefully (need at least 2x the candidate period)

### Files to Create/Modify
- `app/analysis/seasonality.py`

### Implementation Steps
1. Create function `compute_autocorrelation(values: numpy.ndarray, max_lag: int | None = None) -> numpy.ndarray`:
   - Subtract mean from values (center the series)
   - Use FFT-based autocorrelation: `fft = numpy.fft.rfft(centered, n=2*len(centered))`
   - Power spectrum: `power = fft * numpy.conj(fft)`
   - Inverse FFT: `acf = numpy.fft.irfft(power)[:len(centered)]`
   - Normalize by `acf[0]` (variance) so lag-0 = 1.0
   - Clip to `max_lag` if provided (default: `len(values) // 2`)
2. Create function `find_dominant_period(acf: numpy.ndarray, min_period: int = 2) -> tuple[int | None, float | None]`:
   - Skip lag 0 and lags < `min_period`
   - Find the lag with the highest autocorrelation value
   - If peak value > threshold (0.3), return `(period, strength)`
   - Otherwise return `(None, None)` — no significant seasonality detected
3. Create main function `analyze_seasonality(ts: TimeSeries) -> SeasonalityResult`:
   - Extract values as numpy array
   - If `len(values) < 14`, return `SeasonalityResult(detected=False, ...)`
   - Compute autocorrelation
   - Find dominant period
   - Return `SeasonalityResult`

### Dependencies to Add
- None (uses `numpy.fft`)

### Tests Needed
- Test with synthetic weekly pattern (sin wave period=7 + noise) → detects `period_days=7`
- Test with constant data → `detected=False`
- Test with pure noise (random) → `detected=False` (no strong peak)
- Test with known period=30 → detects monthly pattern
- Test short series (< 14 points) → returns `detected=False` gracefully
- Test autocorrelation normalization: lag-0 should be 1.0

---

## Item: Anomaly detection module (`anomalies.py`)
**Status:** planned
**Phase:** 3

### Requirements
- Flag outlier points using two methods: z-score and IQR
- Z-score method: flag points where `|z| > threshold` (default 2.5)
- IQR method: flag points outside `[Q1 - k*IQR, Q3 + k*IQR]` (default k=1.5)
- Return an `AnomalyReport` with the flagged points, their scores, and summary stats
- Caller can choose the method; default to z-score

### Files to Create/Modify
- `app/analysis/anomalies.py`

### Implementation Steps
1. Create function `detect_zscore(dates, values, threshold=2.5) -> AnomalyReport`
2. Create function `detect_iqr(dates, values, k=1.5) -> AnomalyReport`
3. Create main function `analyze_anomalies(ts, method="zscore", **kwargs) -> AnomalyReport`
   - Dispatch to the chosen method
   - Raise `ValueError` for unknown method
   - Handle edge cases: empty or single-point series → return empty report

### Dependencies to Add
- None (uses numpy)

### Tests Needed
- Test z-score with synthetic data containing known outliers → flags the spike
- Test z-score with constant data → no anomalies
- Test IQR with known data → verify exact bounds and flagged points
- Test choosing `method="iqr"` routes correctly
- Test unknown method raises `ValueError`
- Test empty series → empty anomaly report

---

## Item: Structural breaks module (`structural_breaks.py`)
**Status:** planned
**Phase:** 3

### Requirements
- Detect regime changes using CUSUM and rolling variance methods
- Return a list of `StructuralBreak` objects

### Files to Create/Modify
- `app/analysis/structural_breaks.py`

### Implementation Steps
1. Create function `detect_cusum(dates, values, threshold=1.0) -> list[StructuralBreak]`
   - Compute CUSUM of deviations from mean
   - Normalize by std, find peaks exceeding threshold
   - Cluster nearby break points
2. Create function `detect_rolling_variance(dates, values, window=30, threshold=2.0) -> list[StructuralBreak]`
   - Compute rolling variance, find ratio spikes between adjacent windows
3. Create main function `analyze_structural_breaks(ts, method="cusum", **kwargs) -> list[StructuralBreak]`

### Dependencies to Add
- None (uses numpy)

### Tests Needed
- Test CUSUM with step function data → detects break near the step
- Test CUSUM with constant data → no breaks detected
- Test rolling variance with variance shift → detects break
- Test short series → returns empty list

---

## Item: Analysis orchestrator (`engine.py`)
**Status:** planned
**Phase:** 3

### Requirements
- Single `analyze()` function that runs all four analysis modules on a `TimeSeries`
- Returns a combined `TrendAnalysis` model
- Fail-fast: if data is too malformed for one detector, the whole analysis is suspect

### Files to Create/Modify
- `app/analysis/engine.py`
- `app/analysis/__init__.py` — re-export `analyze`

### Implementation Steps
1. Create function `analyze(ts: TimeSeries, anomaly_method: str = "zscore") -> TrendAnalysis`
   - Validate: empty series → raise `ValueError`
   - Call all four analysis functions
   - Assemble and return `TrendAnalysis`
2. Update `app/analysis/__init__.py` to export `analyze`

### Dependencies to Add
- None

### Tests Needed
- Test orchestrator with synthetic rising data → all sub-results present
- Test orchestrator with empty series → raises `ValueError`
- Test anomaly_method parameter is passed through

---

## Item: `/api/analyze` endpoint
**Status:** planned
**Phase:** 3

### Requirements
- `GET /api/analyze?source=pypi&query=fastapi` — fetch time series, run analysis, return `TrendAnalysis`
- Optional params: `start`, `end`, `anomaly_method`
- Same error handling pattern as `/api/series`

### Files to Create/Modify
- `app/routers/api.py` — add the new route handler

### Implementation Steps
1. Add `GET /analyze` route following the `/api/series` pattern
2. Resolve adapter, fetch series, run `analyze()`, return result
3. Handle errors: `KeyError` → 404, `ValueError` → 404

### Dependencies to Add
- None

### Tests Needed
- Test successful response shape with all expected keys
- Test unknown source → 404
- Test missing query → 422
- Test `anomaly_method=iqr` param is accepted

---

## Phase 3 Execution Order

1. Add numpy dependency
2. Analysis Pydantic models
3. Trend metrics module (+ tests)
4. Seasonality module (+ tests)
5. Anomaly detection module (+ tests)
6. Structural breaks module (+ tests)
7. Analysis orchestrator (+ tests)
8. `/api/analyze` endpoint (+ API tests)

Items 3-6 are independent of each other and can be developed in any order.
