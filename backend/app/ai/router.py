"""InferenceRouter — task → policy → provider → model (ADR-004, AI_ARCHITECTURE §2).

Application code depends only on this router and the provider contracts.
Every routing decision is observable: task, provider, model, reason,
thinking, degraded flag, latency, tokens.

Deterministic policy: TaskPolicyTable maps a task class to a model; the
router resolves the model's provider, checks the provider implements the
required capability, executes, and on connection failure walks the explicit
fallback chain from the policy. There are no hidden provider calls.

Escalation-only semantics: deepseek-v4-flash is reached only when the task
policy names it (or as a fallback for 4B tasks) — never as a default.
"""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, cast

from app.ai.contracts import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatStreamChunk,
    EmbeddingProvider,
    EmbedRequest,
    EmbedResponse,
    RerankingProvider,
    RerankRequest,
    RerankResponse,
    TextGenerationProvider,
)
from app.ai.errors import AIError, ProviderConfigurationError, ProviderConnectionError
from app.ai.policy import ModelId, ProviderKind, TaskClass, TaskPolicyTable
from app.core.logging import get_logger


@dataclass(frozen=True)
class RouterDecision:
    """Observable routing decision (telemetry/log payload)."""

    task: TaskClass
    provider: str
    model: str
    reason: str
    thinking: bool | None
    degraded: bool = False
    fallback_of: str | None = None


@dataclass(frozen=True)
class RouterResult:
    """A completed generation with its decision."""

    decision: RouterDecision
    response: ChatResponse


class InferenceRouter:
    """Routes tasks to providers per the task policy table."""

    def __init__(
        self,
        *,
        policy: TaskPolicyTable,
        omlx: TextGenerationProvider | EmbeddingProvider | RerankingProvider | None = None,
        deepseek: TextGenerationProvider | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._policy = policy
        self._omlx = omlx
        self._deepseek = deepseek
        self._logger = logger or get_logger("app.ai.router")

    # -- text generation ----------------------------------------------------

    async def generate(
        self,
        task: TaskClass,
        messages: list[ChatMessage],
        *,
        json_mode: bool = False,
        thinking: bool | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> RouterResult:
        task_policy = self._policy.for_task(task)
        chain = (task_policy.model, *task_policy.fallback_models)
        attempts: list[dict[str, object]] = []

        for model in chain:
            spec = self._policy.model_spec(model)
            if spec.capability != "generate":
                raise ProviderConfigurationError(
                    f"task {task.value} routes to non-generation model {model.value}"
                )
            provider = self._text_provider(spec.provider)
            if provider is None:
                attempts.append({"model": model.value, "status": "not_configured"})
                continue

            request = ChatRequest(
                messages=messages,
                json_mode=json_mode,
                thinking=thinking if thinking is not None else spec.thinking,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            try:
                started = time.monotonic()
                response = await provider.generate(request)
            except ProviderConnectionError:
                attempts.append({"model": model.value, "status": "unavailable"})
                continue
            except AIError:
                raise  # auth/request errors are not fallback-eligible

            latency_ms = (time.monotonic() - started) * 1000
            degraded = model != task_policy.model
            decision = RouterDecision(
                task=task,
                provider=spec.provider.value,
                model=model.value,
                reason=self._reason(task_policy.model, model, degraded),
                thinking=request.thinking,
                degraded=degraded,
                fallback_of=task_policy.model.value if degraded else None,
            )
            self._log_decision(
                level="warning" if degraded else "info",
                decision=decision,
                latency_ms=latency_ms,
                tokens=response.usage.total_tokens,
            )
            return RouterResult(decision=decision, response=response)

        raise ProviderConnectionError(
            f"no available provider for task {task.value}",
            details={
                "task": task.value,
                "primary": task_policy.model.value,
                "fallbacks": [m.value for m in task_policy.fallback_models],
                "attempts": attempts,
            },
        )

    # -- streaming text generation (V1.1) -----------------------------------

    async def stream(
        self,
        task: TaskClass,
        messages: list[ChatMessage],
        *,
        json_mode: bool = False,
        thinking: bool | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[tuple[RouterDecision | None, str]]:
        """Stream a generation; yields (decision, text_delta) per chunk.

        Same policy resolution as ``generate()``. Providers without a real
        stream implementation fall back to a single-chunk yield of the full
        content (so fakes/legacy providers keep working). The first yield
        carries the decision; later yields carry decision=None.
        """
        task_policy = self._policy.for_task(task)
        chain = (task_policy.model, *task_policy.fallback_models)
        attempts: list[dict[str, object]] = []

        for model in chain:
            spec = self._policy.model_spec(model)
            if spec.capability != "generate":
                raise ProviderConfigurationError(
                    f"task {task.value} routes to non-generation model {model.value}"
                )
            provider = self._text_provider(spec.provider)
            if provider is None:
                attempts.append({"model": model.value, "status": "not_configured"})
                continue
            request = ChatRequest(
                messages=messages,
                json_mode=json_mode,
                thinking=thinking if thinking is not None else spec.thinking,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            try:
                started = time.monotonic()
                full = ""
                decision: RouterDecision | None = None
                streamer = getattr(provider, "stream", None)
                if not callable(streamer) or not await _supports_stream(provider):
                    # Fallback: non-streaming provider -> single chunk.
                    response = await provider.generate(request)
                    full = response.content
                    latency_ms = (time.monotonic() - started) * 1000
                    decision = self._decision(
                        task, task_policy, spec, model, request, latency_ms, full
                    )
                    yield decision, full
                    return
                async for chunk in cast("AsyncIterator[ChatStreamChunk]", streamer(request)):
                    delta = chunk.delta if hasattr(chunk, "delta") else str(chunk)
                    full += delta
                    if decision is None:
                        latency_ms = (time.monotonic() - started) * 1000
                        decision = self._decision(
                            task, task_policy, spec, model, request, latency_ms, full
                        )
                        yield decision, delta
                    else:
                        yield None, delta
                if decision is None:
                    decision = self._decision(task, task_policy, spec, model, request, 0.0, full)
                    yield decision, ""
                return
            except ProviderConnectionError:
                attempts.append({"model": model.value, "status": "unavailable"})
                continue
            except AIError:
                raise  # auth/request errors are not fallback-eligible

        raise ProviderConnectionError(
            f"no available provider for task {task.value}",
            details={
                "task": task.value,
                "primary": task_policy.model.value,
                "fallbacks": [m.value for m in task_policy.fallback_models],
                "attempts": attempts,
            },
        )

    def _decision(
        self,
        task: TaskClass,
        task_policy: Any,
        spec: Any,
        model: ModelId,
        request: ChatRequest,
        latency_ms: float,
        full_text: str,
    ) -> RouterDecision:
        degraded = model != task_policy.model
        decision = RouterDecision(
            task=task,
            provider=spec.provider.value,
            model=model.value,
            reason=self._reason(task_policy.model, model, degraded),
            thinking=request.thinking,
            degraded=degraded,
            fallback_of=task_policy.model.value if degraded else None,
        )
        self._log_decision(
            level="warning" if degraded else "info",
            decision=decision,
            latency_ms=latency_ms,
            tokens=len(full_text),
        )
        return decision

    # -- embeddings ---------------------------------------------------------

    async def embed(self, texts: list[str]) -> EmbedResponse:
        task_policy = self._policy.for_task(TaskClass.EMBEDDING)
        spec = self._policy.model_spec(task_policy.model)
        provider = self._omlx if isinstance(self._omlx, EmbeddingProvider) else None
        if provider is None:
            raise ProviderConfigurationError("embedding provider not configured (need oMLX)")
        request = EmbedRequest(texts=texts, model=spec.id)
        started = time.monotonic()
        response = await provider.embed(request)
        latency_ms = (time.monotonic() - started) * 1000
        self._log_decision(
            level="info",
            decision=RouterDecision(
                task=TaskClass.EMBEDDING,
                provider=spec.provider.value,
                model=spec.id,
                reason=f"task-class policy: {TaskClass.EMBEDDING.value} -> {spec.id}",
                thinking=None,
            ),
            latency_ms=latency_ms,
            tokens=len(texts),
        )
        return response

    # -- reranking ----------------------------------------------------------

    async def rerank(
        self, query: str, documents: list[str], *, top_n: int | None = None
    ) -> RerankResponse:
        task_policy = self._policy.for_task(TaskClass.RERANKING)
        spec = self._policy.model_spec(task_policy.model)
        provider = self._omlx if isinstance(self._omlx, RerankingProvider) else None
        if provider is None:
            raise ProviderConfigurationError("reranking provider not configured (need oMLX)")
        request = RerankRequest(query=query, documents=documents, top_n=top_n)
        started = time.monotonic()
        response = await provider.rerank(request)
        latency_ms = (time.monotonic() - started) * 1000
        self._log_decision(
            level="info",
            decision=RouterDecision(
                task=TaskClass.RERANKING,
                provider=spec.provider.value,
                model=spec.id,
                reason=f"task-class policy: {TaskClass.RERANKING.value} -> {spec.id}",
                thinking=None,
            ),
            latency_ms=latency_ms,
            tokens=len(documents),
        )
        return response

    # -- internals ----------------------------------------------------------

    def _text_provider(self, kind: ProviderKind) -> TextGenerationProvider | None:
        candidate = self._omlx if kind == ProviderKind.OMLX else self._deepseek
        return candidate if isinstance(candidate, TextGenerationProvider) else None

    @staticmethod
    def _reason(primary: ModelId, chosen: ModelId, degraded: bool) -> str:
        if degraded:
            return f"fallback: {primary.value} unavailable -> {chosen.value}"
        return f"task-class policy: primary {primary.value}"

    def _log_decision(
        self,
        *,
        level: str,
        decision: RouterDecision,
        latency_ms: float,
        tokens: int,
    ) -> None:
        fields = {
            "event": "routing_decision",
            "task": decision.task.value,
            "provider": decision.provider,
            "model": decision.model,
            "reason": decision.reason,
            "thinking": decision.thinking,
            "degraded": decision.degraded,
            "fallback_of": decision.fallback_of,
            "latency_ms": round(latency_ms, 1),
            "tokens": tokens,
        }
        log = getattr(self._logger, level, self._logger.info)
        log("routing decision", extra={"extra_fields": fields})


async def _supports_stream(provider: object) -> bool:
    """True when the provider advertises real streaming."""
    supports: Any = getattr(provider, "supports_stream", None)
    if not callable(supports):
        return True  # has stream attr and no explicit opt-out
    try:
        result = await cast("Any", supports)()
        return bool(result)
    except Exception:  # pragma: no cover - defensive
        logging.getLogger("app.ai.router").debug("stream support probe failed", exc_info=True)
        return True
