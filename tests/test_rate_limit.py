"""Tests for rate limiting middleware."""

from unittest.mock import MagicMock

from app.middleware.rate_limit import (
    RateLimitConfig,
    RateLimiter,
    RateLimitMiddleware,
)


class TestRateLimitConfig:
    def test_default_values(self):
        config = RateLimitConfig()
        assert config.requests_per_minute == 60
        assert config.requests_per_hour == 1000
        assert config.burst_size == 10
        assert config.enabled is True

    def test_custom_values(self):
        config = RateLimitConfig(
            requests_per_minute=30,
            requests_per_hour=500,
            burst_size=5,
            enabled=False,
        )
        assert config.requests_per_minute == 30
        assert config.requests_per_hour == 500
        assert config.burst_size == 5
        assert config.enabled is False


class TestRateLimiter:
    def test_allows_requests_under_limit(self):
        config = RateLimitConfig(requests_per_minute=10, burst_size=5)
        limiter = RateLimiter(config)

        request = MagicMock()
        request.headers = {}
        request.client.host = "127.0.0.1"

        # Should allow first few requests
        for _ in range(5):
            allowed, info = limiter.check(request)
            assert allowed is True

    def test_blocks_after_burst_exceeded(self):
        config = RateLimitConfig(requests_per_minute=60, burst_size=3)
        limiter = RateLimiter(config)

        request = MagicMock()
        request.headers = {}
        request.client.host = "127.0.0.1"

        # Exhaust burst tokens
        for _ in range(3):
            allowed, _ = limiter.check(request)
            assert allowed is True

        # Next request should be blocked (no tokens left)
        allowed, info = limiter.check(request)
        assert allowed is False
        assert info["reason"] == "burst_limit"

    def test_disabled_allows_all(self):
        config = RateLimitConfig(enabled=False)
        limiter = RateLimiter(config)

        request = MagicMock()
        request.headers = {}
        request.client.host = "127.0.0.1"

        # Should always allow when disabled
        for _ in range(100):
            allowed, _ = limiter.check(request)
            assert allowed is True

    def test_uses_forwarded_for_header(self):
        config = RateLimitConfig()
        limiter = RateLimiter(config)

        request = MagicMock()
        request.headers = {"X-Forwarded-For": "1.2.3.4, 5.6.7.8"}
        request.client.host = "127.0.0.1"

        limiter.check(request)

        # Should use the first IP from X-Forwarded-For
        assert "1.2.3.4" in limiter.buckets

    def test_different_clients_have_separate_limits(self):
        config = RateLimitConfig(requests_per_minute=60, burst_size=2)
        limiter = RateLimiter(config)

        request1 = MagicMock()
        request1.headers = {}
        request1.client.host = "1.1.1.1"

        request2 = MagicMock()
        request2.headers = {}
        request2.client.host = "2.2.2.2"

        # Client 1 uses up burst
        for _ in range(2):
            allowed, _ = limiter.check(request1)
            assert allowed is True

        # Client 1 is now blocked
        allowed, _ = limiter.check(request1)
        assert allowed is False

        # Client 2 should still be allowed
        allowed, _ = limiter.check(request2)
        assert allowed is True


class TestRateLimitMiddleware:
    def test_skips_health_endpoint(self):
        """Health endpoint should not be rate limited."""
        middleware = RateLimitMiddleware(app=MagicMock())

        # Verify health is in skip paths
        assert "/health" in middleware.SKIP_PATHS

    def test_skips_static_files(self):
        """Static files should not be rate limited."""
        middleware = RateLimitMiddleware(app=MagicMock())

        # Verify static prefixes are skipped
        assert any(
            prefix.startswith("/assets") or prefix.startswith("/static")
            for prefix in middleware.SKIP_PREFIXES
        )
