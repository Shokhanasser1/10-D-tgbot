import asyncpg
import pytest

from app.config import get_settings
from scripts import create_databases as script

SCRATCH = "storefront_create_db_test"


def test_the_maintenance_database_keeps_server_and_credentials() -> None:
    dsn = script.admin_dsn("postgresql+asyncpg://shop:pw@db.local:5433/storefront")
    assert dsn == "postgresql://shop:pw@db.local:5433/postgres"
    assert script.database_name("postgresql+asyncpg://shop:pw@db.local:5433/storefront") == (
        "storefront"
    )


def test_a_url_without_a_database_is_refused() -> None:
    with pytest.raises(ValueError):
        script.database_name("postgresql+asyncpg://shop:pw@db.local:5433")


async def test_creates_what_is_missing_and_is_safe_to_rerun() -> None:
    base = get_settings().test_database_url
    scratch_url = base.rsplit("/", 1)[0] + f"/{SCRATCH}"
    conn = await asyncpg.connect(script.admin_dsn(base))
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{SCRATCH}"')

        assert await script.create_missing([base, scratch_url]) == [SCRATCH]
        assert await script.create_missing([base, scratch_url]) == []
    finally:
        await conn.execute(f'DROP DATABASE IF EXISTS "{SCRATCH}" WITH (FORCE)')
        await conn.close()
