"""Tests for the American Soccer Analysis adapter."""

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.data.adapters.asa import ASAAdapter

MOCK_TEAMS = [
    {
        "team_id": "jYQJ19EqGR",
        "team_name": "Seattle Sounders FC",
        "team_short_name": "Seattle",
        "team_abbreviation": "SEA",
    },
    {
        "team_id": "kaDQ0wRqEv",
        "team_name": "LA Galaxy",
        "team_short_name": "LA Galaxy",
        "team_abbreviation": "LAG",
    },
]

MOCK_GAMES = [
    {
        "game_id": "game1",
        "date_time_utc": "2024-03-01 00:00:00 UTC",
        "home_team_id": "jYQJ19EqGR",
        "away_team_id": "kaDQ0wRqEv",
        "home_score": 2,
        "away_score": 1,
        "season_name": "2024",
        "status": "FullTime",
        "knockout_game": False,
    },
    {
        "game_id": "game2",
        "date_time_utc": "2024-03-15 00:00:00 UTC",
        "home_team_id": "kaDQ0wRqEv",
        "away_team_id": "jYQJ19EqGR",
        "home_score": 0,
        "away_score": 3,
        "season_name": "2024",
        "status": "FullTime",
        "knockout_game": False,
    },
    {
        "game_id": "game3",
        "date_time_utc": "2024-04-01 00:00:00 UTC",
        "home_team_id": "jYQJ19EqGR",
        "away_team_id": "other",
        "home_score": 1,
        "away_score": 1,
        "season_name": "2024",
        "status": "FullTime",
        "knockout_game": True,
    },
]

MOCK_XGOALS = [
    {
        "team_id": "jYQJ19EqGR",
        "game_id": "game1",
        "goals_for": 2,
        "goals_against": 1,
        "xgoals_for": 1.5,
        "xgoals_against": 0.8,
        "xgoal_difference": 0.7,
        "shots_for": 12,
        "shots_against": 8,
        "points": 3,
        "xpoints": 2.1,
    },
    {
        "team_id": "jYQJ19EqGR",
        "game_id": "game2",
        "goals_for": 3,
        "goals_against": 0,
        "xgoals_for": 2.2,
        "xgoals_against": 0.5,
        "xgoal_difference": 1.7,
        "shots_for": 15,
        "shots_against": 5,
        "points": 3,
        "xpoints": 2.5,
    },
    {
        "team_id": "jYQJ19EqGR",
        "game_id": "game3",
        "goals_for": 1,
        "goals_against": 1,
        "xgoals_for": 1.1,
        "xgoals_against": 1.0,
        "xgoal_difference": 0.1,
        "shots_for": 10,
        "shots_against": 10,
        "points": 1,
        "xpoints": 1.5,
    },
]

MOCK_XPASS = [
    {
        "team_id": "jYQJ19EqGR",
        "game_id": "game1",
        "attempted_passes_for": 500,
        "pass_completion_percentage_for": 0.85,
        "xpass_completion_percentage_for": 0.83,
        "passes_completed_over_expected_for": 10.0,
        "passes_completed_over_expected_p100_for": 2.0,
    },
]

# --- Player-level mock data ---

MOCK_PLAYERS = [
    {"player_id": "p1abc", "player_name": "Jordan Morris"},
    {"player_id": "p2def", "player_name": "Raul Ruidiaz"},
]

MOCK_PLAYER_XGOALS = [
    {
        "player_id": "p1abc",
        "game_id": "game1",
        "team_id": "jYQJ19EqGR",
        "minutes_played": 90,
        "shots": 3,
        "shots_on_target": 2,
        "goals": 1,
        "xgoals": 0.8,
        "goals_minus_xgoals": 0.2,
        "key_passes": 2,
        "primary_assists": 0,
        "xassists": 0.3,
        "xgoals_plus_xassists": 1.1,
    },
    {
        "player_id": "p1abc",
        "game_id": "game2",
        "team_id": "jYQJ19EqGR",
        "minutes_played": 75,
        "shots": 1,
        "shots_on_target": 0,
        "goals": 0,
        "xgoals": 0.3,
        "goals_minus_xgoals": -0.3,
        "key_passes": 1,
        "primary_assists": 1,
        "xassists": 0.5,
        "xgoals_plus_xassists": 0.8,
    },
]

MOCK_PLAYER_XPASS = [
    {
        "player_id": "p1abc",
        "game_id": "game1",
        "team_id": "jYQJ19EqGR",
        "attempted_passes": 45,
        "pass_completion_percentage": 0.82,
        "xpass_completion_percentage": 0.80,
        "passes_completed_over_expected": 1.0,
    },
]


def _mock_response(json_data, status_code=200):
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data
    mock.raise_for_status = MagicMock()
    if status_code >= 400:
        import httpx

        mock.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=mock
        )
    return mock


@pytest.fixture
def adapter():
    return ASAAdapter()


class TestASAAdapter:
    def test_adapter_metadata(self, adapter):
        assert adapter.name == "asa"
        assert "soccer" in adapter.description.lower() or "MLS" in adapter.description

    def test_form_fields(self, adapter):
        fields = adapter.form_fields()
        names = [f.name for f in fields]
        assert "league" in names
        assert "entity_type" in names
        assert "metric" in names
        assert "entity" in names

    @pytest.mark.asyncio
    async def test_lookup_teams(self, adapter):
        with patch("app.data.adapters.asa.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _mock_response(MOCK_TEAMS)

            items = await adapter.lookup("teams", league="mls")
            assert len(items) == 2
            assert items[0].label == "Seattle Sounders FC"
            assert items[0].value == "jYQJ19EqGR"

    @pytest.mark.asyncio
    async def test_fetch_xgoals_for(self, adapter):
        with patch("app.data.adapters.asa.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            # First call: games, second call: xgoals
            mock_client.get.side_effect = [
                _mock_response(MOCK_GAMES),
                _mock_response(MOCK_XGOALS),
            ]

            ts = await adapter.fetch("mls:teams:jYQJ19EqGR:xgoals_for")
            assert ts.source == "asa"
            assert len(ts.points) == 3
            assert ts.points[0].date == datetime.date(2024, 3, 1)
            assert ts.points[0].value == 1.5  # xgoals_for from game1

    @pytest.mark.asyncio
    async def test_fetch_goals_for(self, adapter):
        with patch("app.data.adapters.asa.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_client.get.side_effect = [
                _mock_response(MOCK_GAMES),
                _mock_response(MOCK_XGOALS),
            ]

            ts = await adapter.fetch("mls:teams:jYQJ19EqGR:goals_for")
            assert len(ts.points) == 3
            assert ts.points[0].value == 2  # goals_for from game1

    @pytest.mark.asyncio
    async def test_fetch_xpass(self, adapter):
        with patch("app.data.adapters.asa.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_client.get.side_effect = [
                _mock_response(MOCK_GAMES),
                _mock_response(MOCK_XPASS),
            ]

            ts = await adapter.fetch(
                "mls:teams:jYQJ19EqGR:pass_completion_percentage_for"
            )
            assert len(ts.points) == 1
            assert ts.points[0].value == 0.85

    @pytest.mark.asyncio
    async def test_fetch_date_filtering(self, adapter):
        with patch("app.data.adapters.asa.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_client.get.side_effect = [
                _mock_response(MOCK_GAMES),
                _mock_response(MOCK_XGOALS),
            ]

            ts = await adapter.fetch(
                "mls:teams:jYQJ19EqGR:xgoals_for",
                start=datetime.date(2024, 3, 10),
            )
            assert len(ts.points) == 2  # game2 and game3

    @pytest.mark.asyncio
    async def test_fetch_invalid_query_format(self, adapter):
        with pytest.raises(ValueError, match="Invalid query format"):
            await adapter.fetch("bad_query")

    @pytest.mark.asyncio
    async def test_fetch_invalid_metric(self, adapter):
        with patch("app.data.adapters.asa.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_client.get.side_effect = [
                _mock_response(MOCK_GAMES),
                _mock_response(MOCK_XGOALS),
            ]

            with pytest.raises(ValueError, match="Unknown metric"):
                await adapter.fetch("mls:teams:jYQJ19EqGR:nonexistent_metric")

    @pytest.mark.asyncio
    async def test_metadata_includes_team_and_metric(self, adapter):
        with patch("app.data.adapters.asa.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_client.get.side_effect = [
                _mock_response(MOCK_GAMES),
                _mock_response(MOCK_XGOALS),
            ]

            ts = await adapter.fetch("mls:teams:jYQJ19EqGR:xgoals_for")
            assert ts.metadata["metric"] == "xgoals_for"
            assert ts.metadata["league"] == "mls"
            assert ts.metadata["entity_type"] == "teams"

    @pytest.mark.asyncio
    async def test_points_sorted_by_date(self, adapter):
        with patch("app.data.adapters.asa.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_client.get.side_effect = [
                _mock_response(MOCK_GAMES),
                _mock_response(MOCK_XGOALS),
            ]

            ts = await adapter.fetch("mls:teams:jYQJ19EqGR:goals_for")
            dates = [p.date for p in ts.points]
            assert dates == sorted(dates)

    @pytest.mark.asyncio
    async def test_fetch_home_only(self, adapter):
        """Home filter should only include games where the team is home."""
        with patch("app.data.adapters.asa.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_client.get.side_effect = [
                _mock_response(MOCK_GAMES),
                _mock_response(MOCK_XGOALS),
            ]

            # game1 and game3 are home for jYQJ19EqGR, game2 is away
            ts = await adapter.fetch("mls:teams:jYQJ19EqGR:goals_for:home:all")
            assert len(ts.points) == 2
            assert ts.points[0].value == 2  # game1
            assert ts.points[1].value == 1  # game3

    @pytest.mark.asyncio
    async def test_fetch_away_only(self, adapter):
        """Away filter should only include games where the team is away."""
        with patch("app.data.adapters.asa.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_client.get.side_effect = [
                _mock_response(MOCK_GAMES),
                _mock_response(MOCK_XGOALS),
            ]

            # game2 is away for jYQJ19EqGR
            ts = await adapter.fetch("mls:teams:jYQJ19EqGR:goals_for:away:all")
            assert len(ts.points) == 1
            assert ts.points[0].value == 3  # game2

    @pytest.mark.asyncio
    async def test_fetch_playoffs_only(self, adapter):
        """Playoffs filter should only include knockout games."""
        with patch("app.data.adapters.asa.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_client.get.side_effect = [
                _mock_response(MOCK_GAMES),
                _mock_response(MOCK_XGOALS),
            ]

            # Only game3 has knockout_game=True
            ts = await adapter.fetch("mls:teams:jYQJ19EqGR:goals_for:all:playoffs")
            assert len(ts.points) == 1
            assert ts.points[0].date == datetime.date(2024, 4, 1)

    @pytest.mark.asyncio
    async def test_fetch_regular_season_only(self, adapter):
        """Regular season filter should exclude knockout games."""
        with patch("app.data.adapters.asa.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_client.get.side_effect = [
                _mock_response(MOCK_GAMES),
                _mock_response(MOCK_XGOALS),
            ]

            # game1 and game2 have knockout_game=False
            ts = await adapter.fetch("mls:teams:jYQJ19EqGR:goals_for:all:regular")
            assert len(ts.points) == 2

    @pytest.mark.asyncio
    async def test_fetch_home_playoffs_combined(self, adapter):
        """Combined venue + stage filter."""
        with patch("app.data.adapters.asa.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_client.get.side_effect = [
                _mock_response(MOCK_GAMES),
                _mock_response(MOCK_XGOALS),
            ]

            # Only game3: home + knockout
            ts = await adapter.fetch("mls:teams:jYQJ19EqGR:goals_for:home:playoffs")
            assert len(ts.points) == 1
            assert ts.points[0].value == 1  # game3

    @pytest.mark.asyncio
    async def test_metadata_includes_filters(self, adapter):
        """Metadata should include home_away and stage filters."""
        with patch("app.data.adapters.asa.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_client.get.side_effect = [
                _mock_response(MOCK_GAMES),
                _mock_response(MOCK_XGOALS),
            ]

            ts = await adapter.fetch("mls:teams:jYQJ19EqGR:goals_for:home:regular")
            assert ts.metadata["home_away"] == "home"
            assert ts.metadata["stage"] == "regular"

    @pytest.mark.asyncio
    async def test_fetch_defaults_filters_when_omitted(self, adapter):
        """4-part query should default home_away=all and stage=all."""
        with patch("app.data.adapters.asa.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_client.get.side_effect = [
                _mock_response(MOCK_GAMES),
                _mock_response(MOCK_XGOALS),
            ]

            ts = await adapter.fetch("mls:teams:jYQJ19EqGR:goals_for")
            assert ts.metadata["home_away"] == "all"
            assert ts.metadata["stage"] == "all"
            assert len(ts.points) == 3  # all games included

    def test_form_fields_include_filters(self, adapter):
        """Form fields should include home_away and stage selectors."""
        fields = adapter.form_fields()
        names = [f.name for f in fields]
        assert "home_away" in names
        assert "stage" in names
        home_away = next(f for f in fields if f.name == "home_away")
        assert len(home_away.options) == 3
        stage = next(f for f in fields if f.name == "stage")
        assert len(stage.options) == 3


class TestASAPlayerQueries:
    """Tests for player-level ASA queries."""

    def test_entity_type_includes_players(self, adapter):
        """entity_type form field should include 'players' option."""
        fields = adapter.form_fields()
        entity_type = next(f for f in fields if f.name == "entity_type")
        values = [o.value for o in entity_type.options]
        assert "players" in values

    @pytest.mark.asyncio
    async def test_lookup_players(self, adapter):
        """lookup('players') should return player list."""
        with patch("app.data.adapters.asa.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _mock_response(MOCK_PLAYERS)

            items = await adapter.lookup("players", league="mls")
            assert len(items) == 2
            assert items[0].label == "Jordan Morris"
            assert items[0].value == "p1abc"

    @pytest.mark.asyncio
    async def test_lookup_unknown_type(self, adapter):
        """Unknown lookup type should return empty list."""
        items = await adapter.lookup("coaches", league="mls")
        assert items == []

    @pytest.mark.asyncio
    async def test_fetch_player_xgoals(self, adapter):
        """Player xgoals query should return TimeSeries."""
        with patch("app.data.adapters.asa.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            # For players: metric data first, then games
            mock_client.get.side_effect = [
                _mock_response(MOCK_PLAYER_XGOALS),
                _mock_response(MOCK_GAMES),
            ]

            ts = await adapter.fetch("mls:players:p1abc:goals")
            assert ts.source == "asa"
            assert len(ts.points) == 2
            assert ts.points[0].date == datetime.date(2024, 3, 1)
            assert ts.points[0].value == 1  # goals from game1
            assert ts.points[1].value == 0  # goals from game2

    @pytest.mark.asyncio
    async def test_fetch_player_xpass(self, adapter):
        """Player xpass query should return TimeSeries."""
        with patch("app.data.adapters.asa.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_client.get.side_effect = [
                _mock_response(MOCK_PLAYER_XPASS),
                _mock_response(MOCK_GAMES),
            ]

            ts = await adapter.fetch(
                "mls:players:p1abc:pass_completion_percentage"
            )
            assert len(ts.points) == 1
            assert ts.points[0].value == 0.82

    @pytest.mark.asyncio
    async def test_player_metadata(self, adapter):
        """Player query metadata should have entity_type=players."""
        with patch("app.data.adapters.asa.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_client.get.side_effect = [
                _mock_response(MOCK_PLAYER_XGOALS),
                _mock_response(MOCK_GAMES),
            ]

            ts = await adapter.fetch("mls:players:p1abc:goals")
            assert ts.metadata["entity_type"] == "players"
            assert ts.metadata["entity_id"] == "p1abc"
            assert ts.metadata["metric"] == "goals"

    @pytest.mark.asyncio
    async def test_player_home_filter(self, adapter):
        """Venue filter should work for player queries using team_id."""
        with patch("app.data.adapters.asa.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_client.get.side_effect = [
                _mock_response(MOCK_PLAYER_XGOALS),
                _mock_response(MOCK_GAMES),
            ]

            # game1 is home for jYQJ19EqGR, game2 is away
            ts = await adapter.fetch("mls:players:p1abc:goals:home:all")
            assert len(ts.points) == 1
            assert ts.points[0].value == 1  # game1 only

    @pytest.mark.asyncio
    async def test_player_empty_metric_data(self, adapter):
        """Empty metric data should return empty TimeSeries."""
        with patch("app.data.adapters.asa.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_client.get.return_value = _mock_response([])

            ts = await adapter.fetch("mls:players:p1abc:goals")
            assert len(ts.points) == 0
