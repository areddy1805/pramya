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
from app.repositories.evidence import EvidenceRepository
from app.repositories.interview import (
    AnswerRepository,
    EvaluationRepository,
    InterviewSessionRepository,
    InterviewTurnRepository,
    QuestionRepository,
)
from app.repositories.misc import RoleRepository
from app.services.idempotency import IdempotencyService
from app.services.prompts import load_prompt

_PLAN_PROMPT = "interview_planning/session_plan.txt"


@dataclass(frozen=True)
class InterviewEvent:
    """One typed SSE event payload."""

    type: str
    data: dict[str, object]

    def serialize(self) -> str:
        return f"event: {self.type}\ndata: {json.dumps(self.data, default=str)}\n\n"


class EventBus:
    """Per-session in-memory event queues (single-process dev runtime)."""

    def __init__(self) -> None:
        self._queues: dict[int, asyncio.Queue[InterviewEvent]] = {}

    def publish(self, session_id: int, event: InterviewEvent) -> None:
        queue = self._queues.get(session_id)
        if queue is not None:
            queue.put_nowait(event)

    def subscribe(self, session_id: int) -> asyncio.Queue[InterviewEvent]:
        if session_id not in self._queues:
            self._queues[session_id] = asyncio.Queue()
        return self._queues[session_id]


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
    ) -> InterviewSession:
        session_row = InterviewSession(
            user_id=user_id,
            role_id=role_id,
            kind=kind,
            status=InterviewSessionStatus.CREATED,
            started_at=datetime.now(UTC),
            config={
                "duration_minutes": duration_minutes,
                "focus_competency_ids": focus_competency_ids,
                "mode": mode,
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
        """PLANNING -> first question (QUESTIONING)."""
        row = await self._owned_session(session_id, user_id)
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
        history = await self._history_text(session_id)
        evidence_summary = await self._evidence_summary(user_id)
        comp, difficulty, seniority = await self._focus(session_id, user_id)

        state = await self.workflow.ainvoke(
            {
                "session_id": session_id,
                "user_id": user_id,
                "action": "question",
                "history": history,
                "evidence_summary": evidence_summary,
                "competency": comp,
                "difficulty": difficulty,
                "seniority": seniority,
                "hints_used": 0,
            },
            config={"configurable": {"thread_id": row.graph_thread_id or f"s{session_id}"}},
        )
        question = InterviewQuestion(
            text=state["question_text"] or "",
            type=state.get("question_type") or "general",
            difficulty=state.get("question_difficulty") or "medium",
            hint_levels=state.get("hint_levels") or [],
            rationale=state.get("rationale"),
            target_competency=state.get("target_competency") or comp,
        )
        q = Question(
            interview_session_id=session_id,
            competency_id=None,
            difficulty=QuestionDifficulty(question.difficulty),
            type=QuestionType(question.type),
            text=question.text,
            hint_levels=question.hint_levels,
            rationale=question.rationale,
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
        event_bus.publish(
            session_id,
            InterviewEvent(
                "question",
                {"question_id": q.id, "text": q.text, "difficulty": question.difficulty},
            ),
        )
        await self.session.commit()
        return q, turn

    async def submit_answer(
        self,
        session_id: int,
        user_id: int,
        *,
        question_id: int,
        answer_text: str,
        idempotency_key: str | None,
        mode: str = "text",
    ) -> Answer:
        """Idempotent answer submission -> evaluation + evidence extraction."""
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

        # Phase C: evaluation + evidence extraction execute through the
        # LangGraph workflow (retrieve_context -> evaluate_answer ->
        # extract_evidence -> update_candidate_state -> determine_next_action).
        state = await self.workflow.ainvoke(
            {
                "session_id": session_id,
                "user_id": user_id,
                "action": "answer",
                "question_text": q.text,
                "answer_text": answer_text,
                "hints_used": 0,
                "history": "",
                "evidence_summary": "",
                "competency": "",
                "difficulty": "",
                "seniority": "",
            },
            config={"configurable": {"thread_id": f"s{session_id}"}},
        )
        evaluation = AnswerEvaluation.model_validate(state["evaluation"] or {})
        await self._persist_evaluation(q, answer, evaluation, 0)
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
        return answer

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
        """Complete the session (evaluations kept; report available)."""
        row = await self._owned_session(session_id, user_id)
        transition(row.status, InterviewSessionStatus.COMPLETED)
        row.status = InterviewSessionStatus.COMPLETED
        row.ended_at = datetime.now(UTC)
        await self.session.commit()
        event_bus.publish(session_id, InterviewEvent("session_status", {"status": "completed"}))
        return row

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
        """Final synthesis report (deepseek FINAL_SYNTHESIS; 4B fallback)."""
        await self._owned_session(session_id, user_id)
        evals = await self._evaluations_for_session(session_id)
        if not evals:
            raise ValidationFailedError("no evaluations to report")
        transcript = await self._history_text(session_id)
        summary_lines: list[str] = []
        for ev in evals:
            answer = await self.answers.get(ev.answer_id)
            if answer is None:
                continue
            q = await self.questions.get(answer.question_id) if answer.question_id else None
            question_text = q.text if q else "(question unavailable)"
            summary_lines.append(f"Q: {question_text}\nA: {answer.text}\nOverall: {ev.overall}/10")

        # Phase C: report synthesis is the graph's generate_report node
        # (LangChain text_chain -> RouterChatModel -> InferenceRouter -> DeepSeek).
        row = await self._owned_session(session_id, user_id)
        state = await self.workflow.ainvoke(
            {
                "session_id": session_id,
                "user_id": user_id,
                "action": "report",
                "report_input": (
                    "SESSION SUMMARY:\n"
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

    async def _evidence_summary(self, user_id: int) -> str:
        items = await self.evidence.list_for_user(user_id, limit=30)
        return " | ".join(i.claim for i in items[:30]) or "no evidence yet"

    async def _focus(self, session_id: int, user_id: int) -> tuple[str, str, str]:
        """Pick focus competency + difficulty from role config or defaults."""
        row = await self._owned_session(session_id, user_id)
        role = None
        if row.role_id:
            role = await self.roles.get_or_raise(row.role_id, name="role")
        if role is not None:
            comps = await self.roles.list_competencies(role.id)
            if comps:
                return comps[0].name, "medium", role.seniority or "mid"
        return "general", "medium", "mid"

    async def _retrieve_context(self, user_id: int, query: str) -> str:
        # Phase D: LlamaIndex retrieval is the primary RAG path; the
        # deterministic hybrid RetrievalService stays as the fallback layer.
        rag = self.rag
        if rag is not None:
            try:
                chunks = await rag.retrieve(query, user_id=user_id, top_k=3)
                if chunks:
                    return "\n---\n".join(chunks)
            except Exception:  # LlamaIndex failure -> deterministic fallback
                self._logger.warning("llamaindex retrieval failed; deterministic fallback")
        if self.retrieval is None:
            return ""
        try:
            result = await self.retrieval.search(user_id, query, top_k=3)
            return "\n---\n".join(c.content for c in result.chunks)
        except Exception:  # retrieval must never break the interview
            self._logger.warning("retrieval failed; continuing without context")
            return ""

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
            queue.task_done()
