# Pramya — Architectural Decisions

This document records important decisions that future engineering sessions must not accidentally reverse.

Only meaningful architectural/product decisions belong here.

---

## Decision Format

For each significant decision:

### ADR-XXX — Title

**Status:** Accepted / Superseded / Rejected

**Date:**

**Decision:**

**Context:**

**Rationale:**

**Consequences:**

---

# Decisions

## ADR-001 — Greenfield Project

**Status:** Accepted

**Decision:**

Pramya is being built as a new greenfield project rather than being adapted from an existing application.

**Context:**

The repository starts with no existing application implementation.

**Rationale:**

This allows the architecture to be deliberately designed around the product requirements rather than inherited from an unrelated codebase.

**Consequences:**

The initial implementation must establish the project structure, architecture, tooling, testing strategy, and development workflow from scratch.

---

## ADR-002 — Evidence-Driven Product Architecture

**Status:** Accepted

**Decision:**

Evidence is a first-class domain concept in Pramya.

**Context:**

Pramya must provide substantially more value than generic conversational AI.

**Rationale:**

The product needs to understand candidate claims, demonstrated capability, supporting evidence, target-role requirements, weaknesses, and longitudinal progress.

**Consequences:**

Interview evaluation, retrieval, candidate memory, and practice recommendations must be designed around structured evidence rather than raw conversation history.

---

## ADR-003 — Model-Routed AI Architecture

**Status:** Accepted

**Decision:**

Pramya will use specialized models for different workloads rather than routing every task through a single LLM.

**Context:**

The product requires reasoning, retrieval, reranking, ASR, TTS, and inexpensive semantic processing.

**Rationale:**

Different workloads have different latency, quality, cost, and hardware requirements.

**Consequences:**

AI capabilities must be accessed through appropriate provider/model abstractions and routing logic.

---

## ADR-004 — Apple Silicon Local AI

**Status:** Accepted

**Decision:**

Local AI development is optimized for the M4 16 GB development machine using MLX/oMLX-compatible inference where appropriate.

**Context:**

The primary development environment is an Apple Silicon MacBook Pro.

**Rationale:**

Native Apple Silicon inference provides a practical local development and experimentation environment without requiring a dedicated GPU server.

**Consequences:**

Model selection and lifecycle management must respect unified-memory constraints.

---

## ADR-005 — Voice as a First-Class Capability

**Status:** Accepted

**Decision:**

Voice interviewing is part of the V1 product rather than a future add-on.

**Rationale:**

Real interview preparation requires natural spoken interaction, and voice provides a materially different experience from text-only chat.

**Consequences:**

ASR, TTS, streaming, interruption, cancellation, pause/resume, audio state, and transcript handling must be treated as core architecture.