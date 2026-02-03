import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.data.adapters.coingecko import CoinGeckoAdapter
from app.data.adapters.pypi import PyPIAdapter
from app.data.registry import registry
from app.routers import api

logger = logging.getLogger(__name__)

registry.register(PyPIAdapter())
registry.register(CoinGeckoAdapter())

if settings.github_token:
    from app.data.adapters.github import GitHubStarsAdapter

    registry.register(GitHubStarsAdapter(token=settings.github_token))
else:
    logger.warning("GITHUB_TOKEN not set — github_stars adapter will not be available")

app = FastAPI(
    title="trendlab",
    description=(
        "AI trend building lab. Connect data sources"
        " to real world data sets and start visualizing"
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api.router, prefix="/api")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Welcome to trendlab"}
