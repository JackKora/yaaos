"""Partitioned-table migration for `coding_agent_activity`.

The codebase's first partitioned table — DDL is `PARTITION BY RANGE
(created_at)` + ~2 weeks of `PARTITION OF` children. The migration must
be idempotent under double-fire so re-running the migrator after a
partial application is safe.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.core import database
from app.core.database.service import _apply_create_coding_agent_activity


@pytest.mark.asyncio
async def test_coding_agent_activity_is_partitioned(_migrated_schema: None) -> None:
    """The parent table is partitioned by RANGE on created_at."""
    engine = database.get_engine()
    async with engine.connect() as conn:
        # `partstrat` = 'r' (range) when partitioned by range; absent otherwise.
        result = await conn.execute(
            text(
                "SELECT pt.partstrat FROM pg_partitioned_table pt"
                " JOIN pg_class c ON c.oid = pt.partrelid"
                " WHERE c.relname = 'coding_agent_activity'"
            )
        )
        row = result.one_or_none()
    assert row is not None, "coding_agent_activity should be partitioned"
    # `partstrat` is Postgres `char` type — driver returns bytes (`b'r'`).
    strat = row[0]
    if isinstance(strat, bytes):
        strat = strat.decode("ascii")
    assert strat == "r", "expected RANGE partitioning"


@pytest.mark.asyncio
async def test_initial_partitions_exist(_migrated_schema: None) -> None:
    """The migration creates at least three weekly child partitions."""
    engine = database.get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT relname FROM pg_class WHERE relname LIKE 'coding_agent_activity_p%' AND relkind = 'r'"
            )
        )
        names = [row[0] for row in result]
    assert len(names) >= 3, f"expected >= 3 weekly partitions, got {names}"


@pytest.mark.asyncio
async def test_migration_idempotent_under_double_fire(_migrated_schema: None) -> None:
    """Re-running `_apply_create_coding_agent_activity` after the initial
    migration must succeed (CREATE TABLE IF NOT EXISTS at every level)."""
    engine = database.get_engine()
    async with engine.begin() as conn:
        # Second fire on top of the already-applied migration; raises on
        # duplicate-table errors if any CREATE lacked IF NOT EXISTS.
        await _apply_create_coding_agent_activity(conn)

    # Verify the table + partitions still exist after the double-fire.
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT COUNT(*) FROM pg_class"
                " WHERE relname = 'coding_agent_activity'"
                " AND relkind = 'p'"  # 'p' = partitioned table
            )
        )
        count = result.scalar_one()
    assert count == 1
