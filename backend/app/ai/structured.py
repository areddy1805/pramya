"""Structured-output helper (AI_ARCHITECTURE §7).

Pydantic schema is the contract for every LLM output that touches state:
schema → prompt (schema embedded) → JSON-mode generation → validate → on
failure, retry with validation feedback (bounded) → typed error after the
retry budget is exhausted. Invalid output never becomes application state.
"""

from __future__ import annotations

import json
from typing import cast

from pydantic import BaseModel, ValidationError

from app.ai.contracts import ChatMessage
from app.ai.errors import StructuredOutputError
from app.ai.policy import TaskClass
from app.ai.router import InferenceRouter, RouterResult

DEFAULT_MAX_ATTEMPTS = 3

_SYSTEM_INSTRUCTION = (
    "You are a structured data extractor. Respond with ONLY a single JSON "
    "object that validates against the JSON Schema below. Do not wrap it in "
    "markdown fences, do not add commentary."
)


def _schema_text[T: BaseModel](schema_model: type[T]) -> str:
    return json.dumps(schema_model.model_json_schema(), sort_keys=True)


def _feedback_message[T: BaseModel](schema_model: type[T], errors: list[dict[str, object]]) -> str:
    return (
        "Your previous response did not validate against the JSON Schema. "
        f"Validation errors: {json.dumps(errors, default=str)}. "
        "Respond again with ONLY a single valid JSON object."
    )


async def generate_structured[T: BaseModel](
    router: InferenceRouter,
    task: TaskClass,
    messages: list[ChatMessage],
    schema_model: type[T],
    *,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    thinking: bool | None = None,
) -> tuple[T, RouterResult]:
    """Generate, validate, and return a Pydantic model instance.

    Raises StructuredOutputError after ``max_attempts`` failed validations.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    conversation: list[ChatMessage] = list(messages)
    for attempt in range(max_attempts):
        system = ChatMessage(
            role="system",
            content=f"{_SYSTEM_INSTRUCTION}\n\nJSON Schema:\n{_schema_text(schema_model)}",
        )
        result = await router.generate(
            task, [system, *conversation], json_mode=True, thinking=thinking
        )
        raw = result.response.content.strip()
        try:
            parsed = schema_model.model_validate_json(raw)
            return parsed, result
        except ValidationError as exc:
            if attempt == max_attempts - 1:
                raise StructuredOutputError(
                    f"model output failed schema validation after {max_attempts} attempts",
                    details={
                        "task": task.value,
                        "attempts": max_attempts,
                        "validation_errors": exc.errors(include_url=False),
                    },
                ) from exc
            conversation = [
                *conversation,
                ChatMessage(role="assistant", content=result.response.content),
                ChatMessage(
                    role="user",
                    content=_feedback_message(
                        schema_model, cast(list[dict[str, object]], exc.errors(include_url=False))
                    ),
                ),
            ]

    # Unreachable: loop either returns or raises inside.
    raise StructuredOutputError("unreachable: structured generation failed")  # pragma: no cover
