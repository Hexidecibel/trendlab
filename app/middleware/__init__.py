"""Middleware components for TrendLab."""

from app.middleware.auth import (
    SecretPhraseMiddleware,
    generate_session_token,
    verify_token,
)
from app.middleware.deprecation import DeprecationMiddleware
from app.middleware.logging import RequestLoggingMiddleware
from app.middleware.rate_limit import RateLimitConfig, RateLimitMiddleware

__all__ = [
    "DeprecationMiddleware",
    "RequestLoggingMiddleware",
    "RateLimitConfig",
    "RateLimitMiddleware",
    "SecretPhraseMiddleware",
    "generate_session_token",
    "verify_token",
]
