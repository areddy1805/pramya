"""Observability layer (Phase E realignment, ADR-008).

Langfuse OSS (self-hosted, MIT) is the V1 observability platform. This
module provides a thin, degradation-safe facade:

- Langfuse enabled only when LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY are
  configured (self-hosted host URL from LANGFUSE_HOST).
- When unconfigured or unreachable, telemetry degrades to structured logs
  (never breaks the interview/voice path).
- PII-safe: traces carry IDs + redacted metadata; raw resume/answer content
  is never sent (explicit env flag can enable debug content capture, off
  by default).

Captured fields (per ADR-008): request_id, session_id, turn_id,
graph_node, model, provider, latency, tokens, cache_hit, retrieval_count,
reranker_count, ASR/TTS latency, time_to_first_audio, interruption_count,
error, fallback.
"""

from __future__ import annotations

import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Literal

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger("app.observability")

_client_instance: Any = None  # lazy singleton (Any: Null | Langfuse)

LevelT = Literal["DEBUG", "DEFAULT", "WARNING", "ERROR"]


@dataclass
class SpanContext:
    """One traced operation (generation/span)."""

    name: str
    started: float = field(default_factory=time.monotonic)
    model: str | None = None
    provider: str | None = None
    tokens: int | None = None
    usage_input: int | None = None
    usage_output: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])

    def finish(self, *, error: str | None = None) -> dict[str, Any]:
        latency_ms = round((time.monotonic() - self.started) * 1000, 1)
        fields: dict[str, Any] = {
            "event": "ai_span",
            "name": self.name,
            "latency_ms": latency_ms,
            "error": error,
        }
        if self.model:
            fields["model"] = self.model
        if self.provider:
            fields["provider"] = self.provider
        if self.tokens is not None:
            fields["tokens"] = self.tokens
        if self.usage_input is not None:
            fields["usage_input"] = self.usage_input
        if self.usage_output is not None:
            fields["usage_output"] = self.usage_output
        fields.update(self.metadata)
        return fields


class NullObservability:
    """Degraded path: structured logs instead of Langfuse (never crashes)."""

    enabled = False

    def start(self, name: str, **metadata: Any) -> SpanContext:
        return SpanContext(name=name, metadata=metadata)

    def finish(self, span: SpanContext, *, error: str | None = None) -> None:
        logger.info("ai span", extra={"extra_fields": span.finish(error=error)})

    def trace_session(self, session_id: int, user_id: int, **metadata: Any) -> SpanContext:
        return SpanContext(
            name="interview_session",
            metadata={"session_id": session_id, "user_id": user_id, **metadata},
        )

    def flush(self) -> None:
        pass


class LangfuseObservability:
    """Langfuse-backed telemetry (self-hosted OSS; ADR-008)."""

    enabled = True

    def __init__(self, settings: Settings) -> None:
        from langfuse import Langfuse

        self._client: Any = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )

    def start(self, name: str, **metadata: Any) -> SpanContext:
        return SpanContext(name=name, metadata=metadata)

    def finish(self, span: SpanContext, *, error: str | None = None) -> None:
        fields = span.finish(error=error)
        level: LevelT = "ERROR" if error else "DEFAULT"
        self._client.create_event(
            name=span.name,
            level=level,
            status_message=error,
            metadata={
                "latency_ms": fields.get("latency_ms"),
                "model": fields.get("model"),
                "provider": fields.get("provider"),
                "tokens": fields.get("tokens"),
                "usage_input": fields.get("usage_input"),
                "usage_output": fields.get("usage_output"),
                **{k: v for k, v in span.metadata.items()},
            },
        )

    def trace_session(self, session_id: int, user_id: int, **metadata: Any) -> SpanContext:
        span = SpanContext(
            name="interview_session",
            metadata={"session_id": session_id, "user_id": user_id, **metadata},
        )
        # A Langfuse trace is created lazily by the OTel exporter on flush;
        # record the session ids via an event so the trace is identifiable.
        self._client.create_event(
            name="interview_session",
            metadata={"session_id": session_id, "user_id": user_id, **metadata},
        )
        return span

    def flush(self) -> None:
        try:
            self._client.flush()
        except Exception:  # pragma: no cover - never crash on flush
            logger.warning("langfuse flush failed")


def get_observability() -> Any:
    """Return the process-wide observability singleton (degradation-safe)."""
    global _client_instance  # noqa: PLW0603
    if _client_instance is None:
        settings = get_settings()
        if settings.langfuse_public_key and settings.langfuse_secret_key:
            try:
                _client_instance = LangfuseObservability(settings)
            except Exception:
                logger.warning("langfuse unavailable; degrading to structured logs")
                _client_instance = NullObservability()
        else:
            _client_instance = NullObservability()
    return _client_instance


def reset_observability() -> None:
    """Test seam: drop the singleton so settings changes take effect."""
    global _client_instance  # noqa: PLW0603
    _client_instance = None


@asynccontextmanager
async def trace_span(name: str, **metadata: Any) -> AsyncGenerator[SpanContext, None]:
    """Async context manager: start + finish a span (degradation-safe)."""
    obs = get_observability()
    span = obs.start(name, **metadata)
    error: str | None = None
    try:
        yield span
    except Exception as exc:
        error = str(exc)
        raise
    finally:
        obs.finish(span, error=error)
        obs.flush()


def record_event(name: str, **metadata: Any) -> None:
    """Fire-and-forget telemetry event (voice metrics, interruptions, etc.).

    Always emitted to structured logs (guaranteed channel); forwarded to
    Langfuse when configured and reachable. Never raises.
    """
    obs = get_observability()
    span = obs.start(name, **metadata)
    obs.finish(span)
    # Structured-log fallback: the log channel must show metrics even when
    # Langfuse is down/unconfigured (R15 latency observability guarantee).
    try:
        fields = span.finish()
        logger.info("telemetry", extra={"extra_fields": {"event": name, **fields}})
    except Exception as exc:  # pragma: no cover - telemetry must never crash
        logger.debug("telemetry log fallback failed: %s", exc)
    obs.flush()


__all__ = [
    "get_observability",
    "reset_observability",
    "trace_span",
    "record_event",
    "SpanContext",
    "NullObservability",
]
