from collections.abc import AsyncGenerator

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_telegram_user
from app.db.session import get_db
from app.models.telegram_user import TelegramUser
from tests.factories import make_init_data


def _build_whoami_app() -> FastAPI:
    app = FastAPI()

    @app.get("/whoami")
    async def whoami(user: TelegramUser = Depends(get_current_telegram_user)) -> dict[str, int]:
        return {"telegram_id": user.telegram_id}

    return app


@pytest.fixture
async def whoami_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    app = _build_whoami_app()

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_valid_init_data_returns_200_and_upserts_user(
    whoami_client: AsyncClient, db_session: AsyncSession
) -> None:
    raw = make_init_data(telegram_id=555, username="bob")
    response = await whoami_client.get("/whoami", headers={"Authorization": f"tma {raw}"})

    assert response.status_code == 200
    assert response.json() == {"telegram_id": 555}

    stored = (
        await db_session.execute(select(TelegramUser).where(TelegramUser.telegram_id == 555))
    ).scalar_one()
    assert stored.username == "bob"


async def test_missing_authorization_header_returns_401(whoami_client: AsyncClient) -> None:
    response = await whoami_client.get("/whoami")
    assert response.status_code == 401


async def test_repeat_call_upserts_rather_than_duplicates(
    whoami_client: AsyncClient, db_session: AsyncSession
) -> None:
    first = make_init_data(telegram_id=777, username="carol")
    second = make_init_data(telegram_id=777, username="carol_renamed")

    await whoami_client.get("/whoami", headers={"Authorization": f"tma {first}"})
    await whoami_client.get("/whoami", headers={"Authorization": f"tma {second}"})

    rows = (
        (await db_session.execute(select(TelegramUser).where(TelegramUser.telegram_id == 777)))
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].username == "carol_renamed"
