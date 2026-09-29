import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.db.session import async_session_factory
from app.services import admin_service, reservation_service


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    ids = settings.admin_bootstrap_ids
    if ids:
        async with async_session_factory() as session:
            await admin_service.bootstrap_owners(session, ids)

    sweeper = None
    if settings.reservation_sweep_seconds > 0:
        sweeper = asyncio.create_task(
            reservation_service.run_sweeper(
                async_session_factory, settings.reservation_sweep_seconds
            )
        )
    yield
    if sweeper is not None:
        sweeper.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await sweeper


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

    if settings.env == "development":
        # In production nginx serves uploaded photos straight from the volume.
        app.mount("/media", StaticFiles(directory=settings.media_root, check_dir=False), "media")

    return app


app = create_app()
