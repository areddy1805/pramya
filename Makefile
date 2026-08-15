.PHONY: up down logs ps \
        dev dev-down dev-status dev-logs dev-verify dev-reset \
        test test-unit test-integration evals lint typecheck \
        dev-backend dev-frontend migrate models-pull demo-setup \
        backend-install frontend-install

# --- Docker ----------------------------------------------------------------

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

ps:
	docker compose ps

# --- Tests -----------------------------------------------------------------

test: test-unit test-contract

test-unit:
	cd backend && uv run pytest -c pyproject.toml ../tests/unit -q

test-contract:
	cd backend && uv run pytest -c pyproject.toml ../tests/contract -q

test-integration:
	cd backend && PYTHONPATH=.. uv run pytest ../tests/integration -p no:warnings

e2e:
	cd frontend && pnpm exec playwright test

evals:
	cd backend && uv run pytest -c pyproject.toml ../tests/evals -q

# --- Quality ---------------------------------------------------------------

lint:
	cd backend && uv run ruff check app ../tests
	cd frontend && pnpm lint

typecheck:
	cd backend && uv run mypy app
	cd frontend && pnpm exec tsc -b --noEmit

# --- Dev -------------------------------------------------------------------

dev: ; @bash scripts/dev up

dev-down:
	@bash scripts/dev down

dev-status:
	@bash scripts/dev status

dev-logs:
	@bash scripts/dev logs

dev-verify:
	@bash scripts/dev check

dev-reset:
	@bash scripts/dev reset

dev-backend:
	cd backend && uv run uvicorn app.main:app --reload --port 8001

dev-frontend:
	cd frontend && pnpm dev

migrate:
	cd backend && uv run alembic upgrade head

models-pull:
	@echo "See docs/MODEL_CATALOG.md for model download commands (Phase 4/7)."

demo-setup:
	cd backend && uv run python ../scripts/seed_demo.py

# --- Install ---------------------------------------------------------------

backend-install:
	cd backend && uv sync

frontend-install:
	cd frontend && pnpm install
