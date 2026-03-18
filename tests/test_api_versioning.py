"""Tests for API versioning and deprecation headers."""

import pytest
from httpx import AsyncClient


class TestVersionedRouting:
    """Ensure both versioned and unversioned paths work."""

    @pytest.mark.asyncio
    async def test_versioned_sources(self, client: AsyncClient):
        response = await client.get("/api/v1/sources")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_unversioned_sources(self, client: AsyncClient):
        response = await client.get("/api/sources")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_both_return_same_data(self, client: AsyncClient):
        v1 = await client.get("/api/v1/sources")
        unversioned = await client.get("/api/sources")
        assert v1.json() == unversioned.json()


class TestDeprecationHeaders:
    """Verify deprecation headers on unversioned requests."""

    @pytest.mark.asyncio
    async def test_unversioned_has_deprecation(
        self, client: AsyncClient
    ):
        response = await client.get("/api/sources")
        assert response.headers["Deprecation"] == "true"

    @pytest.mark.asyncio
    async def test_unversioned_has_sunset(
        self, client: AsyncClient
    ):
        response = await client.get("/api/sources")
        assert "Sunset" in response.headers

    @pytest.mark.asyncio
    async def test_unversioned_has_link(
        self, client: AsyncClient
    ):
        response = await client.get("/api/sources")
        assert "successor-version" in response.headers["Link"]

    @pytest.mark.asyncio
    async def test_versioned_no_deprecation(
        self, client: AsyncClient
    ):
        response = await client.get("/api/v1/sources")
        assert "Deprecation" not in response.headers

    @pytest.mark.asyncio
    async def test_versioned_no_sunset(
        self, client: AsyncClient
    ):
        response = await client.get("/api/v1/sources")
        assert "Sunset" not in response.headers


class TestApiVersionHeader:
    """Both versioned and unversioned get X-API-Version."""

    @pytest.mark.asyncio
    async def test_versioned_has_version_header(
        self, client: AsyncClient
    ):
        response = await client.get("/api/v1/sources")
        assert response.headers["X-API-Version"] == "1"

    @pytest.mark.asyncio
    async def test_unversioned_has_version_header(
        self, client: AsyncClient
    ):
        response = await client.get("/api/sources")
        assert response.headers["X-API-Version"] == "1"


class TestOpenAPISchema:
    """Unversioned routes should be excluded from the schema."""

    @pytest.mark.asyncio
    async def test_schema_has_versioned_routes(
        self, client: AsyncClient
    ):
        response = await client.get("/openapi.json")
        paths = response.json()["paths"]
        versioned = [p for p in paths if p.startswith("/api/v1/")]
        assert len(versioned) > 0

    @pytest.mark.asyncio
    async def test_schema_excludes_unversioned(
        self, client: AsyncClient
    ):
        response = await client.get("/openapi.json")
        paths = response.json()["paths"]
        # No paths should start with /api/ without /v1
        unversioned = [
            p
            for p in paths
            if p.startswith("/api/")
            and not p.startswith("/api/v1/")
        ]
        assert unversioned == []
