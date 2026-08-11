"""Interview engine state machine (Phase 3).

The interview_session status transitions are authoritative here (plan §7
design rule: "Enforced in the interview service"). LangGraph is not used:
the deterministic DB-backed state machine below satisfies every Phase 3
acceptance criterion (resume-after-refresh via persisted state, idempotent
answers, interrupt/pause/resume, evaluation versioning). See DECISIONS.md.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import InterviewSessionStatus
from app.domain.errors import InterviewStateError

# Legal transitions: status -> set of reachable statuses.
TRANSITIONS: dict[InterviewSessionStatus, set[InterviewSessionStatus]] = {
    InterviewSessionStatus.CREATED: {
        InterviewSessionStatus.PLANNING,
        InterviewSessionStatus.CANCELLED,
    },
    InterviewSessionStatus.PLANNING: {
        InterviewSessionStatus.QUESTIONING,
        InterviewSessionStatus.CANCELLED,
        InterviewSessionStatus.ERROR,
    },
    InterviewSessionStatus.QUESTIONING: {
        InterviewSessionStatus.PAUSED,
        InterviewSessionStatus.INTERRUPTED,
        InterviewSessionStatus.COMPLETED,
        InterviewSessionStatus.CANCELLED,
        InterviewSessionStatus.ERROR,
    },
    InterviewSessionStatus.PAUSED: {
        InterviewSessionStatus.QUESTIONING,
        InterviewSessionStatus.CANCELLED,
    },
    InterviewSessionStatus.INTERRUPTED: {
        InterviewSessionStatus.QUESTIONING,
        InterviewSessionStatus.PAUSED,
        InterviewSessionStatus.CANCELLED,
        InterviewSessionStatus.ERROR,
    },
    # Terminal states.
    InterviewSessionStatus.COMPLETED: set(),
    InterviewSessionStatus.CANCELLED: set(),
    InterviewSessionStatus.ERROR: {InterviewSessionStatus.CANCELLED},
}


@dataclass(frozen=True)
class StateTransition:
    current: InterviewSessionStatus
    target: InterviewSessionStatus

    def is_legal(self) -> bool:
        return self.target in TRANSITIONS.get(self.current, set())


def transition(current: InterviewSessionStatus, target: InterviewSessionStatus) -> None:
    """Validate and return nothing; raise InterviewStateError on illegal move.

    Terminal states are final: completed/cancelled cannot be left (except
    ERROR -> CANCELLED).
    """
    if not StateTransition(current, target).is_legal():
        raise InterviewStateError(
            f"illegal interview state transition {current.value} -> {target.value}",
            details={"current": current.value, "target": target.value},
        )
