"""Interview question generation (Phase 3.3) + evaluation (3.4) + hints (3.5).

Question generation is STREAMING (V1.1 realtime path): the interviewer
question is produced as a plain-text stream with the spoken question first
(``QUESTION:`` header), so the voice engine can begin TTS on the first
complete sentence while the rest of the response is still being generated.
The trailing KEY: VALUE lines (difficulty/type/rationale/hints) are parsed
into the same InterviewQuestion schema — persistence and text interviews
are unchanged. All output is validated before persistence.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

from langchain_core.runnables import Runnable

from app.ai.contracts import ChatMessage
from app.ai.langchain.model import RouterChatModel
from app.ai.langchain.structured import generate_structured
from app.ai.policy import TaskClass
from app.ai.router import InferenceRouter
from app.core.logging import get_logger
from app.domain.errors import ValidationFailedError
from app.domain.schemas import (
    AnswerEvaluation,
    HintOutput,
    InterviewerReasoning,
    InterviewQuestion,
)
from app.services.prompts import load_prompt

_Q_STREAM_PROMPT = "question_generation/adaptive_question_stream.txt"
_EVAL_PROMPT = "answer_evaluation/answer_eval.txt"
_HINT_PROMPT = "question_generation/hint.txt"
_REASON_PROMPT = "interview_planning/interviewer_reasoning.txt"

# Metadata keys that follow the QUESTION: section in the streamed format.
# The TTS presentation boundary strips everything after the first of
# these (the interviewer must never speak workflow metadata).
QUESTION_META_PREFIXES = (
    "TYPE:",
    "DIFFICULTY:",
    "RATIONALE:",
    "RATIONAL:",
    "TARGET:",
    "HINTS:",
    "CATEGORY:",
    "SOURCE:",
    "SOURCE_REF:",
)


def parse_question_output(text: str, default_competency: str = "general") -> InterviewQuestion:
    """Deterministically parse the streamed QUESTION:/KEY: format.

    Resilient: the question is everything before the first KEY line;
    missing keys fall back to defaults; the QUESTION may span multiple
    lines. Raises ValidationFailedError when no question text is found.
    """
    lines = [ln.strip() for ln in (text or "").splitlines()]
    question_lines: list[str] = []
    kv: dict[str, str] = {}
    hints: list[str] = []
    mode = "question"
    for ln in lines:
        if not ln:
            continue
        upper = ln.upper()
        if mode == "question":
            if upper.startswith("QUESTION:"):
                rest = ln[len("QUESTION:") :].strip()
                if rest:
                    question_lines.append(rest)
                continue
            is_key = upper.startswith(QUESTION_META_PREFIXES)
            if not is_key:
                question_lines.append(ln)
                continue
            mode = "kv"
        if mode == "kv":
            if upper.startswith("HINTS:"):
                mode = "hints"
                continue
            key, _, value = ln.partition(":")
            if key.strip().upper() + ":" in QUESTION_META_PREFIXES and value.strip():
                kv[key.strip().upper()] = value.strip()
            continue
        if mode == "hints":
            if ln.startswith("-") and len(ln) > 1:
                hints.append(ln[1:].strip())
    question = " ".join(question_lines).strip()
    if not question:
        raise ValidationFailedError("question generation returned no question text")
    return InterviewQuestion(
        text=question,
        type=kv.get("TYPE", "general"),
        difficulty=kv.get("DIFFICULTY", "medium"),
        hint_levels=hints or [],
        rationale=kv.get("RATIONALE") or kv.get("RATIONAL"),
        target_competency=kv.get("TARGET") or default_competency,
        category=kv.get("CATEGORY"),
        source=kv.get("SOURCE"),
        source_ref=kv.get("SOURCE_REF"),
    )


class QuestionGenerator:
    """Adaptive question generation (deepseek-v4-flash, streaming)."""

    def __init__(self, router: InferenceRouter, *, logger: logging.Logger | None = None) -> None:
        self.router = router
        self._logger = logger or get_logger("app.interview.questions")
        self._prompt = load_prompt(
            _Q_STREAM_PROMPT,
            fallback="Generate one adaptive spoken interview question.",
        )

    def _chain(self) -> Runnable[dict[str, str], object]:
        """prompt -> RouterChatModel (plain text, streams tokens)."""
        from langchain_core.prompts import ChatPromptTemplate

        prompt = ChatPromptTemplate.from_messages([("system", self._prompt), ("user", "{context}")])
        model = RouterChatModel(router=self.router, task=TaskClass.INTERVIEW_CONTENT_GENERATION)
        return prompt | model

    async def stream_question(
        self,
        *,
        competency: str,
        difficulty: str,
        seniority: str,
        evidence_summary: str,
        history: str,
        hints_used: int,
        context: dict[str, object] | None = None,
    ) -> AsyncIterator[str]:
        """Yield raw model token chunks for the next question.

        Tokens are streamed from the router (DeepSeek SSE) through the
        LangChain runnable; the graph node accumulates them and LangGraph
        ``stream_mode="messages"`` surfaces them to the voice engine.

        ``context`` carries the productization grounding snapshot (profile /
        resume / JD / role / evidence / taxonomy / coverage / novelty /
        style / follow-up directive / time budget). Legacy keyword args are
        folded in for backward compatibility (evals).
        """
        ctx: dict[str, object] = dict(context or {})
        ctx.setdefault("target_competency", competency)
        ctx.setdefault("difficulty", difficulty)
        ctx.setdefault("seniority", seniority)
        ctx.setdefault("evidence_summary", evidence_summary)
        ctx.setdefault("session_history", history)
        ctx.setdefault("hints_used_so_far", hints_used)
        chain = self._chain()
        async for chunk in chain.astream({"context": json.dumps(ctx, default=str)}):
            content = getattr(chunk, "content", chunk)
            if isinstance(content, str) and content:
                yield content

    async def generate(
        self,
        *,
        competency: str,
        difficulty: str,
        seniority: str,
        evidence_summary: str,
        history: str,
        hints_used: int,
        context: dict[str, object] | None = None,
    ) -> InterviewQuestion:
        """Non-streaming convenience: accumulate the stream and parse."""
        from app.observability import trace_span

        text = ""
        async with trace_span(
            "question_generation",
            task="interview_content_generation",
            competency=competency,
            difficulty=difficulty,
            seniority=seniority,
        ):
            async for token in self.stream_question(
                competency=competency,
                difficulty=difficulty,
                seniority=seniority,
                evidence_summary=evidence_summary,
                history=history,
                hints_used=hints_used,
                context=context,
            ):
                text += token
        return parse_question_output(text, default_competency=competency)


class Evaluator:
    """Answer evaluation + evidence extraction (deep evaluation policy)."""

    def __init__(self, router: InferenceRouter, *, logger: logging.Logger | None = None) -> None:
        self.router = router
        self._logger = logger or get_logger("app.interview.eval")
        self._prompt = load_prompt(
            _EVAL_PROMPT,
            fallback="Evaluate the answer across evidence-backed dimensions.",
        )

    async def evaluate(
        self,
        *,
        question_text: str,
        answer_text: str,
        evidence_context: str,
        hints_used: int,
    ) -> AnswerEvaluation:
        messages = [
            ChatMessage(role="system", content=self._prompt),
            ChatMessage(
                role="user",
                content=f"QUESTION:\n{question_text}\n\nCANDIDATE ANSWER:\n{answer_text}",
            ),
            ChatMessage(
                role="assistant",
                content=f"RETRIEVED EVIDENCE:\n{evidence_context}\nHINTS_USED: {hints_used}",
            ),
        ]
        from app.observability import trace_span

        async with trace_span(
            "answer_evaluation",
            task="deep_evaluation",
            hints_used=hints_used,
        ):
            evaluation, _ = await generate_structured(
                self.router, TaskClass.DEEP_EVALUATION, messages, AnswerEvaluation
            )
        return evaluation


class Interviewer:
    """Post-answer interviewer reasoning (productization step 4).

    Runs in the ANSWER lane (background for voice): decides the follow-up
    routing for the next question. Never blocks the next-question stream.
    """

    def __init__(self, router: InferenceRouter, *, logger: logging.Logger | None = None) -> None:
        self.router = router
        self._logger = logger or get_logger("app.interview.reason")
        self._prompt = load_prompt(
            _REASON_PROMPT,
            fallback="Decide the next action after this interview answer.",
        )

    async def reason(
        self,
        *,
        question_text: str,
        answer_text: str,
        evaluation: dict[str, object],
        context_digest: str,
    ) -> InterviewerReasoning:
        from app.observability import trace_span

        messages = [
            ChatMessage(role="system", content=self._prompt),
            ChatMessage(
                role="user",
                content=(
                    f"QUESTION:\n{question_text}\n\n"
                    f"CANDIDATE ANSWER:\n{answer_text}\n\n"
                    f"EVALUATION:\n{json.dumps(evaluation, default=str)[:4000]}\n\n"
                    f"CONTEXT:\n{context_digest}"
                ),
            ),
        ]
        async with trace_span("interviewer_reasoning", task="complex_reasoning"):
            reasoning, _ = await generate_structured(
                self.router, TaskClass.COMPLEX_REASONING, messages, InterviewerReasoning
            )
        return reasoning


class Hints:
    """Progressive hints (4 levels) via router (3.5)."""

    def __init__(self, router: InferenceRouter) -> None:
        self.router = router
        self._prompt = load_prompt(
            _HINT_PROMPT,
            fallback=(
                "Provide the next progressive hint for the question. "
                "Nudge -> direction -> partial reasoning -> worked approach."
            ),
        )

    async def hint_for(
        self, *, question_text: str, hint_level: int, answer_so_far: str = ""
    ) -> str:
        messages = [
            ChatMessage(role="system", content=self._prompt),
            ChatMessage(
                role="user",
                content=(
                    f"QUESTION:\n{question_text}\nHINT_LEVEL: {hint_level}"
                    f"\nANSWER_SO_FAR:\n{answer_so_far}"
                ),
            ),
        ]
        hint, _ = await generate_structured(
            self.router, TaskClass.INTERVIEW_CONTENT_GENERATION, messages, HintOutput
        )
        return hint.hint
