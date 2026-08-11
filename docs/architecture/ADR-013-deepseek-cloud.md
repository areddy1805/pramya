# ADR-013 — deepseek-v4-flash Cloud Reasoning + Thinking Policy

**Status:** Accepted
**Date:** 2026-08

## Context

Cloud reasoning model for difficult reasoning, adaptive questioning, deep
evaluation, synthesis. Legacy IDs deprecated 2026-07-24. Verified: model ID
`deepseek-v4-flash` current (V4-Flash-0731); 1M context / 384K max output;
thinking toggle via `thinking: {"type": "enabled"|"disabled"}`; OpenAI-
compatible base URL `https://api.deepseek.com`; pricing $0.14/M in (miss),
$0.28/M out; uses `max_tokens`; thinking mode ignores temperature/top_p.

## Problem

How to use DeepSeek without hard-coding it, without indiscriminate spending,
and with deliberate thinking-mode policy?

## Decision

- Use only `deepseek-v4-flash` (never legacy IDs). OpenAI SDK with custom
  base_url; `extra_body={"thinking": {...}}` per task policy.
- Task-level thinking policy (observable in telemetry):
  - **Thinking enabled** (default): complex evaluation, adaptive question
    generation, resume deep-dive reasoning, system-design reasoning, final
    synthesis, difficult follow-up generation.
  - **Thinking disabled**: latency-sensitive paths where quality suffices
    (e.g., quick classification fallback, streaming question text for the
    live interview when local model unavailable).
- Cost control: prompt minimization, context selection via retrieval
  (never dump full profile), deterministic preprocessing, local routing for
  cheap tasks, response caching where safe, request dedup, token/cost
  telemetry per call.
- Provider abstraction (`DeepSeekProvider`) so the model is swappable.
- Tool calls in thinking mode: preserve `reasoning_content` across turns;
  do not send `tool_choice` in thinking mode (API constraint).

## Alternatives

- deepseek-v4-pro — rejected: costlier; flash suffices for V1 policies.
- Single local model — rejected: quality ceiling on hard reasoning.

## Tradeoffs

- Thinking mode costs more tokens; policy + caching bounds spend.
- API churn risk (fast-moving DeepSeek line) — mitigated by adapter + tests
  against recorded fixtures.

## Consequences

- `packages/ai/providers/deepseek.py`; task policies in config; telemetry
  records thinking flag + token cost.
- Failure strategy: DeepSeek unavailable → local Qwen3.5-9B fallback for
  non-critical tasks; user-visible degraded state.
