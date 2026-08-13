"""Progress aggregation (Phase 5.3 / 10.2): session trends.

Deterministic aggregation of evaluations per competency across sessions.
No fabricated progress: only completed evaluations count. Output feeds the
progress UI (per-competency series).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class ProgressPoint:
    evaluation_id: int
    session_id: int
    competency_id: int | None
    competency_name: str
    overall: float
    created_at: datetime


@dataclass(frozen=True)
class CompetencySeries:
    competency_id: int | None
    name: str
    points: list[ProgressPoint] = field(default_factory=lambda: [])
    latest: float | None = None
    trend: float | None = None  # +/-, last point vs first


@dataclass(frozen=True)
class ProgressSummary:
    series: list[CompetencySeries]
    total_evaluations: int
    sessions: int
    average_overall: float


def aggregate_progress(
    points: list[ProgressPoint],
) -> ProgressSummary:
    """Build per-competency series + overall stats from evaluation points."""
    by_comp: dict[tuple[int | None, str], list[ProgressPoint]] = {}
    sessions: set[int] = set()
    for p in points:
        by_comp.setdefault((p.competency_id, p.competency_name), []).append(p)
        sessions.add(p.session_id)

    series: list[CompetencySeries] = []
    for (cid, name), pts in by_comp.items():
        ordered = sorted(pts, key=lambda p: p.created_at)
        latest = ordered[-1].overall
        trend = round(ordered[-1].overall - ordered[0].overall, 2) if len(ordered) > 1 else None
        series.append(
            CompetencySeries(
                competency_id=cid,
                name=name,
                points=ordered,
                latest=latest,
                trend=trend,
            )
        )
    series.sort(key=lambda s: s.name)

    avg = round(sum(p.overall for p in points) / len(points), 2) if points else 0.0
    return ProgressSummary(
        series=series,
        total_evaluations=len(points),
        sessions=len(sessions),
        average_overall=avg,
    )
