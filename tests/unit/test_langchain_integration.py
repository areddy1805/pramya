"""LangChain integration tests (Phase B realignment).

Prove the LangChain execution path is REAL, not decorative:
- RouterChatModel is a genuine langchain BaseChatModel that routes every
  call through the InferenceRouter (ADR-004/023: DeepSeek is the sole text
  LLM; no bypass, no local fallback).
- Production runnables (structured_chain/text_chain) execute through
  LangChain composition and produce validated pydantic models.
- Bounded retry-with-feedback semantics are preserved.
"""

from __future__ import annotations

from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import Runnable
from pydantic import BaseModel, Field

from app.ai.contracts import ChatMessage, ChatResponse, Usage
from app.ai.errors import StructuredOutputError
from app.ai.langchain.model import RouterChatModel
from app.ai.langchain.pipelines import structured_chain, text_chain
from app.ai.langchain.structured import generate_structured
from app.ai.policy import TaskClass, TaskPolicyTable
from app.ai.router import InferenceRouter


class Extract(BaseModel):
    """Sample structured output schema."""

    title: str
    score: int = Field(ge=0, le=10)


class QueueProvider:
    """Fake provider returning queued content strings per call."""

    name = "fake"

    def __init__(self, contents: list[str]) -> None:
        self.contents = contents
        self.calls: list[list[ChatMessage]] = []

    async def generate(self, request: Any) -> ChatResponse:
        self.calls.append(request.messages)
        content = self.contents.pop(0) if self.contents else '{"title": "x", "score": 1}'
        return ChatResponse(content=content, model="fake", usage=Usage(total_tokens=1))


def _router(provider: QueueProvider) -> InferenceRouter:
    return InferenceRouter(policy=TaskPolicyTable(), omlx=None, deepseek=provider)


MSG = [ChatMessage(role="user", content="extract")]


async def test_router_chat_model_is_real_langchain_model() -> None:
    """RouterChatModel subclasses BaseChatModel and routes via the router."""
    provider = QueueProvider(['{"title": "T", "score": 8}'])
    model = RouterChatModel(router=_router(provider), task=TaskClass.EXTRACTION)

    assert isinstance(model, BaseChatModel)
    assert model._llm_type == "pramya-router"
    result = await model.ainvoke("extract")
    assert result.content == '{"title": "T", "score": 8}'
    # Routed through the policy: DeepSeek is the sole text provider.
    assert model.last_decision is not None
    assert model.last_decision.model == "deepseek-v4-flash"
    assert model.last_decision.provider == "deepseek"
    assert provider.calls  # the router (not a local model) handled the call


async def test_structured_chain_composes_real_langchain_runnables() -> None:
    """structured_chain returns a runnable that executes via LangChain."""
    provider = QueueProvider(['{"title": "T", "score": 9}'])
    chain = structured_chain(_router(provider), TaskClass.EXTRACTION, "sys", Extract)

    assert isinstance(chain, Runnable)
    message = await chain.ainvoke({"user": "extract"})
    assert message.content == '{"title": "T", "score": 9}'
    # Schema is embedded in the LangChain system prompt.
    prompt = chain.first  # type: ignore[attr-defined]
    rendered = prompt.format_prompt(user="extract")
    assert "JSON Schema" in rendered.messages[0].content


async def test_generate_structured_via_langchain_happy_path() -> None:
    """Production helper returns a validated model + routing decision."""
    provider = QueueProvider(['{"title": "T", "score": 8}'])
    parsed, result = await generate_structured(
        _router(provider), TaskClass.EXTRACTION, MSG, Extract
    )

    assert parsed.title == "T"
    assert parsed.score == 8
    assert result.decision.model == "deepseek-v4-flash"


async def test_generate_structured_via_langchain_retries_with_feedback() -> None:
    """Bounded retry with validation feedback, executed via LangChain."""
    provider = QueueProvider(["not json", '{"title": "T", "score": 9}'])
    parsed, _ = await generate_structured(_router(provider), TaskClass.EXTRACTION, MSG, Extract)

    assert parsed.title == "T"
    assert len(provider.calls) == 2
    feedback = provider.calls[1][-1].content
    assert "[VALIDATION ERRORS]" in feedback
    assert "[PREVIOUS OUTPUT]" in feedback


async def test_generate_structured_via_langchain_bounded_attempts() -> None:
    """Never loops unbounded; raises typed error after the budget."""
    provider = QueueProvider(["nope", "nope", "nope"])
    with pytest.raises(StructuredOutputError):
        await generate_structured(_router(provider), TaskClass.EXTRACTION, MSG, Extract)
    assert len(provider.calls) == 3


async def test_text_chain_produces_str_output() -> None:
    """Report-style free text executes through the LangChain text chain."""
    provider = QueueProvider(["report body"])
    chain = text_chain(_router(provider), TaskClass.FINAL_SYNTHESIS, "sys")

    out = await chain.ainvoke({"user": "summarize"})
    assert out == "report body"
