from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.main import create_app


async def test_health_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_api_docs_are_enabled_in_development(client: AsyncClient) -> None:
    assert (await client.get("/docs")).status_code == 200


async def test_api_docs_are_disabled_in_production() -> None:
    settings = get_settings()
    original = settings.env
    settings.env = "production"
    try:
        production_app = create_app()
    finally:
        settings.env = original

    async with AsyncClient(transport=ASGITransport(app=production_app), base_url="http://t") as ac:
        assert (await ac.get("/docs")).status_code == 404
        assert (await ac.get("/openapi.json")).status_code == 404
        assert (await ac.get("/health")).status_code == 200
