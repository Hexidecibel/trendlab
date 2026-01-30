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
