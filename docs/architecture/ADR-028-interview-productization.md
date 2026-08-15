# ADR-028 — Interview Productization: Grounded Context, Follow-Up Engine, Coverage, Prep Memory

**Status:** Accepted (2026-08-15)
**Supersedes:** none (extends Phase 3 interview engine + ADR-026 profile workspace)
**Related:** ADR-023 (DeepSeek-only text), ADR-026 (career profiles), ADR-027 (Pocket TTS)

## Context

The interview engine generated questions from only competency/difficulty/
seniority/evidence-summary/history. It had no resume, JD, role, or profile
grounding; evidence was user-scoped (cross-profile leak); `_focus()` always
picked competencies[0]; the graph computed follow-up decisions that
`next_question` discarded; questions carried no provenance; the report was
free-text markdown. Productization requires real interview intelligence:
personalized questioning grounded in the candidate's actual material, with
coverage, follow-up routing, gap detection, and per-profile preparation
memory.

## Decision

Bounded changes within the existing architecture (LangGraph workflow +
service layer + JSONB session config; no new frameworks):

1. **Grounding snapshot** — `InterviewContextBuilder` builds an immutable
   snapshot per session (profile, resume chunks, JD chunks, role competency
   graph, profile-scoped evidence ≤40, latest 3 `interview_feedback` rows)
   stored in `session.config["context"]` at begin()/first question. All
   retrieval and evidence reads are profile-scoped (`retrieval.search`
   gained `profile_id`, filtering chunks via the document join).
2. **Provenance** — migration 0005 adds `question.category/source/source_ref/
   target_competency`; the prompt emits CATEGORY (20-category taxonomy),
   SOURCE (resume|jd|profile|competency|followup|weakness|generic), and
   SOURCE_REF (exact entity). Every question is attributable.
3. **Follow-up engine** — `InterviewerReasoning` (decision: follow_up_deep/
   follow_up_light/move_on/challenge/clarify/change_topic + topic + gaps)
   runs in the ANSWER lane after evaluation. It never blocks the next-
   question stream (voice runs it as the existing background evaluation
   task). Directives persist in `session.config["directives"]` and the next
   question consumes the latest one (topic preference + style guidance).
4. **CoverageTracker** — deterministic, `session.config["coverage"]`;
   focus selection rotates over uncovered role competencies, seeded by
   `random.Random(session_id)` (reproducible). Novelty (already-asked
   competencies) is passed to the prompt.
5. **Gap detection** — JD-required competencies with no evidence, not asked,
   plus interviewer-detected gaps → `session.config["gaps"]`.
6. **Prep memory** — `interview_feedback` row (weaknesses/gaps/topics/
   avg_overall) written at stop(); the next session's context reads the
   latest 3 rows and re-probes prior weak areas.
7. **Report v2** — deterministic scorecard (per-dimension averages, overall,
   top strengths/weaknesses) + per-question feedback (good/missing/
   expected follow-ups/derived prep recommendation) + gaps; the LLM
   narrative is retained (`report` field unchanged).
8. **Styles** — structured|curious|time_pressured|technical_expert|
   conversational|skeptical|screening via `InterviewCreate.style`, injected
   into the prompt + UI selector; duration presets 15/30/45/60.
9. **Anti-hallucination** — prompt strictness (grounding-only) + minimal
   deterministic entity guard (capitalized token absent from the grounding
   snapshot → regenerate once on the text path; streaming path logs only,
   since tokens already reached TTS).

## Consequences

- Questions are grounded, attributable, and profile-isolated (verified by
  12 integration tests + 2 real DeepSeek interviews).
- Follow-up depth is bounded per answer and the interviewer can change
  topic; coverage rotation still yields to repeated deep follow-ups in
  short interviews (accepted interviewer behavior; per-topic follow-up
  caps are a future tuning knob).
- `session.config` carries context/coverage/gaps/directives; the snapshot
  is immutable per session (rebuilt only when absent).
- The answer lane gained one bounded retry on transient provider failure
  (evaluation is analytical; the answer is already durably committed).
- Fixed pre-existing defect: resume extraction compared `document.kind.value`
  on a str column (500 on extract).

## Validation

- 232 unit+contract + 68 integration tests pass (22 new productization
  tests: grounding fixture Atlas/Angular/Node/MongoDB/AWS/-42%, JD
  React/Next/Python/FastAPI/LLM; isolation; rotation; follow-up flow;
  prep memory; guard; report v2; 30-min simulation).
- ruff/mypy/pyright clean; frontend tsc/lint/build clean.
- Real interviews (user 1, profiles 8/9, DeepSeek): questions grounded in
  each profile's resume only, no cross-profile leakage, follow-ups drill
  prior answers, gaps detected, report v2 renders.
