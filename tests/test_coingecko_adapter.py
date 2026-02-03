import datetime
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from app.data.adapters.coingecko import CoinGeckoAdapter

# Timestamps in milliseconds for known dates
JAN_1_MS = 1704067200000  # 2024-01-01 00:00:00 UTC
JAN_2_MS = 1704153600000  # 2024-01-02 00:00:00 UTC
JAN_3_MS = 1704240000000  # 2024-01-03 00:00:00 UTC

MOCK_COINGECKO_RESPONSE = {
    "prices": [
        [JAN_1_MS, 42000.50],
        [JAN_2_MS, 43100.75],
        [JAN_3_MS, 41500.25],
    ],
    "market_caps": [],
    "total_volumes": [],
}


@pytest.fixture
def adapter():
    return CoinGeckoAdapter()


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


class TestCoinGeckoAdapter:
    @pytest.mark.asyncio
    async def test_fetch_returns_timeseries(self, adapter):
        mock_resp = _mock_response(json_data=MOCK_COINGECKO_RESPONSE)
        with patch("app.data.adapters.coingecko.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            ts = await adapter.fetch("bitcoin")

        assert ts.source == "crypto"
        assert ts.query == "bitcoin"
        assert len(ts.points) == 3

    @pytest.mark.asyncio
    async def test_correct_date_conversion(self, adapter):
        mock_resp = _mock_response(json_data=MOCK_COINGECKO_RESPONSE)
        with patch("app.data.adapters.coingecko.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            ts = await adapter.fetch("bitcoin")

        assert ts.points[0].date == datetime.date(2024, 1, 1)
        assert ts.points[0].value == 42000.50
        assert ts.points[1].date == datetime.date(2024, 1, 2)
        assert ts.points[2].date == datetime.date(2024, 1, 3)

    @pytest.mark.asyncio
    async def test_deduplicates_dates(self, adapter):
        duped = {
            "prices": [
                [JAN_1_MS, 42000.0],
                [JAN_1_MS + 3600000, 42500.0],  # Same day, 1hr later
                [JAN_2_MS, 43000.0],
            ],
            "market_caps": [],
            "total_volumes": [],
        }
        mock_resp = _mock_response(json_data=duped)
        with patch("app.data.adapters.coingecko.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            ts = await adapter.fetch("bitcoin")

        assert len(ts.points) == 2
        # Last value for the duplicated date wins
        assert ts.points[0].value == 42500.0

    @pytest.mark.asyncio
    async def test_date_filtering(self, adapter):
        mock_resp = _mock_response(json_data=MOCK_COINGECKO_RESPONSE)
        with patch("app.data.adapters.coingecko.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            ts = await adapter.fetch(
                "bitcoin",
                start=datetime.date(2024, 1, 2),
                end=datetime.date(2024, 1, 2),
            )

        assert len(ts.points) == 1
        assert ts.points[0].date == datetime.date(2024, 1, 2)

    @pytest.mark.asyncio
    async def test_error_handling(self, adapter):
        mock_resp = _mock_response(status_code=404)
        with patch("app.data.adapters.coingecko.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(ValueError, match="not found"):
                await adapter.fetch("fakecoin999")

    def test_adapter_metadata(self, adapter):
        assert adapter.name == "crypto"
        assert "Cryptocurrency" in adapter.description
