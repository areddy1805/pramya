# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownParameterType=false
"""Deterministic coverage tracking, focus selection, gap detection,
and the minimal anti-hallucination entity guard (productization steps 5-9).

Everything here is pure/deterministic — no LLM. Session state lives in
``session.config`` JSONB: ``coverage`` (what was asked), ``gaps`` (uncovered
JD requirements), ``directives`` (per-question interviewer reasoning).
"""

from __future__ import annotations

import re

# 20-category taxonomy (single source of truth, prompt + guard + tests).
QUESTION_CATEGORIES: tuple[str, ...] = (
    "architecture_design",
    "system_scaling",
    "data_modeling",
    "api_design",
    "backend_engineering",
    "frontend_engineering",
    "devops_infrastructure",
    "cloud_platforms",
    "security",
    "performance_optimization",
    "testing_quality",
    "coding_algorithms",
    "debugging_troubleshooting",
    "project_deep_dive",
    "behavioral_leadership",
    "collaboration_communication",
    "product_judgment",
    "llm_ai_applications",
    "database_engineering",
    "career_motivation",
)

# Interviewer personas (single source of truth: prompt + API + UI).
INTERVIEW_STYLES: tuple[str, ...] = (
    "structured",
    "curious",
    "time_pressured",
    "technical_expert",
    "conversational",
    "skeptical",
    "screening",
)

_KNOWN_SOURCES = {"resume", "jd", "profile", "competency", "followup", "weakness", "generic"}

_WORD_RE = re.compile(r"[A-Z][A-Za-z0-9+.#/-]{2,}")

# Question words / connective words never treated as invented entities.
_STOPWORDS = {
    "Tell",
    "What",
    "How",
    "Why",
    "Where",
    "When",
    "Which",
    "Who",
    "Whom",
    "Describe",
    "Explain",
    "Walk",
    "Think",
    "Talk",
    "Could",
    "Would",
    "Should",
    "Have",
    "Had",
    "Has",
    "About",
    "Your",
    "With",
    "That",
    "This",
    "There",
    "They",
    "Then",
    "Than",
    "Now",
    "One",
    "Two",
    "You",
    "Into",
    "From",
    "Been",
    "Being",
    "Also",
    "Even",
    "Only",
    "Just",
    "But",
    "And",
    "The",
    "Not",
    "Can",
    "Will",
    "Might",
    "Must",
    "Very",
    "Much",
    "Many",
    "More",
    "Most",
    "Some",
    "Such",
    "Each",
    "Every",
    "Both",
    "Neither",
    "Were",
    "Was",
    "Did",
    "Done",
    "Let",
    "Get",
    "Make",
    "Take",
    "Give",
    "Need",
    "Want",
    "Used",
    "Use",
    "Hand",
    "Please",
    "First",
    "Next",
    "Last",
    "Recent",
    "Another",
    "Other",
    "Different",
    "Together",
    "Through",
    "During",
    "Before",
    "After",
    "While",
    "Because",
    "However",
    "Instead",
    "Rather",
    "Really",
    "Actually",
    "Basically",
    "Cloud",
    "Backend",
    "Frontend",
    "Database",
    "System",
    "Project",
    "Role",
    "Team",
    "Company",
    "Manager",
    "Interview",
    "Question",
    "Answer",
}


def new_coverage() -> dict[str, object]:
    """Fresh coverage state for one session."""
    return {
        "categories": [],
        "competencies": [],
        "jd_skills": [],
        "projects": [],
        "asked_refs": [],
    }


def mark_asked(
    coverage: dict[str, object],
    *,
    category: str | None = None,
    competency: str | None = None,
    jd_skill: str | None = None,
    project: str | None = None,
    source_ref: str | None = None,
) -> dict[str, object]:
    """Record one asked question in the coverage state (idempotent)."""
    if category:
        _append_unique(coverage, "categories", category)
    if competency:
        _append_unique(coverage, "competencies", competency)
    if jd_skill:
        _append_unique(coverage, "jd_skills", jd_skill)
    if project:
        _append_unique(coverage, "projects", project)
    if source_ref:
        _append_unique(coverage, "asked_refs", source_ref)
    return coverage


def _append_unique(coverage: dict[str, object], key: str, value: str) -> None:
    raw = coverage.get(key)
    items = [str(v) for v in raw] if isinstance(raw, list) else []
    if value and value not in items:
        items.append(value)
    coverage[key] = items


def _str_list(coverage: dict[str, object], key: str) -> list[str]:
    raw = coverage.get(key)
    if not isinstance(raw, list):
        return []
    return [str(v) for v in raw if v is not None]


def focus_competency(
    coverage: dict[str, object],
    competencies: list[str],
    rng: object,
    follow_up_topic: str | None = None,
) -> str | None:
    """Pick the next competency: follow-up topic wins, then rotate over
    uncovered competencies, then round-robin over all (novelty kept by the
    prompt's already_asked list). Deterministic given the same state+rng."""
    if not competencies:
        return None
    if follow_up_topic and follow_up_topic in competencies:
        return follow_up_topic
    asked = set(_str_list(coverage, "competencies"))
    uncovered = [c for c in competencies if c not in asked]
    pool = uncovered or competencies
    index = getattr(rng, "randrange", None)
    if index is not None:  # random.Random instance
        return pool[index(0, len(pool))]  # type: ignore[no-any-return]
    return pool[0]


def _jd_required(context: dict[str, object]) -> list[str]:
    role = context.get("role")
    if not isinstance(role, dict):
        return []
    comps = role.get("competencies") or []
    out: list[str] = []
    for c in comps:
        if isinstance(c, dict):
            importance = str(c.get("importance") or "")
            if importance in ("required", "high", "critical", "mandatory"):
                out.append(str(c.get("name") or "").strip())
    return [c for c in out if c]


def compute_gaps(
    context: dict[str, object],
    coverage: dict[str, object],
    reasoning_gaps: list[str] | None = None,
) -> list[str]:
    """JD-required competencies the candidate has not shown evidence for and
    the session has not asked about yet — plus interviewer-detected gaps."""
    resume = context.get("resume")
    resume_text = str(resume.get("text", "")).lower() if isinstance(resume, dict) else ""
    evidence = context.get("evidence")
    evidence_text = (
        " ".join(str(e.get("claim", "")) for e in evidence).lower()
        if isinstance(evidence, list)
        else ""
    )
    jd_text = ""
    jd = context.get("jd")
    if isinstance(jd, dict):
        jd_text = str(jd.get("text", "")).lower()
    known = resume_text + " " + evidence_text + " " + jd_text

    gaps: list[str] = []
    asked = {str(c).lower() for c in _str_list(coverage, "competencies")}
    for req in _jd_required(context):
        if req.lower() in asked:
            continue
        if req.lower() in known:
            continue
        gaps.append(req)
    for g in reasoning_gaps or []:
        g = str(g).strip()
        if g and g not in gaps:
            gaps.append(g)
    return gaps


def detect_invented_entities(question_text: str, context: dict[str, object]) -> list[str]:
    """Minimal deterministic guard: capitalized words in the question that
    appear in NO context material are likely invented. Returns offenders.

    ``context`` is the grounding snapshot; only real entities count as
    known. Stopwords and known taxonomy/source vocabulary are excluded.
    """
    known_parts: list[str] = []
    resume = context.get("resume")
    if isinstance(resume, dict):
        known_parts.append(str(resume.get("text", "")))
    jd = context.get("jd")
    if isinstance(jd, dict):
        known_parts.append(str(jd.get("text", "")))
    evidence = context.get("evidence")
    if isinstance(evidence, list):
        for e in evidence:
            if isinstance(e, dict):
                known_parts.append(str(e.get("claim", "")))
    role = context.get("role")
    if isinstance(role, dict):
        for c in role.get("competencies") or []:
            known_parts.append(str(c.get("name", "")) if isinstance(c, dict) else "")
    profile = context.get("profile")
    if isinstance(profile, dict):
        known_parts.append(str(profile.get("name", "")))
    known_text = " ".join(p for p in known_parts if p).lower()

    offenders: list[str] = []
    for raw in _WORD_RE.findall(question_text):
        word = raw.rstrip(
            ".",
        ).rstrip(",;:!?'\"()")
        word = word.rstrip(".;:!?,()'\"")
        if not word:
            continue
        if word in _STOPWORDS:
            continue
        if word in QUESTION_CATEGORIES or word in INTERVIEW_STYLES:
            continue
        if word.lower() in known_text:
            continue
        offenders.append(word)
    return offenders


def normalize_source(source: str | None) -> str:
    """Clamp the model's SOURCE value to the known vocabulary."""
    if source and str(source).lower() in _KNOWN_SOURCES:
        return str(source).lower()
    return "generic"


def jd_skill_matches(resume_techs: list[str], jd_text: str | None) -> list[str]:
    """Resume technologies that also appear in the JD text (deterministic)."""
    if not jd_text:
        return []
    lower = jd_text.lower()
    return [t for t in resume_techs if t.lower() in lower]


__all__ = [
    "QUESTION_CATEGORIES",
    "INTERVIEW_STYLES",
    "new_coverage",
    "mark_asked",
    "focus_competency",
    "compute_gaps",
    "detect_invented_entities",
    "normalize_source",
    "jd_skill_matches",
]
