from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.exceptions import register_exception_handlers


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title="Storefront API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins if settings.env != "production" else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    from app.api.router import api_router

    app.include_router(api_router)

    return app


app = create_app()
