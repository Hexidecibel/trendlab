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

- [planned] Saved views / shareable URLs: persist query config + results to DB, generate short URL or hash — load full view (series, analysis, forecast, annotations) from a single link
- [x] Add proper error handling and structured error responses across all endpoints
- [planned] Frontend redesign — migrate to MUI (Material UI), better theme, better structuring/layout of data (currently functional but dense with a lot of information on screen)
- [x] Add player-level queries to ASA adapter (xgoals, goals-added, xpass per player per game)
- [x] Enhance current adapters — ASA allows advanced config of querying; determine if other adapters (PyPI, crypto, football-data) could benefit from similar configurable fields

---

## Tier 4: Production & Ops

Ship it.

- [ ] Add logging (structured JSON logs)
- [ ] Add request validation and rate limiting
- [ ] Write a `Dockerfile` and `docker-compose.yml` for one-command deployment
- [ ] Add CI pipeline config (GitHub Actions): lint, test, type-check on every push
- [ ] Add OpenAPI schema customization — clean descriptions for all endpoints
- [ ] Final README with architecture diagram, screenshots, and setup instructions

---

## Tier 5: Future

Post-v1 ideas.

- [ ] Add a `/api/watchlist` endpoint — save trends to watch and get periodic updates
- [ ] Add background task scheduling — periodic data refresh using FastAPI background tasks or APScheduler
- [ ] Multi-tenant support — user accounts with personal watchlists
- [ ] Webhook/Slack notifications when a watched trend crosses a threshold
- [ ] More adapters: Spotify, npm, Reddit, crypto exchanges
- [ ] LLM vs statistical forecast comparison — track where each method fails
- [ ] Export reports as PDF
- [ ] Plugin system for community-contributed adapters

---

## Done

- [x] Natural language trend analyzer — describe a team/player/stat in plain English, AI builds the query and analysis automatically
