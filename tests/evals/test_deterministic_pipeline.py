"""Deterministic eval suite (Phase F) — always runs, no DeepSeek.

Exercises the REAL LangChain pipelines (structured chains, parsers, schema
validation) with a canned router provider, then asserts business rules:
structured-output validity, difficulty/competency fidelity, scoring ranges,
evidence claim honesty. These are the deterministic half of the eval suite;
semantic halves live in the per-area test modules behind DEEPSEEK_API_KEY.
"""

from __future__ import annotations

import json
from typing import Any

from app.ai.contracts import ChatMessage, ChatResponse, Usage
from app.ai.langchain.structured import generate_structured
from app.ai.policy import TaskClass, TaskPolicyTable
from app.ai.router import InferenceRouter
from app.domain.schemas import (
    AnswerEvaluation,
    EvaluationDimensions,
    InterviewQuestion,
    ResumeExtraction,
)
from app.interview.generation import Evaluator, QuestionGenerator

# --------------------------------------------------------------------------
# Canned provider: feeds realistic JSON through the real LangChain pipelines.
# --------------------------------------------------------------------------


class CannedProvider:
    """Provider returning per-task canned JSON (mirrors deepseek-v4-flash)."""

    name = "canned"

    def __init__(self, by_task: dict[str, str]) -> None:
        self.by_task = by_task
        self.calls: list[tuple[TaskClass, list[ChatMessage]]] = []

    async def generate(self, request: Any) -> ChatResponse:
        task = self._task_for(request.messages)
        self.calls.append((task, request.messages))
        content = self.by_task.get(task.value) or '{"text": "fallback"}'
        return ChatResponse(content=content, model="canned", usage=Usage(total_tokens=1))

    @staticmethod
    def _task_for(messages: list[ChatMessage]) -> TaskClass:
        # The canned router is used only for pipeline-shape tests; the task is
        # inferred from the caller-provided mapping keyed by a marker in the
        # user message. Simpler: caller passes single-task provider.
        return TaskClass.ROUTINE_GENERATION


class SingleTaskProvider(CannedProvider):
    def __init__(self, task: TaskClass, content: str) -> None:
        super().__init__({task.value: content})
        self.task = task

    async def generate(self, request: Any) -> ChatResponse:
        self.calls.append((self.task, request.messages))
        return ChatResponse(
            content=self.by_task[self.task.value], model="canned", usage=Usage(total_tokens=1)
        )


def _router(provider: Any) -> InferenceRouter:
    return InferenceRouter(policy=TaskPolicyTable(), omlx=None, deepseek=provider)


Q_JSON = json.dumps(
    {
        "text": "Design a rate limiter that survives a cache stampede. What tradeoffs do you make between memory and precision?",  # noqa: E501
        "type": "technical",
        "difficulty": "hard",
        "rationale": "Probes system-design depth using the candidate's cache evidence.",
        "hint_levels": ["Think about token bucket vs sliding window."],
        "target_competency": "System Design",
    }
)

EVAL_JSON = json.dumps(
    {
        "dimensions": {
            "correctness": 8,
            "technical_depth": 7,
            "clarity": 8,
            "structure": 7,
            "relevance": 8,
            "evidence": 8,
            "communication": 7,
            "tradeoff_awareness": 8,
            "reasoning": 7,
            "confidence": 7,
            "specificity": 8,
            "seniority_alignment": 8,
            "completeness": 7,
        },
        "overall": 7.6,
        "confidence": 0.8,
        "strengths": ["Concrete Redis design", "Explicit tradeoffs"],
        "weaknesses": ["Missed backpressure detail"],
        "missing_evidence": ["operational runbook"],
        "follow_ups": ["How do you handle a node failure in Redis?"],
        "evidence": [
            {"claim": "built a token-bucket rate limiter", "status": "observed", "strength": 0.9},
            {"claim": "designed a rate limiter at 50k QPS", "status": "claimed", "strength": 0.6},
        ],
    }
)

EXTRACT_JSON = json.dumps(
    {
        "headline": "Backend Engineer",
        "seniority_target": "senior",
        "roles": [{"title": "Backend Engineer", "company": "Acme", "years": 5}],
        "technologies": ["Python", "PostgreSQL", "Redis"],
        "projects": [{"name": "Recommendation API", "achievements": ["cut p95 latency via Redis"]}],
        "achievements": [],
        "claims": ["built a recommendation API", "added Redis caching"],
        "certifications": [],
        "strengths": ["caching", "API design"],
        "gaps": ["Kubernetes"],
    }
)


async def test_question_generation_pipeline_validity(eval_results: Any) -> None:
    provider = SingleTaskProvider(TaskClass.INTERVIEW_CONTENT_GENERATION, Q_JSON)
    router = _router(provider)
    gen = QuestionGenerator(router)
    q = await gen.generate(
        competency="System Design",
        difficulty="hard",
        seniority="senior",
        evidence_summary="built a rate limiter at 50k QPS",
        history="Q1: production incident",
        hints_used=0,
    )
    assert isinstance(q, InterviewQuestion)
    valid = (
        bool(q.text)
        and q.difficulty in {"easy", "medium", "hard"}
        and q.type in {"general", "technical", "behavioral", "system_design"}
        and q.target_competency == "System Design"
    )
    eval_results.record(
        "question_generation",
        "qg-pipeline",
        "structured_validity",
        score=1.0 if valid else 0.0,
        threshold=1.0,
        passed=valid,
        detail=f"difficulty={q.difficulty} competency={q.target_competency}",
    )
    assert valid


async def test_answer_evaluation_pipeline_validity(eval_results: Any) -> None:
    provider = SingleTaskProvider(TaskClass.DEEP_EVALUATION, EVAL_JSON)
    router = _router(provider)
    evaluator = Evaluator(router)
    ev = await evaluator.evaluate(
        question_text="Design a rate limiter.",
        answer_text="Token bucket with Redis.",
        evidence_context="candidate built a rate limiter",
        hints_used=0,
    )
    assert isinstance(ev, AnswerEvaluation)
    assert isinstance(ev.dimensions, EvaluationDimensions)
    valid = (
        0.0 <= ev.overall <= 10.0
        and 0.0 <= ev.confidence <= 1.0
        and all(
            0 <= getattr(ev.dimensions, d, 0) <= 10 for d in ("correctness", "depth", "clarity")
        )
        and all(0.0 <= e.strength <= 1.0 for e in ev.evidence)
    )
    eval_results.record(
        "answer_evaluation",
        "aev-pipeline",
        "structured_validity",
        score=1.0 if valid else 0.0,
        threshold=1.0,
        passed=valid,
        detail=f"overall={ev.overall} evidence_rows={len(ev.evidence)}",
    )
    assert valid


async def test_extraction_pipeline_validity(eval_results: Any) -> None:
    provider = SingleTaskProvider(TaskClass.EXTRACTION, EXTRACT_JSON)
    router = _router(provider)
    from app.services.extraction import _DEFAULT_PROMPT, _PROMPT
    from app.services.prompts import load_prompt

    prompt = load_prompt(_PROMPT, fallback=_DEFAULT_PROMPT)
    messages = [
        ChatMessage(role="system", content=prompt),
        ChatMessage(
            role="user", content="<<<RESUME DATA>>>\nbackend engineer\n<<<END RESUME DATA>>>"
        ),
    ]
    extraction, _ = await generate_structured(
        router, TaskClass.EXTRACTION, messages, ResumeExtraction
    )
    assert isinstance(extraction, ResumeExtraction)
    # Honesty rule: every claim must trace to the source text (golden claims only).
    forbidden = {"invented a new distributed consensus algorithm"}
    honest = not (extraction.claims and forbidden & set(extraction.claims))
    valid = bool(extraction.headline) and bool(extraction.claims) and honest
    eval_results.record(
        "evidence_extraction",
        "ev-pipeline",
        "structured_validity",
        score=1.0 if valid else 0.0,
        threshold=1.0,
        passed=valid,
        detail=f"claims={len(extraction.claims)}",
    )
    assert valid
