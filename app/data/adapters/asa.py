"""American Soccer Analysis adapter — team metrics for MLS, NWSL, USL."""

import asyncio
import datetime

import httpx

from app.data.base import DataAdapter
from app.logging_config import get_logger
from app.models.schemas import (
    DataPoint,
    FormField,
    FormFieldOption,
    LookupItem,
    ResamplePeriod,
    TimeSeries,
)

logger = get_logger(__name__)

# Rate limit ASA API requests - only one at a time with delay between
_asa_lock = asyncio.Lock()
_asa_last_request = 0.0
_ASA_REQUEST_DELAY = 0.5  # seconds between requests


async def _rate_limited_get(client: httpx.AsyncClient, url: str, **kwargs) -> httpx.Response:
    """Make a rate-limited GET request to ASA API."""
    global _asa_last_request
    async with _asa_lock:
        # Wait if needed to respect rate limit
        import time
        now = time.time()
        elapsed = now - _asa_last_request
        if elapsed < _ASA_REQUEST_DELAY:
            await asyncio.sleep(_ASA_REQUEST_DELAY - elapsed)

        response = await client.get(url, **kwargs)
        _asa_last_request = time.time()
        return response

ASA_API_URL = "https://app.americansocceranalysis.com/api/v1"

LEAGUES = ["mls", "nwsl", "usl"]

# Metrics available from the xgoals endpoint (split_by_games)
XGOALS_METRICS = [
    "goals_for",
    "goals_against",
    "goal_difference",
    "xgoals_for",
    "xgoals_against",
    "xgoal_difference",
    "shots_for",
    "shots_against",
    "points",
    "xpoints",
]

# Metrics available from the xpass endpoint (split_by_games)
XPASS_METRICS = [
    "pass_completion_percentage_for",
    "xpass_completion_percentage_for",
    "passes_completed_over_expected_for",
    "attempted_passes_for",
    "pass_completion_percentage_against",
]

ALL_METRICS = XGOALS_METRICS + XPASS_METRICS

# Map metric name to which endpoint category it comes from
METRIC_ENDPOINT: dict[str, str] = {}
for m in XGOALS_METRICS:
    METRIC_ENDPOINT[m] = "xgoals"
for m in XPASS_METRICS:
    METRIC_ENDPOINT[m] = "xpass"

METRIC_LABELS = {
    "goals_for": "Goals Scored",
    "goals_against": "Goals Conceded",
    "goal_difference": "Goal Difference",
    "xgoals_for": "Expected Goals (xG)",
    "xgoals_against": "Expected Goals Against (xGA)",
    "xgoal_difference": "xG Difference",
    "shots_for": "Shots",
    "shots_against": "Shots Against",
    "points": "Points",
    "xpoints": "Expected Points (xPts)",
    "pass_completion_percentage_for": "Pass Completion %",
    "xpass_completion_percentage_for": "Expected Pass Completion %",
    "passes_completed_over_expected_for": "Passes Over Expected",
    "attempted_passes_for": "Attempted Passes",
    "pass_completion_percentage_against": "Opponent Pass Completion %",
}


class ASAAdapter(DataAdapter):
    name = "asa"
    description = "American Soccer Analysis — MLS, NWSL, USL team metrics"

    def form_fields(self) -> list[FormField]:
        return [
            FormField(
                name="league",
                label="League",
                field_type="select",
                options=[
                    FormFieldOption(value="mls", label="MLS"),
                    FormFieldOption(value="nwsl", label="NWSL"),
                    FormFieldOption(value="usl", label="USL"),
                ],
            ),
            FormField(
                name="team",
                label="Team",
                field_type="autocomplete",
                placeholder="Search teams...",
                depends_on="league",
            ),
            FormField(
                name="metric",
                label="Metric",
                field_type="select",
                options=[
                    FormFieldOption(value=m, label=METRIC_LABELS.get(m, m))
                    for m in ALL_METRICS
                ],
            ),
            FormField(
                name="home_away",
                label="Venue",
                field_type="select",
                options=[
                    FormFieldOption(value="all", label="All Games"),
                    FormFieldOption(value="home", label="Home Only"),
                    FormFieldOption(value="away", label="Away Only"),
                ],
            ),
            FormField(
                name="stage",
                label="Stage",
                field_type="select",
                options=[
                    FormFieldOption(value="all", label="All Stages"),
                    FormFieldOption(value="regular", label="Regular Season"),
                    FormFieldOption(value="playoffs", label="Playoffs"),
                ],
            ),
        ]

    def custom_resample_periods(self) -> list[ResamplePeriod]:
        return [
            ResamplePeriod(
                value="mls_season",
                label="MLS Season",
                description="Aggregate by MLS/NWSL/USL season (Feb-Dec)",
            ),
        ]

    def custom_resample(self, series: TimeSeries, period: str) -> TimeSeries:
        """Resample by MLS/NWSL/USL season using actual season_name from API."""
        if period != "mls_season":
            raise NotImplementedError(f"Unknown custom period: {period}")

        if not series.points:
            return TimeSeries(
                source=series.source,
                query=series.query,
                points=[],
                metadata={**series.metadata, "resample": period},
            )

        from collections import defaultdict

        # Get date->season mapping from metadata
        date_to_season = series.metadata.get("date_to_season", {})

        # Group by season
        buckets: dict[str, list[float]] = defaultdict(list)
        for p in series.points:
            # Look up season from metadata, fall back to year if not found
            season = date_to_season.get(p.date.isoformat(), str(p.date.year))
            buckets[season].append(p.value)

        # Determine aggregation method based on metric
        metric = series.metadata.get("metric", "")
        # Sum metrics: goals, points, shots, passes
        sum_metrics = {
            "goals_for", "goals_against", "goal_difference",
            "shots_for", "shots_against", "points",
            "attempted_passes_for", "passes_completed_over_expected_for",
        }
        use_sum = metric in sum_metrics

        agg_fn = sum if use_sum else (lambda vals: sum(vals) / len(vals))

        # Sort seasons and create points
        # Use Feb 1 of season year as representative date (MLS starts ~late Feb)
        points = []
        for season in sorted(buckets.keys()):
            try:
                season_year = int(season)
            except ValueError:
                season_year = 2000  # Fallback for non-numeric seasons
            points.append(
                DataPoint(
                    date=datetime.date(season_year, 2, 1),
                    value=agg_fn(buckets[season]),
                )
            )

        # Remove date_to_season from output metadata (it's large and internal)
        output_meta = {
            k: v for k, v in series.metadata.items() if k != "date_to_season"
        }
        output_meta["resample"] = period

        return TimeSeries(
            source=series.source,
            query=series.query,
            points=points,
            metadata=output_meta,
        )

    async def lookup(self, lookup_type: str, **kwargs: str) -> list[LookupItem]:
        league = kwargs.get("league", "mls")
        if league not in LEAGUES:
            league = "mls"

        if lookup_type in ("teams", "team"):
            return await self._lookup_teams(league)

        return []

    async def _lookup_teams(self, league: str) -> list[LookupItem]:
        url = f"{ASA_API_URL}/{league}/teams"
        async with httpx.AsyncClient() as client:
            response = await _rate_limited_get(client, url, timeout=15.0)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                if response.status_code in (400, 404):
                    raise ValueError(f"League '{league}' not found on ASA") from None
                raise

        teams = response.json()
        return [LookupItem(value=t["team_id"], label=t["team_name"]) for t in teams]

    async def _get_team_name(self, league: str, team_id: str) -> str | None:
        """Look up team name from ID. Returns None if not found."""
        try:
            items = await self._lookup_teams(league)
            for item in items:
                if item.value == team_id:
                    return item.label
        except Exception:
            pass
        return None

    async def fetch(
        self,
        query: str,
        start: datetime.date | None = None,
        end: datetime.date | None = None,
    ) -> TimeSeries:
        parts = query.split(":")
        if len(parts) < 3 or len(parts) > 5:
            raise ValueError(
                f"Invalid query format: '{query}'. "
                "Expected 'league:team_id:metric[:home_away:stage]' "
                "(e.g. 'mls:jYQJ19EqGR:xgoals_for')"
            )

        league, team_id, metric = parts[:3]
        home_away = parts[3] if len(parts) > 3 else "all"
        stage = parts[4] if len(parts) > 4 else "all"

        if metric not in METRIC_ENDPOINT:
            raise ValueError(
                f"Unknown metric: '{metric}'. Available: {', '.join(ALL_METRICS)}"
            )

        endpoint_category = METRIC_ENDPOINT[metric]

        # Fetch games (with season info) and metric data
        game_dates, game_seasons = await self._fetch_game_info(
            league, team_id, home_away=home_away, stage=stage
        )
        metric_data = await self._fetch_metric_data(league, team_id, endpoint_category)

        # Build time series by joining on game_id
        # Also build date->season mapping for custom resample
        points = []
        date_to_season: dict[str, str] = {}
        for row in metric_data:
            game_id = row.get("game_id")
            if game_id not in game_dates:
                continue
            value = row.get(metric)
            if value is None:
                continue
            game_date = game_dates[game_id]
            points.append(DataPoint(date=game_date, value=float(value)))
            date_to_season[game_date.isoformat()] = game_seasons.get(game_id, "")

        points.sort(key=lambda p: p.date)

        if start:
            points = [p for p in points if p.date >= start]
            date_to_season = {
                d: s for d, s in date_to_season.items()
                if datetime.date.fromisoformat(d) >= start
            }
        if end:
            points = [p for p in points if p.date <= end]
            date_to_season = {
                d: s for d, s in date_to_season.items()
                if datetime.date.fromisoformat(d) <= end
            }

        # Look up team name for better display
        team_name = await self._get_team_name(league, team_id)

        # Build metadata
        meta = {
            "league": league,
            "team_id": team_id,
            "metric": metric,
            "metric_label": METRIC_LABELS.get(metric, metric),
            "home_away": home_away,
            "stage": stage,
            "date_to_season": date_to_season,  # For custom resample
        }
        if team_name:
            meta["team"] = team_name

        return TimeSeries(
            source=self.name,
            query=query,
            points=points,
            metadata=meta,
        )

    async def _fetch_game_info(
        self,
        league: str,
        team_id: str,
        *,
        home_away: str = "all",
        stage: str = "all",
    ) -> tuple[dict[str, datetime.date], dict[str, str]]:
        """Fetch games and return mappings of game_id -> date and game_id -> season."""
        url = f"{ASA_API_URL}/{league}/games"
        params = {"team_id": team_id}

        async with httpx.AsyncClient() as client:
            response = await _rate_limited_get(client, url, params=params, timeout=30.0)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                if response.status_code in (400, 404):
                    raise ValueError(
                        f"Games not found for team '{team_id}' in {league}"
                    ) from None
                raise

        games = response.json()
        date_map: dict[str, datetime.date] = {}
        season_map: dict[str, str] = {}
        for game in games:
            game_id = game["game_id"]

            # Filter by home/away venue
            if home_away == "home" and game.get("home_team_id") != team_id:
                continue
            if home_away == "away" and game.get("away_team_id") != team_id:
                continue

            # Filter by stage (knockout_game flag from ASA API)
            if stage == "playoffs" and not game.get("knockout_game", False):
                continue
            if stage == "regular" and game.get("knockout_game", False):
                continue

            dt_str = game["date_time_utc"]
            # Format: "2024-03-01 00:00:00 UTC"
            dt = datetime.datetime.strptime(
                dt_str.replace(" UTC", ""), "%Y-%m-%d %H:%M:%S"
            )
            date_map[game_id] = dt.date()
            season_map[game_id] = game.get("season_name", str(dt.year))

        return date_map, season_map

    async def _fetch_metric_data(
        self,
        league: str,
        team_id: str,
        endpoint_category: str,
    ) -> list[dict]:
        """Fetch metric data with split_by_games=true."""
        url = f"{ASA_API_URL}/{league}/teams/{endpoint_category}"
        params = {
            "team_id": team_id,
            "split_by_games": "true",
        }

        async with httpx.AsyncClient() as client:
            response = await _rate_limited_get(client, url, params=params, timeout=30.0)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                if response.status_code in (400, 404):
                    raise ValueError(
                        f"Metric data not found for team '{team_id}' in {league}"
                    ) from None
                raise

        return response.json()
