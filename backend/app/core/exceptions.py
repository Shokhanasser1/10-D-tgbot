from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError


class InvalidInitDataError(Exception):
    """Raised when a Telegram initData payload fails HMAC validation or has expired."""


class NotFoundError(Exception):
    """Raised by the service layer when a referenced entity does not exist."""


class ConflictError(Exception):
    """Raised by the service layer for business-rule conflicts (e.g. insufficient stock).

    `code` is a stable machine-readable reason. `detail` text is English, but the UI is
    localised, so clients map `code` to their own message instead of showing `detail`.
    """

    def __init__(self, message: str = "", *, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code


class ForbiddenError(Exception):
    """Raised by the service layer when the caller is authenticated but not allowed."""


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
        content = {"detail": str(exc) or "Conflict"}
        if exc.code is not None:
            content["code"] = exc.code
        return JSONResponse(status_code=409, content=content)

    @app.exception_handler(ForbiddenError)
    async def _forbidden_handler(request: Request, exc: ForbiddenError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc) or "Forbidden"})

    @app.exception_handler(BadRequestError)
    async def _bad_request_handler(request: Request, exc: BadRequestError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc) or "Bad request"})

    @app.exception_handler(IntegrityError)
    async def _integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
        return JSONResponse(
            status_code=400, content={"detail": "Request conflicts with existing data"}
        )
