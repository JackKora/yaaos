"""SQLAlchemy async engine + session factory + `schema_migrations` bootstrap.

The skeleton uses no ORM models yet. The infrastructure exists so /health can
do a `SELECT 1` against the DB and so future modules drop in their tables
without reshaping bootstrap.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy declarative base. Module models inherit from this."""


_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        kwargs: dict[str, object] = {"pool_pre_ping": True, "future": True}
        # In dev/test we use NullPool — avoids cross-event-loop contamination
        # in TestClient-driven integration tests where each test brings up a
        # fresh loop. Prod uses the default pool.
        if settings.yaaof_env == "dev":
            from sqlalchemy.pool import NullPool  # noqa: PLC0415

            kwargs["poolclass"] = NullPool
            kwargs.pop("pool_pre_ping", None)
        _engine = create_async_engine(settings.database_url, **kwargs)  # type: ignore[arg-type]
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            get_engine(),
            expire_on_commit=False,
            class_=AsyncSession,
        )
    return _sessionmaker


@asynccontextmanager
async def session() -> AsyncIterator[AsyncSession]:
    """Yield an async session. Caller decides commit/rollback boundaries."""
    async with get_sessionmaker()() as s:
        yield s


async def ping() -> bool:
    """`SELECT 1` against the DB. Returns True on success, False on any error.

    Used by `/api/health` to report DB connectivity. Swallows all exceptions
    intentionally — the endpoint reports a boolean, not a stack trace.
    """
    try:
        async with session() as s:
            await s.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def ensure_schema_migrations_table() -> None:
    """Idempotently create the `schema_migrations` tracking table."""
    async with get_engine().begin() as conn:
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )


# M01 ships a single named migration ("001_create_all_m01"). Subsequent schema
# changes add new versions and the runner skips already-applied ones. The
# create_all approach is idempotent (CREATE TABLE IF NOT EXISTS underneath) so
# re-running is safe.
_M01_MIGRATIONS: tuple[tuple[str, str], ...] = (("001_create_all_m01", "create_all"),)


async def _apply_create_all(conn) -> None:  # type: ignore[no-untyped-def]
    import importlib  # noqa: PLC0415

    for mod in (
        "app.core.audit_log.models",
        "app.core.workspace.models",
        "app.plugins.claude_code.models",
        "app.plugins.github.models",
        "app.domain.repos.models",
        "app.domain.pull_requests.models",
        "app.domain.tickets.models",
        "app.domain.memory.models",
        "app.domain.reviewer.models",
    ):
        importlib.import_module(mod)
    await conn.run_sync(Base.metadata.create_all)


async def migrate() -> None:
    """Apply any un-applied migrations. Idempotent."""
    await ensure_schema_migrations_table()
    async with get_engine().begin() as conn:
        result = await conn.execute(text("SELECT version FROM schema_migrations"))
        applied = {row[0] for row in result}
    for version, kind in _M01_MIGRATIONS:
        if version in applied:
            continue
        async with get_engine().begin() as conn:
            if kind == "create_all":
                await _apply_create_all(conn)
            await conn.execute(
                text("INSERT INTO schema_migrations (version) VALUES (:v)"),
                {"v": version},
            )


async def dispose() -> None:
    """Close the engine — used on shutdown."""
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None
