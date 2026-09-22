from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError


class InvalidInitDataError(Exception):
    """Raised when a Telegram initData payload fails HMAC validation or has expired."""


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(InvalidInitDataError)
    async def _invalid_init_data_handler(
        request: Request, exc: InvalidInitDataError
    ) -> JSONResponse:
        detail = str(exc) or "Invalid Telegram init data"
        return JSONResponse(status_code=401, content={"detail": detail})

    @app.exception_handler(IntegrityError)
    async def _integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
        return JSONResponse(
            status_code=400, content={"detail": "Request conflicts with existing data"}
        )
