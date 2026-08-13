"""Preparation engine (Phase 5.2): gap -> priority -> today's queue.

Deterministic: reads readiness gaps + evidence + interview history and
produces prioritized preparation items with observable reasons. No LLM.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PreparationRecommendation:
    competency_id: int
    competency_name: str
    priority: int  # higher = do first (0..100)
    estimated_minutes: int
    reason: str
    assessment_type: str
    expected_improvement: float  # 0..1


@dataclass(frozen=True)
class GapInput:
    competency_id: int
    name: str
    demonstrated_level: int
    required_level: int
    score: float
    gap: int


def plan_preparation(
    gaps: list[GapInput],
    *,
    weak_evidence_competency_ids: set[int] | None = None,
    recently_practiced_ids: set[int] | None = None,
) -> list[PreparationRecommendation]:
    """Prioritize gaps into an actionable practice queue.

    Priority score:
      50 × gap_size + 30 × (weak evidence bonus) + 20 × (not-recently-practiced)
    Deterministic and golden-testable.
    """
    weak = weak_evidence_competency_ids or set()
    recent = recently_practiced_ids or set()

    items: list[PreparationRecommendation] = []
    for g in sorted(gaps, key=lambda g: g.gap, reverse=True):
        priority = 50 * g.gap
        if g.competency_id in weak:
            priority += 30
        if g.competency_id not in recent:
            priority += 20
        items.append(
            PreparationRecommendation(
                competency_id=g.competency_id,
                competency_name=g.name,
                priority=min(100, priority),
                estimated_minutes=25 if g.gap >= 2 else 15,
                reason=(
                    f"demonstrated level {g.demonstrated_level} vs required "
                    f"{g.required_level} ({g.gap} level gap)"
                ),
                assessment_type="targeted_exercise",
                expected_improvement=min(1.0, 0.1 * g.gap + 0.05),
            )
        )
    return sorted(items, key=lambda i: i.priority, reverse=True)
