"""Provider capability contracts.

Application code (services, router consumers) depends only on these typed
capabilities — never on oMLX or DeepSeek specifics. Providers are swappable:
``DeepSeekProvider`` implements text generation only; ``MLXProvider`` (oMLX)
implements text generation + embeddings + reranking.

Separate typed capabilities per concern so the router can compose providers
per capability (ADR-004: generate / embed / rerank / transcribe / synthesize).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

Role = Literal["system", "user", "assistant"]


class ChatMessage(BaseModel):
    """One chat turn."""

    role: Role
    content: str


class Usage(BaseModel):
    """Token usage; DeepSeek cache fields surfaced for cost telemetry."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    prompt_cache_hit_tokens: int | None = None
    prompt_cache_miss_tokens: int | None = None


class ChatRequest(BaseModel):
    """Input to ``generate()``. Framework-agnostic; provider maps to its API."""

    messages: list[ChatMessage]
    temperature: float | None = None
    max_tokens: int | None = None
    # Request JSON-object output (provider maps to its structured-output mode).
    json_mode: bool = False
    # Thinking policy. None = provider/task default; True/False = explicit.
    thinking: bool | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    """Output of ``generate()``. Content is untrusted data — validate before use."""

    content: str
    model: str
    usage: Usage = Field(default_factory=Usage)
    finish_reason: str | None = None
    # Preserved reasoning trace when provider returns one (e.g. DeepSeek
    # reasoning_content). Telemetry/UI may expose it; never parse as output.
    thinking_content: str | None = None


class ChatStreamChunk(BaseModel):
    """One delta of a streaming generation (``stream()``).

    ``delta`` is the raw text token produced so far (never validated — the
    caller applies the same schema validation as non-streaming output).
    ``finish_reason`` is set on the final chunk when the provider reports it.
    """

    delta: str = ""
    model: str = ""
    finish_reason: str | None = None
    usage: Usage | None = None


class EmbedRequest(BaseModel):
    """Input to ``embed()``. ``model`` overrides the provider default when set."""

    texts: list[str]
    model: str | None = None


class EmbedResponse(BaseModel):
    embeddings: list[list[float]]
    model: str
    dimension: int
    usage: Usage | None = None


class RerankRequest(BaseModel):
    query: str
    documents: list[str]
    top_n: int | None = None


class RerankItem(BaseModel):
    index: int
    score: float
    document: str | None = None


class RerankResponse(BaseModel):
    results: list[RerankItem]
    model: str


@runtime_checkable
class TextGenerationProvider(Protocol):
    """Capability: generate text / structured JSON.

    Deliberately minimal so runtime protocol checks are stable. Streaming is
    an OPTIONAL capability declared by StreamingTextGenerationProvider —
    providers without it are handled by the router's single-chunk fallback.
    """

    name: str

    async def generate(self, request: ChatRequest) -> ChatResponse: ...


@runtime_checkable
class StreamingTextGenerationProvider(TextGenerationProvider, Protocol):
    """Optional capability: streaming generation (SSE deltas).

    Implemented as an async generator: ``def stream(...) -> AsyncIterator[...]``.
    The router falls back to generate() for providers that do not implement
    this protocol.
    """

    def stream(self, request: ChatRequest) -> AsyncIterator[ChatStreamChunk]: ...

    async def supports_stream(self) -> bool: ...


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Capability: dense embeddings (BGE-M3 via oMLX)."""

    name: str

    async def embed(self, request: EmbedRequest) -> EmbedResponse: ...


@runtime_checkable
class RerankingProvider(Protocol):
    """Capability: relevance reranking (Qwen3-Reranker-0.6B via oMLX)."""

    name: str

    async def rerank(self, request: RerankRequest) -> RerankResponse: ...


@runtime_checkable
class InferenceProvider(TextGenerationProvider, EmbeddingProvider, RerankingProvider, Protocol):
    """Provider offering all three capabilities (oMLX local runtime)."""


@runtime_checkable
class HealthCheckable(Protocol):
    """Optional provider health probe (used by ops, not routing decisions)."""

    name: str

    async def health(self) -> bool: ...
