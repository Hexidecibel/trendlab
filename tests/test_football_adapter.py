import datetime
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from app.data.adapters.football import FootballDataAdapter

MOCK_MATCHES_RESPONSE = {
    "resultSet": {"count": 3},
    "matches": [
        {
            "utcDate": "2024-08-17T15:00:00Z",
            "status": "FINISHED",
            "matchday": 1,
            "homeTeam": {"id": 66, "name": "Manchester United"},
            "awayTeam": {"id": 57, "name": "Arsenal"},
            "score": {
                "fullTime": {"home": 2, "away": 1},
            },
        },
        {
            "utcDate": "2024-08-24T15:00:00Z",
            "status": "FINISHED",
            "matchday": 2,
            "homeTeam": {"id": 61, "name": "Chelsea"},
            "awayTeam": {"id": 66, "name": "Manchester United"},
            "score": {
                "fullTime": {"home": 0, "away": 3},
            },
        },
        {
            "utcDate": "2024-08-31T15:00:00Z",
            "status": "FINISHED",
            "matchday": 3,
            "homeTeam": {"id": 66, "name": "Manchester United"},
            "awayTeam": {"id": 65, "name": "Man City"},
            "score": {
                "fullTime": {"home": 1, "away": 1},
            },
        },
    ],
}


@pytest.fixture
def adapter():
    return FootballDataAdapter(token="fake-token-123")


def _mock_response(status_code=200, json_data=None):
    response = Mock(spec=httpx.Response)
    response.status_code = status_code
    response.json.return_value = json_data
    if status_code >= 400:
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Error",
            request=Mock(),
            response=response,
        )
    return response


class TestFootballDataAdapter:
    @pytest.mark.asyncio
    async def test_fetch_returns_timeseries(self, adapter):
        mock_resp = _mock_response(json_data=MOCK_MATCHES_RESPONSE)
        with patch("app.data.adapters.football.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            ts = await adapter.fetch("PL/66")

        assert ts.source == "football"
        assert ts.query == "PL/66"
        assert len(ts.points) == 3

    @pytest.mark.asyncio
    async def test_extracts_goals_for_team(self, adapter):
        """Team 66 scored: 2 (home), 3 (away), 1 (home)."""
        mock_resp = _mock_response(json_data=MOCK_MATCHES_RESPONSE)
        with patch("app.data.adapters.football.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            ts = await adapter.fetch("PL/66")

        assert ts.points[0].value == 2.0  # matchday 1: home, scored 2
        assert ts.points[1].value == 3.0  # matchday 2: away, scored 3
        assert ts.points[2].value == 1.0  # matchday 3: home, scored 1

    @pytest.mark.asyncio
    async def test_dates_from_matches(self, adapter):
        mock_resp = _mock_response(json_data=MOCK_MATCHES_RESPONSE)
        with patch("app.data.adapters.football.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            ts = await adapter.fetch("PL/66")

        assert ts.points[0].date == datetime.date(2024, 8, 17)
        assert ts.points[1].date == datetime.date(2024, 8, 24)
        assert ts.points[2].date == datetime.date(2024, 8, 31)

    @pytest.mark.asyncio
    async def test_metadata_includes_team_name(self, adapter):
        mock_resp = _mock_response(json_data=MOCK_MATCHES_RESPONSE)
        with patch("app.data.adapters.football.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            ts = await adapter.fetch("PL/66")

        assert ts.metadata["team"] == "Manchester United"
        assert ts.metadata["competition"] == "PL"

    @pytest.mark.asyncio
    async def test_date_filtering(self, adapter):
        mock_resp = _mock_response(json_data=MOCK_MATCHES_RESPONSE)
        with patch("app.data.adapters.football.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            ts = await adapter.fetch(
                "PL/66",
                start=datetime.date(2024, 8, 20),
                end=datetime.date(2024, 8, 30),
            )

        assert len(ts.points) == 1
        assert ts.points[0].date == datetime.date(2024, 8, 24)

    @pytest.mark.asyncio
    async def test_404_raises_value_error(self, adapter):
        mock_resp = _mock_response(status_code=404)
        with patch("app.data.adapters.football.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(ValueError, match="not found"):
                await adapter.fetch("XX/9999")

    @pytest.mark.asyncio
    async def test_403_raises_auth_error(self, adapter):
        mock_resp = _mock_response(status_code=403)
        with patch("app.data.adapters.football.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(ValueError, match="rate limit"):
                await adapter.fetch("PL/66")

    @pytest.mark.asyncio
    async def test_invalid_query_format_raises(self, adapter):
        with pytest.raises(ValueError, match="format"):
            await adapter.fetch("invalid-query")

    def test_adapter_metadata(self, adapter):
        assert adapter.name == "football"
        assert "football" in adapter.description.lower()
