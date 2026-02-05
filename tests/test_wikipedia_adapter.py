import datetime
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from app.data.adapters.wikipedia import WikipediaAdapter

MOCK_PAGEVIEWS_RESPONSE = {
    "items": [
        {
            "project": "en.wikipedia",
            "article": "Python_(programming_language)",
            "granularity": "daily",
            "timestamp": "2024010100",
            "access": "all-access",
            "agent": "user",
            "views": 50000,
        },
        {
            "project": "en.wikipedia",
            "article": "Python_(programming_language)",
            "granularity": "daily",
            "timestamp": "2024010200",
            "access": "all-access",
            "agent": "user",
            "views": 52000,
        },
        {
            "project": "en.wikipedia",
            "article": "Python_(programming_language)",
            "granularity": "daily",
            "timestamp": "2024010300",
            "access": "all-access",
            "agent": "user",
            "views": 48000,
        },
    ]
}

MOCK_SEARCH_RESPONSE = [
    "Python",
    ["Python (programming language)", "Python (genus)", "Pythonidae"],
    ["A programming language", "A genus of snakes", "Family of snakes"],
    ["https://en.wikipedia.org/wiki/Python_(programming_language)"],
]


@pytest.fixture
def adapter():
    return WikipediaAdapter()


def _mock_response(status_code=200, json_data=None):
    response = Mock(spec=httpx.Response)
    response.status_code = status_code
    response.json.return_value = json_data
    if status_code >= 400:
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Error", request=Mock(), response=response
        )
    return response


class TestWikipediaAdapter:
    @pytest.mark.asyncio
    async def test_fetch_returns_timeseries(self, adapter):
        mock_resp = _mock_response(json_data=MOCK_PAGEVIEWS_RESPONSE)
        with patch("app.data.adapters.wikipedia.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            ts = await adapter.fetch(
                "en.wikipedia:Python_(programming_language):all-access:user:daily",
                start=datetime.date(2024, 1, 1),
                end=datetime.date(2024, 1, 3),
            )

        assert ts.source == "wikipedia"
        assert len(ts.points) == 3
        assert ts.points[0].value == 50000.0
        assert ts.points[1].value == 52000.0

    @pytest.mark.asyncio
    async def test_fetch_with_metadata(self, adapter):
        mock_resp = _mock_response(json_data=MOCK_PAGEVIEWS_RESPONSE)
        with patch("app.data.adapters.wikipedia.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            ts = await adapter.fetch(
                "en.wikipedia:Python_(programming_language):all-access:user:daily"
            )

        assert ts.metadata["project"] == "en.wikipedia"
        assert ts.metadata["article"] == "Python (programming language)"
        assert ts.metadata["access"] == "all-access"
        assert ts.metadata["agent"] == "user"

    @pytest.mark.asyncio
    async def test_invalid_query_format_raises(self, adapter):
        with pytest.raises(ValueError, match="Invalid query format"):
            await adapter.fetch("invalid-query")

    @pytest.mark.asyncio
    async def test_invalid_project_raises(self, adapter):
        with pytest.raises(ValueError, match="Invalid project"):
            await adapter.fetch("fake.wikipedia:Article:all-access:user:daily")

    @pytest.mark.asyncio
    async def test_invalid_access_raises(self, adapter):
        with pytest.raises(ValueError, match="Invalid access type"):
            await adapter.fetch("en.wikipedia:Article:bad-access:user:daily")

    @pytest.mark.asyncio
    async def test_invalid_agent_raises(self, adapter):
        with pytest.raises(ValueError, match="Invalid agent type"):
            await adapter.fetch("en.wikipedia:Article:all-access:bad-agent:daily")

    @pytest.mark.asyncio
    async def test_invalid_granularity_raises(self, adapter):
        with pytest.raises(ValueError, match="Invalid granularity"):
            await adapter.fetch("en.wikipedia:Article:all-access:user:hourly")

    @pytest.mark.asyncio
    async def test_404_raises_value_error(self, adapter):
        mock_resp = _mock_response(status_code=404)
        with patch("app.data.adapters.wikipedia.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(ValueError, match="not found"):
                await adapter.fetch(
                    "en.wikipedia:Nonexistent_Article_XYZ:all-access:user:daily"
                )

    @pytest.mark.asyncio
    async def test_lookup_returns_items(self, adapter):
        mock_resp = _mock_response(json_data=MOCK_SEARCH_RESPONSE)
        with patch("app.data.adapters.wikipedia.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            items = await adapter.lookup("article", search="Python")

        assert len(items) == 3
        assert items[0].label == "Python (programming language)"
        assert items[0].value == "Python_(programming_language)"

    @pytest.mark.asyncio
    async def test_lookup_empty_search_returns_empty(self, adapter):
        items = await adapter.lookup("article", search="")
        assert items == []

    def test_adapter_metadata(self, adapter):
        assert adapter.name == "wikipedia"
        assert "Wikipedia" in adapter.description

    def test_form_fields(self, adapter):
        fields = adapter.form_fields()
        field_names = [f.name for f in fields]
        assert "project" in field_names
        assert "article" in field_names
        assert "access" in field_names
        assert "agent" in field_names
        assert "granularity" in field_names
