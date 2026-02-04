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
**Status:** done
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
**Status:** done
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
**Status:** done
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
**Status:** done
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
**Status:** done
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
**Status:** done
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
**Status:** done
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
**Status:** done
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

---
---

# Phase 5: AI Commentary Layer

> Use an LLM (Anthropic Claude) to generate natural-language summaries of
> trends and forecasts, exposed via a streaming SSE endpoint.

---

## Item: Add Anthropic SDK dependency
**Status:** done
**Phase:** 5

### Requirements
- Add `anthropic` Python SDK for calling Claude API
- Add `ANTHROPIC_API_KEY` to the config module
- Commentary layer is optional — app should start without the key (endpoint returns 503)

### Files to Create/Modify
- `pyproject.toml` — add `anthropic>=0.40.0` to main dependencies
- `app/config.py` — add `anthropic_api_key` setting

### Implementation Steps
1. Add `"anthropic>=0.40.0"` to `[project] dependencies` in `pyproject.toml`
2. Add `self.anthropic_api_key: str | None = os.environ.get("ANTHROPIC_API_KEY")` to `Settings.__init__` in `app/config.py`
3. Run `uv sync` to update lockfile
4. Verify import: `python -c "import anthropic; print(anthropic.__version__)"`

### Dependencies to Add
- `anthropic>=0.40.0` — Anthropic Python SDK for Claude API access

### Tests Needed
- Test that `Settings` reads `ANTHROPIC_API_KEY` from environment
- Test that missing key defaults to `None`

---

## Item: Prompt templates module (`app/ai/prompts.py`)
**Status:** done
**Phase:** 5

### Requirements
- Store all prompt templates as Python string constants/functions in a single module
- Support a versioned prompt selection mechanism (swap strategies without code changes)
- Prompts should accept structured data (TrendAnalysis + ForecastComparison) and format them into LLM-ready text
- Four prompt types: trend summary, forecast explanation, risk flags, narrative ("if this continues...")

### Files to Create/Modify
- `app/ai/prompts.py` — prompt templates and formatter functions

### Implementation Steps
1. Create a `format_analysis_context(analysis: TrendAnalysis, forecast: ForecastComparison) -> str` function that serializes the structured data into a clean text block the LLM can reason over. Include:
   - Series metadata (source, query, length)
   - Trend direction, momentum, acceleration
   - Seasonality status and period
   - Anomaly count and notable outliers
   - Structural break count and dates
   - Forecast model rankings (name, MAE) and recommended model
   - Forecast values for the recommended model (first/middle/last points + CI range)
2. Define `SYSTEM_PROMPT: str` — the system message establishing the role: concise data analyst that explains trends to non-technical users, avoids jargon, includes caveats
3. Define a `PROMPT_REGISTRY: dict[str, str]` mapping version names to user prompt templates:
   - `"default"` — balanced summary covering all aspects
   - `"concise"` — 2-3 sentence executive summary
   - `"detailed"` — thorough analysis with section headers
4. Each prompt template uses `{context}` placeholder that gets filled with the formatted analysis context
5. Create `get_prompt(version: str = "default") -> str` that returns the template, raising `ValueError` for unknown versions
6. Create `build_messages(analysis, forecast, version="default") -> list[dict]` that returns the `[{"role": "system", ...}, {"role": "user", ...}]` message list ready for the Anthropic API

### Dependencies to Add
- None (pure Python, references Pydantic models)

### Tests Needed
- Test `format_analysis_context` produces non-empty string containing key data points (source name, direction, recommended model)
- Test `get_prompt("default")` returns a string containing `{context}`
- Test `get_prompt("unknown")` raises `ValueError`
- Test `build_messages` returns a list with system and user messages
- Test that all registered prompt versions are valid (contain `{context}`)

---

## Item: LLM client module (`app/ai/client.py`)
**Status:** done
**Phase:** 5

### Requirements
- Thin wrapper around the Anthropic SDK that handles initialization, error handling, and both streaming/non-streaming calls
- Uses `anthropic.AsyncAnthropic` for async compatibility with FastAPI
- Configurable model name (default to `claude-sonnet-4-20250514`)
- Returns raw text for non-streaming, async generator of text chunks for streaming

### Files to Create/Modify
- `app/ai/client.py` — LLM client class

### Implementation Steps
1. Create `class LLMClient`:
   - `__init__(self, api_key: str, model: str = "claude-sonnet-4-20250514")` — stores key and model, creates `anthropic.AsyncAnthropic(api_key=api_key)`
   - `async def generate(self, messages: list[dict], max_tokens: int = 1024) -> str` — non-streaming call, returns full text response
   - `async def stream(self, messages: list[dict], max_tokens: int = 1024) -> AsyncGenerator[str, None]` — streaming call, yields text deltas as they arrive
2. In `generate()`:
   - Call `self.client.messages.create(model=self.model, max_tokens=max_tokens, system=system_msg, messages=user_msgs)`
   - Extract and return `response.content[0].text`
   - Catch `anthropic.APIError` and re-raise as a domain-specific error (or let it propagate)
3. In `stream()`:
   - Use `async with self.client.messages.stream(...)` context manager
   - `async for text in stream.text_stream:` yield each chunk
4. Handle the message format: Anthropic API takes `system` as a separate param, not in the messages list. The `build_messages()` from prompts.py returns `[{"role": "system", ...}, {"role": "user", ...}]` — the client should split these.

### Dependencies to Add
- None (uses `anthropic` added in the dependency item)

### Tests Needed
- Test `generate()` with a mocked `AsyncAnthropic` — verify correct model and message passing
- Test `stream()` with a mocked streaming response — verify yields text chunks
- Test that system message is extracted and passed as `system` param (not in messages list)

---

## Item: Summarizer module (`app/ai/summarizer.py`)
**Status:** done
**Phase:** 5

### Requirements
- Takes `TrendAnalysis` + `ForecastComparison` and generates a natural-language `InsightReport`
- Uses the prompt templates module to build messages and the LLM client to call Claude
- Returns structured `InsightReport` with parsed fields
- Also provides a streaming variant that yields text chunks
- Gracefully handles LLM errors (timeout, rate limit, etc.)

### Files to Create/Modify
- `app/ai/summarizer.py` — main summarizer logic

### Implementation Steps
1. Create `async def summarize(analysis: TrendAnalysis, forecast: ForecastComparison, prompt_version: str = "default", client: LLMClient | None = None) -> InsightReport`:
   - Build messages using `prompts.build_messages(analysis, forecast, version=prompt_version)`
   - Call `client.generate(messages)`
   - Parse the raw text into an `InsightReport`:
     - `source`, `query` from the analysis
     - `summary` = the full LLM response text
     - `risk_flags` = extract bullet points or keywords about risks (or empty list if none mentioned)
     - `recommended_action` = extract a one-line recommendation if present (or None)
     - `prompt_version` = the version used
   - Return `InsightReport`
2. Create `async def summarize_stream(analysis, forecast, prompt_version="default", client=None) -> AsyncGenerator[str, None]`:
   - Build messages same way
   - Yield chunks from `client.stream(messages)`
3. If `client` is None, create one using `settings.anthropic_api_key` — raise `ValueError("ANTHROPIC_API_KEY not configured")` if key is missing
4. Wrap LLM calls in try/except — catch `anthropic.APIError`, log warning, raise a `RuntimeError` with user-friendly message

### Dependencies to Add
- None

### Tests Needed
- Test `summarize()` with mocked LLM client returning canned text — verify `InsightReport` fields populated
- Test `summarize_stream()` with mocked streaming client — verify yields chunks
- Test missing API key raises `ValueError`
- Test LLM error is caught and re-raised with descriptive message

---

## Item: Pydantic models for Phase 5 (`Commentary`, `RiskFlag`, `InsightReport`)
**Status:** done
**Phase:** 5

### Requirements
- Define output models for the AI commentary layer
- Keep it simple — the LLM returns free-form text, we wrap it in structure

### Files to Create/Modify
- `app/models/schemas.py` — add new models at the bottom

### Implementation Steps
1. Define `RiskFlag` model:
   - `label: str` — short risk identifier (e.g. "volatility_spike", "data_insufficient")
   - `description: str` — one-sentence explanation
2. Define `InsightReport` model:
   - `source: str` — data source name
   - `query: str` — original query
   - `summary: str` — full LLM-generated narrative text
   - `risk_flags: list[RiskFlag]` — extracted risk indicators (can be empty)
   - `recommended_action: str | None` — one-line suggestion (optional)
   - `prompt_version: str` — which prompt template was used
   - `model_used: str` — which LLM model generated this

### Dependencies to Add
- None

### Tests Needed
- Test `InsightReport` serialization round-trip
- Test with empty `risk_flags` and `None` recommended_action
- Test all fields appear in `.model_dump()` output

---

## Item: `/api/insight` streaming SSE endpoint
**Status:** done
**Phase:** 5

### Requirements
- `GET /api/insight?source=...&query=...` — full pipeline: fetch → analyze → forecast → summarize via LLM
- Returns SSE (Server-Sent Events) stream via `StreamingResponse`
- Streams the LLM text as it generates, then sends a final JSON event with the structured `InsightReport`
- Falls back to 503 if `ANTHROPIC_API_KEY` is not configured
- Optional params: `start`, `end`, `horizon` (for forecast), `prompt_version` (default "default")

### Files to Create/Modify
- `app/routers/api.py` — add the new streaming endpoint

### Implementation Steps
1. Add `GET /insight` route:
   ```python
   @router.get("/insight")
   async def insight_stream(
       source: str = Query(...),
       query: str = Query(...),
       horizon: int = Query(14, ge=1, le=365),
       start: datetime.date | None = Query(None),
       end: datetime.date | None = Query(None),
       prompt_version: str = Query("default"),
   ):
   ```
2. Inside the handler:
   - Check `settings.anthropic_api_key` — if None, return 503 with detail "ANTHROPIC_API_KEY not configured"
   - Resolve adapter, fetch `ts` (same pattern as other endpoints)
   - Run `analyze(ts)` and `forecast(ts, horizon=horizon)`
   - Create an async generator that:
     - Sends an initial `event: status` SSE with `data: {"stage": "analyzing"}` (optional — nice UX hint)
     - Calls `summarize_stream(analysis, forecast, prompt_version=prompt_version)`
     - Yields each text chunk as `event: delta\ndata: {chunk}\n\n`
     - After streaming completes, runs `summarize()` (non-streaming) to get the structured `InsightReport` (or builds it from the accumulated text)
     - Sends a final `event: complete\ndata: {insight_report_json}\n\n`
   - Return `StreamingResponse(generator(), media_type="text/event-stream")`
3. Error handling: wrap in try/except, send `event: error\ndata: {message}\n\n` on failure

### Dependencies to Add
- None (FastAPI `StreamingResponse` is built-in, `sse-starlette` not needed for basic SSE)

### Tests Needed
- Test successful SSE stream — mock adapter + LLM, verify response is `text/event-stream`
- Test SSE events contain `delta` and `complete` event types
- Test missing API key returns 503
- Test unknown source returns 404
- Test missing query returns 422
- Test `prompt_version` parameter is accepted

---

## Item: Update `app/ai/__init__.py` exports
**Status:** done
**Phase:** 5

### Requirements
- Export the main public API from the `app/ai` package

### Files to Create/Modify
- `app/ai/__init__.py` — add exports

### Implementation Steps
1. Add `from app.ai.summarizer import summarize, summarize_stream`
2. Add `__all__ = ["summarize", "summarize_stream"]`

### Dependencies to Add
- None

### Tests Needed
- None (verified by import in other tests)

---

## Phase 5 Execution Order

1. Add `anthropic` dependency + config (`pyproject.toml`, `app/config.py`)
2. Pydantic models (`InsightReport`, `RiskFlag` in `schemas.py`)
3. Prompt templates (`app/ai/prompts.py` + tests)
4. LLM client (`app/ai/client.py` + tests)
5. Summarizer (`app/ai/summarizer.py` + tests)
6. SSE endpoint (`/api/insight` in `app/routers/api.py` + API tests)
7. Update `app/ai/__init__.py`
8. Full test suite + lint

Items 3 and 4 are independent of each other and can be developed in either order.

---

## Files Summary

### New Files (4 modules + 4 test files)

| File | Purpose |
|------|---------|
| `app/ai/prompts.py` | Prompt templates, context formatter, version registry |
| `app/ai/client.py` | Async Anthropic SDK wrapper (generate + stream) |
| `app/ai/summarizer.py` | Orchestrator: build prompts → call LLM → return InsightReport |
| `tests/test_prompts.py` | Unit tests for prompt formatting and version registry |
| `tests/test_llm_client.py` | Unit tests for LLM client (mocked Anthropic SDK) |
| `tests/test_summarizer.py` | Unit tests for summarizer (mocked LLM client) |
| `tests/test_api_insight.py` | API endpoint tests for SSE streaming (mocked adapter + LLM) |

### Modified Files (4)

| File | Change |
|------|--------|
| `pyproject.toml` | Add `anthropic>=0.40.0` dependency |
| `app/config.py` | Add `anthropic_api_key` setting |
| `app/models/schemas.py` | Add `RiskFlag`, `InsightReport` models |
| `app/routers/api.py` | Add `GET /api/insight` SSE endpoint |
| `app/ai/__init__.py` | Export `summarize`, `summarize_stream` |

---

## Key Design Decisions

- **Anthropic Claude via official SDK** — async-native, streaming built-in, clean API
- **Default model: `claude-sonnet-4-20250514`** — fast, cost-effective for summaries; configurable via constructor
- **Prompts as Python constants** — type-safe, versionable, no file I/O or template engine dependencies
- **SSE streaming** — progressive text delivery via `text/event-stream`, works with browser `EventSource`; final `complete` event carries the structured `InsightReport` JSON
- **Graceful degradation** — app starts without `ANTHROPIC_API_KEY`; `/api/insight` returns 503, all other endpoints unaffected
- **Mocked tests throughout** — no real LLM calls in tests; mock at the SDK boundary
- **Risk flags extracted from LLM text** — simple keyword/pattern matching on the response; not perfect but useful. Can be improved later with structured output or tool use

---
---

# Phase 6: Visualization & Dashboard

> React + Vite SPA with Tailwind CSS, served as static files from FastAPI.
> Charts via Chart.js (react-chartjs-2). Independent of Phase 5 — AI commentary
> section is shown only if `/api/insight` is available.

---

## Item: Scaffold React + Vite + Tailwind project
**Status:** done
**Phase:** 6

### Requirements
- Create a `frontend/` directory at the project root with a Vite + React + TypeScript setup
- Add Tailwind CSS for styling
- Configure Vite to build output into `frontend/dist/`
- FastAPI serves `frontend/dist/` as static files in production
- During development, Vite dev server proxies API requests to FastAPI on port 8000

### Files to Create/Modify
- `frontend/` — new directory (entire React project)
- `frontend/package.json` — dependencies: react, react-dom, react-chartjs-2, chart.js, tailwindcss
- `frontend/vite.config.ts` — proxy `/api` to `http://localhost:8000`, build output to `dist/`
- `frontend/tailwind.config.js` — content paths for Tailwind purge
- `frontend/postcss.config.js` — Tailwind + autoprefixer
- `frontend/tsconfig.json` — TypeScript config
- `frontend/index.html` — Vite entry point
- `frontend/src/main.tsx` — React entry point
- `frontend/src/App.tsx` — root component with layout shell
- `frontend/src/index.css` — Tailwind directives (`@tailwind base/components/utilities`)
- `app/main.py` — mount `StaticFiles` for `frontend/dist` and serve `index.html` as catch-all

### Implementation Steps
1. Run `npm create vite@latest frontend -- --template react-ts` (or scaffold manually)
2. Install dependencies: `npm install react-chartjs-2 chart.js`
3. Install dev dependencies: `npm install -D tailwindcss @tailwindcss/vite`
4. Configure `vite.config.ts`:
   - Set `server.proxy` to forward `/api` and `/health` to `http://localhost:8000`
   - Set `build.outDir` to `dist`
5. Configure Tailwind (via Vite plugin + CSS import)
6. Create minimal `App.tsx` with a header and placeholder content
7. Update `app/main.py`:
   - Add `from fastapi.staticfiles import StaticFiles`
   - Mount `app.mount("/", StaticFiles(directory="frontend/dist", html=True))` — AFTER the API router so `/api/*` takes priority
   - Only mount if `frontend/dist` directory exists (don't crash if frontend isn't built)
8. Add `frontend/dist/` to `.gitignore`
9. Verify: `cd frontend && npm run dev` opens the app with Tailwind styles working

### Dependencies to Add
- `react`, `react-dom`, `react-chartjs-2`, `chart.js` (npm, frontend)
- `tailwindcss`, `@tailwindcss/vite` (npm dev, frontend)
- No new Python dependencies

### Tests Needed
- None (verified manually — frontend scaffolding)

---

## Item: API client module and TypeScript types
**Status:** done
**Phase:** 6

### Requirements
- Type-safe TypeScript client for all backend API endpoints
- Types mirror the Pydantic schemas: `TimeSeries`, `DataPoint`, `TrendAnalysis`, `ForecastComparison`, etc.
- Fetch functions for each endpoint: `fetchSources`, `fetchSeries`, `fetchAnalysis`, `fetchForecast`
- Optional `fetchInsight` that returns an `EventSource` for SSE (Phase 5 dependent — only used if available)

### Files to Create/Modify
- `frontend/src/api/types.ts` — TypeScript interfaces matching Pydantic models
- `frontend/src/api/client.ts` — fetch wrappers for each endpoint

### Implementation Steps
1. Define interfaces in `types.ts`:
   - `DataPoint { date: string; value: number }`
   - `TimeSeries { source: string; query: string; points: DataPoint[]; metadata: Record<string, unknown> }`
   - `DataSourceInfo { name: string; description: string }`
   - `TrendSignal`, `SeasonalityResult`, `AnomalyReport`, `StructuralBreak`, `TrendAnalysis`
   - `ForecastPoint`, `ModelForecast`, `ModelEvaluation`, `ForecastComparison`
   - `InsightReport` (for Phase 5, optional)
2. Create fetch functions in `client.ts`:
   - `fetchSources(): Promise<DataSourceInfo[]>` — `GET /api/sources`
   - `fetchSeries(source, query, start?, end?): Promise<TimeSeries>` — `GET /api/series`
   - `fetchAnalysis(source, query, start?, end?, anomalyMethod?): Promise<TrendAnalysis>` — `GET /api/analyze`
   - `fetchForecast(source, query, horizon?, start?, end?): Promise<ForecastComparison>` — `GET /api/forecast`
3. All fetch functions handle errors (non-200 responses) by throwing with the API error detail
4. Use `URLSearchParams` for query string building

### Dependencies to Add
- None (uses built-in `fetch` API)

### Tests Needed
- None (integration tested via the dashboard components)

---

## Item: Source selector and query input component
**Status:** done
**Phase:** 6

### Requirements
- Dropdown to select a data source (populated from `/api/sources`)
- Text input for the query (e.g. package name, repo, coin ID)
- Placeholder text updates based on selected source (e.g. "fastapi" for PyPI, "owner/repo" for GitHub)
- Submit button to load data
- Optional date range inputs (start/end)
- Horizon selector for forecast (slider or number input, 1-365, default 14)

### Files to Create/Modify
- `frontend/src/components/QueryForm.tsx` — the form component
- `frontend/src/hooks/useApi.ts` — custom hook managing fetch state (loading, error, data)

### Implementation Steps
1. Create `useApi` hook:
   - State: `loading`, `error`, `sources`, `series`, `analysis`, `forecast`
   - On mount: fetch sources list
   - `loadData(source, query, horizon, start?, end?)`: fetches series, analysis, and forecast in parallel
2. Create `QueryForm` component:
   - Source dropdown populated from `sources` state
   - Query text input with dynamic placeholder
   - Horizon number input (default 14)
   - Submit button — calls `loadData`
   - Loading spinner state
   - Error display (red alert banner)
3. Style with Tailwind: clean card layout, responsive flex/grid

### Dependencies to Add
- None

### Tests Needed
- None (UI component — tested manually)

---

## Item: Time-series line chart with raw data
**Status:** done
**Phase:** 6

### Requirements
- Line chart showing the raw `TimeSeries` data points (date vs value)
- X-axis: dates, Y-axis: values
- Tooltip on hover showing exact date and value
- Zoom: Chart.js zoom plugin for click-drag date range zoom
- Responsive: fills container width

### Files to Create/Modify
- `frontend/src/components/charts/SeriesChart.tsx` — the chart component
- `frontend/src/components/Dashboard.tsx` — main dashboard layout composing all charts

### Implementation Steps
1. Install `chartjs-plugin-zoom` and `chartjs-adapter-date-fns` (for time axis):
   - `npm install chartjs-plugin-zoom chartjs-adapter-date-fns date-fns`
2. Register Chart.js plugins in `main.tsx`:
   - `Chart.register(...registerables)`, zoom plugin
3. Create `SeriesChart` component:
   - Props: `series: TimeSeries`
   - Render a `<Line>` chart with:
     - Dataset: points mapped to `{ x: date, y: value }`
     - X-axis: `type: 'time'`, time unit auto-detected
     - Tooltip: show date + value formatted
     - Zoom: enabled on x-axis via drag
4. Create `Dashboard` component:
   - Layout: `QueryForm` at top, charts below in a grid
   - Conditionally renders charts only when data is loaded

### Dependencies to Add
- `chartjs-plugin-zoom`, `chartjs-adapter-date-fns`, `date-fns` (npm, frontend)

### Tests Needed
- None (visual component)

---

## Item: Forecast overlay with confidence bands
**Status:** done
**Phase:** 6

### Requirements
- Overlay the recommended model's forecast on the same chart as the raw series
- Forecast line in a different color (dashed)
- Confidence interval as a shaded band (fill between `lower_ci` and `upper_ci`)
- Legend showing "Actual" vs "Forecast (model_name)" vs "95% CI"
- Model selector to switch between forecast models

### Files to Create/Modify
- `frontend/src/components/charts/ForecastChart.tsx` — combined series + forecast chart
- `frontend/src/components/ModelSelector.tsx` — dropdown to pick which model's forecast to display

### Implementation Steps
1. Create `ForecastChart` component:
   - Props: `series: TimeSeries`, `forecast: ForecastComparison`, `selectedModel: string`
   - Dataset 1: raw series (solid blue line)
   - Dataset 2: forecast values (dashed orange line)
   - Dataset 3: upper CI (transparent line, used as fill boundary)
   - Dataset 4: lower CI (with `fill: '-1'` to shade between lower and upper)
   - Use Chart.js `fill` option for the confidence band
2. Create `ModelSelector` component:
   - Dropdown listing all model names from `forecast.forecasts`
   - Badge showing recommended model
   - Shows MAE score next to each model name (from evaluations)
3. When user switches model, the chart re-renders with that model's forecast points

### Dependencies to Add
- None

### Tests Needed
- None (visual component)

---

## Item: Trend analysis panel
**Status:** done
**Phase:** 6

### Requirements
- Trend direction indicator: colored arrow or badge ("Rising", "Falling", "Stable") with momentum value
- Seasonality status: detected/not-detected, period if detected
- Anomaly count with severity indicator
- Structural breaks listed with dates

### Files to Create/Modify
- `frontend/src/components/AnalysisPanel.tsx` — trend analysis display

### Implementation Steps
1. Create `AnalysisPanel` component:
   - Props: `analysis: TrendAnalysis`
   - Section 1: **Trend** — direction badge (green/red/gray for rising/falling/stable), momentum value, acceleration value
   - Section 2: **Seasonality** — "Weekly pattern detected (strength: 0.7)" or "No seasonality detected"
   - Section 3: **Anomalies** — count badge, list of anomaly dates/values if < 10, truncated with "and N more" otherwise
   - Section 4: **Structural Breaks** — list of break dates with method labels
2. Style with Tailwind cards, color-coded badges

### Dependencies to Add
- None

### Tests Needed
- None (visual component)

---

## Item: Model comparison table
**Status:** done
**Phase:** 6

### Requirements
- Table showing all model evaluations side by side
- Columns: Model Name, MAE, RMSE, MAPE, Train Size, Test Size
- Highlight the recommended model row
- Sortable by any metric column (click column header)

### Files to Create/Modify
- `frontend/src/components/EvaluationTable.tsx` — comparison table

### Implementation Steps
1. Create `EvaluationTable` component:
   - Props: `evaluations: ModelEvaluation[]`, `recommended: string`
   - Render a `<table>` with sortable column headers
   - Highlight recommended model row with a distinct background color
   - Format numbers to 2 decimal places
   - Click column header to sort ascending/descending
2. Use Tailwind table utilities for clean styling

### Dependencies to Add
- None

### Tests Needed
- None (visual component)

---

## Item: AI commentary section (Phase 5 optional)
**Status:** done
**Phase:** 6

### Requirements
- Section that displays AI-generated commentary if Phase 5 is implemented
- Connects to `/api/insight` SSE endpoint
- Shows streaming text as it arrives
- Falls back gracefully: if endpoint returns 503 (no API key) or doesn't exist, shows a "AI commentary not available" placeholder
- Styled as a distinct card/panel

### Files to Create/Modify
- `frontend/src/components/InsightPanel.tsx` — AI commentary display

### Implementation Steps
1. Create `InsightPanel` component:
   - Props: `source: string`, `query: string`, `horizon: number`, `enabled: boolean`
   - On mount (when `enabled` is true): open `EventSource` to `/api/insight?source=...&query=...`
   - Listen for `delta` events — append text chunks to display
   - Listen for `complete` event — parse JSON, show structured insight
   - Listen for `error` events — show error message
   - If `EventSource` fails to connect (503, network error): show "AI commentary unavailable" placeholder
2. `enabled` flag starts as `false`; after series/forecast load, check if `/api/insight` is reachable (HEAD request or try/catch on EventSource)
3. Loading state: show typing indicator while streaming
4. Render as a Tailwind card with prose-style text

### Dependencies to Add
- None (uses built-in `EventSource` API)

### Tests Needed
- None (visual component, Phase 5 dependent)

---

## Item: Responsive dashboard layout
**Status:** done
**Phase:** 6

### Requirements
- Desktop: 2-column grid (charts left, analysis/table right)
- Tablet: single column, stacked
- Mobile: single column, simplified
- Header with TrendLab branding
- Footer or attribution line

### Files to Create/Modify
- `frontend/src/App.tsx` — layout shell
- `frontend/src/components/Dashboard.tsx` — grid layout composing all components

### Implementation Steps
1. Update `App.tsx`:
   - Header bar: "TrendLab" title, simple branding
   - Main content area: `<Dashboard />` component
2. Create/update `Dashboard` layout:
   - Top: `<QueryForm />`
   - Grid:
     - Left column (2/3 width on desktop): `<ForecastChart />`, `<EvaluationTable />`
     - Right column (1/3 width): `<AnalysisPanel />`, `<InsightPanel />`
   - On tablet/mobile: single column, all stacked
3. Use Tailwind responsive utilities: `grid-cols-1 lg:grid-cols-3`, `lg:col-span-2`
4. Add inter-component spacing with consistent Tailwind gap/margin

### Dependencies to Add
- None

### Tests Needed
- None (layout — tested manually)

---

## Item: FastAPI static file serving
**Status:** done
**Phase:** 6

### Requirements
- Mount `frontend/dist/` as static files in FastAPI
- Serve `index.html` for all non-API routes (SPA catch-all)
- Only mount if the `frontend/dist` directory exists (don't break the API if frontend isn't built)
- API routes (`/api/*`, `/health`, `/`) take priority over static files

### Files to Create/Modify
- `app/main.py` — add static file mount

### Implementation Steps
1. Add to `app/main.py` after `app.include_router(...)`:
   ```python
   import os
   from pathlib import Path
   from fastapi.staticfiles import StaticFiles

   frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
   if frontend_dist.is_dir():
       app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
   ```
2. The `html=True` option makes StaticFiles serve `index.html` for any path that doesn't match a file — enabling SPA client-side routing
3. This mount goes LAST so API routes take priority
4. Add `frontend/dist/` and `frontend/node_modules/` to `.gitignore`

### Dependencies to Add
- None (FastAPI `StaticFiles` is built-in via starlette)

### Tests Needed
- Test that `/api/sources` still works when static mount is active
- Test that a non-API path returns 200 (serves index.html) when `frontend/dist` exists

---

## Item: Development workflow scripts
**Status:** done
**Phase:** 6

### Requirements
- Simple way to run both frontend dev server and backend simultaneously
- Build command for production

### Files to Create/Modify
- `frontend/package.json` — add scripts
- Update CLAUDE.md with new commands

### Implementation Steps
1. In `frontend/package.json`, ensure scripts:
   - `"dev"` — runs Vite dev server (default)
   - `"build"` — runs Vite production build
   - `"preview"` — runs Vite preview server
2. Development workflow:
   - Terminal 1: `uv run uvicorn app.main:app --reload` (backend)
   - Terminal 2: `cd frontend && npm run dev` (frontend with API proxy)
3. Production build: `cd frontend && npm run build` → then `uv run uvicorn app.main:app` serves everything
4. Update CLAUDE.md commands section

### Dependencies to Add
- None

### Tests Needed
- None (workflow documentation)

---

## Phase 6 Execution Order

1. Scaffold React + Vite + Tailwind project
2. API client module and TypeScript types
3. Source selector and query input component + `useApi` hook
4. Time-series line chart (raw data)
5. Forecast overlay with confidence bands + model selector
6. Trend analysis panel
7. Model comparison table
8. AI commentary section (optional Phase 5 integration)
9. Responsive dashboard layout (compose everything)
10. FastAPI static file serving
11. Development workflow scripts + CLAUDE.md update
12. Manual QA: verify all views on desktop and tablet

Items 6 and 7 are independent and can be developed in either order.
Items 4 and 5 can be merged into a single chart component if preferred.

---

## Files Summary

### New Files

| File | Purpose |
|------|---------|
| `frontend/` (entire directory) | React + Vite + Tailwind SPA |
| `frontend/src/api/types.ts` | TypeScript interfaces matching Pydantic models |
| `frontend/src/api/client.ts` | Fetch wrappers for all API endpoints |
| `frontend/src/hooks/useApi.ts` | Custom hook managing API fetch state |
| `frontend/src/components/QueryForm.tsx` | Source selector + query input + horizon |
| `frontend/src/components/Dashboard.tsx` | Main dashboard layout grid |
| `frontend/src/components/charts/SeriesChart.tsx` | Raw time-series line chart |
| `frontend/src/components/charts/ForecastChart.tsx` | Series + forecast + CI bands |
| `frontend/src/components/ModelSelector.tsx` | Dropdown to switch forecast models |
| `frontend/src/components/AnalysisPanel.tsx` | Trend/seasonality/anomaly display |
| `frontend/src/components/EvaluationTable.tsx` | Model comparison table |
| `frontend/src/components/InsightPanel.tsx` | AI commentary (Phase 5 optional) |

### Modified Files

| File | Change |
|------|--------|
| `app/main.py` | Mount `frontend/dist` as static files |
| `.gitignore` | Add `frontend/dist/`, `frontend/node_modules/` |
| `CLAUDE.md` | Add frontend dev commands |

---

## Key Design Decisions

- **React + Vite + TypeScript** — modern toolchain, fast HMR, type safety. Vite proxies to FastAPI in dev
- **Tailwind CSS** — utility-first, no custom CSS framework. Responsive breakpoints built in
- **Chart.js via react-chartjs-2** — lightweight, well-documented, supports time axes, zoom, and fill between lines for CI bands
- **Built output served by FastAPI** — single deployment unit. `StaticFiles(html=True)` handles SPA routing
- **Phase 5 independent** — InsightPanel gracefully degrades if `/api/insight` is unavailable (503 or missing)
- **No SSR needed** — pure client-side SPA. Data comes from the existing JSON API
- **No Python test changes** — all frontend code is tested manually or via browser. Python tests remain backend-only
