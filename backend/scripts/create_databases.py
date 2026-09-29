"""Create the app and test databases on a local PostgreSQL (no Docker, no psql needed).

Usage (from backend/, with the virtual environment active):
    python -m scripts.create_databases

Reads DATABASE_URL and TEST_DATABASE_URL (backend/.env), connects to the server's built-in
`postgres` database with the same user and password, and creates each database that does not
exist yet. Running it again changes nothing.
"""

import asyncio
import sys

import asyncpg
from sqlalchemy.engine import make_url

from app.config import get_settings


def admin_dsn(database_url: str) -> str:
    """The same server and credentials, but the maintenance database `postgres`."""
    url = make_url(database_url).set(drivername="postgresql", database="postgres")
    return url.render_as_string(hide_password=False)


def database_name(database_url: str) -> str:
    name = make_url(database_url).database
    if not name:
        raise ValueError(f"no database name in {make_url(database_url)!r}")
    return name


async def create_missing(database_urls: list[str]) -> list[str]:
    """Create the databases that are missing; returns the names it created."""
    conn = await asyncpg.connect(admin_dsn(database_urls[0]))
    created = []
    try:
        for name in dict.fromkeys(database_name(url) for url in database_urls):
            exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", name)
            if not exists:
                # Identifiers cannot be bound as parameters; quote the name instead.
                await conn.execute(f'CREATE DATABASE "{name.replace(chr(34), chr(34) * 2)}"')
                created.append(name)
    finally:
        await conn.close()
    return created


def main() -> int:
    settings = get_settings()
    urls = [settings.database_url, settings.test_database_url]
    try:
        created = asyncio.run(create_missing(urls))
    except (OSError, asyncpg.PostgresError) as exc:
        print(
            "error: could not reach PostgreSQL. Is it installed and running, and do the user "
            f"and password in DATABASE_URL match? ({type(exc).__name__}: {exc})",
            file=sys.stderr,
        )
        return 1
    for name in (database_name(url) for url in urls):
        print(f"{name}: {'created' if name in created else 'already exists'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
