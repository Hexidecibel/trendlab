"""API deprecation middleware.

Adds deprecation headers to unversioned ``/api/`` requests and an
``X-API-Version`` header to every API response.
"""

from datetime import datetime, timedelta, timezone

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


def _sunset_date() -> str:
    """Return an HTTP-date six months from now (RFC 7231)."""
    dt = datetime.now(timezone.utc) + timedelta(days=180)
    return dt.strftime("%a, %d %b %Y %H:%M:%S GMT")


class DeprecationMiddleware(BaseHTTPMiddleware):
    """Adds version / deprecation headers to ``/api`` responses.

    * Every ``/api/...`` response gets ``X-API-Version: 1``.
    * Unversioned ``/api/...`` (not ``/api/v1/...``) responses also
      get ``Deprecation``, ``Sunset``, and ``Link`` headers.
    """

    async def dispatch(
        self, request: Request, call_next
    ) -> Response:
        response = await call_next(request)
        path = request.url.path

        if not path.startswith("/api"):
            return response

        response.headers["X-API-Version"] = "1"

        # Only add deprecation headers for unversioned paths
        if not path.startswith("/api/v1"):
            response.headers["Deprecation"] = "true"
            response.headers["Sunset"] = _sunset_date()
            response.headers["Link"] = (
                "</api/v1/>; rel=\"successor-version\""
            )

        return response
