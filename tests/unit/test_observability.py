"""Observability tests (Phase E, ADR-008).

- Degradation: without Langfuse keys the facade falls back to structured
  logs and never raises (interview/voice paths stay safe).
- Span capture: latency/model/provider/tokens/metadata recorded.
- PII rule: the facade never forces raw candidate content into spans
  (only IDs + explicit metadata the caller chooses).
"""

from __future__ import annotations

from app.core.config import get_settings
from app.observability import (
    NullObservability,
    SpanContext,
    get_observability,
    reset_observability,
    trace_span,
)


def _force_unconfigured(monkeypatch: object) -> None:
    """Isolate from ambient .env: the degradation tests assert the DISABLED
    path regardless of what the developer's .env currently sets. The flag
    LANGFUSE_ENABLED=false is authoritative even when keys exist."""
    import app.observability as obs_module
    from app.core import config

    monkeypatch.setattr(obs_module, "get_settings", lambda: get_settings())
    config.get_settings.cache_clear()
    settings = get_settings()
    settings.langfuse_enabled = False
    settings.langfuse_public_key = ""
    settings.langfuse_secret_key = ""
    settings.langfuse_host = "http://127.0.0.1:3030"
    monkeypatch.setattr(obs_module, "get_settings", lambda: settings)
    reset_observability()


async def test_default_degrades_to_null_when_unconfigured(monkeypatch: object) -> None:
    _force_unconfigured(monkeypatch)
    obs = get_observability()
    assert isinstance(obs, NullObservability)
    assert obs.enabled is False
    # The facade never crashes the caller path.
    span = obs.start("test", session_id=1)
    obs.finish(span)
    obs.flush()


async def test_null_observability_span_context_measures_latency() -> None:
    obs = NullObservability()
    span = obs.start(
        "question_generation",
        session_id=1,
        competency="System Design",
        task="interview_content_generation",
    )
    span.model = "deepseek-v4-flash"
    span.provider = "deepseek"
    span.tokens = 42
    fields = span.finish()
    assert fields["event"] == "ai_span"
    assert fields["name"] == "question_generation"
    assert fields["latency_ms"] >= 0
    assert fields["model"] == "deepseek-v4-flash"
    assert fields["provider"] == "deepseek"
    assert fields["tokens"] == 42
    assert fields["session_id"] == 1
    assert fields["competency"] == "System Design"


async def test_trace_span_context_manager_records_error(monkeypatch: object) -> None:
    _force_unconfigured(monkeypatch)
    try:
        async with trace_span("eval", session_id=7):
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    # No exception propagated beyond the intended one; facade stays alive.
    obs = get_observability()
    assert isinstance(obs, NullObservability)


def test_span_context_no_pii_by_default() -> None:
    """PII-safe: only caller-chosen metadata is captured."""
    span = SpanContext(name="retrieval", metadata={"session_id": 5, "query_len": 12})
    fields = span.finish()
    assert "session_id" in fields
    assert "query_len" in fields
    # No raw content key is ever injected by the facade itself.
    assert "content" not in fields
    assert "answer" not in fields
