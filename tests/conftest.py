import os

import pytest
from httpx import ASGITransport, AsyncClient

# Disable rate limiting for tests
os.environ["RATE_LIMIT_ENABLED"] = "false"

from app.main import app  # noqa: E402


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
