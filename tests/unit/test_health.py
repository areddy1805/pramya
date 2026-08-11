"""Unit tests: health endpoint + request-id middleware."""

import httpx
import pytest

from app.main import create_app


@pytest.fixture
def client() -> httpx.AsyncClient:
    app = create_app()
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_health_ok(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["app"] == "pramya"


async def test_health_has_request_id(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/health")
    assert resp.headers.get("X-Request-ID")


async def test_request_id_forwarded(client: httpx.AsyncClient) -> None:
    rid = "abc123"
    resp = await client.get("/api/v1/health", headers={"X-Request-ID": rid})
    assert resp.headers.get("X-Request-ID") == rid


async def test_openapi_served() -> None:
    app = create_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        resp = await c.get("/api/v1/openapi.json")
    assert resp.status_code == 200
    assert resp.json()["info"]["version"] == "0.1.0"
