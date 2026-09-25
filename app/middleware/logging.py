"""Request/response logging middleware for FastAPI."""

import re
import time
from collections.abc import Callable
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.logging_config import (
    generate_request_id,
    get_logger,
    request_context,
)

logger = get_logger(__name__)

# A client may supply its own request ID (the frontend does, so it can
# subscribe to WebSocket progress for the request before it completes).
# Anything that isn't a short, header/log-safe token is ignored.
_CLIENT_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9-]{1,64}$")


def resolve_request_id(header_value: str | None) -> str:
    """Use a sane client-supplied ``X-Request-ID``, else generate one."""
    if header_value and _CLIENT_REQUEST_ID_RE.fullmatch(header_value):
        return header_value
    return generate_request_id()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that logs requests and responses with timing."""

    # Paths to skip logging (health checks, static files)
    SKIP_PATHS = {"/health", "/favicon.ico"}
    SKIP_PREFIXES = ("/assets/", "/static/")

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Any]
    ) -> Response:
        # Skip logging for certain paths
        path = request.url.path
        if path in self.SKIP_PATHS or path.startswith(self.SKIP_PREFIXES):
            return await call_next(request)

        # Accept the client's request ID (if sane) or generate one
        request_id = resolve_request_id(request.headers.get("x-request-id"))
        ctx = {
            "request_id": request_id,
            "path": path,
            "method": request.method,
        }
        token = request_context.set(ctx)

        # Store request_id in request state for access in route handlers
        request.state.request_id = request_id

        # Log request start
        req_logger = logger.with_fields(
            request_id=request_id,
            method=request.method,
            path=path,
            query=str(request.query_params) if request.query_params else None,
            client_ip=request.client.host if request.client else None,
        )
        req_logger.info("Request started")

        # Process request and time it
        start_time = time.perf_counter()
        try:
            response = await call_next(request)
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            # Log response
            resp_logger = logger.with_fields(
                request_id=request_id,
                method=request.method,
                path=path,
                status_code=response.status_code,
                elapsed_ms=round(elapsed_ms, 2),
            )

            if response.status_code >= 500:
                resp_logger.error("Request failed")
            elif response.status_code >= 400:
                resp_logger.warning("Request error")
            else:
                resp_logger.info("Request completed")

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            err_logger = logger.with_fields(
                request_id=request_id,
                method=request.method,
                path=path,
                elapsed_ms=round(elapsed_ms, 2),
                error_type=type(e).__name__,
            )
            err_logger.exception("Request exception")
            raise

        finally:
            request_context.reset(token)
