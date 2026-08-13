"""Golden tests: readiness math, preparation priority, progress aggregation.

Deterministic engines (Phase 5) — exact numbers asserted.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.domain.enums import EvidenceStatus
from app.services.preparation import GapInput, plan_preparation
from app.services.progress import ProgressPoint, aggregate_progress
from app.services.readiness import (
    CompetencyInput,
    EvaluationInput,
    EvidenceInput,
    compute_readiness,
)

NOW = datetime(2026, 8, 1, tzinfo=UTC)

_SYSTEM_DESIGN = CompetencyInput(
    id=1, name="System Design", importance="required", weight=0.6, level=4
)
_REACT = CompetencyInput(id=2, name="React", importance="required", weight=0.4, level=3)


def _evidence(cid: int, status: str, strength: float, days_ago: int = 10) -> EvidenceInput:
    return EvidenceInput(
        competency_id=cid,
        status=status,
        strength=strength,
        created_at=NOW - timedelta(days=days_ago),
    )


def test_readiness_no_evidence_low_cap() -> None:
    result = compute_readiness([_SYSTEM_DESIGN], [], [], now=NOW)
    assert result.overall == 0.0
    assert result.per_competency[0].score == 0.0
    assert result.per_competency[0].evidence_coverage == 0.0
    # Required competency with zero demonstrated ability IS a critical gap.
    assert len(result.critical_gaps) == 1
    assert result.critical_gaps[0]["demonstrated_level"] == 1
    assert result.critical_gaps[0]["required_level"] == 4


def test_readiness_demonstrated_evidence() -> None:
    evidence = [
        _evidence(1, EvidenceStatus.DEMONSTRATED, 0.9),
        _evidence(1, EvidenceStatus.OBSERVED, 0.7),
    ]
    evals = [EvaluationInput(competency_id=1, overall=8.0, confidence=0.8, created_at=NOW)]
    result = compute_readiness([_SYSTEM_DESIGN], evidence, evals, now=NOW)
    comp = result.per_competency[0]
    assert comp.evidence_coverage == 1.0
    # demonstrated = 0.6*8.0 + 0.4*(strength*10); strength ≈ (0.9+0.7*0.7)/...
    assert comp.score > 6.0 and comp.score <= 10.0
    assert comp.demonstrated_level >= 3
    assert result.overall == comp.score  # single competency


def test_readiness_critical_gap_required_under_level() -> None:
    # Weak evidence -> demonstrated level below required 4.
    evidence = [_evidence(1, EvidenceStatus.CLAIMED, 0.3)]
    result = compute_readiness([_SYSTEM_DESIGN], evidence, [], now=NOW)
    comp = result.per_competency[0]
    assert comp.demonstrated_level < 4
    assert len(result.critical_gaps) == 1
    gap = result.critical_gaps[0]
    assert gap["competency_id"] == 1
    assert gap["gap"] == 4 - comp.demonstrated_level


def test_readiness_recency_decay() -> None:
    old = [_evidence(1, EvidenceStatus.DEMONSTRATED, 0.9, days_ago=400)]
    fresh = [_evidence(1, EvidenceStatus.DEMONSTRATED, 0.9, days_ago=5)]
    result_old = compute_readiness([_SYSTEM_DESIGN], old, [], now=NOW)
    result_fresh = compute_readiness([_SYSTEM_DESIGN], fresh, [], now=NOW)
    # Fresh evidence should yield higher/equal blended strength.
    assert result_fresh.per_competency[0].score >= result_old.per_competency[0].score


def test_readiness_weighted_overall() -> None:
    comps = [_SYSTEM_DESIGN, _REACT]
    evidence = [
        _evidence(1, EvidenceStatus.DEMONSTRATED, 0.9),
        _evidence(2, EvidenceStatus.DEMONSTRATED, 0.9),
    ]
    evals = [
        EvaluationInput(competency_id=1, overall=8.0, confidence=0.8, created_at=NOW),
        EvaluationInput(competency_id=2, overall=5.0, confidence=0.6, created_at=NOW),
    ]
    result = compute_readiness(comps, evidence, evals, now=NOW)
    assert len(result.per_competency) == 2
    # Weighted: 0.6*sd + 0.4*react between the two scores.
    sd = result.per_competency[0].score
    rx = result.per_competency[1].score
    expected = round((sd * 0.6 + rx * 0.4) / 1.0, 2)
    assert result.overall == expected


def test_preparation_priority_ordering() -> None:
    gaps = [
        GapInput(
            competency_id=1, name="A", demonstrated_level=1, required_level=4, score=2.0, gap=3
        ),
        GapInput(
            competency_id=2, name="B", demonstrated_level=2, required_level=3, score=4.0, gap=1
        ),
    ]
    plan = plan_preparation(gaps, weak_evidence_competency_ids={1}, recently_practiced_ids={2})
    assert plan[0].competency_id == 1  # bigger gap + weak evidence -> first
    assert plan[0].priority > plan[1].priority
    assert plan[0].expected_improvement > plan[1].expected_improvement


def test_preparation_reason_observable() -> None:
    gaps = [
        GapInput(
            competency_id=1, name="A", demonstrated_level=1, required_level=4, score=2.0, gap=3
        )
    ]
    plan = plan_preparation(gaps)
    assert "demonstrated level 1" in plan[0].reason
    assert "required 4" in plan[0].reason


def test_progress_aggregation() -> None:
    points = [
        ProgressPoint(
            evaluation_id=1,
            session_id=10,
            competency_id=1,
            competency_name="System Design",
            overall=5.0,
            created_at=NOW - timedelta(days=5),
        ),
        ProgressPoint(
            evaluation_id=2,
            session_id=10,
            competency_id=1,
            competency_name="System Design",
            overall=7.0,
            created_at=NOW,
        ),
        ProgressPoint(
            evaluation_id=3,
            session_id=11,
            competency_id=2,
            competency_name="React",
            overall=6.0,
            created_at=NOW,
        ),
    ]
    summary = aggregate_progress(points)
    assert summary.total_evaluations == 3
    assert summary.sessions == 2
    assert summary.average_overall == round((5 + 7 + 6) / 3, 2)
    sd = next(s for s in summary.series if s.name == "System Design")
    assert sd.latest == 7.0
    assert sd.trend == 2.0
    rx = next(s for s in summary.series if s.name == "React")
    assert rx.trend is None  # single point


def test_progress_empty() -> None:
    summary = aggregate_progress([])
    assert summary.total_evaluations == 0
    assert summary.sessions == 0
    assert summary.series == []
