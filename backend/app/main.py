"""FastAPI application entrypoint.

Creates the app with lifespan, middleware, exception handlers, and the
versioned API router.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.db import engine
from app.core.logging import request_id_var, setup_logging
from app.core.middleware import (
    ApiTokenMiddleware,
    RateLimitMiddleware,
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
)
from app.domain.errors import ErrorEnvelope, PramyaError
from app.observability import flush_pending


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    setup_logging()
    # Future: provider health checks, model lifecycle.
    yield
    # Best-effort, bounded: never let a stuck telemetry exporter delay
    # shutdown (broken/slow Langfuse ingestion must not block the app).
    flush_pending()
    await engine.dispose()


ExceptionHandler = Callable[[Request, Exception], Awaitable[Response]]


def _envelope(exc: PramyaError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorEnvelope(
            code=exc.code,
            message=exc.message,
            request_id=request_id_var.get(),
            details=exc.details,
        ).__dict__,
    )


async def pramya_error_handler(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, PramyaError)
    return _envelope(exc)


async def validation_error_handler(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, RequestValidationError)
    envelope = ErrorEnvelope(
        code="validation_failed",
        message="request validation failed",
        request_id=request_id_var.get(),
        details={"errors": exc.errors()},
    )
    return JSONResponse(status_code=422, content=envelope.__dict__)


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url=f"{settings.api_prefix}/openapi.json",
    )
    app.include_router(api_router, prefix=settings.api_prefix)
    # Middleware stack: LAST added = OUTERMOST (Starlette reverses on build).
    # Add innermost first: ApiToken, RateLimit, SecurityHeaders, RequestID,
    # and CORS last so it is outermost — preflights resolve before auth and
    # 401/429 responses still carry security headers + request id.
    app.add_middleware(
        ApiTokenMiddleware,
        tokens=settings.api_tokens,
        api_prefix=settings.api_prefix,
    )
    app.add_middleware(
        RateLimitMiddleware, rpm=settings.rate_limit_rpm, api_prefix=settings.api_prefix
    )
    if settings.security_headers:
        app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    app.add_exception_handler(PramyaError, pramya_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    return app


app = create_app()
