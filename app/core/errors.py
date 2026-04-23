from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def _error_payload(code: str, message: str, details: object | None = None) -> dict:
    body = {
        "error": {
            "code": code,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    }
    if details is not None:
        body["error"]["details"] = details
    return body


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=_error_payload("VALIDATION_ERROR", "Request validation failed", exc.errors()),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException):
        if isinstance(exc.detail, dict):
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload("HTTP_ERROR", str(exc.detail)),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content=_error_payload("INTERNAL_SERVER_ERROR", "Unexpected server error", str(exc)),
        )
