from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.db.session import async_session_factory
from app.services import admin_service


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    ids = get_settings().admin_bootstrap_ids
    if ids:
        async with async_session_factory() as session:
            await admin_service.bootstrap_owners(session, ids)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    is_production = settings.env == "production"

    # Interactive docs enumerate every route, including /internal/*, so they stay off in production.
    app = FastAPI(
        title="Storefront API",
        version="0.1.0",
        docs_url=None if is_production else "/docs",
        redoc_url=None if is_production else "/redoc",
        openapi_url=None if is_production else "/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[] if is_production else settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(api_router)

    return app


app = create_app()
