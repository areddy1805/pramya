"""Interview question generation (Phase 3.3) + evaluation (3.4) + hints (3.5).

All LLM output goes through generate_structured: validated Pydantic before
any persistence. Prompts live in the prompts/ tree.
"""

from __future__ import annotations

import json
import logging

from app.ai.contracts import ChatMessage
from app.ai.policy import TaskClass
from app.ai.router import InferenceRouter
from app.ai.structured import generate_structured
from app.core.logging import get_logger
from app.domain.schemas import AnswerEvaluation, HintOutput, InterviewQuestion
from app.services.prompts import load_prompt

_Q_PROMPT = "question_generation/adaptive_question.txt"
_EVAL_PROMPT = "answer_evaluation/answer_eval.txt"
_HINT_PROMPT = "question_generation/hint.txt"


class QuestionGenerator:
    """Adaptive question generation (pramya-4b, INTERVIEW_CONTENT_GENERATION)."""

    def __init__(self, router: InferenceRouter, *, logger: logging.Logger | None = None) -> None:
        self.router = router
        self._logger = logger or get_logger("app.interview.questions")
        self._prompt = load_prompt(_Q_PROMPT, fallback="Generate one adaptive interview question.")

    async def generate(
        self,
        *,
        competency: str,
        difficulty: str,
        seniority: str,
        evidence_summary: str,
        history: str,
        hints_used: int,
    ) -> InterviewQuestion:
        context = {
            "target_competency": competency,
            "difficulty": difficulty,
            "seniority": seniority,
            "evidence_summary": evidence_summary,
            "session_history": history,
            "hints_used_so_far": hints_used,
        }
        messages = [
            ChatMessage(role="system", content=self._prompt),
            ChatMessage(role="user", content=json.dumps(context, default=str)),
        ]
        question, _ = await generate_structured(
            self.router, TaskClass.INTERVIEW_CONTENT_GENERATION, messages, InterviewQuestion
        )
        return question


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
        evaluation, _ = await generate_structured(
            self.router, TaskClass.DEEP_EVALUATION, messages, AnswerEvaluation
        )
        return evaluation


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
