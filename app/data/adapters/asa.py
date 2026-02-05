"""American Soccer Analysis adapter — configurable soccer metrics."""

import datetime
import logging

import httpx

from app.data.base import DataAdapter
from app.models.schemas import (
    DataPoint,
    FormField,
    FormFieldOption,
    LookupItem,
    TimeSeries,
)

logger = logging.getLogger(__name__)

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
    description = "American Soccer Analysis — MLS, NWSL, USL metrics"

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
                name="entity_type",
                label="Type",
                field_type="select",
                options=[
                    FormFieldOption(value="teams", label="Teams"),
                ],
            ),
            FormField(
                name="entity",
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

    async def lookup(self, lookup_type: str, **kwargs: str) -> list[LookupItem]:
        league = kwargs.get("league", "mls")
        if league not in LEAGUES:
            league = "mls"

        if lookup_type == "teams":
            return await self._lookup_teams(league)

        return []

    async def _lookup_teams(self, league: str) -> list[LookupItem]:
        url = f"{ASA_API_URL}/{league}/teams"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=15.0)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                if response.status_code in (400, 404):
                    raise ValueError(f"League '{league}' not found on ASA") from None
                raise

        teams = response.json()
        return [LookupItem(value=t["team_id"], label=t["team_name"]) for t in teams]

    async def fetch(
        self,
        query: str,
        start: datetime.date | None = None,
        end: datetime.date | None = None,
    ) -> TimeSeries:
        parts = query.split(":")
        if len(parts) < 4 or len(parts) > 6:
            raise ValueError(
                f"Invalid query format: '{query}'. "
                "Expected 'league:entity_type:entity_id:metric[:home_away:stage]' "
                "(e.g. 'mls:teams:jYQJ19EqGR:xgoals_for')"
            )

        league, entity_type, entity_id, metric = parts[:4]
        home_away = parts[4] if len(parts) > 4 else "all"
        stage = parts[5] if len(parts) > 5 else "all"

        if metric not in METRIC_ENDPOINT:
            raise ValueError(
                f"Unknown metric: '{metric}'. Available: {', '.join(ALL_METRICS)}"
            )

        endpoint_category = METRIC_ENDPOINT[metric]

        # Fetch games to get date mapping (with venue/stage filtering)
        game_dates = await self._fetch_game_dates(
            league, entity_type, entity_id, home_away=home_away, stage=stage
        )

        # Fetch metric data
        metric_data = await self._fetch_metric_data(
            league, entity_type, entity_id, endpoint_category
        )

        # Build time series by joining on game_id
        points = []
        for row in metric_data:
            game_id = row.get("game_id")
            if game_id not in game_dates:
                continue
            value = row.get(metric)
            if value is None:
                continue
            points.append(DataPoint(date=game_dates[game_id], value=float(value)))

        points.sort(key=lambda p: p.date)

        if start:
            points = [p for p in points if p.date >= start]
        if end:
            points = [p for p in points if p.date <= end]

        return TimeSeries(
            source=self.name,
            query=query,
            points=points,
            metadata={
                "league": league,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "metric": metric,
                "metric_label": METRIC_LABELS.get(metric, metric),
                "home_away": home_away,
                "stage": stage,
            },
        )

    async def _fetch_game_dates(
        self,
        league: str,
        entity_type: str,
        entity_id: str,
        *,
        home_away: str = "all",
        stage: str = "all",
    ) -> dict[str, datetime.date]:
        """Fetch games and return a mapping of game_id -> date.

        Filters games by venue (home/away) and stage (regular/playoffs).
        """
        url = f"{ASA_API_URL}/{league}/games"
        params: dict[str, str] = {}
        if entity_type == "teams":
            params["team_id"] = entity_id

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=30.0)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                if response.status_code in (400, 404):
                    raise ValueError(
                        f"Games not found for '{entity_id}' in {league}"
                    ) from None
                raise

        games = response.json()
        date_map: dict[str, datetime.date] = {}
        for game in games:
            game_id = game["game_id"]

            # Filter by home/away venue
            if home_away == "home" and game.get("home_team_id") != entity_id:
                continue
            if home_away == "away" and game.get("away_team_id") != entity_id:
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

        return date_map

    async def _fetch_metric_data(
        self,
        league: str,
        entity_type: str,
        entity_id: str,
        endpoint_category: str,
    ) -> list[dict]:
        """Fetch metric data with split_by_games=true."""
        url = f"{ASA_API_URL}/{league}/{entity_type}/{endpoint_category}"
        id_param = "team_id" if entity_type == "teams" else "player_id"
        params = {
            id_param: entity_id,
            "split_by_games": "true",
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=30.0)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                if response.status_code in (400, 404):
                    raise ValueError(
                        f"Metric data not found for '{entity_id}' in {league}"
                    ) from None
                raise

        return response.json()
