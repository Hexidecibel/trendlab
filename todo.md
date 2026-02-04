# TrendLab — Build Plan

> From bare FastAPI scaffold to AI-powered trend explorer & forecaster.
> Each phase produces a working, testable increment.

---

## Phase 1: Foundation — Data Layer & First Adapter

**Goal:** Establish the data adapter pattern and pull real time-series data from one source.

- [x] Design the `DataAdapter` abstract base class (ABC) defining the interface all adapters share: `fetch(query, start, end) -> TimeSeries`
- [x] Define core Pydantic models: `TimeSeries` (timestamps + values + metadata), `DataPoint`, `DataSourceConfig`
- [x] Create project directory structure: `app/data/adapters/`, `app/analysis/`, `app/forecasting/`, `app/ai/`
- [x] Implement the first adapter: **PyPI download counts** (no API key needed, uses `pypistats` public JSON API)
- [x] Add a `/api/sources` endpoint listing available data adapters
- [x] Add a `/api/series` endpoint that accepts a source + query and returns a `TimeSeries`
- [x] Add `httpx` as a project dependency (already in dev deps, promote to main)
- [x] Write integration tests for the PyPI adapter (with mocked HTTP responses)
- [x] Write API tests for the new endpoints

**You'll have:** A running API that fetches real PyPI download data and returns clean JSON time-series.

---

## Phase 2: Second Adapter & Adapter Registry

**Goal:** Prove the adapter pattern works by adding a second source and a registry to manage them.

- [x] Implement second adapter: **GitHub stargazers timeline** (requires `GITHUB_TOKEN`)
- [x] Build an `AdapterRegistry` — *(done in Phase 1)*
- [x] Add `.env` support for API keys (`GITHUB_TOKEN`, etc.)
- [x] Update `/api/sources` to pull from the registry dynamically — *(done in Phase 1)*
- [x] Update `/api/series` to resolve adapters via the registry — *(done in Phase 1)*
- [x] Add third adapter: **CoinGecko crypto prices** (free, no auth)
- [x] Tests for GitHub and CoinGecko adapters (mocked)

**You'll have:** A pluggable data system where adding a new source means writing one class.

---

## Phase 3: Trend Detection Engine

**Goal:** Analyze ingested time-series and output structured trend signals.

- [x] Implement `trend_metrics.py` — compute: momentum (rate of change), acceleration (second derivative), moving averages (7d, 30d)
- [x] Implement `seasonality.py` — detect periodic patterns using autocorrelation or FFT
- [x] Implement `anomalies.py` — flag outliers using z-score or IQR methods
- [x] Define Pydantic models for analysis output: `TrendSignal`, `SeasonalityResult`, `AnomalyReport`
- [x] Implement `structural_breaks.py` — detect regime changes (simple: CUSUM or rolling variance threshold)
- [x] Create an `analyze()` orchestrator that runs all detectors on a `TimeSeries` and returns a combined `TrendAnalysis`
- [x] Add `/api/analyze` endpoint — accepts source + query, returns trend analysis
- [x] Write unit tests for each analysis module with known synthetic data
- [x] Write API tests for the analyze endpoint

**You'll have:** An API that tells you *what's happening* in a trend — not just the raw numbers.

---

## Phase 4: Forecasting Engine

**Goal:** Predict where a trend is heading using multiple models, then compare them.

- [x] Implement `baseline.py` — naive forecasts: last value, moving average projection, linear extrapolation
- [x] Implement `statistical.py` — AutoETS wrapper via statsforecast (replaced Prophet plan; statsforecast already a dependency)
- [x] Implement `evaluation.py` — backtest framework: train/test split, compute MAE, RMSE, MAPE per model
- [x] Define Pydantic models: `ForecastPoint` (point + confidence interval), `ModelEvaluation`, `ForecastComparison` (defined in Phase 3 schemas)
- [x] Create a `forecast()` orchestrator that runs all 4 models, evaluates, and ranks by lowest MAE
- [x] Add `/api/forecast` endpoint — accepts source + query + horizon (1-365, default 14), returns forecasts from all models with evaluation scores
- [x] Write tests: unit tests for each model with synthetic data, API tests for forecast endpoint (52 new tests)

**You'll have:** An API that answers "where is this going?" with multiple competing opinions and honest evaluation.

---

## Phase 5: AI Commentary Layer

**Goal:** Use an LLM to generate natural-language summaries of trends and forecasts.

- [x] Set up LLM integration — Anthropic Claude via `anthropic` SDK, add dependency + config
- [x] Implement `summarizer.py` — takes `TrendAnalysis` + `ForecastComparison` and generates a narrative via Claude
- [x] Create prompt templates in `app/ai/prompts.py` — Python module with versioned prompts (default, concise, detailed)
- [x] Implement `app/ai/client.py` — async Anthropic SDK wrapper with generate + stream methods
- [x] Define Pydantic models: `RiskFlag`, `InsightReport` in `schemas.py`
- [x] Add `/api/insight` endpoint — SSE streaming: fetch data → analyze → forecast → stream LLM commentary
- [x] Implement prompt versioning / selection (swap prompt strategies without code changes)
- [x] Tests for all modules (mocked LLM responses), API tests for SSE insight endpoint (37 new tests)

**You'll have:** An endpoint that returns something like: *"PyPI downloads for fastapi accelerated 3x over the last 14 days. Prophet and baseline models agree on continued growth, but variance is rising — this could be a spike, not sustained momentum."*

---

## Phase 6: Visualization & Dashboard

**Goal:** Make the data visible — a lightweight frontend that renders charts from the API.

- [x] Choose frontend approach: React + Vite + Tailwind CSS, built and served from FastAPI
- [x] Implement time-series line chart with raw data (Chart.js via react-chartjs-2)
- [x] Add forecast overlay with confidence bands (shaded region) + model selector
- [x] Add trend analysis panel (direction indicator, seasonality, anomalies, breaks)
- [x] Add model comparison table (MAE/RMSE/MAPE, sortable, recommended highlighted)
- [x] Display AI commentary alongside charts (optional, graceful degradation if Phase 5 not implemented)
- [x] Add source selector, query input, and horizon control
- [x] Serve the frontend from FastAPI (StaticFiles mount, SPA catch-all)
- [x] Basic responsive layout — 2-col desktop, stacked tablet/mobile
- [x] API client module with TypeScript types matching Pydantic schemas

**You'll have:** A dashboard you can open in a browser, pick a data source, and see trends + forecasts + AI commentary in one view.

---

## Phase 7: Polish, Persistence & Production Readiness

**Goal:** Make it durable, deployable, and portfolio-worthy.

- [ ] Add SQLite (or PostgreSQL) persistence for fetched time-series data (avoid re-fetching on every request)
- [ ] Implement a caching layer — TTL-based cache so repeated queries don't hit external APIs
- [ ] Add background task scheduling — periodic data refresh using FastAPI background tasks or APScheduler
- [ ] Add proper error handling and structured error responses across all endpoints
- [ ] Add request validation and rate limiting
- [ ] Add logging (structured JSON logs)
- [ ] Add a `/api/compare` endpoint — compare two trends side by side
- [ ] Add a `/api/watchlist` endpoint — save trends to watch and get periodic updates
- [ ] Write a `Dockerfile` and `docker-compose.yml` for one-command deployment
- [ ] Add CI pipeline config (GitHub Actions): lint, test, type-check on every push
- [ ] Add OpenAPI schema customization — clean descriptions for all endpoints
- [ ] Add query autocomplete/lookup for adapters — e.g. football adapter needs a `/api/lookup?source=football` endpoint that returns available competitions and team IDs with names, so users don't need to know numeric IDs. Could also add placeholder hints per source in the frontend QueryForm.
- [ ] Final README with architecture diagram, screenshots, and setup instructions

**You'll have:** A deployable, documented project that demonstrates real engineering — not just code, but system thinking.

---

## Stretch Goals (Post-v1)

- [ ] Multi-tenant support — user accounts with personal watchlists
- [ ] LLM vs statistical forecast comparison — track where each method fails
- [ ] Webhook/Slack notifications when a watched trend crosses a threshold
- [ ] More adapters: Spotify, npm, Reddit, crypto exchanges
- [ ] Export reports as PDF
- [ ] Plugin system for community-contributed adapters
- [ ] Natural language trend analyzer — describe a team/player/stat in plain English, AI builds the query and analysis automatically
- [ ] Migrate frontend to MUI (Material UI) for richer UI components (data grids, autocomplete, dialogs)
- [ ] Add player-level queries to ASA adapter (xgoals, goals-added, xpass per player per game)

---

## Summary

| Phase | What You Build | Key Signal It Shows |
|-------|---------------|-------------------|
| 1 | Data adapter + first source | Clean abstractions, real data |
| 2 | Second adapter + registry | Pluggable architecture |
| 3 | Trend detection | Analytical depth, not just CRUD |
| 4 | Forecasting + evaluation | Model comparison, skepticism |
| 5 | AI commentary | LLM integration done right |
| 6 | Visualization | Full-stack delivery |
| 7 | Persistence + deploy | Production engineering |
