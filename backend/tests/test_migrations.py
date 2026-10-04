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
COURIER_REVISION = "6293a99b0b9c"  # the schema before the admin panel


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
    has_seller = await conn.fetchval(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = 'orders' AND column_name = 'seller_id'"
    )
    has_rate = await conn.fetchval(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = 'orders' AND column_name = 'commission_percent'"
    )
    if has_rate:  # Spec 11: the seller's rate is copied onto the order
        seller_id = await conn.fetchval("INSERT INTO sellers (name) VALUES ('Shop') RETURNING id")
        return await conn.fetchval(
            "INSERT INTO orders (telegram_id, status, currency, subtotal, shipping_cost, total, "
            "delivery_address, seller_id, commission_percent) "
            "VALUES ($1, $2, 'EUR', 10, 4.99, 14.99, $3::jsonb, $4, 10) RETURNING id",
            telegram_id,
            status,
            json.dumps({"city": "Berlin", "notes": None}),
            seller_id,
        )
    if has_seller:  # Spec 10: from then on every order belongs to a seller
        seller_id = await conn.fetchval("INSERT INTO sellers (name) VALUES ('Shop') RETURNING id")
        return await conn.fetchval(
            "INSERT INTO orders (telegram_id, status, currency, subtotal, shipping_cost, total, "
            "delivery_address, seller_id) VALUES ($1, $2, 'EUR', 10, 4.99, 14.99, $3::jsonb, $4) "
            "RETURNING id",
            telegram_id,
            status,
            json.dumps({"city": "Berlin", "notes": None}),
            seller_id,
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


async def test_admin_panel_downgrade_drops_cancelled_shipments(scratch_database: str) -> None:
    """The courier schema has no 'cancelled' shipment status, so going back must not leave one."""
    up = await asyncio.to_thread(_alembic, scratch_database, "upgrade", "head")
    assert up.returncode == 0, up.stderr

    conn = await _connect_scratch()
    try:
        cancelled = await _insert_order(conn, 1, "cancelled")
        await conn.execute(
            "INSERT INTO shipments (order_id, status) VALUES ($1, 'cancelled')", cancelled
        )
        live = await _insert_order(conn, 2, "paid")
        await conn.execute(
            "INSERT INTO shipments (order_id, status) VALUES ($1, 'processing')", live
        )
    finally:
        await conn.close()

    down = await asyncio.to_thread(_alembic, scratch_database, "downgrade", COURIER_REVISION)
    assert down.returncode == 0, down.stderr

    conn = await _connect_scratch()
    try:
        statuses = await conn.fetch("SELECT order_id, status FROM shipments ORDER BY order_id")
        assert [(r["order_id"], r["status"]) for r in statuses] == [(live, "processing")]
        assert await conn.fetchval("SELECT status FROM orders WHERE id = $1", cancelled) == (
            "cancelled"
        )
        assert await conn.fetchval("SELECT to_regclass('admins')") is None
    finally:
        await conn.close()


ADMIN_PASSWORDS_REVISION = "f1a2b3c4d5e6"  # the schema before sellers


async def _insert_product(conn: asyncpg.Connection, sku: str) -> int:
    category_id = await conn.fetchval(
        "INSERT INTO categories (slug, sort_order) VALUES ($1, 0) RETURNING id", f"cat-{sku}"
    )
    return await conn.fetchval(
        "INSERT INTO products (category_id, base_sku, base_price, status) "
        "VALUES ($1, $2, 10, 'active') RETURNING id",
        category_id,
        sku,
    )


async def test_sellers_migration_gives_existing_products_a_main_shop(
    scratch_database: str,
) -> None:
    old = await asyncio.to_thread(_alembic, scratch_database, "upgrade", ADMIN_PASSWORDS_REVISION)
    assert old.returncode == 0, old.stderr

    conn = await _connect_scratch()
    try:
        first = await _insert_product(conn, "OLD-1")
        second = await _insert_product(conn, "OLD-2")
    finally:
        await conn.close()

    up = await asyncio.to_thread(_alembic, scratch_database, "upgrade", "head")
    assert up.returncode == 0, up.stderr

    conn = await _connect_scratch()
    try:
        sellers = await conn.fetch("SELECT id, name, pickup_address, is_active FROM sellers")
        assert [(s["name"], s["pickup_address"], s["is_active"]) for s in sellers] == [
            ("Main shop", None, True)
        ]
        owners = await conn.fetch(
            "SELECT seller_id FROM products WHERE id = ANY($1::int[])", [first, second]
        )
        assert {row["seller_id"] for row in owners} == {sellers[0]["id"]}

        # A seller account, which the previous schema cannot represent.
        await conn.execute(
            "INSERT INTO admins (telegram_id, role, display_name, seller_id) "
            "VALUES (5, 'seller', 'Lola', $1)",
            sellers[0]["id"],
        )
    finally:
        await conn.close()

    down = await asyncio.to_thread(
        _alembic, scratch_database, "downgrade", ADMIN_PASSWORDS_REVISION
    )
    assert down.returncode == 0, down.stderr

    conn = await _connect_scratch()
    try:
        assert await conn.fetchval("SELECT count(*) FROM admins WHERE role = 'seller'") == 0
        assert await conn.fetchval("SELECT count(*) FROM products") == 2
        assert await conn.fetchval("SELECT to_regclass('sellers')") is None
    finally:
        await conn.close()


async def test_sellers_migration_creates_no_shop_for_an_empty_catalog(
    scratch_database: str,
) -> None:
    up = await asyncio.to_thread(_alembic, scratch_database, "upgrade", "head")
    assert up.returncode == 0, up.stderr

    conn = await _connect_scratch()
    try:
        assert await conn.fetchval("SELECT count(*) FROM sellers") == 0
    finally:
        await conn.close()


SELLERS_REVISION = "a9b8c7d6e5f4"  # the schema before orders knew their seller


async def test_seller_orders_migration_fills_seller_and_readiness(scratch_database: str) -> None:
    old = await asyncio.to_thread(_alembic, scratch_database, "upgrade", SELLERS_REVISION)
    assert old.returncode == 0, old.stderr

    conn = await _connect_scratch()
    try:
        seller_id = await conn.fetchval("INSERT INTO sellers (name) VALUES ('Lola') RETURNING id")
        category_id = await conn.fetchval(
            "INSERT INTO categories (slug, sort_order) VALUES ('so-cat', 0) RETURNING id"
        )
        product_id = await conn.fetchval(
            "INSERT INTO products (category_id, seller_id, base_sku, base_price, status) "
            "VALUES ($1, $2, 'SO-1', 10, 'active') RETURNING id",
            category_id,
            seller_id,
        )
        variant_id = await conn.fetchval(
            "INSERT INTO variants (product_id, sku, price, stock_qty, attribute_values) "
            "VALUES ($1, 'SO-1-V', 10, 5, '{}'::jsonb) RETURNING id",
            product_id,
        )
        order_id = await _insert_order(conn, 1, "paid")
        await conn.execute(
            "INSERT INTO order_items (order_id, variant_id, product_name_snapshot, qty, "
            "unit_price_snapshot) VALUES ($1, $2, 'Lipstick', 1, 10)",
            order_id,
            variant_id,
        )
        no_items = await _insert_order(conn, 2, "paid")
        await conn.execute(
            "INSERT INTO shipments (order_id, status) VALUES ($1, 'processing')", order_id
        )
    finally:
        await conn.close()

    up = await asyncio.to_thread(_alembic, scratch_database, "upgrade", "head")
    assert up.returncode == 0, up.stderr

    conn = await _connect_scratch()
    try:
        assert await conn.fetchval("SELECT seller_id FROM orders WHERE id = $1", order_id) == (
            seller_id
        )
        main_shop = await conn.fetchval("SELECT seller_id FROM orders WHERE id = $1", no_items)
        assert await conn.fetchval("SELECT name FROM sellers WHERE id = $1", main_shop) == (
            "Main shop"
        )
        # Orders already in the pool stay there.
        row = await conn.fetchrow(
            "SELECT ready_at, created_at FROM shipments WHERE order_id = $1", order_id
        )
        assert row["ready_at"] == row["created_at"]
    finally:
        await conn.close()


SELLER_ORDERS_REVISION = "b1c2d3e4f5a6"  # the schema before commissions


async def test_seller_money_migration_copies_rates_onto_orders(scratch_database: str) -> None:
    old = await asyncio.to_thread(_alembic, scratch_database, "upgrade", SELLER_ORDERS_REVISION)
    assert old.returncode == 0, old.stderr
    conn = await _connect_scratch()
    try:
        order_id = await _insert_order(conn, 1, "paid")
    finally:
        await conn.close()

    up = await asyncio.to_thread(_alembic, scratch_database, "upgrade", "head")
    assert up.returncode == 0, up.stderr

    conn = await _connect_scratch()
    try:
        rate = await conn.fetchval("SELECT commission_percent FROM orders WHERE id = $1", order_id)
        assert str(rate) == "10.00"
        assert await conn.fetchval("SELECT to_regclass('seller_earnings')") is not None
        assert await conn.fetchval("SELECT to_regclass('seller_payouts')") is not None
    finally:
        await conn.close()
