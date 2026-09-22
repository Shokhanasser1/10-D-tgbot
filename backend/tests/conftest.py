from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from app.config import get_settings
from app.db.session import get_db
from app.main import app
from app.models import Base
from tests.factories import TEST_BOT_TOKEN

settings = get_settings()
settings.telegram_bot_token = TEST_BOT_TOKEN
settings.internal_api_token = "test-internal-token"


@pytest.fixture(scope="session")
def test_engine() -> AsyncEngine:
    return create_async_engine(settings.test_database_url, pool_pre_ping=True)


@pytest.fixture(scope="session", autouse=True)
async def _setup_schema(test_engine: AsyncEngine) -> AsyncGenerator[None, None]:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    await test_engine.dispose()


@pytest.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    connection = await test_engine.connect()
    trans = await connection.begin()
    session = AsyncSession(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    try:
        yield session
    finally:
        await session.close()
        await trans.rollback()
        await connection.close()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
