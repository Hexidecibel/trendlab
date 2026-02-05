import datetime
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from app.data.adapters.weather import WeatherAdapter

MOCK_WEATHER_RESPONSE = {
    "latitude": 40.7128,
    "longitude": -74.006,
    "timezone": "America/New_York",
    "elevation": 10.0,
    "daily": {
        "time": ["2024-01-01", "2024-01-02", "2024-01-03"],
        "temperature_2m_max": [5.2, 7.8, 3.1],
    },
}

MOCK_GEOCODING_RESPONSE = {
    "results": [
        {
            "name": "New York",
            "latitude": 40.7128,
            "longitude": -74.006,
            "admin1": "New York",
            "country": "United States",
        },
        {
            "name": "New York Mills",
            "latitude": 43.1056,
            "longitude": -75.2912,
            "admin1": "New York",
            "country": "United States",
        },
    ]
}


@pytest.fixture
def adapter():
    return WeatherAdapter()


def _mock_response(status_code=200, json_data=None):
    response = Mock(spec=httpx.Response)
    response.status_code = status_code
    response.json.return_value = json_data
    if status_code >= 400:
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Error", request=Mock(), response=response
        )
    return response


class TestWeatherAdapter:
    @pytest.mark.asyncio
    async def test_fetch_returns_timeseries(self, adapter):
        mock_resp = _mock_response(json_data=MOCK_WEATHER_RESPONSE)
        with patch("app.data.adapters.weather.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            ts = await adapter.fetch(
                "40.7128,-74.006:temperature_2m_max:celsius:kmh:mm",
                start=datetime.date(2024, 1, 1),
                end=datetime.date(2024, 1, 3),
            )

        assert ts.source == "weather"
        assert len(ts.points) == 3
        assert ts.points[0].value == 5.2
        assert ts.points[1].value == 7.8

    @pytest.mark.asyncio
    async def test_fetch_with_metadata(self, adapter):
        mock_resp = _mock_response(json_data=MOCK_WEATHER_RESPONSE)
        with patch("app.data.adapters.weather.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            ts = await adapter.fetch(
                "40.7128,-74.006:temperature_2m_max:celsius:kmh:mm"
            )

        assert ts.metadata["latitude"] == 40.7128
        assert ts.metadata["longitude"] == -74.006
        assert ts.metadata["metric"] == "temperature_2m_max"
        assert ts.metadata["timezone"] == "America/New_York"

    @pytest.mark.asyncio
    async def test_invalid_query_format_raises(self, adapter):
        with pytest.raises(ValueError, match="Invalid query format"):
            await adapter.fetch("invalid")

    @pytest.mark.asyncio
    async def test_invalid_coordinates_raises(self, adapter):
        with pytest.raises(ValueError, match="Invalid coordinates"):
            await adapter.fetch("notacoord:temperature_2m_max:celsius:kmh:mm")

    @pytest.mark.asyncio
    async def test_invalid_metric_raises(self, adapter):
        with pytest.raises(ValueError, match="Invalid metric"):
            await adapter.fetch("40.7128,-74.006:bad_metric:celsius:kmh:mm")

    @pytest.mark.asyncio
    async def test_invalid_temp_unit_raises(self, adapter):
        with pytest.raises(ValueError, match="Invalid temp unit"):
            await adapter.fetch("40.7128,-74.006:temperature_2m_max:kelvin:kmh:mm")

    @pytest.mark.asyncio
    async def test_invalid_wind_unit_raises(self, adapter):
        with pytest.raises(ValueError, match="Invalid wind unit"):
            await adapter.fetch("40.7128,-74.006:temperature_2m_max:celsius:bad:mm")

    @pytest.mark.asyncio
    async def test_invalid_precip_unit_raises(self, adapter):
        with pytest.raises(ValueError, match="Invalid precip unit"):
            await adapter.fetch("40.7128,-74.006:temperature_2m_max:celsius:kmh:bad")

    @pytest.mark.asyncio
    async def test_lookup_returns_items(self, adapter):
        mock_resp = _mock_response(json_data=MOCK_GEOCODING_RESPONSE)
        with patch("app.data.adapters.weather.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            items = await adapter.lookup("location", search="New York")

        assert len(items) == 2
        assert "New York" in items[0].label
        assert "40.7128,-74.006" == items[0].value

    @pytest.mark.asyncio
    async def test_lookup_empty_returns_empty(self, adapter):
        items = await adapter.lookup("location", search="")
        assert items == []

    @pytest.mark.asyncio
    async def test_lookup_short_query_returns_empty(self, adapter):
        items = await adapter.lookup("location", search="a")
        assert items == []

    def test_adapter_metadata(self, adapter):
        assert adapter.name == "weather"
        assert "weather" in adapter.description.lower()

    def test_form_fields(self, adapter):
        fields = adapter.form_fields()
        field_names = [f.name for f in fields]
        assert "location" in field_names
        assert "metric" in field_names
        assert "temp_unit" in field_names
        assert "wind_unit" in field_names
        assert "precip_unit" in field_names
