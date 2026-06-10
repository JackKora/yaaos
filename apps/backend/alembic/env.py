"""Alembic env.py — dual-path migration runner.

Runs in two modes:

- **Boot path** (called via ``core/database.migrate()``): ``migrate()`` opens an
  async connection, bridges to sync via ``await conn.run_sync(_drive_alembic_upgrade)``,
  stashes the sync DBAPI connection on ``config.attributes["connection"]``, then calls
  ``alembic.command.upgrade(config, "head")``.  When ``run_migrations_online()`` sees
  a non-None ``config.attributes["connection"]`` it calls ``do_run_migrations`` directly
  with that stashed connection — no second engine is opened.

- **CLI path** (``alembic revision --autogenerate -m "<msg>"`` from terminal): no
  connection is stashed, so ``run_migrations_online()`` falls through to
  ``asyncio.run(run_async_migrations())``, which builds a fresh async engine from
  ``settings.database_url`` and bridges via ``await connection.run_sync(do_run_migrations)``.

The ``sqlalchemy.url`` in ``alembic.ini`` is ignored at runtime; ``env.py`` reads
``settings.database_url`` directly so dev / CI / prod all hit the right DB without
per-env ``alembic.ini`` edits.  The ini value remains only so misconfigured CLI
invocations fail loudly.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import async_engine_from_config

# ---------------------------------------------------------------------------
# Import every model module so Base.metadata is fully populated.
# This list MUST stay in sync with the find apps/backend/app -name models.py
# sweep; autogenerate reflects only tables registered on Base.
# ---------------------------------------------------------------------------
import app.core.agent_gateway.models
import app.core.audit_log.models
import app.core.byok.models
import app.core.coding_agent.models
import app.core.identity.models
import app.core.notifications.models
import app.core.tasks.models
import app.core.tenancy.models
import app.core.workflow.models
import app.core.workspace.models
import app.domain.integrations.models
import app.domain.lessons.models
import app.domain.mcp_proxy.models
import app.domain.orgs.models
import app.domain.reviewer.models
import app.domain.tickets.models
import app.plugins.claude_code.models
import app.plugins.github.models  # noqa: F401
from alembic import context
from app.core.database.service import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    """Shared sync inner — configures Alembic context and runs migrations."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """CLI path: build a fresh async engine from settings.database_url and bridge to sync."""
    from app.core.config import get_settings  # noqa: PLC0415

    settings = get_settings()
    # Build config section from the ini but override the URL with settings so
    # dev / CI / prod hit the right DB without per-env alembic.ini edits.
    ini_section = config.get_section(config.config_ini_section, {})
    ini_section["sqlalchemy.url"] = str(settings.database_url)
    connectable = async_engine_from_config(
        ini_section,
        prefix="sqlalchemy.",
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_offline() -> None:
    """--sql mode: emit raw SQL without a live connection (rarely used)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Online mode: dual-path per boot vs. CLI caller."""
    connection = config.attributes.get("connection")
    if connection is not None:
        # Boot path: caller stashed a sync DBAPI connection via run_sync.
        do_run_migrations(connection)
    else:
        # CLI path: no stashed connection — build own async engine.
        # asyncio.run() only works from a sync (non-running-loop) context,
        # which is guaranteed for terminal `alembic` invocations.
        asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
