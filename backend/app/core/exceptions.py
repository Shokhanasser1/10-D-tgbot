from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError


class InvalidInitDataError(Exception):
    """Raised when a Telegram initData payload fails HMAC validation or has expired."""


class NotFoundError(Exception):
    """Raised by the service layer when a referenced entity does not exist."""


class ConflictError(Exception):
    """Raised by the service layer for business-rule conflicts (e.g. insufficient stock)."""


class BadRequestError(Exception):
    """Raised by the service layer for invalid requests that aren't a resource conflict."""


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(InvalidInitDataError)
    async def _invalid_init_data_handler(
        request: Request, exc: InvalidInitDataError
    ) -> JSONResponse:
        detail = str(exc) or "Invalid Telegram init data"
        return JSONResponse(status_code=401, content={"detail": detail})

    @app.exception_handler(NotFoundError)
    async def _not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc) or "Not found"})

    @app.exception_handler(ConflictError)
    async def _conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc) or "Conflict"})

    @app.exception_handler(BadRequestError)
    async def _bad_request_handler(request: Request, exc: BadRequestError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc) or "Bad request"})

    @app.exception_handler(IntegrityError)
    async def _integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
        return JSONResponse(
            status_code=400, content={"detail": "Request conflicts with existing data"}
        )
