"""Contract tests: OpenAPI surface + error envelope shape (no DB)."""

from __future__ import annotations

import httpx
import pytest

from app.core.db import get_session
from app.domain.errors import NotFoundError
from app.main import create_app


@pytest.fixture
def openapi() -> dict:
    app = create_app()
    return app.openapi()


def _resolve(ref: dict, spec: dict) -> dict:
    """Resolve a one-hop JSON pointer ref."""
    path = ref["$ref"].lstrip("#/").split("/")
    node: dict = spec
    for part in path:
        node = node[part]
    return node


def test_openapi_paths_contract(openapi: dict) -> None:
    paths = set(openapi["paths"])
    required = {
        "/api/v1/health",
        "/api/v1/candidates/{user_id}",
        "/api/v1/documents",
        "/api/v1/documents/{document_id}",
        "/api/v1/candidates/{user_id}/evidence",
        "/api/v1/candidates/{user_id}/evidence/{evidence_id}",
    }
    assert required <= paths, required - paths


def test_documents_upload_contract(openapi: dict) -> None:
    post = openapi["paths"]["/api/v1/documents"]["post"]
    body = _resolve(post["requestBody"]["content"]["multipart/form-data"]["schema"], openapi)
    props = body["properties"]
    assert "user_id" in props and "kind" in props and "file" in props
    assert post["responses"]["201"]


def test_evidence_patch_contract(openapi: dict) -> None:
    patch = openapi["paths"]["/api/v1/candidates/{user_id}/evidence/{evidence_id}"]["patch"]
    body = _resolve(patch["requestBody"]["content"]["application/json"]["schema"], openapi)
    assert "status" in body["properties"] and "strength" in body["properties"]
    assert patch["responses"]["200"]


async def test_error_envelope_shape() -> None:
    app = create_app()

    # Envelope shape is an HTTP/exception-handler contract, not a persistence
    # concern: raise the same NotFoundError the route would raise after a DB
    # lookup, without opening PostgreSQL. The real ASGI app, middleware, and
    # pramya_error_handler are preserved via FastAPI's dependency-override seam.
    async def _candidate_not_found() -> None:
        raise NotFoundError("candidate profile not found")

    app.dependency_overrides[get_session] = _candidate_not_found
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as c:
            resp = await c.get("/api/v1/candidates/999999")
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == "not_found"
    assert "request_id" in body
    assert isinstance(body["details"], dict)


async def test_validation_error_envelope() -> None:
    app = create_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        resp = await c.patch(
            "/api/v1/candidates/1/evidence/1",
            json={"strength": 5.0},  # out of [0,1]
        )
    assert resp.status_code == 422
    assert resp.json()["code"] == "validation_failed"
