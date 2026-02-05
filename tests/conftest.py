import os

# Disable rate limiting and auth for tests - must be set before importing app
# Set explicitly to empty string to override .env file
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["TRENDLAB_SECRET_PHRASE"] = ""  # Empty = no auth required

import pytest
from httpx import ASGITransport, AsyncClient

# Import and patch settings before app imports it
from app import config  # noqa: E402
config.settings.secret_phrase = None  # Explicitly disable auth

from app.main import app  # noqa: E402


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
