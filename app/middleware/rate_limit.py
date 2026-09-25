"""Rate limiting middleware for FastAPI."""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    # One page load fans out to ~10 API calls (sources, views, series,
    # analyze, forecast, watchlist, ...), so the burst must cover a few quick
    # reloads; the sustained rate refills 2 tokens a second.
    requests_per_minute: int = 120
    requests_per_hour: int = 3000
    burst_size: int = 40  # Max requests allowed in quick succession
    enabled: bool = True


# AI endpoints call a paid LLM, so they get their own, much tighter bucket on
# top of the general one (the old general limits, which were sized for them).
AI_RATE_LIMIT_DEFAULTS = RateLimitConfig(
    requests_per_minute=20,
    requests_per_hour=200,
    burst_size=10,
)

# Paths (after the /api or /api/v1 prefix) that call the LLM
AI_PATHS = (
    "/insight",
    "/insight-followup",
    "/insights-feed",
    "/natural-query",
    "/compare-insight",
    "/compare-insight-followup",
    "/event-context",
)

# Cheap GET metadata endpoints (DB reads, no upstream fetch or LLM) that are
# never rate limited
EXEMPT_GET_PATHS = (
    "/auth-status",
    "/sources",
    "/views",
    "/uploads",
    "/watchlist",
    "/notifications/config",
    "/notifications/status",
)
EXEMPT_GET_PREFIXES = ("/views/",)


def api_subpath(path: str) -> str | None:
    """``/api/v1/foo`` or ``/api/foo`` -> ``/foo``; None if not an API path."""
    for prefix in ("/api/v1", "/api"):
        if path == prefix:
            return "/"
        if path.startswith(prefix + "/"):
            return path[len(prefix) :]
    return None


@dataclass
class ClientBucket:
    """Token bucket for a single client."""

    tokens: float = 0.0
    last_update: float = field(default_factory=time.time)
    minute_count: int = 0
    minute_window_start: float = field(default_factory=time.time)
    hour_count: int = 0
    hour_window_start: float = field(default_factory=time.time)


class RateLimiter:
    """In-memory rate limiter using token bucket algorithm."""

    def __init__(self, config: RateLimitConfig | None = None):
        self.config = config or RateLimitConfig()
        self.buckets: dict[str, ClientBucket] = {}
        # Refill rate: tokens per second based on per-minute limit
        self.refill_rate = self.config.requests_per_minute / 60.0

    def _get_or_create_bucket(self, client_key: str) -> ClientBucket:
        """Get existing bucket or create a new one with full tokens."""
        if client_key not in self.buckets:
            initial_tokens = float(self.config.burst_size)
            self.buckets[client_key] = ClientBucket(tokens=initial_tokens)
        return self.buckets[client_key]

    def _get_client_key(self, request: Request) -> str:
        """Get a unique key for the client (IP-based for now)."""
        # Use X-Forwarded-For if behind a proxy, otherwise use client IP
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Take the first IP in the chain (original client)
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def check(self, request: Request) -> tuple[bool, dict[str, Any]]:
        """Check if request should be allowed.

        Returns:
            (allowed, info) where info contains rate limit details
        """
        if not self.config.enabled:
            return True, {}

        client_key = self._get_client_key(request)
        bucket = self._get_or_create_bucket(client_key)
        now = time.time()

        # Refill tokens based on time elapsed
        elapsed = now - bucket.last_update
        bucket.tokens = min(
            self.config.burst_size, bucket.tokens + elapsed * self.refill_rate
        )
        bucket.last_update = now

        # Reset minute window if needed
        if now - bucket.minute_window_start >= 60:
            bucket.minute_count = 0
            bucket.minute_window_start = now

        # Reset hour window if needed
        if now - bucket.hour_window_start >= 3600:
            bucket.hour_count = 0
            bucket.hour_window_start = now

        # Check limits
        info = {
            "client": client_key,
            "tokens": round(bucket.tokens, 2),
            "minute_count": bucket.minute_count,
            "hour_count": bucket.hour_count,
            "limit_minute": self.config.requests_per_minute,
            "limit_hour": self.config.requests_per_hour,
        }

        # Token bucket check (for burst protection)
        if bucket.tokens < 1:
            info["reason"] = "burst_limit"
            return False, info

        # Per-minute check
        if bucket.minute_count >= self.config.requests_per_minute:
            info["reason"] = "minute_limit"
            info["retry_after"] = int(60 - (now - bucket.minute_window_start))
            return False, info

        # Per-hour check
        if bucket.hour_count >= self.config.requests_per_hour:
            info["reason"] = "hour_limit"
            info["retry_after"] = int(3600 - (now - bucket.hour_window_start))
            return False, info

        # Request allowed - consume a token and increment counters
        bucket.tokens -= 1
        bucket.minute_count += 1
        bucket.hour_count += 1

        return True, info


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces rate limits on API requests."""

    # Paths to skip rate limiting
    SKIP_PATHS = {"/health", "/", "/docs", "/redoc", "/openapi.json"}
    SKIP_PREFIXES = ("/assets/", "/static/")

    def __init__(
        self,
        app: Any,
        config: RateLimitConfig | None = None,
        ai_config: RateLimitConfig | None = None,
    ):
        super().__init__(app)
        self.limiter = RateLimiter(config)
        ai = ai_config or RateLimitConfig(
            requests_per_minute=AI_RATE_LIMIT_DEFAULTS.requests_per_minute,
            requests_per_hour=AI_RATE_LIMIT_DEFAULTS.requests_per_hour,
            burst_size=AI_RATE_LIMIT_DEFAULTS.burst_size,
            enabled=self.limiter.config.enabled,
        )
        self.ai_limiter = RateLimiter(ai)

    @staticmethod
    def is_exempt(method: str, sub: str) -> bool:
        """Cheap metadata reads that are never limited."""
        if method not in ("GET", "HEAD"):
            return False
        return sub in EXEMPT_GET_PATHS or sub.startswith(EXEMPT_GET_PREFIXES)

    @staticmethod
    def is_ai(sub: str) -> bool:
        return sub in AI_PATHS

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Any]
    ) -> Response:
        path = request.url.path

        # Skip rate limiting for certain paths
        if path in self.SKIP_PATHS or path.startswith(self.SKIP_PREFIXES):
            return await call_next(request)

        # Only rate limit API endpoints
        sub = api_subpath(path)
        if sub is None or self.is_exempt(request.method, sub):
            return await call_next(request)

        allowed, info = True, {}
        if self.is_ai(sub):
            allowed, info = self.ai_limiter.check(request)
            if not allowed:
                info["bucket"] = "ai"
        if allowed:
            allowed, info = self.limiter.check(request)

        if not allowed:
            logger.with_fields(
                client=info.get("client"),
                reason=info.get("reason"),
                bucket=info.get("bucket", "general"),
                path=path,
            ).warning("Rate limit exceeded")

            retry_after = info.get("retry_after", 60)
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded",
                    "retry_after": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        response = await call_next(request)

        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(
            self.limiter.config.requests_per_minute
        )
        minute_limit = self.limiter.config.requests_per_minute
        remaining = max(0, minute_limit - info.get("minute_count", 0))
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response
