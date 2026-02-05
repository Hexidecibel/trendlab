# TrendLab — Remaining Work

> Phases 1-6 complete. See FEATURES.md for everything built so far.

---

## Tier 1: Data Foundation

Everything else builds on this.

- [x] Add SQLite persistence — store raw series, analysis results, forecasts, and query configs; foundation for caching, shareable URLs, and saved views
- [x] Implement a caching layer — TTL-based cache on top of persistence so repeated queries don't hit external APIs
- [x] Time-based aggregation: optional `resample` param (week/month/season) on API endpoints, centralized utility in data layer, adapter-agnostic

---

## Tier 2: Core Features

The high-impact demos — what makes TrendLab compelling.

- [x] Multi-series comparison: support comparing 2-3 teams/entities on the same chart (NL parser, /api/compare endpoint, dashboard overlay with legend)
- [x] Derived metrics / computed series: `?apply=rolling_avg_7d|pct_change|cumulative|normalize` param to transform series without new adapters — essential for meaningful cross-source comparisons
- [x] Annotation layer: mark events on the timeline (manual or LLM-detected), surface structural breaks as chart annotations, vertical lines with labels
- [x] Cross-source correlation: endpoint that takes two series, returns r-value, lag analysis, and scatter plot — "does Bitcoin price correlate with crypto library downloads?"

---

## Tier 3: UX & Polish

Make it feel finished.

- [x] Saved views / shareable URLs: persist query config + results to DB, generate short URL or hash — load full view (series, analysis, forecast, annotations) from a single link
- [x] Add proper error handling and structured error responses across all endpoints
- [x] Frontend redesign — migrate to MUI (Material UI), better theme, better structuring/layout of data (currently functional but dense with a lot of information on screen)
- [x] Add player-level queries to ASA adapter (xgoals, goals-added, xpass per player per game)
- [x] Enhance current adapters — ASA allows advanced config of querying; determine if other adapters (PyPI, crypto, football-data) could benefit from similar configurable fields

---

## Tier 4: Production & Ops

Ship it.

- [x] Add logging (structured JSON logs)
- [x] Add request validation and rate limiting
- [x] Write a `Dockerfile` and `docker-compose.yml` for one-command deployment
- [x] Add CI pipeline config (GitHub Actions): lint, test, type-check on every push
- [x] Add OpenAPI schema customization — clean descriptions for all endpoints
- [x] Final README with architecture diagram, screenshots, and setup instructions

---

## Tier 5: New Adapters

Expand data source coverage.

- [ ] **CSV Upload adapter** — user uploads date/value CSV, instant analysis on custom data
- [ ] **npm adapter** — JavaScript package downloads (mirrors PyPI pattern)
- [ ] **Reddit adapter** — subreddit subscriber growth, post frequency
- [x] **Wikipedia adapter** — page view trends for any article, multiple languages, access/agent filters
- [x] **Stock/Finance adapter** — stock prices, ETFs, indices, crypto via Yahoo Finance (no auth)
- [x] **Weather adapter** — historical weather data for any location via Open-Meteo (no auth)

---

## Tier 6: UX Enhancements

Features that make the app shine.

- [ ] **Correlation Explorer UI** — third tab with scatter plot, r-values, lag analysis (backend ready)
- [ ] **Saved Views UI** — save/load/share buttons, "My Views" modal (backend ready)
- [ ] **Export PNG** — download chart as image (Chart.js built-in)
- [ ] **Forecast Accuracy Tracker** — store past forecasts, compare to actuals over time
- [ ] **NL Insights Feed** — auto-generate headline summaries, "What's interesting today?" widget
- [ ] **Export PDF Report** — analysis + forecast + insights as downloadable PDF

---

## Tier 7: Production & Ops

Ship it.

- [ ] Add logging (structured JSON logs)
- [ ] Add request validation and rate limiting
- [ ] Write a `Dockerfile` and `docker-compose.yml` for one-command deployment
- [ ] Add CI pipeline config (GitHub Actions): lint, test, type-check on every push
- [ ] Add OpenAPI schema customization — clean descriptions for all endpoints
- [ ] Final README with architecture diagram, screenshots, and setup instructions

---

## Tier 8: Future

Post-v1 ideas.

- [ ] Add a `/api/watchlist` endpoint — save trends to watch and get periodic updates
- [ ] Add background task scheduling — periodic data refresh using FastAPI background tasks or APScheduler
- [ ] Multi-tenant support — user accounts with personal watchlists
- [ ] Webhook/Slack notifications when a watched trend crosses a threshold
- [ ] LLM vs statistical forecast comparison — track where each method fails
- [ ] Plugin system for community-contributed adapters

---

## Done

- [x] Natural language trend analyzer — describe a team/player/stat in plain English, AI builds the query and analysis automatically
