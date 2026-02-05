import datetime
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from app.data.adapters.github import GitHubStarsAdapter

MOCK_PAGE_1 = [
    {"starred_at": "2024-01-01T10:00:00Z", "user": {"login": "u1"}},
    {"starred_at": "2024-01-01T18:00:00Z", "user": {"login": "u2"}},
    {"starred_at": "2024-01-02T12:00:00Z", "user": {"login": "u3"}},
]

MOCK_PAGE_2 = [
    {"starred_at": "2024-01-03T09:00:00Z", "user": {"login": "u4"}},
]


@pytest.fixture
def adapter():
    return GitHubStarsAdapter(token="ghp_faketoken123")


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


class TestGitHubStarsAdapter:
    @pytest.mark.asyncio
    async def test_fetch_returns_timeseries(self, adapter):
        """Test basic fetch with a single page of results."""
        resp_page1 = _mock_response(json_data=MOCK_PAGE_1)
        resp_empty = _mock_response(json_data=[])

        with patch("app.data.adapters.github.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = [resp_page1, resp_empty]
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            ts = await adapter.fetch("owner/repo")

        assert ts.source == "github_stars"
        assert ts.query == "owner/repo"
        assert len(ts.points) == 2  # 2 unique dates

    @pytest.mark.asyncio
    async def test_pagination(self, adapter):
        """Test that pagination fetches multiple pages."""
        resp_page1 = _mock_response(json_data=MOCK_PAGE_1)
        resp_page2 = _mock_response(json_data=MOCK_PAGE_2)
        resp_empty = _mock_response(json_data=[])

        with patch("app.data.adapters.github.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = [resp_page1, resp_page2, resp_empty]
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            ts = await adapter.fetch("owner/repo")

        assert len(ts.points) == 3  # Jan 1, Jan 2, Jan 3
        assert ts.metadata["total_stars"] == 4

    @pytest.mark.asyncio
    async def test_daily_bucketing(self, adapter):
        """Test that multiple stars on the same day are summed."""
        resp_page1 = _mock_response(json_data=MOCK_PAGE_1)
        resp_empty = _mock_response(json_data=[])

        with patch("app.data.adapters.github.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = [resp_page1, resp_empty]
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            ts = await adapter.fetch("owner/repo")

        # Jan 1 had 2 stars, Jan 2 had 1 star
        jan1 = [p for p in ts.points if p.date == datetime.date(2024, 1, 1)]
        assert len(jan1) == 1
        assert jan1[0].value == 2.0

        jan2 = [p for p in ts.points if p.date == datetime.date(2024, 1, 2)]
        assert len(jan2) == 1
        assert jan2[0].value == 1.0

    @pytest.mark.asyncio
    async def test_date_filtering(self, adapter):
        resp_page1 = _mock_response(json_data=MOCK_PAGE_1)
        resp_page2 = _mock_response(json_data=MOCK_PAGE_2)
        resp_empty = _mock_response(json_data=[])

        with patch("app.data.adapters.github.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = [resp_page1, resp_page2, resp_empty]
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            ts = await adapter.fetch(
                "owner/repo",
                start=datetime.date(2024, 1, 2),
                end=datetime.date(2024, 1, 2),
            )

        assert len(ts.points) == 1
        assert ts.points[0].date == datetime.date(2024, 1, 2)

    @pytest.mark.asyncio
    async def test_404_raises_value_error(self, adapter):
        mock_resp = _mock_response(status_code=404)

        with patch("app.data.adapters.github.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(ValueError, match="not found"):
                await adapter.fetch("owner/nonexistent")

    @pytest.mark.asyncio
    async def test_403_raises_descriptive_error(self, adapter):
        mock_resp = _mock_response(status_code=403)

        with patch("app.data.adapters.github.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(ValueError, match="rate limit"):
                await adapter.fetch("owner/repo")

    @pytest.mark.asyncio
    async def test_total_stars_in_metadata(self, adapter):
        resp_page1 = _mock_response(json_data=MOCK_PAGE_1)
        resp_empty = _mock_response(json_data=[])

        with patch("app.data.adapters.github.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = [resp_page1, resp_empty]
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            ts = await adapter.fetch("owner/repo")

        assert ts.metadata["total_stars"] == 3

    def test_adapter_metadata(self, adapter):
        assert adapter.name == "github_stars"
        assert "GitHub" in adapter.description

    def test_form_fields_has_placeholder(self, adapter):
        """Form fields should have a descriptive placeholder."""
        fields = adapter.form_fields()
        assert len(fields) == 1
        assert fields[0].name == "query"
        assert "owner/repo" in fields[0].placeholder.lower()
