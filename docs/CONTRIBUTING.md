# Contributing to Pramya

Thanks for considering a contribution. The project is engineered for
correctness, determinism, and honest status — the contribution process
reflects that.

## Setup

```bash
git clone <your-fork>/pramya.git && cd pramya
cp .env.example .env        # add DEEPSEEK_API_KEY for anything that calls the LLM
make up                     # postgres+pgvector (+ backend/frontend images)
make migrate
make backend-install        # uv sync
make frontend-install       # pnpm install
make demo-setup             # optional: 4-role demo dataset
```

## Conventions

- **Python 3.12/3.13**, `uv`; **Node 20+**, `pnpm`.
- Backend: FastAPI + SQLAlchemy async; all model access through the
  `InferenceRouter` (never call providers directly from business code).
- Frontend: React 19 + TypeScript strict; components consume semantic tokens
  only (no hard-coded colors); dark/light/system themes must stay correct.
- Deterministic logic over LLM calls wherever equivalent behavior exists.
- Treat model output as untrusted data: validate before persisting.
- Never log or trace raw candidate content (resumes, answers, transcripts).

## Definition of done (before opening a PR)

1. `make lint` — ruff + oxlint clean
2. `make typecheck` — mypy + pyright + tsc clean
3. `make test` — unit + contract green
4. `make test-integration` — integration green (isolated `pramya_test` DB)
5. If the change touches user-visible flows: `make e2e` green
6. If the change touches AI behavior: a golden case in `tests/evals/` (see
   `docs/EVALUATION.md`); borderline judge variance is recorded as WARNING,
   never gamed to PASS
7. Docs: if behavior changed, update the relevant `docs/` file (plan,
   ADR, architecture, operations) — documentation must describe reality
8. Commit: one coherent feature/phase per commit, human-readable message,
   no secrets, no local runtime state (`.runtime/`, `.pi/`)

## Testing notes

- Integration tests create and drop the isolated `pramya_test` database per
  run — they never touch the dev `pramya` database.
- Voice engine tests use stubs (no real oMLX). Real-model E2E requires the
  local oMLX runtime and a microphone (or the fake-device WAV harness,
  `frontend/scripts/voice_e2e_real.mjs`).
- `make evals` costs DeepSeek tokens (judge = `deepseek-v4-flash`); run it
  deliberately, not in a tight loop.

## Reporting issues

- Bugs: include the `X-Request-ID` from the failing response, the endpoint,
  and the backend log lines around the failure.
- Security: see `docs/operations/SECURITY.md` — do not open a public issue
  for credential/secrets problems.
