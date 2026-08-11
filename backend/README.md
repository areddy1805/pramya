# Pramya Backend

FastAPI application layer for Pramya — evidence-driven interview preparation.

See `../docs/MASTER_IMPLEMENTATION_PLAN.md` for architecture, phases, and tasks.

## Layout

- `app/main.py` — FastAPI entrypoint (lifespan, router registration)
- `app/core/` — config, logging, middleware, dependencies
- `app/api/v1/` — versioned REST routers
- `app/domain/` — Pydantic schemas + state enums
- `app/services/` — application services (added in later phases)
- `app/interview/` — LangGraph interview workflow (Phase 3)
- `app/knowledge/` — LlamaIndex ingestion + retrieval (Phase 2)
- `app/ai/` — InferenceRouter + providers (Phase 4)
- `app/voice/` — audio state machine, ASR/TTS (Phase 7)

Tests live at the repository root under `tests/` (unit / integration / contract / e2e / evals).

## Development

```sh
uv sync
uv run pytest
uv run ruff check .
uv run mypy app
```
