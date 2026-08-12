"""LangChain runnable pipelines (Phase B realignment, ADR-001 boundary).

Builders compose LangChain primitives — ChatPromptTemplate, RouterChatModel,
StrOutputParser — into RunnableSequences. Every model call still goes
through the InferenceRouter (ADR-004/ADR-023): DeepSeek is the sole text
LLM, no local text fallback, no bypass.

Two shapes:
- ``structured_chain``: prompt -> RouterChatModel (json_mode) -> raw
  AIMessage; validation + bounded retry-with-feedback lives in
  ``app.ai.langchain.structured`` (mirrors ``app.ai.structured`` semantics
  but executes through LangChain runnables).
- ``text_chain``: prompt -> RouterChatModel -> StrOutputParser for
  free-text outputs (report synthesis).
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable

from app.ai.langchain.model import RouterChatModel
from app.ai.policy import TaskClass
from app.ai.router import InferenceRouter

_STRUCTURED_SYSTEM = (
    "You are a structured data extractor. Respond with ONLY a single JSON "
    "object that validates against the JSON Schema below. Do not wrap it in "
    "markdown fences, do not add commentary."
)


def _escape_template(value: str) -> str:
    """Double braces so prompt-template rendering treats them as literals."""
    return value.replace("{", "{{").replace("}", "}}")


def _system_message(system_prompt: str, schema_text: str | None = None) -> str:
    if schema_text is None:
        return _escape_template(system_prompt)
    return _escape_template(
        f"{_STRUCTURED_SYSTEM}\n\nJSON Schema:\n{schema_text}\n\n{system_prompt}"
    )


def structured_chain(
    router: InferenceRouter,
    task: TaskClass,
    system_prompt: str,
    schema_model: type[Any],
    *,
    thinking: bool | None = None,
) -> Runnable[dict[str, Any], AIMessage]:
    """prompt -> RouterChatModel(json_mode) chain yielding a raw AIMessage.

    The caller validates JSON (see app.ai.langchain.structured) so the
    retry-with-feedback loop can include the raw model output — same
    semantics as the deterministic reference path, executed via LangChain.
    """
    schema_text = json.dumps(schema_model.model_json_schema(), sort_keys=True)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", _system_message(system_prompt, schema_text)),
            ("user", "{user}"),
        ]
    )
    model = RouterChatModel(router=router, task=task, json_mode=True, thinking=thinking)
    return prompt | model


def text_chain(
    router: InferenceRouter,
    task: TaskClass,
    system_prompt: str,
    *,
    thinking: bool | None = None,
) -> Runnable[dict[str, Any], str]:
    """prompt -> RouterChatModel -> StrOutputParser for free-text output."""
    prompt = ChatPromptTemplate.from_messages([("system", system_prompt), ("user", "{user}")])
    model = RouterChatModel(router=router, task=task, thinking=thinking)
    return prompt | model | StrOutputParser()


__all__ = ["structured_chain", "text_chain"]
