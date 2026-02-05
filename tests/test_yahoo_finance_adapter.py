from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from app.data.adapters.yahoo_finance import YahooFinanceAdapter

MOCK_CHART_RESPONSE = {
    "chart": {
        "result": [
            {
                "meta": {
                    "currency": "USD",
                    "symbol": "AAPL",
                    "shortName": "Apple Inc.",
                },
                "timestamp": [1704067200, 1704153600, 1704240000],  # 2024-01-01, 02, 03
                "indicators": {
                    "quote": [
                        {
                            "open": [185.0, 186.0, 184.0],
                            "high": [186.5, 187.0, 185.5],
                            "low": [184.0, 185.0, 183.0],
                            "close": [185.5, 186.5, 184.5],
                            "volume": [50000000, 55000000, 48000000],
                        }
                    ],
                    "adjclose": [
                        {
                            "adjclose": [185.5, 186.5, 184.5],
                        }
                    ],
                },
            }
        ],
        "error": None,
    }
}

MOCK_SEARCH_RESPONSE = {
    "quotes": [
        {
            "symbol": "AAPL",
            "shortname": "Apple Inc.",
            "exchange": "NASDAQ",
            "quoteType": "EQUITY",
        },
        {
            "symbol": "AAPL.MX",
            "shortname": "Apple Inc.",
            "exchange": "MEX",
            "quoteType": "EQUITY",
        },
    ],
    "news": [],
}


@pytest.fixture
def adapter():
    return YahooFinanceAdapter()


def _mock_response(status_code=200, json_data=None):
    response = Mock(spec=httpx.Response)
    response.status_code = status_code
    response.json.return_value = json_data
    if status_code >= 400:
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Error", request=Mock(), response=response
        )
    return response


class TestYahooFinanceAdapter:
    @pytest.mark.asyncio
    async def test_fetch_returns_timeseries(self, adapter):
        mock_resp = _mock_response(json_data=MOCK_CHART_RESPONSE)
        with patch("app.data.adapters.yahoo_finance.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            ts = await adapter.fetch("AAPL:close:1d:1y")

        assert ts.source == "stocks"
        assert len(ts.points) == 3
        assert ts.points[0].value == 185.5
        assert ts.points[1].value == 186.5

    @pytest.mark.asyncio
    async def test_fetch_different_metrics(self, adapter):
        mock_resp = _mock_response(json_data=MOCK_CHART_RESPONSE)
        with patch("app.data.adapters.yahoo_finance.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            ts = await adapter.fetch("AAPL:volume:1d:1y")

        assert ts.points[0].value == 50000000.0

    @pytest.mark.asyncio
    async def test_fetch_with_metadata(self, adapter):
        mock_resp = _mock_response(json_data=MOCK_CHART_RESPONSE)
        with patch("app.data.adapters.yahoo_finance.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            ts = await adapter.fetch("AAPL:close:1d:1y")

        assert ts.metadata["symbol"] == "AAPL"
        assert ts.metadata["name"] == "Apple Inc."
        assert ts.metadata["currency"] == "USD"
        assert ts.metadata["metric"] == "close"

    @pytest.mark.asyncio
    async def test_invalid_query_format_raises(self, adapter):
        with pytest.raises(ValueError, match="Invalid query format"):
            await adapter.fetch("AAPL")

    @pytest.mark.asyncio
    async def test_invalid_metric_raises(self, adapter):
        with pytest.raises(ValueError, match="Invalid metric"):
            await adapter.fetch("AAPL:badmetric:1d:1y")

    @pytest.mark.asyncio
    async def test_invalid_interval_raises(self, adapter):
        with pytest.raises(ValueError, match="Invalid interval"):
            await adapter.fetch("AAPL:close:1h:1y")

    @pytest.mark.asyncio
    async def test_invalid_range_raises(self, adapter):
        with pytest.raises(ValueError, match="Invalid range"):
            await adapter.fetch("AAPL:close:1d:10y")

    @pytest.mark.asyncio
    async def test_404_raises_value_error(self, adapter):
        mock_resp = _mock_response(status_code=404)
        with patch("app.data.adapters.yahoo_finance.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            with pytest.raises(ValueError, match="not found"):
                await adapter.fetch("FAKESYMBOL123:close:1d:1y")

    @pytest.mark.asyncio
    async def test_lookup_returns_items(self, adapter):
        mock_resp = _mock_response(json_data=MOCK_SEARCH_RESPONSE)
        with patch("app.data.adapters.yahoo_finance.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            items = await adapter.lookup("symbol", search="AAPL")

        assert len(items) == 2
        assert items[0].value == "AAPL"
        assert "Apple" in items[0].label

    @pytest.mark.asyncio
    async def test_lookup_empty_returns_empty(self, adapter):
        items = await adapter.lookup("symbol", search="")
        assert items == []

    def test_adapter_metadata(self, adapter):
        assert adapter.name == "stocks"
        assert "Yahoo Finance" in adapter.description

    def test_form_fields(self, adapter):
        fields = adapter.form_fields()
        field_names = [f.name for f in fields]
        assert "symbol" in field_names
        assert "metric" in field_names
        assert "interval" in field_names
        assert "range" in field_names
