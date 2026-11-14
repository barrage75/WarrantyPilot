<<<<<<< HEAD
.PHONY: setup dev smtp test p0 lint typecheck openapi login reset preflight frontend-build
||||||| parent of 13ec235 (feat(securite): écran de connexion, session frontend, e2e authentifiés et ancrage non bloquant)
.PHONY: setup dev smtp test lint typecheck openapi login reset preflight frontend-build
=======
.PHONY: setup seed dev smtp test lint typecheck openapi login reset preflight frontend-build
>>>>>>> 13ec235 (feat(securite): écran de connexion, session frontend, e2e authentifiés et ancrage non bloquant)

setup:
	uv sync --project backend
	cd frontend && npm ci
	uv run --project backend alembic -c backend/alembic.ini upgrade head
	$(MAKE) seed
	$(MAKE) openapi

seed:
	uv run --project backend python -m app.core.reset

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
	uv run --project backend pytest -m "not p0" backend/tests

p0:
	uv sync --project repro/dell --locked
	uv run --project backend playwright install chromium
	@set -eu; \
	(cd repro/dell && DELL_REPRO_PORT=8100 DELL_REPRO_RUNTIME="$$(mktemp -d)" uv run --locked python -m dell_repro) & \
	dell_pid=$$!; \
	trap 'kill "$$dell_pid" 2>/dev/null || true; wait "$$dell_pid" 2>/dev/null || true' EXIT; \
	attempt=0; \
	ready=0; \
	while kill -0 "$$dell_pid" 2>/dev/null; do \
		if curl --fail --silent http://127.0.0.1:8100/__test__/cases >/dev/null; then \
			ready=1; \
			break; \
		fi; \
		attempt=$$((attempt + 1)); \
		if [ "$$attempt" -ge 60 ]; then break; fi; \
		sleep 1; \
	done; \
	if [ "$$ready" -ne 1 ]; then \
		echo "Dell reproduction did not start on 127.0.0.1:8100" >&2; \
		exit 1; \
	fi; \
	uv run --project backend pytest -m p0 backend/tests/p0/test_p0_gate.py

lint:
	cd backend && uv run ruff check app tests ../data/appelia
	cd backend && uv run ruff format --check app tests
	cd frontend && npm run lint

typecheck:
	cd backend && MYPYPATH=.:../data uv run --project . mypy --strict --explicit-package-bases app/contracts app/core app/ingestion app/rules ../data/appelia
	cd frontend && npm run typecheck

openapi:
	uv run --project backend python -c 'from app.api.main import app; import json; from pathlib import Path; Path("backend/app/contracts/openapi.json").write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")'
	cd frontend && npm run openapi

WP_ADMIN_ID ?= 97225c38-d686-5d99-a6cf-53e18aa92e8d
WP_API ?= http://127.0.0.1:8001/api
WP_COOKIES := runtime/.make-session

login:
	@mkdir -p runtime
	@curl --fail --silent --show-error -o /dev/null -c $(WP_COOKIES) -H 'Content-Type: application/json' \
		-d "{\"person_id\":\"$(WP_ADMIN_ID)\",\"password\":\"$${WP_DEMO_PASSWORD:-appelia-demo}\"}" $(WP_API)/auth/login

reset: login
	curl --fail --silent --show-error -b $(WP_COOKIES) -H 'Content-Type: application/json' \
		-d '{"confirm":"RESET"}' $(WP_API)/demo/reset

preflight: login
	curl --fail --silent --show-error -b $(WP_COOKIES) $(WP_API)/demo/preflight

frontend-build:
	cd frontend && npm run build
