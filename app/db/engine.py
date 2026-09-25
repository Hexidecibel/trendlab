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
        await conn.run_sync(add_missing_columns)


def add_missing_columns(sync_conn) -> list[str]:
    """Additive schema migration: ``ALTER TABLE ... ADD COLUMN`` for every
    model column the existing table lacks.

    ``create_all`` only creates missing *tables*, so a column added to a
    model (e.g. the watchlist alert fields) would otherwise be absent from
    databases created before it. New columns must be nullable (or have a
    server default). Returns the ``table.column`` names that were added.
    """
    from sqlalchemy import inspect, text

    from app.db.models import Base

    insp = inspect(sync_conn)
    existing_tables = set(insp.get_table_names())
    added: list[str] = []
    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue
        have = {c["name"] for c in insp.get_columns(table.name)}
        for col in table.columns:
            if col.name in have:
                continue
            col_type = col.type.compile(dialect=sync_conn.dialect)
            sync_conn.execute(
                text(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {col_type}')
            )
            added.append(f"{table.name}.{col.name}")
    return added


def get_engine():
    return _engine
