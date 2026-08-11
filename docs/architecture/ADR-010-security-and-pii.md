# ADR-010 — Security and PII

**Status:** Accepted
**Date:** 2026-08

## Context

Pramya processes resumes, JDs, interview answers, voice recordings, personal
information. Documents are untrusted input (prompt injection, malicious
content, oversized uploads). LLM output must never directly mutate privileged
state. API keys and secrets must never leak.

## Problem

How to keep the product safe by default?

## Decision

- Upload validation: size limit, file-type allowlist (PDF, DOCX, TXT, MD),
  content scanning, max pages; reject unsupported/oversized.
- Prompt-injection defense: strict separation of SYSTEM INSTRUCTIONS, USER
  DATA, DOCUMENT DATA, RETRIEVED EVIDENCE, MODEL OUTPUT; documents never
  become privileged instructions; instruction delimiters + validation.
- LLM output pipeline: LLM → structured proposal → Pydantic validation →
  application logic → persistence. Model cannot write privileged state.
- Evidence provenance: LLM cannot fabricate candidate experience; evidence
  rows require source attribution; inference vs claim vs demonstration
  distinguished.
- Secrets: env-only, never committed; `.env.example` only; key rotation docs.
- No PII in logs/traces; redaction layer; audio retention configurable;
  deletion endpoints (profile, sessions, audio, transcripts).
- API hardening: CORS policy, rate limiting, request validation, secure
  headers; auth only if deployment requires (not a V1 blocker).
- Privacy documentation: SECURITY.md + PRIVACY.md; local-only mode where
  practical (no candidate data sent to cloud when local routing suffices).

## Alternatives

- Trust LLM output directly — rejected: state corruption + injection risk.
- No upload limits — rejected: DoS/malware vector.

## Tradeoffs

- Validation overhead on ingestion; stricter content policy may reject edge
  files (acceptable).

## Consequences

- Security tests: injection fixtures, oversized uploads, structured-output
  validation, redaction assertions, authz checks.
- SECURITY.md/PRIVACY.md published; threat model documented in
  `docs/operations/security.md`.
