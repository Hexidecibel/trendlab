import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.data.adapters.asa import ASAAdapter
from app.data.adapters.coingecko import CoinGeckoAdapter
from app.data.adapters.pypi import PyPIAdapter
from app.data.registry import registry
from app.db.engine import init_db
from app.routers import api

logger = logging.getLogger(__name__)

registry.register(PyPIAdapter())
registry.register(CoinGeckoAdapter())
registry.register(ASAAdapter())

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    lifespan=lifespan,
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
