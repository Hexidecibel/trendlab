import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.data.adapters.asa import ASAAdapter
from app.data.adapters.coingecko import CoinGeckoAdapter
from app.data.adapters.csv_upload import CSVUploadAdapter
from app.data.adapters.npm import NpmAdapter
from app.data.adapters.pypi import PyPIAdapter
from app.data.adapters.reddit import RedditAdapter
from app.data.adapters.weather import WeatherAdapter
from app.data.adapters.wikipedia import WikipediaAdapter
from app.data.adapters.yahoo_finance import YahooFinanceAdapter
from app.data.registry import registry
from app.db.engine import init_db
from app.logging_config import get_logger, setup_logging
from app.middleware import (
    RateLimitConfig,
    RateLimitMiddleware,
    RequestLoggingMiddleware,
    SecretPhraseMiddleware,
)
from app.plugins import load_plugins
from app.routers import api

# Initialize logging before anything else
setup_logging(
    level=os.getenv("LOG_LEVEL", "INFO"),
    json_output=os.getenv("LOG_FORMAT", "json").lower() == "json",
)

logger = get_logger(__name__)

registry.register(PyPIAdapter())
registry.register(NpmAdapter())
registry.register(CSVUploadAdapter())
registry.register(RedditAdapter())
registry.register(CoinGeckoAdapter())
registry.register(ASAAdapter())
registry.register(WikipediaAdapter())
registry.register(YahooFinanceAdapter())
registry.register(WeatherAdapter())

if settings.github_token:
    from app.data.adapters.github import GitHubStarsAdapter

    registry.register(GitHubStarsAdapter(token=settings.github_token))
else:
    logger.warning("GITHUB_TOKEN not set — github_stars adapter will not be available")

if settings.football_data_token:
    from app.data.adapters.football import FootballDataAdapter

    registry.register(FootballDataAdapter(token=settings.football_data_token))
else:
    logger.warning(
        "FOOTBALL_DATA_TOKEN not set — football adapter will not be available"
    )

# Load community plugins from plugins/ directory
plugin_count = load_plugins()
if plugin_count:
    logger.info("Loaded %d community plugin(s)", plugin_count)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="TrendLab",
    description="""
**AI-powered trend analysis platform** for time-series data
visualization and forecasting.

## Features

- **Multi-source data adapters**: PyPI, crypto, GitHub, soccer stats
- **Trend analysis**: Momentum, seasonality, anomalies, structural breaks
- **Forecasting**: Compare ARIMA, ETS, Prophet with evaluation metrics
- **Natural language queries**: Describe what you want in plain English
- **Series comparison**: Overlay series with normalization and transforms
- **Correlation analysis**: Pearson/Spearman with lag analysis
- **AI insights**: LLM-generated commentary via streaming SSE

## Data Sources

| Source | Description |
|--------|-------------|
| `pypi` | Python package downloads |
| `coingecko` | Cryptocurrency prices |
| `github_stars` | GitHub repository stars (requires token) |
| `asa` | American Soccer Analysis team/player stats |
| `football` | European football match data (requires token) |
""",
    version="1.0.0",
    openapi_tags=[
        {
            "name": "Data",
            "description": "Fetch and transform time-series data from various sources",
        },
        {
            "name": "Analysis",
            "description": "Trend analysis, anomaly detection, and forecasting",
        },
        {
            "name": "Comparison",
            "description": "Multi-series comparison and correlation analysis",
        },
        {
            "name": "AI",
            "description": "Natural language queries and AI-generated insights",
        },
        {
            "name": "Views",
            "description": "Save and share analysis configurations",
        },
        {
            "name": "System",
            "description": "Health checks and system information",
        },
    ],
    contact={
        "name": "TrendLab",
        "url": "https://github.com/yourusername/trendlab",
    },
    license_info={
        "name": "MIT",
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware (added after CORS so it sees the processed request)
app.add_middleware(RequestLoggingMiddleware)

# Rate limiting middleware (configurable via environment)
rate_limit_config = RateLimitConfig(
    requests_per_minute=int(os.getenv("RATE_LIMIT_PER_MINUTE", "60")),
    requests_per_hour=int(os.getenv("RATE_LIMIT_PER_HOUR", "1000")),
    burst_size=int(os.getenv("RATE_LIMIT_BURST", "10")),
    enabled=os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true",
)
app.add_middleware(RateLimitMiddleware, config=rate_limit_config)

# Secret phrase authentication (if configured)
app.add_middleware(SecretPhraseMiddleware)

app.include_router(api.router, prefix="/api")


def _get_request_id(request: Request) -> str | None:
    """Extract request ID from request state if available."""
    return getattr(request.state, "request_id", None)


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    request_id = _get_request_id(request)
    logger.with_fields(
        error_type="ValueError",
        path=str(request.url.path),
        request_id=request_id,
    ).warning("Validation error: %s", str(exc))
    return JSONResponse(
        status_code=422,
        content={"detail": str(exc), "request_id": request_id},
    )


@app.exception_handler(httpx.HTTPStatusError)
async def http_status_error_handler(request: Request, exc: httpx.HTTPStatusError):
    request_id = _get_request_id(request)
    logger.with_fields(
        error_type="HTTPStatusError",
        path=str(request.url.path),
        external_status=exc.response.status_code,
        request_id=request_id,
    ).warning("External API error")
    return JSONResponse(
        status_code=503,
        content={
            "detail": f"External API error: {exc.response.status_code}",
            "request_id": request_id,
        },
    )


@app.exception_handler(httpx.ConnectError)
async def connect_error_handler(request: Request, exc: httpx.ConnectError):
    request_id = _get_request_id(request)
    logger.with_fields(
        error_type="ConnectError",
        path=str(request.url.path),
        request_id=request_id,
    ).warning("External service unavailable")
    return JSONResponse(
        status_code=503,
        content={"detail": "External service unavailable", "request_id": request_id},
    )


@app.exception_handler(httpx.TimeoutException)
async def timeout_error_handler(request: Request, exc: httpx.TimeoutException):
    request_id = _get_request_id(request)
    logger.with_fields(
        error_type="TimeoutException",
        path=str(request.url.path),
        request_id=request_id,
    ).warning("External service timeout")
    return JSONResponse(
        status_code=503,
        content={"detail": "External service timeout", "request_id": request_id},
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    request_id = _get_request_id(request)
    logger.with_fields(
        error_type=type(exc).__name__,
        path=str(request.url.path),
        method=request.method,
        request_id=request_id,
    ).exception("Unhandled error")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": request_id},
    )


@app.get("/health", tags=["System"])
async def health_check():
    """
    Check if the service is running.

    Returns a simple status object. Used by container orchestration
    and load balancers for health monitoring.
    """
    return {"status": "ok"}


# Serve frontend static files (must be LAST so API routes take priority)
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount(
        "/",
        StaticFiles(directory=str(frontend_dist), html=True),
        name="frontend",
    )
else:

    @app.get("/")
    async def root():
        """Root endpoint (when frontend is not built)."""
        return {"message": "Welcome to trendlab"}
