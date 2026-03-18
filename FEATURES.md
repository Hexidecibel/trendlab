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
- Custom "MLS Season" resample period (aggregates by calendar year)
- 19 tests

### Custom Resample Periods
- `DataAdapter.custom_resample_periods()` — adapters declare domain-specific time periods
- `DataAdapter.custom_resample()` — adapters implement custom aggregation logic
- `ResamplePeriod` model with value, label, and description
- `DataSourceInfo.resample_periods` exposed via `/api/sources` endpoint
- Frontend QueryForm dynamically shows custom resample options per source
- Implemented custom periods:
  - **ASA**: `mls_season` — aggregates by MLS/NWSL/USL season year (calendar year)
  - **Weather**: `meteorological_season` — Winter (Dec-Feb), Spring (Mar-May), Summer (Jun-Aug), Fall (Sep-Nov)
  - **Football**: `football_season` — European football season (Aug-May, e.g., 2023-24)
- 12 tests for custom resample system

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

## Tier 1: Data Foundation

### SQLite Persistence
- SQLAlchemy async ORM with aiosqlite driver
- Auto-create tables on app startup
- Alembic migrations for schema versioning
- Models: `SeriesRecord`, `AnalysisRecord`, `ForecastRecord`, `QueryConfig`, `SavedView`, `ForecastSnapshot`
- JSON columns for complex nested data (TrendAnalysis, ForecastComparison)
- Repository layer with async CRUD functions

### Caching Layer
- TTL-based cache with per-source configurable TTLs
- Cache-aware fetch: DB first → if stale, fetch from adapter → save to DB
- `?refresh=true` query param for cache bypass
- Automatic cache invalidation on re-fetch
- Default TTLs: crypto 15min, pypi 6hr, asa 24hr, github_stars 1hr

### Time-Based Aggregation
- `?resample` query param: `week`, `month`, `quarter`, `season`, `year`
- Aggregation method per adapter: `sum` for counts (PyPI), `mean` for rates (crypto)
- Applied between fetch and downstream consumers
- Period buckets: ISO week start, 1st of month, quarter starts, calendar year

---

## Tier 2: Core Features

### Multi-Series Comparison
- `POST /api/compare` — fetch 2-3 series in one request
- Cross-source comparison (e.g., Bitcoin vs PyPI downloads)
- Uniform resample/transforms applied to all series
- Frontend: Compare tab with overlay chart, per-series analysis panels
- Compare insight panel with AI-generated comparison commentary

### Derived Metrics / Computed Series
- `?apply` query param: pipe-delimited transforms
- Transforms: `rolling_avg_Nd`, `pct_change`, `cumulative`, `normalize`, `diff`
- Pipeline execution left-to-right
- Applied after resample, before analysis/forecast

### Annotation Layer
- Structural breaks as vertical lines with labels
- Anomaly points highlighted with red markers
- chartjs-plugin-annotation integration
- Toggle controls for show/hide annotations
- Anomaly method selector (z-score / IQR)

### Cross-Source Correlation
- `POST /api/correlate` — align two series by date, compute statistics
- Pearson r, Spearman ρ with p-values
- Lag analysis (-30 to +30 days)
- Scatter plot data for visualization
- Frontend: Correlate tab with scatter chart, stats card, lag bar chart

---

## Tier 3: UX & Polish

### Saved Views / Shareable URLs
- `POST /api/views` — save view config, returns short hash ID
- `GET /api/views` — list all saved views
- `GET /api/views/{hash}` — load view by hash
- `DELETE /api/views/{hash}` — delete view
- Frontend: Save View button, Views dropdown, shareable links

### Structured Error Handling
- Standardized error response model
- Global exception handlers (ValueError, httpx errors, catch-all)
- Consistent HTTP status codes (400, 404, 422, 503)
- Request ID tracking in error responses

### Frontend Redesign (MUI)
- Material UI v6 component library
- Tabbed layout: Forecast, Compare, Correlate
- Card-based layout for charts and panels
- Consistent theme and typography

### Player-Level ASA Queries
- "players" entity type for ASA adapter
- Player lookup per league
- Player xgoals and xpass metrics

### Enhanced Adapters
- Football adapter: competition select, team autocomplete
- GitHub adapter: improved placeholder text
- Weather adapter: location-based weather data
- Wikipedia adapter: page views by project
- Yahoo Finance adapter: stock/ETF price history

---

## Tier 5: New Adapters

### npm Adapter
- `app/data/adapters/npm.py`
- Fetches package download counts from npm API
- 180-day lookback (mirrors PyPI pattern)
- Simple text query (package name)

### CSV Upload Adapter
- `app/data/adapters/csv_upload.py`
- Upload custom CSV files for analysis
- Auto-detects date/value columns from common names
- Supports multiple date formats (YYYY-MM-DD, MM/DD/YYYY, etc.)
- In-memory storage with upload management
- Endpoints: `POST /upload-csv`, `GET /uploads`, `DELETE /uploads/{id}`
- Frontend: `CSVUpload.tsx` with drag-and-drop, preview, upload

### Reddit Adapter
- `app/data/adapters/reddit.py`
- Fetches subreddit metrics (subscribers, active users)
- Uses Reddit JSON API (no authentication required)
- Current snapshot only (API limitation)

---

## Tier 6: UX Enhancements

### Export PNG
- Download chart as PNG button on ForecastChart and CompareChart
- Uses Chart.js `toBase64Image()` method
- Filename includes source, query, and comparison info

### Correlation Explorer UI
- `CorrelateTab.tsx` component
- New "Correlate" tab in Dashboard
- Two series pickers with source/query inputs
- Scatter plot with correlation line
- Stats card: Pearson r, Spearman r, p-values, significance interpretation
- Lag correlation bar chart (positive/negative color coding)
- Export PNG for both charts

### Saved Views UI
- `SaveViewButton.tsx` — save current config with shareable link
- `ViewsDropdown.tsx` — load/delete saved views
- Copy link to clipboard functionality
- View preview with config details

### NL Insights Feed
- `GET /api/insights-feed` endpoint
- Auto-generated headline summaries for trending data
- `generate_headline()` function in summarizer
- `InsightsFeed.tsx` component with trend indicators
- Clickable insights to load analysis

### Export PDF Report
- `app/services/pdf_export.py` using reportlab + matplotlib
- Full analysis report as downloadable PDF
- Includes: title, summary statistics, trend analysis table, chart image, forecast table, AI insight
- `GET /api/export-pdf` endpoint
- `ExportPdfButton.tsx` frontend component

### Forecast Accuracy Tracker
- `ForecastSnapshot` DB model for storing predictions
- `POST /forecast-snapshot` — save current forecast for later comparison
- `GET /forecast-snapshots` — list past forecasts
- `GET /forecast-accuracy` — compare predictions vs actuals (MAE, RMSE, CI coverage)
- `ForecastAccuracyPanel.tsx` — expandable panel with snapshot table and accuracy metrics

### Plugin System
- `plugins/` directory for community-contributed adapters
- `app/plugins.py` — auto-loader scans directory on startup
- Drop-in `.py` files with `DataAdapter` subclass
- Full documentation in README.md with examples
- 9 tests for plugin loading logic

---

## Architecture Summary

| Layer | What | Key Signal |
|-------|------|-----------|
| Data adapters (10+) | PyPI, npm, GitHub, CoinGecko, Football, ASA, Wikipedia, Yahoo Finance, Weather, CSV + plugins | Pluggable architecture |
| Trend detection | Momentum, seasonality, anomalies, structural breaks | Analytical depth |
| Forecasting | 4 models + backtest evaluation + accuracy tracking | Model comparison, skepticism |
| AI commentary | LLM-generated narrative via SSE + insights feed | LLM integration done right |
| Frontend | React + MUI + Chart.js dashboard | Full-stack delivery |
| Dynamic forms | Adapter-specific configurable UI | Extensible UX |
| Persistence | SQLite + caching layer + saved views | Data durability |
| Export | PNG charts, PDF reports | Shareable outputs |

## Dependencies

### Backend
- fastapi, uvicorn, pydantic, python-dotenv
- httpx (async HTTP client)
- numpy, statsforecast (forecasting)
- anthropic (AI commentary)
- sqlalchemy[asyncio], aiosqlite, alembic (persistence)
- reportlab, matplotlib (PDF export)
- python-multipart (file uploads)

### Frontend
- React 18, Vite, TypeScript
- @mui/material, @mui/icons-material (UI components)
- chart.js, react-chartjs-2, chartjs-plugin-annotation, chartjs-plugin-zoom
