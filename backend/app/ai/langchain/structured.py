"""LangChain-structured generation (Phase B realignment).

Signature-compatible with ``app.ai.structured.generate_structured`` so the
production call sites (question generation, evaluation, hints, extraction,
role analysis, transcript/debrief analysis) execute through LangChain
runnables while keeping identical validation semantics: JSON-mode call →
pydantic validation → bounded retry with feedback → typed error.

The deterministic implementation remains in ``app.ai.structured`` as the
reference/fallback layer (documented in DECISIONS.md ADR-024).
"""

from __future__ import annotations

import json
from typing import Any, cast

from pydantic import BaseModel, ValidationError

from app.ai.contracts import ChatMessage
from app.ai.errors import StructuredOutputError
from app.ai.langchain.model import RouterChatModel
from app.ai.langchain.pipelines import structured_chain
from app.ai.policy import TaskClass
from app.ai.router import InferenceRouter, RouterResult

DEFAULT_MAX_ATTEMPTS = 3


def _render_user_payload(messages: list[ChatMessage]) -> str:
    """Flatten trailing conversation messages into the user payload.

    Mirrors the deterministic path's message layout (system prompt is the
    first system message; the rest is user/context content).
    """
    payload: list[str] = []
    for message in messages[1:]:
        label = {
            "system": "SYSTEM",
            "user": "USER",
            "assistant": "CONTEXT",
        }.get(message.role, message.role.upper())
        payload.append(f"[{label}]\n{message.content}")
    return "\n\n".join(payload)


async def generate_structured[T: BaseModel](
    router: InferenceRouter,
    task: TaskClass,
    messages: list[ChatMessage],
    schema_model: type[T],
    *,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    thinking: bool | None = None,
) -> tuple[T, RouterResult]:
    """Generate, validate, and return a Pydantic model via LangChain runnables.

    Raises StructuredOutputError after ``max_attempts`` failed validations
    (identical contract to the deterministic reference path).
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    system_prompt = messages[0].content if messages else ""
    user_payload = _render_user_payload(messages)
    chain = structured_chain(router, task, system_prompt, schema_model, thinking=thinking)

    model = _model_from_chain(chain)
    for attempt in range(max_attempts):
        raw: str = ""
        try:
            message = await chain.ainvoke({"user": user_payload})
            raw = str(message.content)
        except Exception as exc:  # LangChain infra/transport failure
            raise StructuredOutputError(
                f"LangChain pipeline failed for task {task.value}",
                details={"task": task.value, "attempts": attempt + 1, "error": str(exc)},
            ) from exc
        try:
            parsed = schema_model.model_validate_json(raw)
            result = model.last_result
            if result is None:  # pragma: no cover - router always records
                result = RouterResult(decision=model.last_decision, response=object())  # type: ignore[arg-type]
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
            errors = json.dumps(exc.errors(include_url=False), default=str)
            user_payload = (
                f"{user_payload}\n\n[PREVIOUS OUTPUT]\n{raw}\n\n"
                f"[VALIDATION ERRORS]\n{errors}\n\n"
                "Respond again with ONLY a single valid JSON object."
            )

    raise StructuredOutputError("unreachable: structured generation failed")  # pragma: no cover


def _model_from_chain(chain: object) -> RouterChatModel:
    """The chains built by app.ai.langchain.pipelines put the
    RouterChatModel at index 1 of ``steps`` (prompt | model [| parser])."""
    steps: Any = cast(Any, getattr(chain, "steps", ()))
    if len(steps) < 2:
        raise RuntimeError("unexpected chain shape")  # pragma: no cover
    model: Any = steps[1]
    if not isinstance(model, RouterChatModel):
        raise RuntimeError("no RouterChatModel in chain")  # pragma: no cover
    return model
