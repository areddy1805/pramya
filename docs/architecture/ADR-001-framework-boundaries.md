# ADR-001 — Framework Boundaries

**Status:** Accepted
**Date:** 2026-08

## Context

Pramya must demonstrate real engineering with LangChain, LangGraph, LlamaIndex,
MCP, DeepEval, Langfuse — without becoming a framework demo. Frameworks evolve
fast; the architecture must stay replaceable.

## Problem

Where does each framework's responsibility end? Unbounded use couples domain
logic to frameworks and makes replacement impossible.

## Decision

- **LangChain** — model abstraction, structured output, prompts, tools, model
  integrations, agent primitives, middleware. Layer *below* workflow.
- **LangGraph** — stateful interview workflow, adaptive routing, checkpoints,
  interrupts, resumable sessions, streaming events. The orchestration engine.
- **LlamaIndex** — document ingestion, indexing, retrieval, metadata, RAG for
  candidate/JD/evidence knowledge. Does NOT own workflow state.
- **MCP** — interoperability boundary only (read-oriented external surface).
- **DeepEval** — AI evaluation suite (semantic metrics, golden datasets).
- **Langfuse** — LLM observability.

Domain logic, persistence, readiness math, and evidence aggregation are plain
Python. Framework adapters live at package boundaries.

## Alternatives

- Everything through LangChain chains — rejected (couples domain to framework).
- No frameworks — rejected (learning objective + genuine value).
- LangGraph for everything — rejected (retrieval is not a graph problem).

## Tradeoffs

- More adapters to write; moderate boilerplate at boundaries.
- Narrow integration is a quality requirement: a framework can be removed
  without rewriting unrelated domain logic.

## Consequences

- Package layout: `domain/` (pure), `application/` (services), `ai/`
  (langchain/langgraph/llamaindex adapters), `mcp_server/`, `api/`.
- ADR-002, ADR-003, ADR-004, ADR-006 detail each boundary.
