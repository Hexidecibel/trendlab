# TrendLab — Completed Features

> Everything built across Phases 1-6, plus post-phase additions.

---

## Phase 1: Foundation — Data Layer & First Adapter

- `DataAdapter` abstract base class with `fetch(query, start, end) -> TimeSeries`
- Core Pydantic models: `DataPoint`, `TimeSeries`, `DataSourceInfo`
- Project structure: `app/data/adapters/`, `app/analysis/`, `app/forecasting/`, `app/ai/`
- **PyPI adapter** — daily download counts via pypistats public API (no auth)
- `GET /api/sources` — lists all registered data adapters
- `GET /api/series` — fetches time-series from a named adapter
- `httpx` as runtime dependency
- Integration tests for PyPI adapter (mocked HTTP)
- API tests for sources and series endpoints

---

## Phase 2: Second Adapter & Adapter Registry

- **GitHub stargazers adapter** — stargazer timeline with pagination (requires `GITHUB_TOKEN`)
- **CoinGecko adapter** — crypto price history, free, no auth
- `AdapterRegistry` — pluggable dict-based registry
- `.env` support for API keys via `app/config.py`
- Conditional adapter registration (GitHub only if token configured)
- Tests for GitHub and CoinGecko adapters (mocked)

---

## Phase 3: Trend Detection Engine

- `trend_metrics.py` — momentum, acceleration, moving averages (7d/30d), direction labels
- `seasonality.py` — FFT-based autocorrelation, dominant period detection
- `anomalies.py` — z-score and IQR outlier detection
- `structural_breaks.py` — CUSUM and rolling variance regime change detection
- `analyze()` orchestrator combining all detectors into `TrendAnalysis`
- `GET /api/analyze` — fetch + analyze in one call
- Pydantic models: `TrendSignal`, `SeasonalityResult`, `AnomalyReport`, `StructuralBreak`, `TrendAnalysis`
- Unit tests for each analysis module with synthetic data

---

## Phase 4: Forecasting Engine

- `baseline.py` — naive, moving average, and linear regression forecasts
- `statistical.py` — AutoETS via statsforecast
- `evaluation.py` — backtest framework with MAE, RMSE, MAPE metrics
- `forecast()` orchestrator — runs all 4 models, backtests, recommends best by MAE
- `GET /api/forecast` — accepts source + query + horizon (1-365)
- Pydantic models: `ForecastPoint`, `ModelForecast`, `ModelEvaluation`, `ForecastComparison`
- 52 new tests covering all forecast modules

---

## Phase 5: AI Commentary Layer

- Anthropic Claude integration via `anthropic` SDK
- `app/ai/prompts.py` — versioned prompt templates (default, concise, detailed) with context formatter
- `app/ai/client.py` — async Anthropic SDK wrapper (generate + stream)
- `app/ai/summarizer.py` — orchestrator producing `InsightReport`
- `GET /api/insight` — SSE streaming endpoint (fetch -> analyze -> forecast -> stream LLM commentary)
- Graceful degradation — app starts without `ANTHROPIC_API_KEY`, endpoint returns 503
- Pydantic models: `RiskFlag`, `InsightReport`
- 37 new tests (mocked LLM responses)

---

## Phase 6: Visualization & Dashboard

- React + Vite + Tailwind CSS frontend, built and served from FastAPI
- Time-series line chart with raw data (Chart.js via react-chartjs-2)
- Forecast overlay with confidence bands (shaded region) + model selector
- Trend analysis panel (direction, seasonality, anomalies, structural breaks)
- Model comparison table (MAE/RMSE/MAPE, sortable, recommended highlighted)
- AI commentary panel with SSE streaming (graceful degradation)
- Source selector, query input, horizon control
- `StaticFiles` mount with SPA catch-all (`html=True`)
- Responsive layout — 2-col desktop, stacked tablet/mobile
- TypeScript API client with types matching Pydantic schemas

---

## Post-Phase Additions

### ASA (American Soccer Analysis) Adapter
- 15 metrics across xgoals and xpass endpoints (goals, xG, shots, points, pass completion, etc.)
- Team autocomplete via `GET /api/lookup?source=asa&lookup_type=teams&league=mls`
- League selector (MLS, NWSL, USL)
- Query format: `league:entity_type:entity_id:metric[:home_away:stage]`
- Joins games endpoint (dates) with metrics endpoint (values) via `game_id`
- 19 tests

### Dynamic Form System
- `FormField`, `FormFieldOption`, `LookupItem` Pydantic models
- `DataAdapter.form_fields()` — adapters declare their own UI fields (text/select/autocomplete)
- `DataAdapter.lookup()` — adapters provide autocomplete data
- `GET /api/lookup` endpoint for frontend autocomplete
- `QueryForm.tsx` dynamically renders adapter-specific forms with dependency chains

### Advanced Filters (ASA)
- Venue filter: All Games / Home Only / Away Only
- Stage filter: All Stages / Regular Season / Playoffs
- Filters applied at game level using `home_team_id`/`away_team_id` and `knockout_game` fields
- Backward-compatible query format (4-6 colon-separated parts)

### Date Range Filter
- Collapsible date range picker (start/end) in QueryForm
- Passed through to all API calls (series, analyze, forecast)

---

## Architecture Summary

| Layer | What | Key Signal |
|-------|------|-----------|
| Data adapters (5) | PyPI, GitHub, CoinGecko, Football, ASA | Pluggable architecture |
| Trend detection | Momentum, seasonality, anomalies, structural breaks | Analytical depth |
| Forecasting | 4 models + backtest evaluation | Model comparison, skepticism |
| AI commentary | LLM-generated narrative via SSE | LLM integration done right |
| Frontend | React + Chart.js dashboard | Full-stack delivery |
| Dynamic forms | Adapter-specific configurable UI | Extensible UX |

## Test Coverage

218 tests across all modules (all passing).
