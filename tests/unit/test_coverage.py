"""Deterministic unit tests for the coverage/focus/gap/guard module
(productization steps 5, 6, 9) — pure functions, no DB, no LLM."""

from __future__ import annotations

import random

from app.services.coverage import (
    compute_gaps,
    detect_invented_entities,
    focus_competency,
    jd_skill_matches,
    mark_asked,
    new_coverage,
    normalize_source,
)

COMPETENCIES = ["System Design", "Full-Stack Engineering", "LLM Applications"]


def _context(**overrides: object) -> dict[str, object]:
    ctx: dict[str, object] = {
        "resume": {
            "text": "Atlas platform Angular Node.js MongoDB AWS cut API latency by 42% "
            "led a 4-person team"
        },
        "jd": {"text": "React Next.js Python FastAPI system design LLM applications"},
        "evidence": [
            {"claim": "Technology: Angular"},
            {"claim": "Project: Atlas"},
            {"claim": "Achievement (Atlas): cut API latency by 42% with caching"},
        ],
        "role": {
            "competencies": [
                {"name": "System Design", "importance": "required"},
                {"name": "Full-Stack Engineering", "importance": "required"},
                {"name": "LLM Applications", "importance": "preferred"},
            ]
        },
        "profile": {"name": "AI Engineer"},
    }
    ctx.update(overrides)
    return ctx


def test_new_coverage_is_empty() -> None:
    cov = new_coverage()
    assert cov["categories"] == []
    assert cov["competencies"] == []
    assert cov["jd_skills"] == []


def test_mark_asked_is_idempotent() -> None:
    cov = new_coverage()
    mark_asked(cov, category="api_design", competency="System Design")
    mark_asked(cov, category="api_design", competency="System Design")
    assert cov["categories"] == ["api_design"]
    assert cov["competencies"] == ["System Design"]


def test_focus_rotates_over_uncovered_then_round_robins() -> None:
    rng = random.Random(42)  # noqa: S311 — seeded, deterministic test RNG
    cov = new_coverage()

    first = focus_competency(cov, COMPETENCIES, rng)
    assert first in COMPETENCIES
    mark_asked(cov, competency=first)

    second = focus_competency(cov, COMPETENCIES, rng)
    assert second in COMPETENCIES and second != first
    mark_asked(cov, competency=second)

    # Only one uncovered left -> forced (no randomness needed).
    third = focus_competency(cov, COMPETENCIES, rng)
    assert third not in (first, second)
    mark_asked(cov, competency=third)

    # All covered -> round-robin over the full list, deterministically.
    again = focus_competency(cov, COMPETENCIES, rng)
    assert again in COMPETENCIES
    assert focus_competency(cov, COMPETENCIES, random.Random(42)) == again  # noqa: S311 — seeded, deterministic test RNG


def test_follow_up_topic_preferred_when_uncovered() -> None:
    cov = new_coverage()
    mark_asked(cov, competency="System Design")
    # Topic is uncovered -> preferred over the remaining uncovered pool.
    pick = focus_competency(
        cov, COMPETENCIES, random.Random(7), follow_up_topic="LLM Applications"  # noqa: S311 — seeded, deterministic test RNG
    )
    assert pick == "LLM Applications"


def test_compute_gaps_uncovered_required_competencies() -> None:
    cov = new_coverage()
    gaps = compute_gaps(_context(), cov)
    # System Design appears in JD text but candidate evidence lacks it ->
    # still a gap? No: System Design is in jd_text -> covered by known text.
    # Full-Stack Engineering is required and absent everywhere -> gap.
    assert "Full-Stack Engineering" in gaps
    assert "System Design" not in gaps  # present in JD text -> known


def test_compute_gaps_merges_reasoning_gaps() -> None:
    gaps = compute_gaps(_context(), new_coverage(), reasoning_gaps=["React"])
    assert "React" in gaps


def test_compute_gaps_asked_competency_is_not_a_gap() -> None:
    cov = new_coverage()
    mark_asked(cov, competency="Full-Stack Engineering")
    gaps = compute_gaps(_context(), cov)
    assert "Full-Stack Engineering" not in gaps


def test_jd_skill_matches_detects_overlap() -> None:
    assert jd_skill_matches(["Angular", "Node.js", "Docker"], "React Next.js Python") == []
    assert jd_skill_matches(["React", "Node.js"], "React Next.js Python") == ["React"]


def test_entity_guard_allows_known_and_rejects_invented() -> None:
    ctx = _context()
    assert detect_invented_entities("Walk me through the Atlas project.", ctx) == []
    # Punctuation-stripped known entity: "API." -> "API" is in the resume.
    assert detect_invented_entities("How did you measure the API latency drop?", ctx) == []
    offenders = detect_invented_entities("Describe your KafkaStreams pipeline and its lag.", ctx)
    assert "KafkaStreams" in offenders


def test_normalize_source_clamps_to_vocabulary() -> None:
    assert normalize_source("resume") == "resume"
    assert normalize_source("RESUME") == "resume"
    assert normalize_source("made_up") == "generic"
    assert normalize_source(None) == "generic"
