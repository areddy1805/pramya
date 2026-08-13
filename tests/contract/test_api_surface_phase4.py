"""Contract tests: models/runtime status surface (Phase 4.5)."""

from __future__ import annotations

import pytest

from app.main import create_app


@pytest.fixture
def openapi() -> dict:
    return create_app().openapi()


def _resolve(ref: dict, spec: dict) -> dict:
    path = ref["$ref"].lstrip("#/").split("/")
    node: dict = spec
    for part in path:
        node = node[part]
    return node


def test_models_status_endpoint_contract(openapi: dict) -> None:
    assert "/api/v1/models/status" in openapi["paths"]
    op = openapi["paths"]["/api/v1/models/status"]["get"]
    assert op["operationId"] == "models_status_models_status_get" or "200" in op["responses"]
    schema_ref = op["responses"]["200"]["content"]["application/json"]["schema"]
    schema = _resolve(schema_ref, openapi)
    props = schema["properties"]
    assert "providers" in props
    assert "models" in props
    assert "policies" in props
    assert "local_ai_enabled" in props


def test_interview_endpoints_contract(openapi: dict) -> None:
    paths = openapi["paths"]
    for expected in (
        "/api/v1/interviews",
        "/api/v1/interviews/{interview_id}/answers",
        "/api/v1/interviews/{interview_id}/questions",
        "/api/v1/interviews/{interview_id}/hint",
        "/api/v1/interviews/{interview_id}/pause",
        "/api/v1/interviews/{interview_id}/resume",
        "/api/v1/interviews/{interview_id}/stop",
        "/api/v1/interviews/{interview_id}/cancel",
        "/api/v1/interviews/{interview_id}/report",
        "/api/v1/interviews/{interview_id}/events",
        "/api/v1/roles/analyze",
        "/api/v1/documents/{document_id}/index",
    ):
        assert expected in paths, f"missing path {expected}"


def test_interview_answer_request_schema(openapi: dict) -> None:
    path = "/api/v1/interviews/{interview_id}/answers"
    op = openapi["paths"][path]["post"]
    body = op["requestBody"]["content"]["application/json"]["schema"]
    schema = _resolve(body, openapi)
    props = schema["properties"]
    assert "question_id" in props
    assert "answer_text" in props
    assert "idempotency_key" in props


def test_roles_analyze_request_schema(openapi: dict) -> None:
    path = "/api/v1/roles/analyze"
    op = openapi["paths"][path]["post"]
    body = op["requestBody"]["content"]["application/json"]["schema"]
    schema = _resolve(body, openapi)
    assert "jd_text" in schema["properties"]
    assert "user_id" in schema["properties"]
