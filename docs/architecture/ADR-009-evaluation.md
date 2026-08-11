# ADR-009 — Evaluation

**Status:** Accepted
**Date:** 2026-08

## Context

Pramya needs a real AI evaluation suite: golden datasets for role analysis,
candidate extraction, question generation, answer evaluation, evidence
extraction, adaptive routing, RAG grounding, final report. Evaluate
structured-output validity, factual grounding, evidence relevance, evaluation
consistency, question relevance, adaptive routing quality, hallucination, task
completion, tool correctness. Deterministic tests wherever possible; semantic
evaluation where required.

## Problem

How to build regression-grade AI quality testing?

## Decision

- DeepEval 4.x as the semantic evaluation framework (pytest-native).
- Golden datasets under `tests/evals/datasets/` (synthetic demo candidates +
  JDs — never real employer data), expected behavioral constraints per task.
- RAG metrics: Faithfulness, AnswerRelevancy, ContextualPrecision/Recall/
  Relevancy for grounding validation.
- Structured-output validity: Pydantic schema checks + JSON contract tests.
- Deterministic domain tests (readiness math, prioritization, routing
  selection, evidence aggregation) — pure unit tests with golden numbers.
- Judge backend: deepseek-v4-flash (non-thinking, temp 0) or local
  Qwen3.5-4B per suite; one judge per benchmark at temperature 0. (Qwen3.5-9B
  is deferred — not a judge option in V1.)
- CI runs: `deepeval test run` + pytest unit/integration.

## Alternatives

- Manual "output looks good" — rejected: not regression-safe.
- Ragas alone — rejected: DeepEval is the specified framework; native metrics
  preferred over RAGAS wrappers.

## Tradeoffs

- Judge calls cost tokens/time; mitigated by caching, parallelism, local
  judge, deterministic subsets in CI.

## Consequences

- `tests/evals/` structure; eval task per phase in master plan; evals gating
  Definition of Done.
