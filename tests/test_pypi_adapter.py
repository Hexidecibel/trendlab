import datetime
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from app.data.adapters.pypi import PyPIAdapter

MOCK_PYPI_RESPONSE = {
    "data": [
        {"category": "without_mirrors", "date": "2024-01-01", "downloads": 1000},
        {"category": "with_mirrors", "date": "2024-01-01", "downloads": 200},
        {"category": "without_mirrors", "date": "2024-01-02", "downloads": 1500},
        {"category": "with_mirrors", "date": "2024-01-02", "downloads": 300},
        {"category": "without_mirrors", "date": "2024-01-03", "downloads": 2000},
        {"category": "with_mirrors", "date": "2024-01-03", "downloads": 400},
    ],
    "package": "fastapi",
    "type": "overall_downloads",
}


@pytest.fixture
def adapter():
    return PyPIAdapter()


def _mock_response(status_code=200, json_data=None):
    response = Mock(spec=httpx.Response)
    response.status_code = status_code
    response.json.return_value = json_data
    if status_code >= 400:
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found",
            request=Mock(),
            response=response,
        )
    return response


class TestPyPIAdapter:
    @pytest.mark.asyncio
    async def test_fetch_returns_timeseries(self, adapter):
        mock_resp = _mock_response(json_data=MOCK_PYPI_RESPONSE)
        with patch("app.data.adapters.pypi.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            ts = await adapter.fetch("fastapi")

        assert ts.source == "pypi"
        assert ts.query == "fastapi"
        assert len(ts.points) == 3

    @pytest.mark.asyncio
    async def test_aggregates_categories_per_date(self, adapter):
        mock_resp = _mock_response(json_data=MOCK_PYPI_RESPONSE)
        with patch("app.data.adapters.pypi.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            ts = await adapter.fetch("fastapi")

        assert ts.points[0].value == 1200.0  # 1000 + 200
        assert ts.points[1].value == 1800.0  # 1500 + 300
        assert ts.points[2].value == 2400.0  # 2000 + 400

    @pytest.mark.asyncio
    async def test_sorts_by_date_ascending(self, adapter):
        mock_resp = _mock_response(json_data=MOCK_PYPI_RESPONSE)
        with patch("app.data.adapters.pypi.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            ts = await adapter.fetch("fastapi")

        dates = [p.date for p in ts.points]
        assert dates == sorted(dates)

    @pytest.mark.asyncio
    async def test_date_filtering_start(self, adapter):
        mock_resp = _mock_response(json_data=MOCK_PYPI_RESPONSE)
        with patch("app.data.adapters.pypi.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            ts = await adapter.fetch("fastapi", start=datetime.date(2024, 1, 2))

        assert len(ts.points) == 2
        assert ts.points[0].date == datetime.date(2024, 1, 2)

    @pytest.mark.asyncio
    async def test_date_filtering_end(self, adapter):
        mock_resp = _mock_response(json_data=MOCK_PYPI_RESPONSE)
        with patch("app.data.adapters.pypi.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            ts = await adapter.fetch("fastapi", end=datetime.date(2024, 1, 2))

        assert len(ts.points) == 2
        assert ts.points[-1].date == datetime.date(2024, 1, 2)

    @pytest.mark.asyncio
    async def test_404_raises_value_error(self, adapter):
        mock_resp = _mock_response(status_code=404)
        with patch("app.data.adapters.pypi.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(ValueError, match="not found"):
                await adapter.fetch("nonexistent-package-xyz")

    def test_adapter_metadata(self, adapter):
        assert adapter.name == "pypi"
        assert "PyPI" in adapter.description
