"""Provider HTTP contract tests — mocked httpx transport, no live services.

Covers request shapes, response normalization, thinking-disabled assertion
for pramya-4b, and typed error mapping (auth/connection/request/timeout).
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

import httpx
import pytest

from app.ai.contracts import (
    ChatMessage,
    ChatRequest,
    EmbedRequest,
    RerankRequest,
)
from app.ai.errors import (
    ProviderAuthError,
    ProviderConnectionError,
    ProviderRequestError,
)
from app.ai.providers.deepseek import DeepSeekProvider
from app.ai.providers.omlx import MLXProvider

T = TypeVar("T")
Handler = Callable[[httpx.Request], Awaitable[httpx.Response]]


def _client(handler: Handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _chat_ok_payload(model: str, *, content: str = "ok") -> dict[str, Any]:
    return {
        "id": "x",
        "object": "chat.completion",
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


def _capture(requests: list[dict[str, Any]], payload: dict[str, Any]) -> Handler:
    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=payload)

    return handler


def _omlx(requests: list[dict[str, Any]], handler: Handler) -> MLXProvider:
    return MLXProvider(
        base_url="http://127.0.0.1:8000/v1",
        api_key=None,
        chat_model="pramya-4b",
        embedding_model="bge-m3-mlx-4bit",
        rerank_model="Qwen3-Reranker-0.6B-4bit",
        client=_client(handler),
    )


def _deepseek(requests: list[dict[str, Any]], handler: Handler) -> DeepSeekProvider:
    return DeepSeekProvider(
        base_url="https://api.deepseek.com",
        api_key="sk-test",
        model="deepseek-v4-flash",
        client=_client(handler),
    )


# --------------------------------------------------------------------------
# DeepSeek provider
# --------------------------------------------------------------------------


async def test_deepseek_request_shape_and_thinking() -> None:
    requests: list[dict[str, Any]] = []
    provider = _deepseek(requests, _capture(requests, _chat_ok_payload("deepseek-v4-flash")))

    response = await provider.generate(
        ChatRequest(
            messages=[ChatMessage(role="user", content="hello")],
            thinking=True,
            json_mode=True,
        )
    )

    body = requests[0]
    assert body["model"] == "deepseek-v4-flash"
    assert body["messages"] == [{"role": "user", "content": "hello"}]
    assert body["thinking"] == {"type": "enabled"}
    assert body["response_format"] == {"type": "json_object"}
    assert response.model == "deepseek-v4-flash"


async def test_deepseek_thinking_disabled_flag() -> None:
    requests: list[dict[str, Any]] = []
    provider = _deepseek(requests, _capture(requests, _chat_ok_payload("deepseek-v4-flash")))

    await provider.generate(
        ChatRequest(messages=[ChatMessage(role="user", content="hi")], thinking=False)
    )

    assert requests[0]["thinking"] == {"type": "disabled"}


async def test_deepseek_usage_cache_fields_parsed() -> None:
    payload = _chat_ok_payload("deepseek-v4-flash")
    payload["usage"] = {
        "prompt_tokens": 100,
        "completion_tokens": 20,
        "total_tokens": 120,
        "prompt_cache_hit_tokens": 90,
        "prompt_cache_miss_tokens": 10,
    }
    provider = _deepseek([], _capture([], payload))

    response = await provider.generate(
        ChatRequest(messages=[ChatMessage(role="user", content="hi")])
    )

    assert response.usage.prompt_cache_hit_tokens == 90
    assert response.usage.prompt_cache_miss_tokens == 10
    assert response.usage.total_tokens == 120


async def test_deepseek_thinking_content_preserved() -> None:
    payload = _chat_ok_payload("deepseek-v4-flash")
    payload["choices"][0]["message"]["reasoning_content"] = "chain of thought"
    provider = _deepseek([], _capture([], payload))

    response = await provider.generate(
        ChatRequest(messages=[ChatMessage(role="user", content="hi")])
    )

    assert response.thinking_content == "chain of thought"


async def test_deepseek_auth_error_mapped() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid api key"})

    provider = _deepseek([], handler)
    with pytest.raises(ProviderAuthError):
        await provider.generate(ChatRequest(messages=[ChatMessage(role="user", content="hi")]))


async def test_deepseek_server_error_maps_to_connection() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "overloaded"})

    provider = _deepseek([], handler)
    with pytest.raises(ProviderConnectionError):
        await provider.generate(ChatRequest(messages=[ChatMessage(role="user", content="hi")]))


async def test_deepseek_timeout_maps_to_connection() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    provider = _deepseek([], handler)
    with pytest.raises(ProviderConnectionError):
        await provider.generate(ChatRequest(messages=[ChatMessage(role="user", content="hi")]))


async def test_deepseek_4xx_request_error() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "bad request"})

    provider = _deepseek([], handler)
    with pytest.raises(ProviderRequestError):
        await provider.generate(ChatRequest(messages=[ChatMessage(role="user", content="hi")]))


# --------------------------------------------------------------------------
# oMLX / MLX provider
# --------------------------------------------------------------------------


async def test_omlx_chat_sends_pramya_4b_with_thinking_disabled() -> None:
    """Thinking-disabled assertion: enable_thinking=false must be on the wire."""
    requests: list[dict[str, Any]] = []
    provider = _omlx(requests, _capture(requests, _chat_ok_payload("pramya-4b", content="ping")))

    response = await provider.generate(
        ChatRequest(messages=[ChatMessage(role="user", content="ping")])
    )

    body = requests[0]
    assert body["model"] == "pramya-4b"
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert response.content == "ping"


async def test_omlx_chat_thinking_flag_follows_config() -> None:
    requests: list[dict[str, Any]] = []
    provider = MLXProvider(
        base_url="http://127.0.0.1:8000/v1",
        api_key=None,
        chat_model="pramya-4b",
        embedding_model="bge-m3-mlx-4bit",
        rerank_model="Qwen3-Reranker-0.6B-4bit",
        thinking_enabled=True,
        client=_client(_capture(requests, _chat_ok_payload("pramya-4b"))),
    )

    await provider.generate(ChatRequest(messages=[ChatMessage(role="user", content="hi")]))

    assert requests[0]["chat_template_kwargs"] == {"enable_thinking": True}


async def test_omlx_embeddings_request_and_parse() -> None:
    requests: list[dict[str, Any]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "object": "list",
                "model": "bge-m3-mlx-4bit",
                "data": [
                    {"object": "embedding", "index": 0, "embedding": [0.1, 0.2, 0.3]},
                    {"object": "embedding", "index": 1, "embedding": [0.4, 0.5, 0.6]},
                ],
                "usage": {"total_tokens": 5},
            },
        )

    provider = _omlx(requests, handler)
    response = await provider.embed(EmbedRequest(texts=["a", "b"]))

    assert requests[0] == {"model": "bge-m3-mlx-4bit", "input": ["a", "b"]}
    assert response.dimension == 3
    assert len(response.embeddings) == 2


async def test_omlx_rerank_request_and_parse() -> None:
    requests: list[dict[str, Any]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "rerank-1",
                "model": "Qwen3-Reranker-0.6B-4bit",
                "results": [
                    {"index": 1, "relevance_score": 0.9},
                    {"index": 0, "relevance_score": 0.4},
                ],
            },
        )

    provider = _omlx(requests, handler)
    response = await provider.rerank(RerankRequest(query="q", documents=["a", "b"], top_n=2))

    assert requests[0] == {
        "model": "Qwen3-Reranker-0.6B-4bit",
        "query": "q",
        "documents": ["a", "b"],
        "top_n": 2,
    }
    assert response.results[0].index == 1
    assert response.results[0].score == 0.9


async def test_omlx_server_error_maps_to_connection() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "model not loaded"})

    provider = _omlx([], handler)
    with pytest.raises(ProviderConnectionError):
        await provider.generate(ChatRequest(messages=[ChatMessage(role="user", content="hi")]))


async def test_provider_protocol_conformance() -> None:
    from app.ai.contracts import EmbeddingProvider, RerankingProvider, TextGenerationProvider

    omlx = MLXProvider(
        base_url="http://127.0.0.1:8000/v1",
        chat_model="pramya-4b",
        embedding_model="bge-m3-mlx-4bit",
        rerank_model="Qwen3-Reranker-0.6B-4bit",
    )
    deepseek = DeepSeekProvider(
        base_url="https://api.deepseek.com",
        api_key="sk-test",
        model="deepseek-v4-flash",
    )

    assert isinstance(omlx, TextGenerationProvider)
    assert isinstance(deepseek, TextGenerationProvider)
    assert isinstance(omlx, EmbeddingProvider)
    assert isinstance(omlx, RerankingProvider)
    assert not isinstance(deepseek, EmbeddingProvider)
