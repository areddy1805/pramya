"""MLXProvider — oMLX local runtime via OpenAI-compatible HTTP (ADR-011).

Serves chat generation (`pramya-4b`), embeddings (BGE-M3), and reranking
(Qwen3-Reranker-0.6B) through the verified oMLX endpoints under `/v1`
(chat/completions, embeddings, rerank). Implemented over httpx — no OpenAI SDK.

pramya-4b thinking is EXPLICITLY disabled on every request via
``chat_template_kwargs: {"enable_thinking": <config flag>}`` — never rely on
the model's default thinking behavior (MODEL_CATALOG §2.2, ADR-020).
"""

from __future__ import annotations

from typing import Any, cast

import httpx

from app.ai.contracts import (
    ChatRequest,
    ChatResponse,
    EmbedRequest,
    EmbedResponse,
    RerankItem,
    RerankRequest,
    RerankResponse,
)
from app.ai.errors import ProviderRequestError
from app.ai.providers._http import build_headers, parse_chat_response, request_json


class MLXProvider:
    """oMLX provider: text generation + embeddings + reranking capabilities."""

    name = "omlx"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        chat_model: str,
        embedding_model: str,
        rerank_model: str,
        thinking_enabled: bool = False,
        timeout_seconds: float = 120.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.chat_model = chat_model
        self.embedding_model = embedding_model
        self.rerank_model = rerank_model
        self.thinking_enabled = thinking_enabled
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)

    def _headers(self) -> dict[str, str]:
        return build_headers(self.api_key)

    async def generate(self, request: ChatRequest) -> ChatResponse:
        body: dict[str, Any] = {
            "model": self.chat_model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            # Explicit thinking policy: pinned from config, never the model default.
            "chat_template_kwargs": {"enable_thinking": self.thinking_enabled},
        }
        if request.temperature is not None:
            body["temperature"] = request.temperature
        if request.max_tokens is not None:
            body["max_tokens"] = request.max_tokens
        if request.json_mode:
            body["response_format"] = {"type": "json_object"}

        payload = await request_json(
            self._client,
            "POST",
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            body=body,
        )
        return parse_chat_response(payload, fallback_model=self.chat_model, provider=self.name)

    async def embed(self, request: EmbedRequest) -> EmbedResponse:
        body: dict[str, Any] = {
            "model": request.model or self.embedding_model,
            "input": request.texts,
        }
        payload = await request_json(
            self._client,
            "POST",
            f"{self.base_url}/embeddings",
            headers=self._headers(),
            body=body,
        )
        return _parse_embeddings(payload, fallback_model=self.embedding_model)

    async def rerank(self, request: RerankRequest) -> RerankResponse:
        body: dict[str, Any] = {
            "model": self.rerank_model,
            "query": request.query,
            "documents": request.documents,
        }
        if request.top_n is not None:
            body["top_n"] = request.top_n
        payload = await request_json(
            self._client,
            "POST",
            f"{self.base_url}/rerank",
            headers=self._headers(),
            body=body,
        )
        return _parse_rerank(payload, fallback_model=self.rerank_model)

    async def health(self) -> bool:
        """Advisory liveness probe: /v1/models reachable (not a routing input)."""
        try:
            response = await self._client.get(f"{self.base_url}/models", headers=self._headers())
            return response.status_code < 500
        except httpx.HTTPError:
            return False


def _parse_embeddings(payload: dict[str, Any], *, fallback_model: str) -> EmbedResponse:
    data_raw = payload.get("data")
    if not isinstance(data_raw, list):
        raise ProviderRequestError("malformed embeddings response", details={"provider": "omlx"})
    embeddings: list[list[float]] = []
    for item in cast(list[dict[str, Any]], data_raw):
        vector_raw = item.get("embedding")
        if not isinstance(vector_raw, list):
            raise ProviderRequestError("malformed embedding item", details={"provider": "omlx"})
        embeddings.append([float(v) for v in cast(list[float], vector_raw)])
    dimension = len(embeddings[0]) if embeddings else 0
    return EmbedResponse(
        embeddings=embeddings,
        model=str(payload.get("model") or fallback_model),
        dimension=dimension,
    )


def _parse_rerank(payload: dict[str, Any], *, fallback_model: str) -> RerankResponse:
    results_raw = payload.get("results")
    if not isinstance(results_raw, list):
        raise ProviderRequestError("malformed rerank response", details={"provider": "omlx"})
    items: list[RerankItem] = []
    for entry in cast(list[dict[str, Any]], results_raw):
        index = entry.get("index")
        score = entry.get("relevance_score")
        if not isinstance(index, int) or not isinstance(score, (int, float)):
            raise ProviderRequestError("malformed rerank item", details={"provider": "omlx"})
        items.append(RerankItem(index=index, score=float(score)))
    return RerankResponse(results=items, model=str(payload.get("model") or fallback_model))
