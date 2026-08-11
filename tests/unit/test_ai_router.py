"""Router tests: deterministic policy selection, capability dispatch, fallbacks.

Uses fake providers (no network) to verify routing behavior and observable
decisions. Fallback semantics: connection failures walk the explicit policy
chain; auth/request errors propagate without fallback.
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


async def test_routine_task_routes_to_omlx_pramya_4b() -> None:
    omlx = FakeProvider()
    deepseek = FakeProvider()
    router = _router(omlx, deepseek)

    result: RouterResult = await router.generate(TaskClass.ROUTINE_GENERATION, MSG)

    assert result.decision.provider == "omlx"
    assert result.decision.model == "pramya-4b"
    assert result.decision.thinking is False  # thinking off for pramya-4b
    assert result.decision.degraded is False
    assert len(deepseek.generate_calls) == 0  # escalation never default


async def test_deep_evaluation_routes_to_deepseek() -> None:
    omlx = FakeProvider()
    deepseek = FakeProvider()
    router = _router(omlx, deepseek)

    result = await router.generate(TaskClass.DEEP_EVALUATION, MSG)

    assert result.decision.provider == "deepseek"
    assert result.decision.model == "deepseek-v4-flash"
    assert result.decision.thinking is True
    assert len(omlx.generate_calls) == 0


async def test_omlx_down_falls_back_to_deepseek_for_routine_task() -> None:
    omlx = FakeProvider(fail_generate=ProviderConnectionError("omlx down"))
    deepseek = FakeProvider()
    router = _router(omlx, deepseek)

    result = await router.generate(TaskClass.ROUTINE_GENERATION, MSG)

    assert result.decision.provider == "deepseek"
    assert result.decision.model == "deepseek-v4-flash"
    assert result.decision.degraded is True
    assert result.decision.fallback_of == "pramya-4b"
    assert result.decision.reason == "fallback: pramya-4b unavailable -> deepseek-v4-flash"


async def test_deepseek_down_falls_back_to_omlx_for_escalation_task() -> None:
    omlx = FakeProvider()
    deepseek = FakeProvider(fail_generate=ProviderConnectionError("deepseek down"))
    router = _router(omlx, deepseek)

    result = await router.generate(TaskClass.DEEP_EVALUATION, MSG)

    assert result.decision.provider == "omlx"
    assert result.decision.model == "pramya-4b"
    assert result.decision.degraded is True
    assert result.decision.fallback_of == "deepseek-v4-flash"


async def test_connection_error_propagates_when_no_fallback_available() -> None:
    omlx = FakeProvider(fail_generate=ProviderConnectionError("omlx down"))
    router = _router(omlx, deepseek=None)  # no escalation fallback configured

    with pytest.raises(ProviderConnectionError):
        await router.generate(TaskClass.ROUTINE_GENERATION, MSG)


async def test_no_providers_configured_raises_connection_error() -> None:
    router = _router(omlx=None, deepseek=None)
    with pytest.raises(ProviderConnectionError):
        await router.generate(TaskClass.ROUTINE_GENERATION, MSG)


async def test_auth_error_not_fallback_eligible() -> None:
    omlx = FakeProvider(fail_generate=ProviderAuthError("bad key"))
    deepseek = FakeProvider()
    router = _router(omlx, deepseek)

    with pytest.raises(ProviderAuthError):
        await router.generate(TaskClass.ROUTINE_GENERATION, MSG)
    assert len(deepseek.generate_calls) == 0  # never silently routed around auth failure


async def test_thinking_override_passes_through() -> None:
    omlx = FakeProvider()
    deepseek = FakeProvider()
    router = _router(omlx, deepseek)

    await router.generate(TaskClass.ROUTINE_GENERATION, MSG, thinking=False)
    assert omlx.generate_calls[0].thinking is False


async def test_embed_routes_to_embedding_capability() -> None:
    omlx = FakeProvider()
    router = _router(omlx, deepseek=None)

    response = await router.embed(["text a", "text b"])

    assert len(omlx.embed_calls) == 1
    assert omlx.embed_calls[0].model == "bge-m3-mlx-4bit"
    assert omlx.embed_calls[0].texts == ["text a", "text b"]
    assert response.dimension == 2


async def test_embed_requires_embedding_provider() -> None:
    router = _router(omlx=None, deepseek=None)
    with pytest.raises(ProviderConfigurationError):
        await router.embed(["text"])


async def test_rerank_routes_to_rerank_capability() -> None:
    omlx = FakeProvider()
    router = _router(omlx, deepseek=None)

    await router.rerank("query", ["doc1", "doc2"], top_n=1)

    assert len(omlx.rerank_calls) == 1
    assert omlx.rerank_calls[0].query == "query"
    assert omlx.rerank_calls[0].documents == ["doc1", "doc2"]
    assert omlx.rerank_calls[0].top_n == 1


async def test_rerank_requires_rerank_provider() -> None:
    router = _router(omlx=None, deepseek=None)
    with pytest.raises(ProviderConfigurationError):
        await router.rerank("query", ["doc1"])
