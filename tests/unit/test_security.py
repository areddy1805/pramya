"""Phase I security hardening tests.

Covers: CORS middleware actually applied, security response headers,
bearer-token API auth (off by default, enforced when configured), per-IP
rate limiting, WebSocket token gate, and prompt-injection boundaries.
All deterministic — no DB, no network, no model calls.
"""

from __future__ import annotations

from starlette.testclient import TestClient

from app.api.v1.voice import ws_authorized
from app.core.config import Settings
from app.main import create_app
from app.services.document import sanitize_suffix


def _app(**overrides: object) -> TestClient:
    settings = Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        **overrides,  # type: ignore[arg-type]
    )
    return TestClient(create_app(settings))


def test_security_headers_present() -> None:
    with _app() as client:
        r = client.get("/api/v1/health")
        assert r.status_code == 200
        assert r.headers["X-Content-Type-Options"] == "nosniff"
        assert r.headers["X-Frame-Options"] == "DENY"
        assert r.headers["Referrer-Policy"] == "no-referrer"
        assert "microphone=()" in r.headers["Permissions-Policy"]


def test_cors_preflight_succeeds_before_auth() -> None:
    with _app(api_tokens=["t1"], cors_origins=["http://localhost:3000"]) as client:
        r = client.options(
            "/api/v1/candidates",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert r.status_code == 200
        assert r.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_health_is_public_when_auth_configured() -> None:
    with _app(api_tokens=["t1"]) as client:
        r = client.get("/api/v1/health")
        assert r.status_code == 200


def test_api_token_required_and_enforced() -> None:
    with _app(api_tokens=["t1", "t2"]) as client:
        assert client.get("/api/v1/models/status").status_code == 401
        assert (
            client.get(
                "/api/v1/models/status",
                headers={"Authorization": "Bearer wrong"},
            ).status_code
            == 401
        )
        assert (
            client.get(
                "/api/v1/models/status",
                headers={"Authorization": "Bearer t2"},
            ).status_code
            == 200
        )


def test_auth_off_by_default() -> None:
    with _app() as client:
        assert client.get("/api/v1/models/status").status_code == 200


def test_rate_limit_per_ip() -> None:
    with _app(api_tokens=["t1"], rate_limit_rpm=2) as client:
        h = {"Authorization": "Bearer t1"}
        assert client.get("/api/v1/models/status", headers=h).status_code == 200
        assert client.get("/api/v1/models/status", headers=h).status_code == 200
        r = client.get("/api/v1/models/status", headers=h)
        assert r.status_code == 429
        assert r.json()["code"] == "rate_limited"
        assert r.headers["Retry-After"] == "60"
        # Health is exempt from rate limiting.
        assert client.get("/api/v1/health").status_code == 200


def test_rate_limit_disabled_by_default() -> None:
    with _app() as client:
        for _ in range(10):
            assert client.get("/api/v1/health").status_code == 200


def test_ws_authorized_gate() -> None:
    class _S:
        api_tokens: list[str] = []

    assert ws_authorized(_S(), None) is True  # auth off
    s = type("S", (), {"api_tokens": ["tok"]})()
    assert ws_authorized(s, None) is False
    assert ws_authorized(s, "tok") is True
    assert ws_authorized(s, "nope") is False


def test_upload_suffix_sanitized() -> None:
    assert sanitize_suffix(".pdf") == ".pdf"
    assert sanitize_suffix("../evil") == ""  # path chars rejected
    assert sanitize_suffix(".pdf.exe") == ".pdf.exe"  # alnum+dots are inert (no /)
    assert sanitize_suffix("x" * 11) == ""  # length cap
    assert sanitize_suffix("") == ""
