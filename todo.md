# TrendLab — Remaining Work

> Phases 1-6 complete. See FEATURES.md for everything built so far.

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
