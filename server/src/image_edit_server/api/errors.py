from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# `input` echoes the rejected value and `ctx` can carry it too; a request holding
# a password, provider token or authorization code must not get it back in a 422.
_SECRET_BEARING_FIELDS = ("input", "ctx")


async def _validation_error_response(
    _request: Request, error: RequestValidationError
) -> JSONResponse:
    detail = [
        {key: value for key, value in item.items() if key not in _SECRET_BEARING_FIELDS}
        for item in error.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": detail})


def install_validation_error_handler(app: FastAPI) -> None:
    """Answer 422 with where and why a field failed, never with the value sent."""
    app.add_exception_handler(RequestValidationError, _validation_error_response)
