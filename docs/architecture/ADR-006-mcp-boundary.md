# ADR-006 — MCP Boundary

**Status:** Accepted
**Date:** 2026-08

## Context

MCP must be a real interoperability boundary, not the internal application
architecture. Core services must not depend on MCP for ordinary database/service
operations. Spec requires at least one genuine external interoperability use case.

## Problem

Where does MCP fit without becoming the internal architecture?

## Decision

- Ship a deliberately small MCP server (`mcp_server/` package) exposing
  read-oriented tools + resources:
  - Tools: `candidate_profile_lookup`, `evidence_search`, `role_requirements`,
    `interview_history`, `practice_history`.
  - Resources: candidate profile, target role, preparation plan.
- The MCP server is an adapter over domain/application services (thin).
- Internal code (API layer, services, LangGraph nodes) calls domain services
  directly. Never Application → MCP → Application Service.
- One genuine external use case: an external MCP-compatible client/agent
  (e.g., a coding agent or external assistant) queries a candidate's evidence
  and preparation state through the MCP server; verified by integration test
  against a real MCP client.
- SDK choice: pin `mcp>=1.27,<2` (classic `FastMCP` API, production-safe
  stable line) for V1. v2.0.0 (`MCPServer` rename, 2026-07-28 stateless
  protocol) evaluated at upgrade time. Transport: streamable HTTP, mounted in
  the FastAPI app (`mcp.streamable_http_app()`), served under `/mcp`.

## Alternatives

- MCP as primary service layer — rejected: forbidden by spec; couples
  everything to MCP lifecycle.
- No MCP — rejected: required learning objective + interop.

## Tradeoffs

- Extra surface to secure (auth on `/mcp` via Bearer middleware; streamable
  HTTP has no built-in auth).
- v1/v2 SDK churn — pinned to avoid breakage.

## Consequences

- `mcp_server/` package + FastAPI mount + tests with real MCP client.
- External-use-case documented in README + tests/contract/mcp.
