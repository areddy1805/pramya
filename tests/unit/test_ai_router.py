"""Router tests: deterministic policy selection, capability dispatch, no-fallback.

Uses fake providers (no network) to verify routing behavior and observable
decisions. ADR-023: every text task routes to deepseek-v4-flash with NO
fallback chain — a DeepSeek connection failure surfaces as a controlled
ProviderConnectionError (never a silent local text model). Auth/request
errors propagate without any retry.
"""

from __future__ import annotations

import pytest

from app.ai.contracts import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    EmbedRequest,
    EmbedResponse,
    RerankRequest,
    RerankResponse,
    Usage,
)
from app.ai.errors import (
    ProviderAuthError,
    ProviderConfigurationError,
    ProviderConnectionError,
)
from app.ai.policy import TaskClass, TaskPolicyTable
from app.ai.router import InferenceRouter, RouterResult


class FakeProvider:
    """Implements all capabilities; records calls; can fail generate."""

    name = "fake"

    def __init__(self, *, fail_generate: Exception | None = None) -> None:
        self.generate_calls: list[ChatRequest] = []
        self.embed_calls: list[EmbedRequest] = []
        self.rerank_calls: list[RerankRequest] = []
        self.fail_generate = fail_generate

    async def generate(self, request: ChatRequest) -> ChatResponse:
        self.generate_calls.append(request)
        if self.fail_generate is not None:
            raise self.fail_generate
        return ChatResponse(content="ok", model=self.name, usage=Usage(total_tokens=7))

    async def embed(self, request: EmbedRequest) -> EmbedResponse:
        self.embed_calls.append(request)
        return EmbedResponse(embeddings=[[0.1, 0.2]], model=self.name, dimension=2)

    async def rerank(self, request: RerankRequest) -> RerankResponse:
        self.rerank_calls.append(request)
        return RerankResponse(results=[], model=self.name)


def _router(
    omlx: FakeProvider | None = None, deepseek: FakeProvider | None = None
) -> InferenceRouter:
    return InferenceRouter(
        policy=TaskPolicyTable(),
        omlx=omlx,
        deepseek=deepseek,
    )


MSG = [ChatMessage(role="user", content="hello")]


async def test_routine_task_routes_to_deepseek() -> None:
    deepseek = FakeProvider()
    omlx = FakeProvider()
    router = _router(omlx, deepseek)

    result: RouterResult = await router.generate(TaskClass.ROUTINE_GENERATION, MSG)

    assert result.decision.provider == "deepseek"
    assert result.decision.model == "deepseek-v4-flash"
    assert result.decision.thinking is False  # cheap + fast by default (ADR-023)
    assert result.decision.degraded is False
    assert len(omlx.generate_calls) == 0  # local text model never called


async def test_all_text_tasks_route_to_deepseek() -> None:
    deepseek = FakeProvider()
    router = _router(deepseek=deepseek)
    for task in (
        TaskClass.EXTRACTION,
        TaskClass.CLASSIFICATION,
        TaskClass.METADATA,
        TaskClass.STRUCTURED_GENERATION,
        TaskClass.SEMANTIC_TASK,
        TaskClass.INTERVIEW_CONTENT_GENERATION,
        TaskClass.ORDINARY_EVALUATION,
        TaskClass.ANALYSIS,
        TaskClass.DEEP_EVALUATION,
        TaskClass.COMPLEX_REASONING,
        TaskClass.ADAPTIVE_REASONING,
        TaskClass.SYSTEM_DESIGN,
        TaskClass.FINAL_SYNTHESIS,
        TaskClass.DIFFICULT_FOLLOWUP,
    ):
        result = await router.generate(task, MSG)
        assert result.decision.model == "deepseek-v4-flash", task
        assert result.decision.degraded is False, task


async def test_deepseek_down_raises_controlled_error_no_local_fallback() -> None:
    # ADR-023: no silent fallback to a local text model. A connection
    # failure must surface as a controlled ProviderConnectionError.
    deepseek = FakeProvider(fail_generate=ProviderConnectionError("deepseek down"))
    omlx = FakeProvider()
    router = _router(omlx, deepseek)

    with pytest.raises(ProviderConnectionError) as excinfo:
        await router.generate(TaskClass.ROUTINE_GENERATION, MSG)

    details = excinfo.value.details or {}
    assert details.get("primary") == "deepseek-v4-flash"
    assert details.get("fallbacks") == []  # no fallback chain
    assert len(omlx.generate_calls) == 0  # local model never touched


async def test_deepseek_unconfigured_is_explicit() -> None:
    router = _router(deepseek=None)

    with pytest.raises(ProviderConnectionError) as excinfo:
        await router.generate(TaskClass.ROUTINE_GENERATION, MSG)

    details = excinfo.value.details or {}
    assert details.get("attempts", [{}])[0].get("status") == "not_configured"


async def test_auth_error_propagates_without_fallback() -> None:
    deepseek = FakeProvider(fail_generate=ProviderAuthError("bad key"))
    router = _router(deepseek=deepseek)

    with pytest.raises(ProviderAuthError):
        await router.generate(TaskClass.ROUTINE_GENERATION, MSG)


async def test_explicit_thinking_override() -> None:
    deepseek = FakeProvider()
    router = _router(deepseek=deepseek)

    result = await router.generate(TaskClass.DEEP_EVALUATION, MSG, thinking=True)

    assert result.decision.thinking is True


async def test_embedding_routes_to_omlx() -> None:
    omlx = FakeProvider()
    router = _router(omlx=omlx)

    response = await router.embed(["text"])

    assert response.model == "fake"
    assert len(omlx.embed_calls) == 1


async def test_embedding_unconfigured_is_explicit() -> None:
    router = _router(omlx=None)

    with pytest.raises(ProviderConfigurationError):
        await router.embed(["text"])


async def test_rerank_routes_to_omlx() -> None:
    omlx = FakeProvider()
    router = _router(omlx=omlx)

    await router.rerank("q", ["d"])

    assert len(omlx.rerank_calls) == 1
