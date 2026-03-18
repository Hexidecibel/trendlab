"""Secret phrase authentication middleware."""

import hashlib
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import settings


def generate_session_token(phrase: str) -> str:
    """Generate a session token from the secret phrase."""
    # Use a hash so the actual phrase isn't stored in cookies
    return hashlib.sha256(f"trendlab:{phrase}".encode()).hexdigest()[:32]


def verify_token(token: str) -> bool:
    """Verify a session token against the configured secret phrase."""
    if not settings.secret_phrase:
        return True  # No auth configured
    expected = generate_session_token(settings.secret_phrase)
    return secrets.compare_digest(token, expected)


class SecretPhraseMiddleware(BaseHTTPMiddleware):
    """
    Middleware that requires a valid session token for API access.

    The token is obtained by POSTing the correct phrase to /api/unlock.
    Static files and the unlock endpoint are always accessible.
    """

    # Paths that don't require authentication
    OPEN_PATHS = {
        "/api/unlock",
        "/api/auth-status",
        "/health",
    }

    async def dispatch(self, request: Request, call_next):
        # Skip auth if not configured
        if not settings.secret_phrase:
            return await call_next(request)

        path = request.url.path

        # Allow static files and open paths
        if not path.startswith("/api") or path in self.OPEN_PATHS:
            return await call_next(request)

        # Check for session token in cookie or header
        token = request.cookies.get("trendlab_session")
        if not token:
            token = request.headers.get("X-TrendLab-Token")

        if not token or not verify_token(token):
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized"},
            )

        return await call_next(request)
