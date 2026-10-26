# Single task runner for local development (Git Bash on Windows) and CI (Linux).
SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help
MAKEFLAGS += --no-builtin-rules --no-print-directory

-include .env
export

API_DIR := apps/api
WEB_DIR := apps/web
UV := uv --directory $(API_DIR)
PNPM := pnpm --dir $(WEB_DIR)
COMPOSE := docker compose

# Connection settings for the natively running api/web processes (Docker uses its own values).
# 127.0.0.1 rather than localhost: on Windows the IPv6 attempt adds ~2 s per new connection.
DATABASE_URL ?= postgresql+asyncpg://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@127.0.0.1:$(POSTGRES_PORT)/$(POSTGRES_DB)
TEST_DATABASE_URL ?= postgresql+asyncpg://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@127.0.0.1:$(POSTGRES_PORT)/smartazmiu_test
# Two Redis instances (D-053): A (`REDIS_PORT`) for web sessions and the job queue, B (`REDIS_CACHE_PORT`) for
# disposable data such as rate limits.
REDIS_URL ?= redis://127.0.0.1:$(REDIS_CACHE_PORT)/0
QUEUE_REDIS_URL ?= redis://127.0.0.1:$(REDIS_PORT)/0
TEST_REDIS_URL ?= redis://127.0.0.1:$(REDIS_CACHE_PORT)/15
# Snowflake leases and WebSocket tickets live on A (D-056); tests use their own database there.
TEST_QUEUE_REDIS_URL ?= redis://127.0.0.1:$(REDIS_PORT)/15
# Web sessions (D-037) use their own database so API cache flushes never sign anyone out.
SESSION_REDIS_URL ?= redis://127.0.0.1:$(REDIS_PORT)/1
S3_ENDPOINT_URL ?= http://127.0.0.1:$(S3_PORT)
# Natively the browser uploads straight to the store; the web dev server allows its origin in the CSP.
S3_PUBLIC_URL ?= http://localhost:$(S3_PORT)
STORAGE_PUBLIC_URL ?= $(S3_PUBLIC_URL)
CLAMAV_HOST ?= 127.0.0.1
KEYCLOAK_URL ?= http://127.0.0.1:$(KEYCLOAK_PORT)
OIDC_ISSUER ?= $(OIDC_PUBLIC_URL)/realms/$(KEYCLOAK_REALM)
OIDC_INTERNAL_URL ?= $(OIDC_ISSUER)
OIDC_JWKS_URL ?= $(OIDC_INTERNAL_URL)/protocol/openid-connect/certs
APP_URL ?= $(WEB_DEV_URL)
# The native web dev server runs on another origin than APP_PUBLIC_URL; it may open chat sockets (ADR 0003).
WS_ALLOWED_ORIGINS ?= ["$(WEB_DEV_URL)"]
# Natively the browser reaches the API's WebSocket directly; behind nginx it is /ws on the app's origin.
WS_PUBLIC_URL ?= ws://localhost:8000/ws
API_INTERNAL_URL ?= http://127.0.0.1:8000

.PHONY: help
help: ## Show available targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'

.env: .env.example
	@if [ -f .env ]; then \
		echo ".env is older than .env.example; review the new settings manually." >&2; \
		touch .env; \
	else \
		cp .env.example .env; \
		while grep -q '=generate$$' .env; do \
			sed -i "0,/=generate$$/s//=$$(openssl rand -hex 24)/" .env; \
		done; \
		echo "Created .env with fresh local secrets."; \
	fi

.PHONY: env
env: .env ## Create .env from .env.example with generated secrets

.PHONY: install
install: .env ## Install backend and frontend dependencies and git hooks
	$(UV) sync --frozen
	$(PNPM) install --frozen-lockfile
	uv run --project $(API_DIR) pre-commit install

# --- Docker -----------------------------------------------------------------

.PHONY: infra
infra: .env ## Start infrastructure services (postgres, redis, s3, clamav, keycloak, mailpit)
	$(COMPOSE) up -d --wait

.PHONY: up
up: .env ## Build and start the full stack in Docker (http://localhost)
	$(COMPOSE) --profile app up -d --build --wait
	@echo "Stack is running at $(APP_PUBLIC_URL)"

.PHONY: down
down: ## Stop all containers
	$(COMPOSE) --profile app down

.PHONY: reset
reset: ## Stop all containers and delete their volumes
	$(COMPOSE) --profile app down --volumes

.PHONY: logs
logs: ## Follow container logs
	$(COMPOSE) --profile app logs -f --tail=100

# --- Native development -------------------------------------------------------

.PHONY: migrate
migrate: ## Apply database migrations
	$(UV) run alembic upgrade head

.PHONY: seed
seed: ## Load the sample academic data (groups 764a1, 765a1, 765a2) through the import pipeline
	$(UV) run python -m app.modules.academics.seed ../../infra/seed/academics

.PHONY: migration
migration: ## Create a migration: make migration m="add enrollments"
	@test -n "$(m)" || (echo 'usage: make migration m="message"' >&2; exit 1)
	$(UV) run alembic revision --autogenerate -m "$(m)"

.PHONY: audit
audit: ## Check dependencies for known vulnerabilities
	$(UV) export --frozen --no-hashes --no-emit-project --format requirements-txt > $(API_DIR)/.audit-requirements.txt
	uvx pip-audit@2.10.1 --strict --requirement $(API_DIR)/.audit-requirements.txt; status=$$?; rm -f $(API_DIR)/.audit-requirements.txt; exit $$status
	$(PNPM) audit --audit-level high

.PHONY: openapi-check
openapi-check: openapi ## Fail if the committed OpenAPI document or web client is out of date
	git diff --exit-code -- $(API_DIR)/openapi.json $(WEB_DIR)/src/lib/api/schema.d.ts

.PHONY: openapi
openapi: ## Export the OpenAPI document and regenerate the typed web client
	$(UV) run python -m app.openapi > $(API_DIR)/openapi.json
	$(PNPM) exec openapi-typescript ../api/openapi.json --output src/lib/api/schema.d.ts
	$(PNPM) exec prettier --write --log-level warn src/lib/api/schema.d.ts

.PHONY: dev-api
dev-api: ## Run the API with reload on :8000
	$(UV) run uvicorn app.main:app --reload --port 8000 --no-access-log

.PHONY: dev-worker
dev-worker: ## Run the ARQ worker (notification delivery, audience sync)
	$(UV) run arq app.workers.main.WorkerSettings

.PHONY: dev-web
dev-web: ## Run the web app with reload on :3000
	$(PNPM) dev

# --- Quality ------------------------------------------------------------------

.PHONY: lint lint-api lint-web
lint: lint-api lint-web ## Lint, format-check and type-check both apps

lint-api:
	$(UV) run ruff check .
	$(UV) run ruff format --check .
	$(UV) run mypy

lint-web:
	$(PNPM) lint --max-warnings=0
	$(PNPM) format:check
	$(PNPM) typecheck

.PHONY: format
format: ## Apply formatters
	$(UV) run ruff check --fix .
	$(UV) run ruff format .
	$(PNPM) format

.PHONY: test
test: test-api test-web ## Run all unit and integration tests

.PHONY: test-deps
test-deps: .env
	$(COMPOSE) up -d --wait postgres redis redis-cache s3 clamav

.PHONY: test-api
test-api: test-deps ## Run backend tests with coverage
	DATABASE_URL=$(TEST_DATABASE_URL) REDIS_URL=$(TEST_REDIS_URL) QUEUE_REDIS_URL=$(TEST_QUEUE_REDIS_URL) S3_BUCKET=smartazmiu-test APP_ENV=test \
		$(UV) run pytest --cov --cov-report=term-missing

.PHONY: test-web
test-web: ## Run frontend unit tests
	$(PNPM) test

# The suite runs on the seeded sample data and checks that it leaves the seed tables as it found them.
.PHONY: e2e
e2e: seed ## Run Playwright functional and accessibility tests (starts the dev server if needed)
	$(PNPM) exec playwright test --project=functional

# Screenshot baselines exist only for the pinned Linux image (DECISIONS D-007). The container keeps its own
# node_modules and .next so it never touches the host's Windows builds.
PLAYWRIGHT_IMAGE := mcr.microsoft.com/playwright:v1.64.1-noble
VISUAL_RUN = MSYS_NO_PATHCONV=1 docker run --rm --ipc=host -e CI=1 -e E2E_DATA_CHECK=off 	-v "$(CURDIR)/$(WEB_DIR):/work" -v smartazmiu-visual-node-modules:/work/node_modules 	-v smartazmiu-visual-next:/work/.next -w /work $(PLAYWRIGHT_IMAGE) 	bash -c "npm install --global --silent pnpm@12.15.0 && pnpm install --frozen-lockfile --silent && pnpm exec playwright test --project=visual $(1)"

.PHONY: visual
visual: ## Compare screenshots with the baselines (Docker)
	$(call VISUAL_RUN)

.PHONY: visual-update
visual-update: ## Re-record screenshot baselines after an intended UI change (Docker)
	$(call VISUAL_RUN,--update-snapshots)
