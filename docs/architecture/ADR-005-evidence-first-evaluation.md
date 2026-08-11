# ADR-005 — Evidence-First Evaluation

**Status:** Accepted
**Date:** 2026-08

## Context

Anti-pattern: `LLM → "You are 8/10"`. Pramya must produce evaluations with
observable reasons: score, confidence, strengths, weaknesses, evidence,
missing evidence, hints used, follow-ups, evaluation version.

## Problem

How to evaluate answers so scores are traceable to evidence and aggregation is
honest?

## Decision

- Per answer, the evaluator (LLM) returns structured dimensions:
  correctness, technical depth, clarity, structure, relevance, evidence,
  communication, tradeoff awareness, reasoning, specificity, seniority
  alignment, completeness, hallucination risk — each with evidence and
  confidence.
- Evidence references point to retrieved nodes (claims from resume, prior
  answers, demonstration in this answer). Distinguish CLAIMED / OBSERVED /
  DEMONSTRATED / INFERRED / UNKNOWN.
- The LLM provides evidence + semantic judgments only. The application owns
  final aggregation (readiness, competency scores) deterministically.
- Evaluator version stored with every evaluation record; prompts versioned
  (`prompts/answer_evaluation/`).

## Alternatives

- Single LLM score — rejected: not evidence-backed.
- Deterministic-only keyword scoring — rejected: misses semantics.

## Tradeoffs

- Multi-call evaluation costs tokens/latency; mitigated by routing to
  deepseek-v4-flash non-thinking for latency-sensitive paths, thinking for
  deep evaluation, caching.

## Consequences

- `packages/evaluation/` with schemas, aggregate math (pure, unit-tested),
  prompt versions, evidence linking.
- Evaluation records are immutable; audit trail preserved.
- ADR-009 (DeepEval) validates evaluator quality.
