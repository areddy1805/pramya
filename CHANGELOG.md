# Changelog

All notable changes to Pramya are recorded here.
Format based on [Keep a Changelog](https://keepachangelog.com/); versions follow [SemVer](https://semver.org/).

## [Unreleased]

### Added

- Master implementation plan (`docs/MASTER_IMPLEMENTATION_PLAN.md`): product vision, architecture, domain model, framework boundaries, AI/voice/retrieval/evaluation architecture, 13 implementation phases with tasks/tests/acceptance criteria, 30-day schedule, risk register, progress tracker.
- Decision records (`docs/DECISIONS.md` + `docs/architecture/ADR-006..020`): framework boundaries, LangGraph workflow, LlamaIndex knowledge layer, evidence-first evaluation, pgvector, observability, evaluation strategy, security/PII, model stack, oMLX runtime, speech stack, MCP boundary, persistence, modular monolith, deployment.
- Model catalog (`docs/MODEL_CATALOG.md`): 8-model definitive V1 stack with verified licenses, MLX weights, memory, fallbacks; alternative/research models documented.
- Architecture companions (`docs/ai/`): AI, Voice, Retrieval, Evaluation.
- Operations docs (`docs/operations/`): Deployment, Troubleshooting.
- Project memory refreshed with verified environment/model/framework facts.
- Updated `.env.example` (DeepSeek v4 flash, oMLX, voice retention, Langfuse, uploads).

### Changed

- Repository skeleton only; no product implementation yet.

## [0.0.0] — 2026-08

### Added

- Initial repository: `AGENTS.md`, README, LICENSE, `.gitignore`, `.env.example`, docs stubs.
