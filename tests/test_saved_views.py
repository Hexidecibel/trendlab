"""Tests for saved views / shareable URLs feature."""

import datetime

import pytest

import app.db.engine as db_engine
from app.db.repository import (
    delete_view,
    get_view_by_hash,
    list_views,
    save_view,
)


@pytest.fixture
async def db():
    """Initialize a fresh in-memory database for each test."""
    await db_engine.init_db("sqlite+aiosqlite://")
    yield


class TestSavedViewsRepository:
    """Test the repository layer directly."""

    @pytest.mark.asyncio
    async def test_save_view_returns_hash(self, db):
        view = await save_view(
            name="My View",
            source="pypi",
            query="fastapi",
        )
        assert view.hash_id
        assert len(view.hash_id) == 8
        assert view.name == "My View"
        assert view.source == "pypi"
        assert view.query == "fastapi"

    @pytest.mark.asyncio
    async def test_get_view_by_hash(self, db):
        view = await save_view(name="Test", source="pypi", query="fastapi")
        fetched = await get_view_by_hash(view.hash_id)
        assert fetched is not None
        assert fetched.hash_id == view.hash_id
        assert fetched.name == "Test"

    @pytest.mark.asyncio
    async def test_get_view_unknown_hash(self, db):
        result = await get_view_by_hash("nonexist")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_views(self, db):
        await save_view(name="View 1", source="pypi", query="fastapi")
        await save_view(name="View 2", source="crypto", query="bitcoin")
        views = await list_views()
        assert len(views) == 2
        # Newest first
        assert views[0].name == "View 2"

    @pytest.mark.asyncio
    async def test_delete_view(self, db):
        view = await save_view(name="Delete Me", source="pypi", query="fastapi")
        assert await delete_view(view.hash_id) is True
        assert await get_view_by_hash(view.hash_id) is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_view(self, db):
        assert await delete_view("nope") is False

    @pytest.mark.asyncio
    async def test_save_view_with_all_fields(self, db):
        view = await save_view(
            name="Full View",
            source="asa",
            query="mls:teams:abc:xgoals_for",
            horizon=30,
            start_date=datetime.date(2024, 1, 1),
            end_date=datetime.date(2024, 12, 31),
            resample="week",
            apply="normalize|rolling_avg_7d",
            anomaly_method="iqr",
        )
        assert view.horizon == 30
        assert view.start == datetime.date(2024, 1, 1)
        assert view.end == datetime.date(2024, 12, 31)
        assert view.resample == "week"
        assert view.apply == "normalize|rolling_avg_7d"
        assert view.anomaly_method == "iqr"

    @pytest.mark.asyncio
    async def test_duplicate_saves_get_different_hashes(self, db):
        v1 = await save_view(name="A", source="pypi", query="fastapi")
        v2 = await save_view(name="B", source="pypi", query="fastapi")
        assert v1.hash_id != v2.hash_id


class TestSavedViewsAPI:
    """Test the API endpoints."""

    @pytest.fixture
    async def client(self):
        await db_engine.init_db("sqlite+aiosqlite://")
        from httpx import ASGITransport, AsyncClient

        from app.main import app

        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    @pytest.mark.asyncio
    async def test_create_view(self, client):
        response = await client.post(
            "/api/views",
            json={
                "name": "My View",
                "source": "pypi",
                "query": "fastapi",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "hash_id" in data
        assert data["name"] == "My View"

    @pytest.mark.asyncio
    async def test_get_view_by_hash(self, client):
        create = await client.post(
            "/api/views",
            json={"name": "V", "source": "pypi", "query": "fastapi"},
        )
        hash_id = create.json()["hash_id"]

        response = await client.get(f"/api/views/{hash_id}")
        assert response.status_code == 200
        assert response.json()["hash_id"] == hash_id

    @pytest.mark.asyncio
    async def test_get_view_not_found(self, client):
        response = await client.get("/api/views/nonexist")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_views(self, client):
        await client.post(
            "/api/views",
            json={"name": "A", "source": "pypi", "query": "fastapi"},
        )
        await client.post(
            "/api/views",
            json={"name": "B", "source": "crypto", "query": "bitcoin"},
        )
        response = await client.get("/api/views")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_delete_view(self, client):
        create = await client.post(
            "/api/views",
            json={"name": "D", "source": "pypi", "query": "fastapi"},
        )
        hash_id = create.json()["hash_id"]

        response = await client.delete(f"/api/views/{hash_id}")
        assert response.status_code == 204

        # Verify deleted
        response = await client.get(f"/api/views/{hash_id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent_view(self, client):
        response = await client.delete("/api/views/nope")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_view_validation(self, client):
        """Name is required and must not be empty."""
        response = await client.post(
            "/api/views",
            json={"name": "", "source": "pypi", "query": "fastapi"},
        )
        assert response.status_code == 422
