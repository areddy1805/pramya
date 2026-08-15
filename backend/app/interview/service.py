# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownParameterType=false
# Scoped to JSONB session-config flows (dict[str, Any] over the config column);
# real contract errors (arg-type/assignment) still surface, and mypy is clean.
"""Interview service — orchestrates the text interview lifecycle (Phase 3).

Created -> planning -> questioning (answer/hint/evaluate loop) ->
completed | cancelled | error. State transitions enforced by
app.interview.state; every answer is idempotency-keyed; evaluations are
append-only + versioned; evidence from answers persists with provenance.

SSE events: each action appends typed events to the session's event sink.
The sink is an in-memory per-session queue (single-process dev runtime);
state remains fully DB-backed so refresh/reconnect can rebuild from rows.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.router import InferenceRouter
from app.core.logging import get_logger
from app.domain.enums import (
    EvidenceSourceKind,
    EvidenceStatus,
    InterviewKind,
    InterviewSessionStatus,
    InterviewTurnKind,
    QuestionDifficulty,
    QuestionType,
)
from app.domain.errors import InterviewStateError, NotFoundError, ValidationFailedError
from app.domain.schemas import (
    AnswerEvaluation,
    InterviewQuestion,
)
from app.interview.generation import Evaluator, Hints, QuestionGenerator
from app.interview.state import transition
from app.interview.workflow import build_interview_workflow
from app.knowledge.retrieval import RetrievalService
from app.models.evidence import Evidence
from app.models.interview import (
    Answer,
    Evaluation,
    InterviewSession,
    InterviewTurn,
    Question,
)
from app.models.interview_feedback import InterviewFeedback
from app.repositories.evidence import EvidenceRepository
from app.repositories.interview import (
    AnswerRepository,
    EvaluationRepository,
    InterviewSessionRepository,
    InterviewTurnRepository,
    QuestionRepository,
)
from app.repositories.misc import InterviewFeedbackRepository, RoleRepository
from app.services.coverage import (
    INTERVIEW_STYLES,
    compute_gaps,
    detect_invented_entities,
    focus_competency,
    jd_skill_matches,
    mark_asked,
    new_coverage,
    normalize_source,
)
from app.services.idempotency import IdempotencyService
from app.services.interview_context import InterviewContextBuilder, resume_signals
from app.services.prompts import load_prompt

_PLAN_PROMPT = "interview_planning/session_plan.txt"


@dataclass(frozen=True)
class InterviewEvent:
    """One typed SSE event payload."""

    type: str
    data: dict[str, object]

    def serialize(self) -> str:
        return f"event: {self.type}\ndata: {json.dumps(self.data, default=str)}\n\n"


def _top_aggregate(items: list[str], limit: int = 5) -> list[str]:
    """Most frequently mentioned items, stable order (deterministic)."""
    counts: dict[str, int] = {}
    for item in items:
        counts[item] = counts.get(item, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [item for item, _ in ranked[:limit]]


def _prep_recommendation(overall: float) -> str:
    """Derived per-question prep recommendation (deterministic)."""
    if overall >= 8:
        return "solid area — maintain and reuse as evidence"
    if overall >= 6:
        return "strengthen with one concrete example or metric"
    if overall >= 4:
        return "re-practice: build a STAR example and quantify the result"
    return "high priority: re-learn fundamentals, then practice with a mentor"


@dataclass
class ReportData:
    """Deterministic report v2 payload (typed; no LLM)."""

    scorecard: dict[str, object]
    questions: list[dict[str, object]]
    gaps: list[str]
    topics: list[str]
    directives: dict[str, object]


def _session_config(row: InterviewSession) -> dict[str, Any]:
    """Typed accessor for the JSONB session config (dict[str, Any])."""
    cfg = row.config
    return dict(cfg) if cfg is not None else {}


class EventBus:
    """Per-session in-memory event queues (single-process dev runtime).

    Long-run safety: queues are bounded and are removed when the last SSE
    consumer unsubscribes, so a session whose browser tab closed cannot grow
    its queue forever (voice interviews publish events even without an SSE
    listener).
    """

    _MAX_QUEUE = 2000

    def __init__(self) -> None:
        self._queues: dict[int, asyncio.Queue[InterviewEvent]] = {}
        self._consumers: dict[int, int] = {}

    def publish(self, session_id: int, event: InterviewEvent) -> None:
        queue = self._queues.get(session_id)
        if queue is None:
            return  # no subscriber: nothing to accumulate
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            # Bounded queue: drop the oldest event instead of growing memory
            # or blocking the producer (dev runtime; SSE is best-effort).
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def subscribe(self, session_id: int) -> asyncio.Queue[InterviewEvent]:
        if session_id not in self._queues:
            self._queues[session_id] = asyncio.Queue(maxsize=self._MAX_QUEUE)
            self._consumers[session_id] = 0
        self._consumers[session_id] += 1
        return self._queues[session_id]

    def unsubscribe(self, session_id: int) -> None:
        """Drop this consumer; remove the queue when the last one leaves."""
        remaining = self._consumers.get(session_id, 1) - 1
        if remaining <= 0:
            self._consumers.pop(session_id, None)
            self._queues.pop(session_id, None)
        else:
            self._consumers[session_id] = remaining


event_bus = EventBus()


@dataclass
class InterviewContext:
    """Wiring for one interview service instance."""

    router: InferenceRouter
    retrieval: RetrievalService | None = None
    storage_dir: Path | None = None


@dataclass
class TurnRecord:
    """One turn of the durable interview record (Phase K memory)."""

    seq: int
    kind: str
    question_id: int | None = None
    question: str | None = None
    answer: str | None = None
    evaluation_overall: float | None = None
    hints_used: int = 0


class InterviewService:
    """Stateful text interview lifecycle (authoritative session state)."""

    def __init__(
        self,
        session: AsyncSession,
        router: InferenceRouter,
        *,
        retrieval: RetrievalService | None = None,
        rag: Any | None = None,
        storage_dir: Path | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.session = session
        self.router = router
        self.retrieval = retrieval
        self.rag = rag  # LlamaIndex retriever (Phase D primary RAG path)
        self.storage_dir = storage_dir
        self._logger = logger or get_logger("app.interview.service")
        self.sessions = InterviewSessionRepository(session)
        self.turns = InterviewTurnRepository(session)
        self.questions = QuestionRepository(session)
        self.answers = AnswerRepository(session)
        self.evaluations = EvaluationRepository(session)
        self.evidence = EvidenceRepository(session)
        self.roles = RoleRepository(session)
        self.questions_gen = QuestionGenerator(router)
        self.evaluator = Evaluator(router)
        self.hints = Hints(router)
        self.idempotency = IdempotencyService(session)
        self._plan_prompt = load_prompt(_PLAN_PROMPT, fallback="Plan the interview session.")
        self.context_builder = InterviewContextBuilder(session, logger=logger)
        self.feedback = InterviewFeedbackRepository(session)
        # Phase C: the interview lifecycle executes through a LangGraph
        # workflow (application layer); this service stays the domain/
        # invariant layer (state transitions, persistence, SSE events).
        self.workflow: Any = build_interview_workflow(router, retrieval=retrieval)

    # -- lifecycle -----------------------------------------------------------

    async def create_session(
        self,
        *,
        user_id: int,
        kind: InterviewKind,
        role_id: int | None,
        duration_minutes: int,
        focus_competency_ids: list[int],
        mode: str = "text",
        profile_id: int | None = None,
        style: str = "structured",
    ) -> InterviewSession:
        if style not in INTERVIEW_STYLES:
            raise ValidationFailedError(
                "unknown interview style",
                details={"style": style, "allowed": list(INTERVIEW_STYLES)},
            )
        session_row = InterviewSession(
            user_id=user_id,
            candidate_profile_id=profile_id,
            role_id=role_id,
            kind=kind,
            status=InterviewSessionStatus.CREATED,
            started_at=datetime.now(UTC),
            config={
                "duration_minutes": duration_minutes,
                "focus_competency_ids": focus_competency_ids,
                "mode": mode,
                "style": style,
            },
            graph_thread_id=f"thread-{kind.value}-{uuid.uuid4().hex[:12]}",
        )
        await self.sessions.add(session_row)
        await self.session.commit()
        event_bus.publish(
            session_row.id,
            InterviewEvent("session_status", {"status": "created", "session_id": session_row.id}),
        )
        return session_row

    async def begin(self, session_id: int, user_id: int) -> InterviewSession:
        """PLANNING -> first question (QUESTIONING).

        Builds + persists the immutable grounding snapshot (profile-scoped
        context) the first time; subsequent calls reuse it.
        """
        row = await self._owned_session(session_id, user_id)
        await self._ensure_context(row)
        if row.status == InterviewSessionStatus.CREATED:
            transition(row.status, InterviewSessionStatus.PLANNING)
            row.status = InterviewSessionStatus.PLANNING
            await self.session.flush()
        transition(row.status, InterviewSessionStatus.QUESTIONING)
        row.status = InterviewSessionStatus.QUESTIONING
        await self.session.flush()
        event_bus.publish(session_id, InterviewEvent("graph_node", {"node": "questioning"}))
        await self.session.commit()
        return row

    async def next_question(self, session_id: int, user_id: int) -> tuple[Question, InterviewTurn]:
        """Generate + persist the next adaptive question via the LangGraph workflow."""
        row = await self._require_questioning(session_id, user_id)
        await self._ensure_context(row)
        history = await self._history_text(session_id)
        input_state = await self._question_input_state(row, history)
        state = await self.workflow.ainvoke(
            input_state,
            config={"configurable": {"thread_id": row.graph_thread_id or f"s{session_id}"}},
        )
        question = self._question_from_state(state, input_state["competency"])
        # Anti-hallucination guard (text path): regenerate once if the model
        # invented entities absent from the grounding context.
        question = await self._guard_question(row, input_state, state, question)
        q, turn = await self._persist_question(question, session_id, input_state["competency"])
        return q, turn

    async def next_question_streaming(
        self, session_id: int, user_id: int
    ) -> AsyncIterator[tuple[str, object]]:
        """Stream the next question (V1.1 realtime path).

        Yields ("token", str) for every model token chunk surfaced by the
        LangGraph workflow (stream_mode="messages"), then a final
        ("question", (Question, InterviewTurn)) after persistence. The voice
        engine consumes tokens through the segmenter and starts TTS on the
        first complete sentence while the rest of the response streams.
        """
        row = await self._require_questioning(session_id, user_id)
        await self._ensure_context(row)
        history = await self._history_text(session_id)
        input_state = await self._question_input_state(row, history)
        config = {"configurable": {"thread_id": row.graph_thread_id or f"s{session_id}"}}
        async for event in self.workflow.astream(input_state, config, stream_mode="messages"):
            message, _meta = event
            content = getattr(message, "content", "")
            if isinstance(content, str) and content:
                yield ("token", content)
        state = await self.workflow.aget_state(config)
        values = state.values if hasattr(state, "values") else state
        question = self._question_from_state(values, input_state["competency"])
        # Streaming path: tokens already reached the voice engine — guard
        # only logs (prompt strictness + context fidelity tests cover it).
        await self._guard_question(row, input_state, values, question, regenerate=False)
        q, turn = await self._persist_question(question, session_id, input_state["competency"])
        yield ("question", (q, turn))

    # -- question planning helpers (productization) --------------------------

    async def _question_input_state(self, row: InterviewSession, history: str) -> dict[str, Any]:
        """Build the full question-lane graph input: grounding snapshot +
        coverage + novelty + follow-up directive + style + time budget."""
        ctx = _session_config(row)
        snapshot = ctx.get("context") or {}
        evidence_summary = self._evidence_summary_from_snapshot(snapshot)
        comp = await self._next_focus(row, snapshot, ctx)
        novelty = await self._novelty(session_id=row.id)
        latest_directive = self._latest_directive(ctx)
        questions_asked = len(novelty)
        duration = int(ctx.get("duration_minutes") or 30)
        time_budget = {
            "minutes": duration,
            "questions_asked": questions_asked,
            "estimated_remaining": max(0, duration - questions_asked * 3),
        }
        return {
            "session_id": row.id,
            "user_id": row.user_id,
            "action": "question",
            "history": history,
            "evidence_summary": evidence_summary,
            "competency": comp or "general",
            "difficulty": "medium",
            "seniority": self._seniority(snapshot, row),
            "profile_id": row.candidate_profile_id,
            "context": snapshot,
            "style": ctx.get("style") or "structured",
            "coverage": ctx.get("coverage") or new_coverage(),
            "novelty": novelty,
            "follow_up_directive": latest_directive,
            "time_budget": time_budget,
            "hints_used": 0,
        }

    @staticmethod
    def _question_from_state(state: dict[str, Any], default_competency: str) -> InterviewQuestion:
        return InterviewQuestion(
            text=state.get("question_text") or "",
            type=state.get("question_type") or "general",
            difficulty=state.get("question_difficulty") or "medium",
            hint_levels=state.get("hint_levels") or [],
            rationale=state.get("rationale"),
            target_competency=state.get("target_competency") or default_competency,
            category=state.get("question_category"),
            source=normalize_source(state.get("question_source")),
            source_ref=state.get("question_source_ref"),
        )

    async def _guard_question(
        self,
        row: InterviewSession,
        input_state: dict[str, Any],
        state: dict[str, Any],
        question: InterviewQuestion,
        *,
        regenerate: bool = True,
    ) -> InterviewQuestion:
        """Minimal deterministic entity guard (step 9). Regenerates once on
        the text path when the model invented capitalized entities; on the
        streaming path (voice) it can only warn — tokens already streamed."""
        snapshot = input_state.get("context") or {}
        offenders = detect_invented_entities(question.text, snapshot)
        if not offenders:
            return question
        self._logger.warning(
            "question mentions entities absent from grounding context",
            extra={"session_id": row.id, "offenders": offenders[:8]},
        )
        if not regenerate:
            return question
        retry = input_state.copy()
        retry["retry_note"] = (
            "Your previous question mentioned terms absent from the candidate's "
            f"material ({', '.join(offenders[:5])}). Rephrase: ground the "
            "question strictly in the supplied context."
        )
        retry_state = await self.workflow.ainvoke(
            retry,
            config={"configurable": {"thread_id": row.graph_thread_id or f"s{row.id}"}},
        )
        retry_question = self._question_from_state(retry_state, input_state["competency"])
        retry_offenders = detect_invented_entities(retry_question.text, snapshot)
        if retry_offenders:
            # Fallback: keep the retry (prompt strictness is the primary
            # anti-hallucination control; the guard is best-effort).
            self._logger.warning(
                "retry still references unknown entities; accepting with warning",
                extra={"session_id": row.id, "offenders": retry_offenders[:8]},
            )
        return retry_question

    @staticmethod
    def _evidence_summary_from_snapshot(snapshot: dict[str, object]) -> str:
        evidence = snapshot.get("evidence")
        if not isinstance(evidence, list):
            return "no evidence yet"
        claims = [str(e.get("claim", "")) for e in evidence if isinstance(e, dict)]
        return " | ".join(claims) if claims else "no evidence yet"

    @staticmethod
    def _competencies(snapshot: dict[str, object]) -> list[str]:
        role = snapshot.get("role")
        if not isinstance(role, dict):
            return []
        return [
            str(c.get("name", ""))
            for c in (role.get("competencies") or [])
            if isinstance(c, dict) and c.get("name")
        ]

    @staticmethod
    def _seniority(snapshot: dict[str, object], row: InterviewSession) -> str:
        role = snapshot.get("role")
        if isinstance(role, dict) and role.get("seniority"):
            return str(role["seniority"])
        profile = snapshot.get("profile")
        if isinstance(profile, dict) and profile.get("seniority_target"):
            return str(profile["seniority_target"])
        return "mid"

    async def _next_focus(
        self, row: InterviewSession, snapshot: dict[str, object], ctx: dict[str, Any]
    ) -> str | None:
        """Focus selection: follow-up topic preference first, then rotation
        over uncovered competencies, seeded by session id (deterministic)."""
        comps = self._competencies(snapshot)
        if not comps:
            # Legacy path: role competencies from the role graph.
            if row.role_id:
                role = await self.roles.get(row.role_id)
                if role is not None:
                    comps = [c.name for c in await self.roles.list_competencies(role.id)]
        if not comps:
            return None
        directive = self._latest_directive(ctx)
        topic = directive.get("topic") if isinstance(directive, dict) else None
        coverage = ctx.get("coverage") or new_coverage()
        # Seeded, non-cryptographic: deterministic per-session focus selection
        # (reproducible interviews) — not used for security.
        rng = random.Random(row.id)  # noqa: S311
        return focus_competency(coverage, comps, rng, follow_up_topic=topic)

    @staticmethod
    def _latest_directive(ctx: dict[str, Any]) -> dict[str, Any] | None:
        directives = ctx.get("directives")
        if not isinstance(directives, dict) or not directives:
            return None
        latest_qid = max((int(k) for k in directives if str(k).isdigit()), default=None)
        if latest_qid is None:
            return None
        value = directives.get(str(latest_qid))
        return value if isinstance(value, dict) else None

    async def _novelty(self, *, session_id: int) -> list[str]:
        questions = await self.questions.list_for_session(session_id)
        seen: list[str] = []
        for q in questions:
            for value in (q.target_competency, q.category):
                if value and value not in seen:
                    seen.append(value)
        return seen

    async def _ensure_context(self, row: InterviewSession) -> None:
        """Build + persist the immutable grounding snapshot on first use."""
        if not row.config or not row.config.get("context"):
            snapshot = await self.context_builder.build(
                user_id=row.user_id,
                profile_id=row.candidate_profile_id,
                role_id=row.role_id,
            )
            cfg = _session_config(row)
            cfg["context"] = snapshot
            cfg.setdefault("coverage", new_coverage())
            cfg.setdefault("gaps", [])
            cfg.setdefault("directives", {})
            row.config = cfg
            await self.session.flush()

    async def _persist_question(
        self, question: InterviewQuestion, session_id: int, default_competency: str
    ) -> tuple[Question, InterviewTurn]:
        q = Question(
            interview_session_id=session_id,
            competency_id=None,
            difficulty=QuestionDifficulty(question.difficulty),
            type=QuestionType(question.type),
            text=question.text,
            hint_levels=question.hint_levels,
            rationale=question.rationale,
            category=question.category,
            source=question.source,
            source_ref=question.source_ref,
            target_competency=question.target_competency,
        )
        await self.questions.add(q)
        seq = (await self.turns.max_seq(session_id)) + 1
        turn = InterviewTurn(
            interview_session_id=session_id,
            seq=seq,
            kind=InterviewTurnKind.QUESTION,
            content=question.text,
        )
        await self.turns.add(turn)
        q.turn_id = turn.id
        await self.session.flush()
        # Coverage tracking (deterministic): record what was asked so the
        # next focus selection rotates over uncovered competencies.
        await self._mark_coverage(session_id, question)
        event_bus.publish(
            session_id,
            InterviewEvent(
                "question",
                {
                    "question_id": q.id,
                    "text": q.text,
                    "difficulty": question.difficulty,
                    "rationale": question.rationale,
                    "category": question.category,
                    "source": question.source,
                },
            ),
        )
        await self.session.commit()
        return q, turn

    async def _mark_coverage(self, session_id: int, question: InterviewQuestion) -> None:
        """Update session.config["coverage"] with the asked question."""
        row = await self.sessions.get_or_raise(session_id, name="interview session")
        cfg = _session_config(row)
        coverage = dict(cfg.get("coverage") or new_coverage())
        snapshot = cfg.get("context") or {}
        signals = resume_signals(snapshot.get("evidence") or [])
        jd_text = None
        jd = snapshot.get("jd")
        if isinstance(jd, dict):
            jd_text = str(jd.get("text", ""))
        matched = jd_skill_matches(signals.get("technologies", []), jd_text)
        mark_asked(
            coverage,
            category=question.category,
            competency=question.target_competency,
            jd_skill=(str(question.source_ref) if question.source == "jd" else None),
            project=(str(question.source_ref) if question.source == "resume" else None),
            source_ref=question.source_ref,
        )
        coverage.setdefault("jd_skills", [])
        for skill in matched:
            mark_asked(coverage, category=None, competency=None, jd_skill=skill)
        cfg["coverage"] = coverage
        row.config = cfg

    async def submit_answer(
        self,
        session_id: int,
        user_id: int,
        *,
        question_id: int,
        answer_text: str,
        idempotency_key: str | None,
        mode: str = "text",
        await_evaluation: bool = True,
    ) -> Answer:
        """Idempotent answer submission; evaluation is optional (two-lane).

        ``await_evaluation=True`` (text API): the answer is recorded and the
        LangGraph evaluation workflow runs inline before returning — V1
        behavior. ``await_evaluation=False`` (voice realtime path): the
        answer + turn are durably committed and the method returns
        immediately; the caller runs evaluation as a background analytical
        task (never blocks the next-question critical path).
        """
        if not answer_text.strip():
            raise ValidationFailedError("answer must not be empty")
        await self._require_questioning(session_id, user_id)
        q = await self.questions.get_or_raise(question_id, name="question")
        if q.interview_session_id != session_id:
            raise NotFoundError("question not found in this session")
        existing = await self.answers.get_by_question(question_id)
        if existing is not None:
            # Idempotent replay: key was recorded on first submission; the
            # same answer row is returned without re-recording.
            return existing
        if idempotency_key:
            await self.idempotency.check_and_record(
                scope=f"answer:{session_id}",
                key=idempotency_key,
                payload={"question_id": question_id},
            )

        seq = (await self.turns.max_seq(session_id)) + 1
        turn = InterviewTurn(
            interview_session_id=session_id,
            seq=seq,
            kind=InterviewTurnKind.ANSWER,
            content=answer_text,
        )
        await self.turns.add(turn)
        answer = Answer(
            question_id=question_id,
            interview_turn_id=turn.id,
            text=answer_text,
            mode=mode,
        )
        await self.answers.add(answer)
        await self.session.flush()
        await self.session.commit()  # durable before the caller proceeds
        if not await_evaluation:
            return answer
        await self.evaluate_answer(
            session_id, user_id, question_id=question_id, answer_text=answer_text
        )
        return answer

    async def evaluate_answer(
        self,
        session_id: int,
        user_id: int,
        *,
        question_id: int,
        answer_text: str,
        hints_used: int = 0,
    ) -> AnswerEvaluation:
        """Analytical lane: LangGraph answer workflow -> persisted evaluation.

        Runs retrieve_context -> evaluate_answer -> extract_evidence ->
        update_candidate_state -> determine_next_action, then persists the
        evaluation + evidence rows. Safe to run as a background task AFTER
        the answer is durably committed (no stale-state race: the next
        question reads the committed answer turn, not this evaluation).
        """
        await self._require_questioning(session_id, user_id)
        q = await self.questions.get_or_raise(question_id, name="question")
        if q.interview_session_id != session_id:
            raise NotFoundError("question not found in this session")
        answer = await self.answers.get_by_question(question_id)
        if answer is None:
            raise NotFoundError("answer not found for question")
        row = await self.sessions.get_or_raise(session_id, name="interview session")
        await self._ensure_context(row)
        ctx = _session_config(row)
        snapshot = ctx.get("context") or {}
        # Evaluation is the analytical lane (never blocks the next-question
        # stream): a transient provider failure gets ONE bounded retry before
        # surfacing — the answer is already durably committed.
        from app.ai.errors import StructuredOutputError

        state: dict[str, Any] = {}
        for _attempt in range(2):
            try:
                state = await self.workflow.ainvoke(
                    {
                        "session_id": session_id,
                        "user_id": user_id,
                        "action": "answer",
                        "question_text": q.text,
                        "answer_text": answer_text,
                        "hints_used": hints_used,
                        "history": "",
                        "evidence_summary": "",
                        "competency": q.target_competency or "",
                        "difficulty": str(q.difficulty),
                        "seniority": "",
                        "profile_id": row.candidate_profile_id,
                        "context": snapshot,
                        "style": ctx.get("style") or "structured",
                        "coverage": ctx.get("coverage") or new_coverage(),
                    },
                    config={"configurable": {"thread_id": f"s{session_id}"}},
                )
                break
            except StructuredOutputError:
                if _attempt == 0:
                    self._logger.warning(
                        "answer evaluation transient failure; retrying once",
                        extra={"session_id": session_id, "question_id": question_id},
                    )
                    continue
                raise
        evaluation = AnswerEvaluation.model_validate(state["evaluation"] or {})
        await self._persist_evaluation(q, answer, evaluation, hints_used)
        # Follow-up directive + gap detection (productization steps 4/6):
        # persist interviewer reasoning per question, consumed by the next
        # question; update session gaps deterministically.
        await self._persist_directive(session_id, question_id, state)
        await self._update_gaps(session_id, row, state)
        await self.session.commit()
        event_bus.publish(
            session_id,
            InterviewEvent(
                "evaluation",
                {
                    "answer_id": answer.id,
                    "overall": evaluation.overall,
                    "next_action": state.get("next_action"),
                },
            ),
        )
        return evaluation

    async def _persist_directive(
        self, session_id: int, question_id: int, state: dict[str, Any]
    ) -> None:
        """Store interviewer reasoning per answered question in
        session.config["directives"] (permanent record; latest is consumed
        by the next question)."""
        reasoning = state.get("interviewer_reasoning")
        if not isinstance(reasoning, dict):
            return
        row = await self.sessions.get_or_raise(session_id, name="interview session")
        cfg = _session_config(row)
        directives = dict(cfg.get("directives") or {})
        directives[str(question_id)] = {
            "decision": reasoning.get("decision"),
            "reason": reasoning.get("reason"),
            "topic": reasoning.get("topic"),
            "gaps_detected": reasoning.get("gaps_detected") or [],
            "coverage_tags": reasoning.get("coverage_tags") or [],
            "next_action": state.get("next_action"),
        }
        cfg["directives"] = directives
        row.config = cfg

    async def _update_gaps(
        self, session_id: int, row: InterviewSession, state: dict[str, Any]
    ) -> None:
        """Deterministic gap detection: JD-required competencies uncovered
        (no evidence, not asked) + interviewer-detected gaps."""
        ctx = _session_config(row)
        snapshot = ctx.get("context") or {}
        reasoning = state.get("interviewer_reasoning") or {}
        reasoning_gaps = reasoning.get("gaps_detected") or []
        gaps = compute_gaps(snapshot, ctx.get("coverage") or new_coverage(), reasoning_gaps)
        cfg = dict(ctx)
        cfg["gaps"] = gaps
        row.config = cfg

    async def request_hint(self, session_id: int, user_id: int, question_id: int) -> str:
        await self._require_questioning(session_id, user_id)
        q = await self.questions.get_or_raise(question_id, name="question")
        if q.interview_session_id != session_id:
            raise NotFoundError("question not found in this session")
        turn = await self.turns.get(q.turn_id) if q.turn_id else None
        used = turn.hints_used if turn else 0
        state = await self.workflow.ainvoke(
            {
                "session_id": session_id,
                "user_id": user_id,
                "action": "hint",
                "question_text": q.text,
                "hints_used": used,
                "history": "",
                "evidence_summary": "",
                "competency": "",
                "difficulty": "",
                "seniority": "",
            },
            config={"configurable": {"thread_id": f"s{session_id}"}},
        )
        hint = state.get("hint") or ""
        if turn is not None:
            turn.hints_used = used + 1
        await self.session.flush()
        await self.session.commit()
        event_bus.publish(
            session_id, InterviewEvent("hint", {"question_id": question_id, "hint": hint})
        )
        return hint

    async def pause(self, session_id: int, user_id: int) -> InterviewSession:
        row = await self._owned_session(session_id, user_id)
        transition(row.status, InterviewSessionStatus.PAUSED)
        row.status = InterviewSessionStatus.PAUSED
        await self.session.commit()
        event_bus.publish(session_id, InterviewEvent("session_status", {"status": "paused"}))
        return row

    async def resume(self, session_id: int, user_id: int) -> InterviewSession:
        row = await self._owned_session(session_id, user_id)
        transition(row.status, InterviewSessionStatus.QUESTIONING)
        row.status = InterviewSessionStatus.QUESTIONING
        await self.session.commit()
        event_bus.publish(session_id, InterviewEvent("session_status", {"status": "questioning"}))
        return row

    async def stop(self, session_id: int, user_id: int) -> InterviewSession:
        """Complete the session (evaluations kept; report available).

        Writes the prep-memory row (interview_feedback) for the profile:
        weaknesses/gaps/topics + avg overall — the next session's context
        builder reads the latest 3 rows and re-probes prior weak areas.
        """
        row = await self._owned_session(session_id, user_id)
        transition(row.status, InterviewSessionStatus.COMPLETED)
        row.status = InterviewSessionStatus.COMPLETED
        row.ended_at = datetime.now(UTC)
        await self._write_feedback(row)
        await self.session.commit()
        event_bus.publish(session_id, InterviewEvent("session_status", {"status": "completed"}))
        return row

    async def _write_feedback(self, row: InterviewSession) -> None:
        """Deterministic prep-memory aggregation (no LLM): weaknesses from
        evaluation rows, gaps from config, topics from coverage, avg."""
        evals = await self._evaluations_for_session(row.id)
        if not evals:
            return
        weaknesses: list[str] = []
        overalls: list[float] = []
        for ev in evals:
            for w in ev.weaknesses or []:
                if w not in weaknesses:
                    weaknesses.append(w)
            overalls.append(float(ev.overall))
        cfg = _session_config(row)
        gaps = list(cfg.get("gaps") or [])
        coverage = cfg.get("coverage") or {}
        topics = list(coverage.get("categories") or [])
        feedback = InterviewFeedback(
            user_id=row.user_id,
            profile_id=row.candidate_profile_id,
            session_id=row.id,
            weaknesses=weaknesses[:25],
            gaps=gaps[:25],
            topics=topics[:25],
            avg_overall=round(sum(overalls) / len(overalls), 2) if overalls else None,
        )
        self.session.add(feedback)
        await self.session.flush()

    async def cancel(self, session_id: int, user_id: int) -> InterviewSession:
        row = await self._owned_session(session_id, user_id)
        transition(row.status, InterviewSessionStatus.CANCELLED)
        row.status = InterviewSessionStatus.CANCELLED
        row.ended_at = datetime.now(UTC)
        await self.session.commit()
        event_bus.publish(session_id, InterviewEvent("session_status", {"status": "cancelled"}))
        return row

    # -- report --------------------------------------------------------------

    async def generate_report(self, session_id: int, user_id: int) -> str:
        """Final synthesis narrative (deepseek FINAL_SYNTHESIS; 4B fallback).

        The structured scorecard + per-question feedback come from
        ``report_data()`` (deterministic); this LLM call adds the narrative.
        """
        await self._owned_session(session_id, user_id)
        evals = await self._evaluations_for_session(session_id)
        if not evals:
            raise ValidationFailedError("no evaluations to report")
        data = await self.report_data(session_id, user_id)
        summary_lines = [
            f"Q: {row['question']}\nA: {row['answer']}\nOverall: {row['overall']}/10"
            for row in data.questions
        ]
        scorecard = data.scorecard
        gaps = data.gaps
        transcript = await self._history_text(session_id)

        # Phase C: report synthesis is the graph's generate_report node
        # (LangChain text_chain -> RouterChatModel -> InferenceRouter -> DeepSeek).
        row = await self._owned_session(session_id, user_id)
        state = await self.workflow.ainvoke(
            {
                "session_id": session_id,
                "user_id": user_id,
                "action": "report",
                "report_input": (
                    "SCORECARD:\n"
                    + "\n".join(f"{k}: {v}/10" for k, v in scorecard.items())
                    + "\n\nGAPS:\n"
                    + ("\n".join(gaps) if gaps else "none detected")
                    + "\n\nSESSION SUMMARY:\n"
                    + "\n---\n".join(summary_lines)
                    + "\n\nTRANSCRIPT:\n"
                    + transcript
                ),
                "history": transcript,
                "evidence_summary": "",
                "competency": "",
                "difficulty": "",
                "seniority": "",
                "hints_used": 0,
            },
            config={"configurable": {"thread_id": row.graph_thread_id or f"s{session_id}"}},
        )
        return state.get("report") or ""

    async def report_data(self, session_id: int, user_id: int) -> ReportData:
        """Deterministic report v2: scorecard + per-question feedback
        (step 7). No LLM: per-dimension averages, per-question strengths /
        missing / expected follow-ups, derived prep recommendation, gaps.
        """
        await self._owned_session(session_id, user_id)
        evals = await self._evaluations_for_session(session_id)
        if not evals:
            raise ValidationFailedError("no evaluations to report")
        row = await self.sessions.get_or_raise(session_id, name="interview session")
        cfg = _session_config(row)
        gaps = [str(g) for g in (cfg.get("gaps") or [])]
        coverage = cfg.get("coverage") or {}
        topics = [str(t) for t in (coverage.get("categories") or [])]

        # Dimension averages across evaluations.
        dims: dict[str, list[float]] = {}
        overalls: list[float] = []
        all_strengths: list[str] = []
        all_weaknesses: list[str] = []
        for ev in evals:
            overalls.append(float(ev.overall))
            for k, v in (ev.dimensions or {}).items():
                if isinstance(v, (int, float)):
                    dims.setdefault(str(k), []).append(float(v))
            all_strengths.extend(str(s) for s in (ev.strengths or []))
            all_weaknesses.extend(str(w) for w in (ev.weaknesses or []))
        scorecard: dict[str, object] = {
            k: round(sum(v) / len(v), 1) for k, v in sorted(dims.items())
        }
        if overalls:
            scorecard["overall"] = round(sum(overalls) / len(overalls), 1)
        scorecard["top_strengths"] = _top_aggregate(all_strengths)
        scorecard["top_weaknesses"] = _top_aggregate(all_weaknesses)

        questions: list[dict[str, object]] = []
        for ev in evals:
            answer = await self.answers.get(ev.answer_id)
            if answer is None:
                continue
            q = await self.questions.get(answer.question_id) if answer.question_id else None
            overall = float(ev.overall)
            questions.append(
                {
                    "question_id": q.id if q else None,
                    "question": q.text if q else "(question unavailable)",
                    "category": q.category if q else None,
                    "source": q.source if q else None,
                    "answer": answer.text,
                    "overall": overall,
                    "good": list(ev.strengths or [])[:5],
                    "missing": list((ev.weaknesses or []) + (ev.missing_evidence or []))[:6],
                    "expected_follow_ups": list(ev.follow_ups or [])[:4],
                    "prep_recommendation": _prep_recommendation(overall),
                }
            )
        directives = cfg.get("directives")
        return ReportData(
            scorecard=scorecard,
            questions=questions,
            gaps=gaps,
            topics=topics,
            directives=directives if isinstance(directives, dict) else {},
        )

    # -- internals -----------------------------------------------------------

    async def _owned_session(self, session_id: int, user_id: int) -> InterviewSession:
        row = await self.sessions.get_or_raise(session_id, name="interview session")
        if row.user_id != user_id:
            raise NotFoundError("interview session not found")
        return row

    async def _require_questioning(self, session_id: int, user_id: int) -> InterviewSession:
        row = await self._owned_session(session_id, user_id)
        if row.status not in (
            InterviewSessionStatus.QUESTIONING,
            InterviewSessionStatus.INTERRUPTED,
        ):
            raise InterviewStateError(
                f"session not in questioning state ({row.status})",
                details={"session_id": session_id, "status": str(row.status)},
            )
        return row

    async def transcript(self, session_id: int, user_id: int) -> list[TurnRecord]:
        """Phase K: durable interview record (memory) — questions, answers,
        evaluations, hint usage per turn, in seq order. Ownership-checked."""
        await self._owned_session(session_id, user_id)
        turns = await self.turns.list_for_session(session_id)
        questions = {q.id: q for q in await self.questions.list_for_session(session_id)}
        question_by_turn = {q.turn_id: q for q in questions.values()}
        answers = await self.answers.list_for_session(session_id)
        answers_by_turn = {a.interview_turn_id: a for a in answers if a.interview_turn_id}
        evaluations: dict[int, float] = {}
        for answer in answers:
            ev = await self.evaluations.get_by_answer(answer.id)
            if ev is not None:
                evaluations[answer.id] = float(ev.overall)
        records: list[TurnRecord] = []
        for turn in sorted(turns, key=lambda t: t.seq):
            if str(turn.kind) == InterviewTurnKind.ANSWER.value:
                ans = answers_by_turn.get(turn.id)
                records.append(
                    TurnRecord(
                        seq=turn.seq,
                        kind=str(turn.kind),
                        answer=ans.text if ans else (turn.content or None),
                        evaluation_overall=evaluations.get(ans.id) if ans else None,
                        hints_used=turn.hints_used or 0,
                    )
                )
            else:
                q = question_by_turn.get(turn.id)
                records.append(
                    TurnRecord(
                        seq=turn.seq,
                        kind=str(turn.kind),
                        question_id=q.id if q else None,
                        question=q.text if q else (turn.content or None),
                        hints_used=turn.hints_used or 0,
                    )
                )
        return records

    async def _history_text(self, session_id: int) -> str:
        turns = await self.turns.list_for_session(session_id)
        return "\n".join(f"{str(t.kind)}: {t.content or ''}" for t in turns)

    async def _evidence_summary(self, user_id: int, profile_id: int | None = None) -> str:
        items = await self.evidence.list_for_user(user_id, profile_id=profile_id, limit=30)
        return " | ".join(i.claim for i in items[:30]) or "no evidence yet"

    async def _persist_evaluation(
        self, q: Question, answer: Answer, evaluation: AnswerEvaluation, hints_used: int
    ) -> Evaluation:
        ev = Evaluation(
            answer_id=answer.id,
            dimensions=evaluation.dimensions.model_dump(),
            overall=evaluation.overall,
            confidence=evaluation.confidence,
            strengths=evaluation.strengths,
            weaknesses=evaluation.weaknesses,
            missing_evidence=evaluation.missing_evidence,
            hints_used=hints_used,
            follow_ups=evaluation.follow_ups,
            evaluator_version="pramya-eval-1.0",
        )
        await self.evaluations.add(ev)
        # Evidence from answer: observed claims with provenance.
        session_row = await self.sessions.get(q.interview_session_id)
        user_id = session_row.user_id if session_row else 0
        for claim in evaluation.evidence:
            await self.evidence.add(
                Evidence(
                    user_id=user_id,
                    source_kind=EvidenceSourceKind.ANSWER,
                    source_ref=f"answer:{answer.id}",
                    claim=claim.claim,
                    status=EvidenceStatus.OBSERVED,
                    strength=claim.strength,
                )
            )
        return ev

    async def _evaluations_for_session(self, session_id: int) -> list[Evaluation]:
        questions = await self.questions.list_for_session(session_id)
        out: list[Evaluation] = []
        for q in questions:
            answer = await self.answers.get_by_question(q.id)
            if answer:
                ev = await self.evaluations.get_by_answer(answer.id)
                if ev:
                    out.append(ev)
        return out

    async def stream_events(self, session_id: int, user_id: int) -> AsyncIterator[str]:
        """SSE generator for a session (subscribes to the event bus)."""
        await self._owned_session(session_id, user_id)
        queue = event_bus.subscribe(session_id)
        yield InterviewEvent("connected", {"session_id": session_id}).serialize()
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                except TimeoutError:
                    # keepalive comment for proxies
                    yield ": keepalive\n\n"
                    continue
                yield event.serialize()
                if event.type in ("session_status",) and event.data.get("status") in (
                    "completed",
                    "cancelled",
                ):
                    return
        finally:
            event_bus.unsubscribe(session_id)
            queue.task_done()
