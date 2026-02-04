import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_root(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    # Returns SPA HTML if frontend is built, JSON otherwise
    if response.headers.get("content-type", "").startswith("text/html"):
        assert "<!doctype html>" in response.text.lower()
    else:
        assert "message" in response.json()
