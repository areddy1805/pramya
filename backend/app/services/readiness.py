"""Deterministic readiness calculator (Phase 5.1).

Pure functions — no I/O. Inputs are value objects loaded by an adapter;
outputs are the readiness model. Every score has observable reasons.

Model (per plan §7 readiness_snapshot):
  per-competency score = importance weight × demonstrated ability blend
  demonstrated ability blend = f(evidence coverage, evaluation scores,
  confidence, recency) — knowledge-confidence vs demonstrated-ability are
  kept separate: the snapshot stores both.

No LLM here. Deterministic and golden-testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.domain.enums import EvidenceStatus


@dataclass(frozen=True)
class CompetencyInput:
    """One role competency with its target importance."""

    id: int
    name: str
    importance: str  # required | preferred | nice_to_have
    weight: float
    level: int  # 1..5 required level


@dataclass(frozen=True)
class EvidenceInput:
    competency_id: int | None
    status: str  # EvidenceStatus value
    strength: float  # 0..1
    created_at: datetime | None = None


@dataclass(frozen=True)
class EvaluationInput:
    competency_id: int | None
    overall: float  # 0..10
    confidence: float  # 0..1
    created_at: datetime | None = None


@dataclass(frozen=True)
class CompetencyReadiness:
    competency_id: int
    name: str
    importance: str
    weight: float
    # Demonstrated-ability score 0..10 (from evaluations + evidence).
    score: float
    confidence: float  # 0..1
    evidence_coverage: float  # 0..1
    knowledge_confidence: float  # 0..1 (self-report proxy: eval confidence)
    demonstrated_level: int  # 1..5
    reasons: list[str] = field(default_factory=lambda: [])


@dataclass(frozen=True)
class ReadinessResult:
    overall: float  # 0..10
    confidence: float  # 0..1
    evidence_coverage: float  # 0..1
    per_competency: list[CompetencyReadiness]
    critical_gaps: list[dict[str, object]]


# Status weights for evidence coverage: demonstrated > observed > claimed.
_STATUS_WEIGHT: dict[str, float] = {
    EvidenceStatus.DEMONSTRATED: 1.0,
    EvidenceStatus.OBSERVED: 0.7,
    EvidenceStatus.INFERRED: 0.5,
    EvidenceStatus.CLAIMED: 0.4,
    EvidenceStatus.UNKNOWN: 0.0,
}

_IMPORTANCE_WEIGHT: dict[str, float] = {
    "required": 1.0,
    "preferred": 0.6,
    "nice_to_have": 0.3,
}

# Months after which evidence decays (recency factor 0.5).
_EVIDENCE_HALFLIFE_MONTHS = 6.0


def _recency_factor(created_at: datetime | None, now: datetime) -> float:
    if created_at is None:
        return 1.0
    months = (now - created_at).days / 30.44
    return 0.5 ** (months / _EVIDENCE_HALFLIFE_MONTHS) if months > 0 else 1.0


def _evidence_coverage(evidence: list[EvidenceInput]) -> tuple[float, float, list[str]]:
    """(coverage 0..1, blended strength 0..1, reasons)."""
    if not evidence:
        return 0.0, 0.0, ["no evidence recorded"]
    total = 0.0
    strength_sum = 0.0
    for item in evidence:
        weight = _STATUS_WEIGHT.get(item.status, 0.0)
        total += weight
        strength_sum += weight * item.strength
    n = len(evidence)
    coverage = min(1.0, total / max(1.0, n * 0.75))  # 75% of max weight = full
    strength = strength_sum / max(1e-9, total)
    return round(coverage, 3), round(strength, 3), [f"{n} evidence records"]


def _evaluation_score(evaluations: list[EvaluationInput], now: datetime) -> tuple[float, float]:
    """(blended overall 0..10, confidence 0..1) with recency weighting."""
    if not evaluations:
        return 0.0, 0.0
    weight_sum = 0.0
    score_sum = 0.0
    conf_sum = 0.0
    for ev in evaluations:
        w = _recency_factor(ev.created_at, now)
        weight_sum += w
        score_sum += w * ev.overall
        conf_sum += w * ev.confidence
    return round(score_sum / max(1e-9, weight_sum), 2), round(conf_sum / max(1e-9, weight_sum), 2)


def compute_readiness(
    competencies: list[CompetencyInput],
    evidence: list[EvidenceInput],
    evaluations: list[EvaluationInput],
    *,
    now: datetime | None = None,
) -> ReadinessResult:
    """Deterministic readiness computation (golden-testable)."""
    now = now or datetime.now()
    per: list[CompetencyReadiness] = []
    gaps: list[dict[str, object]] = []

    for comp in competencies:
        comp_evidence = [e for e in evidence if e.competency_id == comp.id]
        comp_evals = [e for e in evaluations if e.competency_id == comp.id]
        coverage, strength, cov_reasons = _evidence_coverage(comp_evidence)
        eval_score, eval_conf = _evaluation_score(comp_evals, now)

        # Demonstrated ability = evidence strength + evaluation score blend.
        # Knowledge-confidence = evaluation confidence (self-report proxy).
        if eval_score > 0:
            demonstrated = round(0.6 * eval_score + 0.4 * (strength * 10), 2)
            confidence = round(0.5 * eval_conf + 0.5 * coverage, 2)
        else:
            demonstrated = round(strength * 10, 2)
            confidence = round(coverage, 2)

        # Cap by evidence coverage: no evidence -> score can't be high.
        if coverage < 0.3:
            demonstrated = min(demonstrated, 4.0)
        demonstrated = round(min(10.0, demonstrated), 2)

        # Demonstrated level 1..5 from score.
        demonstrated_level = max(1, min(5, round(demonstrated / 2)))

        reasons = list(cov_reasons)
        reasons.append(f"target level {comp.level}; demonstrated level {demonstrated_level}")
        if coverage < 0.3:
            reasons.append("low evidence coverage caps demonstrated ability")

        per.append(
            CompetencyReadiness(
                competency_id=comp.id,
                name=comp.name,
                importance=comp.importance,
                weight=comp.weight,
                score=demonstrated,
                confidence=confidence,
                evidence_coverage=coverage,
                knowledge_confidence=confidence,
                demonstrated_level=demonstrated_level,
                reasons=reasons,
            )
        )

        # Critical gap: required competency with demonstrated below target.
        if comp.importance == "required" and demonstrated_level < comp.level:
            gaps.append(
                {
                    "competency_id": comp.id,
                    "name": comp.name,
                    "demonstrated_level": demonstrated_level,
                    "required_level": comp.level,
                    "score": demonstrated,
                    "gap": comp.level - demonstrated_level,
                }
            )

    if per:
        total_weight = sum(c.weight for c in per)
        overall = round(sum(c.score * c.weight for c in per) / max(1e-9, total_weight), 2)
    else:
        overall = 0.0
    total_weight = sum(c.weight for c in per)
    confidence = (
        round(sum(c.confidence * c.weight for c in per) / max(1e-9, total_weight), 2)
        if per
        else 0.0
    )
    evidence_coverage = (
        round(
            sum(c.evidence_coverage * c.weight for c in per) / max(1e-9, total_weight),
            2,
        )
        if per
        else 0.0
    )
    gaps.sort(key=lambda g: int(g["gap"]) if isinstance(g["gap"], int) else 0, reverse=True)

    return ReadinessResult(
        overall=overall,
        confidence=confidence,
        evidence_coverage=evidence_coverage,
        per_competency=per,
        critical_gaps=gaps,
    )
