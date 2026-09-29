import logging

import stripe
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)


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

    @app.exception_handler(stripe.StripeError)
    async def _stripe_error_handler(request: Request, exc: stripe.StripeError) -> JSONResponse:
        # Missing keys, an outage or a rejected request: the customer can only try again later.
        # Stripe's message may describe the shop's account, so it is logged, not returned.
        logger.error("Stripe call failed on %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse(
            status_code=502,
            content={"detail": "Payment provider unavailable", "code": "payment_unavailable"},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        # FastAPI's default handler echoes each error's `input`. That is user-controlled and, for
        # a float field given `NaN`, cannot even be serialised (a 500 instead of a 422), so only
        # where and why the request was rejected is reported.
        detail = [
            {"type": error["type"], "loc": list(error["loc"]), "msg": error["msg"]}
            for error in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": detail})
