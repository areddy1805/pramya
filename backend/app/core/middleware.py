"""Request ID middleware.

Assigns or forwards a request_id per HTTP request (X-Request-ID), makes it
available to logging via contextvars, and echoes it in the response header
so frontend errors can be correlated with backend logs.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.logging import request_id_var


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = request_id
        return response


# Paths exempt from auth + rate limiting (health/docs don't touch data).
_PUBLIC_PATHS = {"/health", "/openapi.json"}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Standard hardening headers on every response (Phase I)."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), browsing-topics=()"
        )
        return response


class ApiTokenMiddleware(BaseHTTPMiddleware):
    """Bearer-token gate for the API (Phase I).

    Enabled only when API_TOKENS is configured; dev runs with auth off.
    Only HTTP requests pass through here; the voice WebSocket performs its
    own token check (query param) in app.api.v1.voice.
    """

    def __init__(
        self,
        app: Any,
        *,
        tokens: list[str],
        api_prefix: str,
        public_paths: set[str] = _PUBLIC_PATHS,
    ) -> None:
        super().__init__(app)
        self._tokens = frozenset(tokens)
        self._api_prefix = api_prefix
        self._public = public_paths

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if not self._tokens:
            return await call_next(request)
        path = request.url.path
        if not path.startswith(self._api_prefix) or self._is_public(path):
            return await call_next(request)
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer ") and auth[7:].strip() in self._tokens:
            return await call_next(request)
        return JSONResponse(
            status_code=401,
            content={
                "code": "unauthorized",
                "message": "missing or invalid API token",
                "request_id": request_id_var.get(),
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    def _is_public(self, path: str) -> bool:
        return any(path == f"{self._api_prefix}{p}" for p in self._public)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Deterministic in-memory fixed-window per-IP rate limit (Phase I).

    Non-configurable at runtime (single process dev target): rpm=0 disables.
    Window is 60s; each IP has its own bucket. Old buckets are pruned on
    access to bound memory.
    """

    WINDOW_SECONDS = 60

    def __init__(
        self,
        app: Any,
        *,
        rpm: int,
        api_prefix: str,
        public_paths: set[str] = _PUBLIC_PATHS,
    ) -> None:
        super().__init__(app)
        self._rpm = rpm
        self._api_prefix = api_prefix
        self._public = public_paths
        self._buckets: dict[str, tuple[float, int]] = {}  # ip -> (window_start, count)
        self._lock = asyncio.Lock()

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if self._rpm <= 0:
            return await call_next(request)
        path = request.url.path
        if not path.startswith(self._api_prefix) or self._is_public(path):
            return await call_next(request)
        ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        async with self._lock:
            window_start, count = self._buckets.get(ip, (0, 0))
            if now - window_start >= self.WINDOW_SECONDS:
                window_start, count = now, 0
            if count >= self._rpm:
                return JSONResponse(
                    status_code=429,
                    content={
                        "code": "rate_limited",
                        "message": "too many requests; slow down",
                        "request_id": request_id_var.get(),
                    },
                    headers={"Retry-After": str(self.WINDOW_SECONDS)},
                )
            self._buckets[ip] = (window_start, count + 1)
        return await call_next(request)

    def _is_public(self, path: str) -> bool:
        return any(path == f"{self._api_prefix}{p}" for p in self._public)
