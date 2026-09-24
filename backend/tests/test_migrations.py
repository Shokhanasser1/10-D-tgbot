"""Runs the real Alembic migrations against a throwaway database.

The rest of the suite builds its schema with Base.metadata.create_all for speed, so this
is the only place that proves the migration scripts themselves apply, roll back, and
match the models.
"""

import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncGenerator
from pathlib import Path

import asyncpg
import pytest
from sqlalchemy.engine import make_url

from app.config import get_settings

BACKEND_DIR = Path(__file__).resolve().parent.parent
SCRATCH_DB = "storefront_migration_test"


def _admin_dsn() -> str:
    url = make_url(get_settings().test_database_url)
    return url.set(drivername="postgresql", database="postgres").render_as_string(
        hide_password=False
    )


def _scratch_url() -> str:
    url = make_url(get_settings().test_database_url)
    return url.set(database=SCRATCH_DB).render_as_string(hide_password=False)


@pytest.fixture
async def scratch_database() -> AsyncGenerator[str, None]:
    conn = await asyncpg.connect(_admin_dsn())
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}"')
        await conn.execute(f'CREATE DATABASE "{SCRATCH_DB}"')
        yield _scratch_url()
    finally:
        await conn.execute(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}" WITH (FORCE)')
        await conn.close()


def _alembic(database_url: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env={**os.environ, "DATABASE_URL": database_url},
        capture_output=True,
        text=True,
        check=False,
    )


async def test_migrations_upgrade_downgrade_and_match_models(scratch_database: str) -> None:
    upgrade = await asyncio.to_thread(_alembic, scratch_database, "upgrade", "head")
    assert upgrade.returncode == 0, upgrade.stderr

    downgrade = await asyncio.to_thread(_alembic, scratch_database, "downgrade", "base")
    assert downgrade.returncode == 0, downgrade.stderr

    reupgrade = await asyncio.to_thread(_alembic, scratch_database, "upgrade", "head")
    assert reupgrade.returncode == 0, reupgrade.stderr

    check = await asyncio.to_thread(_alembic, scratch_database, "check")
    assert check.returncode == 0, check.stderr
