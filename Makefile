.PHONY: setup dev smtp test lint typecheck openapi reset preflight frontend-build

setup:
	uv sync --project backend
	cd frontend && npm ci
	uv run --project backend alembic -c backend/alembic.ini upgrade head
	$(MAKE) openapi

dev:
	uv run --project backend python -m app.actions.email.local_smtp_server --port "$${WP_SMTP_PORT:-2525}" --maildir runtime/mail & \
	smtp_pid=$$!; \
	uv run --project backend uvicorn --app-dir backend app.api.main:app --host 127.0.0.1 --port 8001 --reload & \
	backend_pid=$$!; \
	trap 'kill $$backend_pid $$smtp_pid 2>/dev/null || true' EXIT; \
	cd frontend && npm run dev

smtp:
	uv run --project backend python -m app.actions.email.local_smtp_server --port "$${WP_SMTP_PORT:-2525}" --maildir runtime/mail

test:
	uv run --project backend pytest backend/tests

lint:
	uv run --project backend ruff check backend/app backend/tests data/appelia
	uv run --project backend ruff format --check backend/app backend/tests
	cd frontend && npm run lint

typecheck:
	cd backend && MYPYPATH=.:../data uv run --project . mypy --strict --explicit-package-bases app/contracts app/core app/ingestion app/rules ../data/appelia
	cd frontend && npm run typecheck

openapi:
	uv run --project backend python -c 'from app.api.main import app; import json; from pathlib import Path; Path("backend/app/contracts/openapi.json").write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")'
	cd frontend && npm run openapi

reset:
	curl --fail --silent --show-error -X POST http://127.0.0.1:8001/api/demo/reset

preflight:
	curl --fail --silent --show-error http://127.0.0.1:8001/api/demo/preflight

frontend-build:
	cd frontend && npm run build
