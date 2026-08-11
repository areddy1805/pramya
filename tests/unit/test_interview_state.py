"""Interview state machine unit tests (Phase 3): transitions."""

from __future__ import annotations

import pytest

from app.domain.enums import InterviewSessionStatus
from app.domain.errors import InterviewStateError
from app.interview.state import StateTransition, transition


def test_created_to_planning_to_questioning() -> None:
    transition(InterviewSessionStatus.CREATED, InterviewSessionStatus.PLANNING)
    transition(InterviewSessionStatus.PLANNING, InterviewSessionStatus.QUESTIONING)


def test_questioning_cycle() -> None:
    transition(InterviewSessionStatus.QUESTIONING, InterviewSessionStatus.PAUSED)
    transition(InterviewSessionStatus.PAUSED, InterviewSessionStatus.QUESTIONING)
    transition(InterviewSessionStatus.QUESTIONING, InterviewSessionStatus.INTERRUPTED)
    transition(InterviewSessionStatus.INTERRUPTED, InterviewSessionStatus.QUESTIONING)


def test_completion_paths() -> None:
    transition(InterviewSessionStatus.QUESTIONING, InterviewSessionStatus.COMPLETED)
    transition(InterviewSessionStatus.QUESTIONING, InterviewSessionStatus.CANCELLED)
    transition(InterviewSessionStatus.PAUSED, InterviewSessionStatus.CANCELLED)


def test_terminal_states_are_final() -> None:
    with pytest.raises(InterviewStateError):
        transition(InterviewSessionStatus.COMPLETED, InterviewSessionStatus.QUESTIONING)
    with pytest.raises(InterviewStateError):
        transition(InterviewSessionStatus.CANCELLED, InterviewSessionStatus.PAUSED)


def test_illegal_jumps_rejected() -> None:
    with pytest.raises(InterviewStateError):
        transition(InterviewSessionStatus.CREATED, InterviewSessionStatus.COMPLETED)
    with pytest.raises(InterviewStateError):
        transition(InterviewSessionStatus.PLANNING, InterviewSessionStatus.PAUSED)


def test_error_recovery() -> None:
    transition(InterviewSessionStatus.QUESTIONING, InterviewSessionStatus.ERROR)
    transition(InterviewSessionStatus.ERROR, InterviewSessionStatus.CANCELLED)


def test_transition_dataclass() -> None:
    t = StateTransition(InterviewSessionStatus.CREATED, InterviewSessionStatus.PLANNING)
    assert t.is_legal()
    bad = StateTransition(InterviewSessionStatus.CREATED, InterviewSessionStatus.COMPLETED)
    assert not bad.is_legal()
