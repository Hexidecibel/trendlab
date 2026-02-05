"""Football-Data.org adapter — team goals per match over a season."""

import datetime

import httpx

from app.data.base import DataAdapter
from app.models.schemas import (
    DataPoint,
    FormField,
    FormFieldOption,
    LookupItem,
    ResamplePeriod,
    TimeSeries,
)

FOOTBALL_API_BASE = "https://api.football-data.org/v4"
FOOTBALL_API_URL = f"{FOOTBALL_API_BASE}/competitions/{{competition}}/matches"

COMPETITIONS = [
    ("PL", "Premier League"),
    ("BL1", "Bundesliga"),
    ("SA", "Serie A"),
    ("PD", "La Liga"),
    ("FL1", "Ligue 1"),
    ("CL", "Champions League"),
    ("ELC", "Championship"),
]


class FootballDataAdapter(DataAdapter):
    name = "football"
    description = "Football match data — goals scored per match (football-data.org)"

    def __init__(self, token: str) -> None:
        self._token = token

    def form_fields(self) -> list[FormField]:
        return [
            FormField(
                name="competition",
                label="Competition",
                field_type="select",
                options=[
                    FormFieldOption(value=code, label=name)
                    for code, name in COMPETITIONS
                ],
            ),
            FormField(
                name="team",
                label="Team",
                field_type="autocomplete",
                placeholder="Search teams...",
                depends_on="competition",
            ),
        ]

    def custom_resample_periods(self) -> list[ResamplePeriod]:
        return [
            ResamplePeriod(
                value="football_season",
                label="Football Season",
                description="European football season (Aug-May, e.g., 2023-24)",
            ),
        ]

    def custom_resample(self, series: TimeSeries, period: str) -> TimeSeries:
        """Resample by European football season (Aug-May)."""
        if period != "football_season":
            raise NotImplementedError(f"Unknown custom period: {period}")

        if not series.points:
            return TimeSeries(
                source=series.source,
                query=series.query,
                points=[],
                metadata={**series.metadata, "resample": period},
            )

        from collections import defaultdict

        def get_season_year(d: datetime.date) -> int:
            """Return season start year. Aug-Dec = that year, Jan-Jul = prior year."""
            if d.month >= 8:  # Aug-Dec
                return d.year
            else:  # Jan-Jul
                return d.year - 1

        # Group by season
        buckets: dict[int, list[float]] = defaultdict(list)
        for p in series.points:
            season_year = get_season_year(p.date)
            buckets[season_year].append(p.value)

        # Sum goals per season
        points = [
            DataPoint(
                date=datetime.date(year, 8, 1),  # Use Aug 1 as season start marker
                value=sum(values),
            )
            for year, values in sorted(buckets.items())
        ]

        return TimeSeries(
            source=series.source,
            query=series.query,
            points=points,
            metadata={**series.metadata, "resample": period},
        )

    async def lookup(self, lookup_type: str, **kwargs: str) -> list[LookupItem]:
        if lookup_type != "teams":
            return []

        competition = kwargs.get("competition", "PL")
        url = f"{FOOTBALL_API_BASE}/competitions/{competition}/teams"
        headers = {"X-Auth-Token": self._token}

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=15.0)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                if response.status_code in (400, 404):
                    raise ValueError(f"Competition '{competition}' not found") from None
                raise

        teams = response.json().get("teams", [])
        return [LookupItem(value=str(t["id"]), label=t["name"]) for t in teams]

    async def fetch(
        self,
        query: str,
        start: datetime.date | None = None,
        end: datetime.date | None = None,
    ) -> TimeSeries:
        # Parse query: "COMPETITION/TEAM_ID" e.g. "PL/66"
        parts = query.split("/")
        if len(parts) != 2:
            raise ValueError(
                f"Invalid query format: '{query}'. "
                "Expected 'COMPETITION/TEAM_ID' (e.g. 'PL/66')"
            )

        competition, team_id_str = parts
        try:
            team_id = int(team_id_str)
        except ValueError:
            raise ValueError(
                f"Invalid team ID: '{team_id_str}'. Must be an integer."
            ) from None

        url = FOOTBALL_API_URL.format(competition=competition)
        headers = {"X-Auth-Token": self._token}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=headers,
                params={"status": "FINISHED"},
            )

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                if response.status_code == 404:
                    raise ValueError(
                        f"Competition or team not found: '{query}'"
                    ) from None
                if response.status_code == 403:
                    raise ValueError(
                        f"Football-Data.org API rate limit exceeded or "
                        f"invalid token for '{query}'."
                    ) from None
                raise

        matches = response.json()["matches"]

        # Filter to matches involving this team and extract goals scored
        points = []
        team_name = None

        for match in matches:
            home_id = match["homeTeam"]["id"]
            away_id = match["awayTeam"]["id"]

            if home_id == team_id:
                goals = match["score"]["fullTime"]["home"]
                if team_name is None:
                    team_name = match["homeTeam"]["name"]
            elif away_id == team_id:
                goals = match["score"]["fullTime"]["away"]
                if team_name is None:
                    team_name = match["awayTeam"]["name"]
            else:
                continue

            match_date = datetime.datetime.fromisoformat(
                match["utcDate"].replace("Z", "+00:00")
            ).date()

            points.append(DataPoint(date=match_date, value=float(goals)))

        # Sort by date
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
                "team": team_name or f"Team {team_id}",
                "competition": competition,
            },
        )
