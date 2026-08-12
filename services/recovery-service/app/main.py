import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from secrets import token_urlsafe

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.router import router
from app.core.config import APP_VERSION, load_settings
from app.domain.recovery import (
    RecoveryAuthorizationError,
    RecoveryConflictError,
    RecoveryNotFoundError,
    RecoveryPersistenceError,
    RecoveryValidationError,
    SecretShareError,
)
from app.runtime import RecoveryRuntime


_RUNTIME = RecoveryRuntime(load_settings())
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await _RUNTIME.start()
    try:
        yield
    finally:
        await _RUNTIME.stop()


app = FastAPI(
    title="Secure SSI Guardian Recovery API",
    version=APP_VERSION,
    description=(
        "Guardian-based M-of-N recovery with encrypted Shamir share envelopes, "
        "persisted time-locks, and managed-key rotation orchestration."
    ),
    lifespan=lifespan,
)
app.state.recovery_runtime = _RUNTIME
app.include_router(router)


@app.middleware("http")
async def request_context(request: Request, call_next):
    supplied = request.headers.get("X-Request-ID", "")
    request.state.request_id = (
        supplied
        if _REQUEST_ID_PATTERN.fullmatch(supplied)
        else "req_" + token_urlsafe(18)
    )
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


def _error(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    *,
    headers: dict[str, str] | None = None,
):
    return JSONResponse(
        status_code=status_code,
        content={
            "code": code,
            "message": message,
            "requestId": getattr(request.state, "request_id", None),
        },
        headers=headers,
    )


@app.exception_handler(HTTPException)
def recovery_http_error(request: Request, error: HTTPException):
    code, message = {
        401: ("RECOVERY_UNAUTHORIZED", "Bearer authentication is required."),
        403: ("RECOVERY_FORBIDDEN", "The operation is not permitted."),
        404: ("RECOVERY_NOT_FOUND", "The requested resource was not found."),
        409: ("RECOVERY_CONFLICT", "The recovery request conflicts with current state."),
        422: ("RECOVERY_INVALID", "Request validation failed."),
    }.get(
        error.status_code,
        ("RECOVERY_REQUEST_FAILED", "The recovery request failed."),
    )
    headers = {"WWW-Authenticate": "Bearer"} if error.status_code == 401 else None
    return _error(request, error.status_code, code, message, headers=headers)


@app.exception_handler(RequestValidationError)
def recovery_request_validation(request: Request, _error_value: RequestValidationError):
    return _error(request, 422, "RECOVERY_INVALID", "Request validation failed.")


@app.exception_handler(RecoveryNotFoundError)
def recovery_not_found(request: Request, _error_value: RecoveryNotFoundError):
    return _error(request, 404, "RECOVERY_NOT_FOUND", "The requested resource was not found.")


@app.exception_handler(RecoveryAuthorizationError)
def recovery_forbidden(request: Request, _error_value: RecoveryAuthorizationError):
    return _error(request, 403, "RECOVERY_FORBIDDEN", "The operation is not permitted.")


@app.exception_handler(RecoveryConflictError)
def recovery_conflict(request: Request, error: RecoveryConflictError):
    return _error(request, 409, "RECOVERY_CONFLICT", str(error))


@app.exception_handler(RecoveryValidationError)
def recovery_validation(request: Request, error: RecoveryValidationError):
    return _error(request, 422, "RECOVERY_INVALID", str(error))


@app.exception_handler(SecretShareError)
def share_validation(request: Request, _error_value: SecretShareError):
    return _error(request, 422, "RECOVERY_EVIDENCE_INVALID", "Recovery evidence is invalid.")


@app.exception_handler(RecoveryPersistenceError)
def recovery_unavailable(request: Request, _error_value: RecoveryPersistenceError):
    return _error(request, 503, "RECOVERY_UNAVAILABLE", "Recovery persistence is unavailable.")
