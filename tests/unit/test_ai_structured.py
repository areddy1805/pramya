"""Structured-output tests: schema validation, bounded retry with feedback."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel, Field

from app.ai.contracts import ChatMessage, ChatResponse, Usage
from app.ai.errors import StructuredOutputError
from app.ai.policy import TaskClass, TaskPolicyTable
from app.ai.router import InferenceRouter
from app.ai.structured import generate_structured


class Extraction(BaseModel):
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


async def test_structured_happy_path() -> None:
    provider = QueueProvider(['{"title": "T", "score": 8}'])
    parsed, result = await generate_structured(
        _router(provider), TaskClass.EXTRACTION, MSG, Extraction
    )

    assert parsed.title == "T"
    assert parsed.score == 8
    assert result.decision.model == "deepseek-v4-flash"
    # Schema is embedded in the system prompt.
    assert "JSON Schema" in provider.calls[0][0].content


async def test_structured_retries_with_feedback_then_succeeds() -> None:
    provider = QueueProvider(["not json at all", '{"title": "T", "score": 9}'])
    parsed, _ = await generate_structured(_router(provider), TaskClass.EXTRACTION, MSG, Extraction)

    assert parsed.title == "T"
    assert len(provider.calls) == 2
    # Second call includes assistant raw output + validation feedback.
    feedback = provider.calls[1]
    assert feedback[-2].role == "assistant"
    assert "Validation errors" in feedback[-1].content


async def test_structured_fails_after_bounded_retries() -> None:
    provider = QueueProvider(["garbage", "also garbage", "still garbage"])
    with pytest.raises(StructuredOutputError) as exc_info:
        await generate_structured(
            _router(provider), TaskClass.EXTRACTION, MSG, Extraction, max_attempts=3
        )

    assert exc_info.value.details["attempts"] == 3
    assert len(provider.calls) == 3  # bounded — no unbounded loop


async def test_structured_retries_are_bounded_by_default() -> None:
    provider = QueueProvider(["bad"] * 100)  # infinite junk
    with pytest.raises(StructuredOutputError):
        await generate_structured(_router(provider), TaskClass.EXTRACTION, MSG, Extraction)
    assert len(provider.calls) <= 3  # default budget, not 100


async def test_structured_rejects_zero_attempts() -> None:
    provider = QueueProvider([])
    with pytest.raises(ValueError):
        await generate_structured(
            _router(provider), TaskClass.EXTRACTION, MSG, Extraction, max_attempts=0
        )
