"""Runs the real Alembic migrations against a throwaway database.

The rest of the suite builds its schema with Base.metadata.create_all for speed, so this
is the only place that proves the migration scripts themselves apply, roll back, and
match the models.
"""

import asyncio
import json
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
PREVIOUS_REVISION = "ced74685a439"  # the schema before couriers existed


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


async def _connect_scratch() -> asyncpg.Connection:
    url = make_url(get_settings().test_database_url)
    url = url.set(drivername="postgresql", database=SCRATCH_DB)
    return await asyncpg.connect(url.render_as_string(hide_password=False))


async def _insert_order(conn: asyncpg.Connection, telegram_id: int, status: str) -> int:
    await conn.execute(
        "INSERT INTO telegram_users (telegram_id, locale) VALUES ($1, 'en') ON CONFLICT DO NOTHING",
        telegram_id,
    )
    return await conn.fetchval(
        "INSERT INTO orders (telegram_id, status, currency, subtotal, shipping_cost, total, "
        "delivery_address) VALUES ($1, $2, 'EUR', 10, 4.99, 14.99, $3::jsonb) RETURNING id",
        telegram_id,
        status,
        json.dumps({"city": "Berlin", "notes": None}),
    )


async def test_courier_migration_preserves_shipments_and_normalises_on_downgrade(
    scratch_database: str,
) -> None:
    """Runs on populated data: the plain-integer courier_id becomes a foreign key, and going
    back must not leave rows the previous schema cannot load (it has no 'assigned' status)."""
    old = await asyncio.to_thread(_alembic, scratch_database, "upgrade", PREVIOUS_REVISION)
    assert old.returncode == 0, old.stderr

    conn = await _connect_scratch()
    try:
        first_order = await _insert_order(conn, 1, "paid")
        await conn.execute(
            "INSERT INTO shipments (order_id, status) VALUES ($1, 'processing')", first_order
        )
    finally:
        await conn.close()

    up = await asyncio.to_thread(_alembic, scratch_database, "upgrade", "head")
    assert up.returncode == 0, up.stderr

    conn = await _connect_scratch()
    try:
        row = await conn.fetchrow(
            "SELECT status, courier_id, assigned_at FROM shipments WHERE order_id = $1", first_order
        )
        assert (row["status"], row["courier_id"], row["assigned_at"]) == ("processing", None, None)
        address = json.loads(
            await conn.fetchval("SELECT delivery_address FROM orders WHERE id = $1", first_order)
        )
        assert address == {"city": "Berlin", "notes": None}

        courier_id = await conn.fetchval(
            "INSERT INTO couriers (telegram_id, name) VALUES (9, 'Ali') RETURNING id"
        )
        second_order = await _insert_order(conn, 2, "processing")
        await conn.execute(
            "INSERT INTO shipments (order_id, status, courier_id) VALUES ($1, 'assigned', $2)",
            second_order,
            courier_id,
        )
    finally:
        await conn.close()

    down = await asyncio.to_thread(_alembic, scratch_database, "downgrade", PREVIOUS_REVISION)
    assert down.returncode == 0, down.stderr

    conn = await _connect_scratch()
    try:
        shipment = await conn.fetchrow(
            "SELECT status, courier_id FROM shipments WHERE order_id = $1", second_order
        )
        assert (shipment["status"], shipment["courier_id"]) == ("processing", None)
        order_status = "SELECT status FROM orders WHERE id = $1"
        assert await conn.fetchval(order_status, second_order) == "paid"
        assert await conn.fetchval(order_status, first_order) == "paid"
        assert await conn.fetchval("SELECT to_regclass('couriers')") is None
    finally:
        await conn.close()
