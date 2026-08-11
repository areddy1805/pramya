# ADR-002 — LangGraph Workflow

**Status:** Accepted
**Date:** 2026-08

## Context

The interview is a stateful, adaptive, resumable, interruptible workflow:
planning → questioning → listening → evaluating → follow-up decision →
question generation → response, with PAUSED/INTERRUPTED/CANCELLED/COMPLETED/
ERROR_RECOVERY states. State must survive browser refresh and interruptions.

## Problem

Interview state cannot live in React state or ephemeral memory. Need durable
state, conditional branches, loops, interrupts, resume without duplicate
questions/evaluations.

## Decision

LangGraph 1.2.x models the interview as a typed StateGraph:

- Typed graph state (Pydantic) holding interview context, turn history,
  current question, evidence, evaluation state, routing decisions.
- Deterministic routing functions between nodes.
- Checkpointing via `AsyncPostgresSaver` (`langgraph-checkpoint-postgres`
  3.1) with `thread_id` per interview; `.setup()` run as migration.
- Interrupt after question generation; resume after answer submission.
- Stream events (`astream_events`) for the frontend.
- Parent graph only compiled with checkpointer (subgraph rule).

## Alternatives

- Hand-rolled state machine + DB rows — rejected: loses checkpointing,
  streaming events, interrupt machinery; more code to maintain.
- Temporal-style job orchestration — rejected: heavy, not interview-shaped.

## Tradeoffs

- LangGraph learning curve; version churn (1.2.x line currently).
- Checkpoint size limits (~1 GB practical) — store blobs outside state.

## Consequences

- `packages/interview/graph/` module: state.py, nodes.py, workflow.py, routing.py.
- Tests: state init, route selection, checkpoint recovery, malformed
  evaluation recovery, interrupt/resume, no duplicated questions.
- ADR-012 (voice models) and DECISIONS cover streaming/interruption
  interaction.
