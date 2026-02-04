from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

_engine = None
async_session: async_sessionmaker[AsyncSession] = None  # type: ignore[assignment]


async def init_db(url: str | None = None) -> None:
    """Create the async engine, session factory, and all tables."""
    global _engine, async_session

    if _engine is not None:
        await _engine.dispose()

    db_url = url or settings.database_url
    _engine = create_async_engine(db_url, echo=False)
    async_session = async_sessionmaker(_engine, expire_on_commit=False)

    from app.db.models import Base

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def get_engine():
    return _engine
