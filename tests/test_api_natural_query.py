"""Tests for the POST /api/natural-query endpoint."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.schemas import (
    NaturalCompareItem,
    NaturalCompareResponse,
    NaturalQueryError,
    NaturalQueryResponse,
)


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


class TestNaturalQueryEndpoint:
    @pytest.mark.asyncio
    async def test_missing_api_key_returns_503(self, client):
        with patch("app.routers.api.settings") as mock_settings:
            mock_settings.anthropic_api_key = None
            response = await client.post(
                "/api/natural-query",
                json={"text": "show me fastapi downloads"},
            )
        assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_successful_parse_returns_200(self, client):
        mock_result = NaturalQueryResponse(
            source="pypi",
            query="fastapi",
            horizon=14,
            start=None,
            end=None,
            interpretation="PyPI downloads for fastapi",
        )

        with (
            patch("app.routers.api.settings") as mock_settings,
            patch(
                "app.routers.api.parse_and_resolve", new_callable=AsyncMock
            ) as mock_parse,
        ):
            mock_settings.anthropic_api_key = "test-key"
            mock_parse.return_value = mock_result

            response = await client.post(
                "/api/natural-query",
                json={"text": "show me fastapi downloads"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "pypi"
        assert data["query"] == "fastapi"
        assert data["interpretation"] == "PyPI downloads for fastapi"

    @pytest.mark.asyncio
    async def test_unparseable_query_returns_422(self, client):
        mock_result = NaturalQueryError(
            error="Cannot parse this",
            suggestions=["Try something else"],
        )

        with (
            patch("app.routers.api.settings") as mock_settings,
            patch(
                "app.routers.api.parse_and_resolve", new_callable=AsyncMock
            ) as mock_parse,
        ):
            mock_settings.anthropic_api_key = "test-key"
            mock_parse.return_value = mock_result

            response = await client.post(
                "/api/natural-query",
                json={"text": "gibberish input"},
            )

        assert response.status_code == 422
        data = response.json()
        assert "Cannot parse" in json.dumps(data)

    @pytest.mark.asyncio
    async def test_empty_text_returns_422(self, client):
        response = await client.post(
            "/api/natural-query",
            json={"text": "ab"},  # min_length=3
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_response_shape(self, client):
        mock_result = NaturalQueryResponse(
            source="crypto",
            query="bitcoin",
            horizon=30,
            start=None,
            end=None,
            interpretation="Bitcoin price trend",
        )

        with (
            patch("app.routers.api.settings") as mock_settings,
            patch(
                "app.routers.api.parse_and_resolve", new_callable=AsyncMock
            ) as mock_parse,
        ):
            mock_settings.anthropic_api_key = "test-key"
            mock_parse.return_value = mock_result

            response = await client.post(
                "/api/natural-query",
                json={"text": "bitcoin price forecast next month"},
            )

        data = response.json()
        assert "source" in data
        assert "query" in data
        assert "horizon" in data
        assert "interpretation" in data
        assert "start" in data
        assert "end" in data

    @pytest.mark.asyncio
    async def test_compare_query_returns_items(self, client):
        mock_result = NaturalCompareResponse(
            items=[
                NaturalCompareItem(source="pypi", query="fastapi"),
                NaturalCompareItem(source="pypi", query="django"),
            ],
            resample=None,
            interpretation="Comparing fastapi vs django",
        )

        with (
            patch("app.routers.api.settings") as mock_settings,
            patch(
                "app.routers.api.parse_and_resolve", new_callable=AsyncMock
            ) as mock_parse,
        ):
            mock_settings.anthropic_api_key = "test-key"
            mock_parse.return_value = mock_result

            response = await client.post(
                "/api/natural-query",
                json={"text": "compare fastapi and django"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) == 2
        assert data["items"][0]["source"] == "pypi"
        assert data["items"][0]["query"] == "fastapi"
        assert data["interpretation"] == "Comparing fastapi vs django"
