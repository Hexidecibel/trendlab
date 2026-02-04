"""Football-Data.org adapter — team goals per match over a season."""

import datetime

import httpx

from app.data.base import DataAdapter
from app.models.schemas import DataPoint, FormField, TimeSeries

FOOTBALL_API_URL = "https://api.football-data.org/v4/competitions/{competition}/matches"


class FootballDataAdapter(DataAdapter):
    name = "football"
    description = "Football match data — goals scored per match (football-data.org)"

    def __init__(self, token: str) -> None:
        self._token = token

    def form_fields(self) -> list[FormField]:
        return [
            FormField(
                name="query",
                label="Competition/Team ID",
                field_type="text",
                placeholder="PL/66",
            )
        ]

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
