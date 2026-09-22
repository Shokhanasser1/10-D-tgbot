from fastapi import FastAPI


class InvalidInitDataError(Exception):
    """Raised when a Telegram initData payload fails HMAC validation or has expired."""


def register_exception_handlers(app: FastAPI) -> None:
    from fastapi import Request
    from fastapi.responses import JSONResponse

    @app.exception_handler(InvalidInitDataError)
    async def _invalid_init_data_handler(
        request: Request, exc: InvalidInitDataError
    ) -> JSONResponse:
        detail = str(exc) or "Invalid Telegram init data"
        return JSONResponse(status_code=401, content={"detail": detail})
