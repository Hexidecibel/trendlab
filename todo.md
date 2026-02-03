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

- [ ] Implement `baseline.py` — naive forecasts: last value, moving average projection, linear extrapolation
- [ ] Implement `prophet_model.py` — Facebook Prophet wrapper for time-series forecasting
- [ ] Add `prophet` (or `neuralprophet`) to project dependencies
- [ ] Implement `evaluator.py` — backtest framework: train/test split, compute MAE, RMSE, MAPE per model
- [ ] Define Pydantic models: `Forecast` (point + confidence interval), `ModelEvaluation`, `ForecastComparison`
- [ ] Create a `forecast()` orchestrator that runs all models, evaluates, and ranks them
- [ ] Add `/api/forecast` endpoint — accepts source + query + horizon, returns forecasts from all models with evaluation scores
- [ ] Optionally add an ARIMA-based model (`statsmodels`) as a third contender
- [ ] Write tests: unit tests for each model with synthetic data, API tests for forecast endpoint

**You'll have:** An API that answers "where is this going?" with multiple competing opinions and honest evaluation.

---

## Phase 5: AI Commentary Layer

**Goal:** Use an LLM to generate natural-language summaries of trends and forecasts.

- [ ] Set up LLM integration — choose provider (OpenAI, Anthropic, or local via Ollama) and add SDK dependency
- [ ] Implement `summarizer.py` — takes `TrendAnalysis` + `ForecastComparison` and generates a narrative
- [ ] Create prompt templates in `app/ai/prompts/` — structured prompts for: trend summary, forecast explanation, risk flags, "if this continues..." narratives
- [ ] Define Pydantic models: `Commentary`, `RiskFlag`, `InsightReport`
- [ ] Add `/api/insight` endpoint — the full pipeline: fetch data → analyze → forecast → summarize
- [ ] Add streaming support for the commentary (SSE via FastAPI `StreamingResponse`)
- [ ] Implement prompt versioning / selection (swap prompt strategies without code changes)
- [ ] Tests for summarizer (mocked LLM responses), API tests for insight endpoint

**You'll have:** An endpoint that returns something like: *"PyPI downloads for fastapi accelerated 3x over the last 14 days. Prophet and baseline models agree on continued growth, but variance is rising — this could be a spike, not sustained momentum."*

---

## Phase 6: Visualization & Dashboard

**Goal:** Make the data visible — a lightweight frontend that renders charts from the API.

- [ ] Choose frontend approach: static HTML + Chart.js (simplest), or lightweight React/Vite app
- [ ] Implement time-series line chart with raw data
- [ ] Add forecast overlay with confidence bands (shaded region)
- [ ] Add trend strength indicator (colored bar or gauge)
- [ ] Add seasonality heatmap (day-of-week or month grid)
- [ ] Add "now vs 30 days ago" comparison view
- [ ] Display AI commentary alongside charts
- [ ] Add source selector and query input
- [ ] Serve the frontend from FastAPI (static files or proxy in dev)
- [ ] Basic responsive layout — works on desktop and tablet

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
