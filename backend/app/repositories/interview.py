"""Interview-related repositories."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select

from app.models.interview import (
    Answer,
    AudioSegment,
    Evaluation,
    InterviewSession,
    InterviewTurn,
    Question,
    TranscriptSegment,
)
from app.repositories.base import BaseRepository


class InterviewSessionRepository(BaseRepository[InterviewSession]):
    model = InterviewSession

    async def get_by_graph_thread(self, thread_id: str) -> InterviewSession | None:
        stmt = select(InterviewSession).where(InterviewSession.graph_thread_id == thread_id)
        return (await self.session.scalars(stmt)).first()

    async def list_for_user(
        self, user_id: int, *, limit: int = 50, offset: int = 0
    ) -> Sequence[InterviewSession]:
        stmt = (
            select(InterviewSession)
            .where(InterviewSession.user_id == user_id)
            .order_by(InterviewSession.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return (await self.session.scalars(stmt)).all()


class InterviewTurnRepository(BaseRepository[InterviewTurn]):
    model = InterviewTurn

    async def list_for_session(self, session_id: int) -> Sequence[InterviewTurn]:
        stmt = (
            select(InterviewTurn)
            .where(InterviewTurn.interview_session_id == session_id)
            .order_by(InterviewTurn.seq)
        )
        return (await self.session.scalars(stmt)).all()

    async def latest_for_session(self, session_id: int) -> InterviewTurn | None:
        stmt = (
            select(InterviewTurn)
            .where(InterviewTurn.interview_session_id == session_id)
            .order_by(InterviewTurn.seq.desc())
            .limit(1)
        )
        return (await self.session.scalars(stmt)).first()

    async def max_seq(self, session_id: int) -> int:
        stmt = select(InterviewTurn.seq).where(InterviewTurn.interview_session_id == session_id)
        seqs = (await self.session.scalars(stmt)).all()
        return max(seqs) if seqs else 0


class AudioSegmentRepository(BaseRepository[AudioSegment]):
    model = AudioSegment

    async def list_for_session(self, session_id: int) -> Sequence[AudioSegment]:
        stmt = (
            select(AudioSegment)
            .where(AudioSegment.interview_session_id == session_id)
            .order_by(AudioSegment.id)
        )
        return (await self.session.scalars(stmt)).all()


class TranscriptSegmentRepository(BaseRepository[TranscriptSegment]):
    model = TranscriptSegment

    async def list_for_session(self, session_id: int) -> Sequence[TranscriptSegment]:
        stmt = (
            select(TranscriptSegment)
            .where(TranscriptSegment.interview_session_id == session_id)
            .order_by(TranscriptSegment.seq)
        )
        return (await self.session.scalars(stmt)).all()

    async def max_seq_for_turn(self, turn_id: int) -> int:
        stmt = select(func.max(TranscriptSegment.seq)).where(TranscriptSegment.turn_id == turn_id)
        value = (await self.session.scalars(stmt)).first()
        return int(value) if value is not None else 0


class QuestionRepository(BaseRepository[Question]):
    model = Question

    async def list_for_session(self, session_id: int) -> Sequence[Question]:
        stmt = (
            select(Question)
            .where(Question.interview_session_id == session_id)
            .order_by(Question.id)
        )
        return (await self.session.scalars(stmt)).all()


class AnswerRepository(BaseRepository[Answer]):
    model = Answer

    async def get_by_question(self, question_id: int) -> Answer | None:
        stmt = select(Answer).where(Answer.question_id == question_id)
        return (await self.session.scalars(stmt)).first()


class EvaluationRepository(BaseRepository[Evaluation]):
    model = Evaluation

    async def get_by_answer(self, answer_id: int) -> Evaluation | None:
        stmt = select(Evaluation).where(Evaluation.answer_id == answer_id)
        return (await self.session.scalars(stmt)).first()
