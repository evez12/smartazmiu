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
REDIS_URL ?= redis://127.0.0.1:$(REDIS_PORT)/0
TEST_REDIS_URL ?= redis://127.0.0.1:$(REDIS_PORT)/15
OIDC_ISSUER ?= $(OIDC_PUBLIC_URL)/realms/$(KEYCLOAK_REALM)
OIDC_INTERNAL_URL ?= $(OIDC_ISSUER)
OIDC_JWKS_URL ?= $(OIDC_INTERNAL_URL)/protocol/openid-connect/certs
APP_URL ?= $(WEB_DEV_URL)
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
infra: .env ## Start infrastructure services (postgres, redis, s3, keycloak, mailpit)
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

.PHONY: migration
migration: ## Create a migration: make migration m="add enrollments"
	@test -n "$(m)" || (echo 'usage: make migration m="message"' >&2; exit 1)
	$(UV) run alembic revision --autogenerate -m "$(m)"

.PHONY: dev-api
dev-api: ## Run the API with reload on :8000
	$(UV) run uvicorn app.main:app --reload --port 8000 --no-access-log

.PHONY: dev-web
dev-web: ## Run the web app with reload on :3000
	$(PNPM) dev

# --- Quality ------------------------------------------------------------------

.PHONY: lint
lint: ## Lint, format-check and type-check both apps
	$(UV) run ruff check .
	$(UV) run ruff format --check .
	$(UV) run mypy
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
	$(COMPOSE) up -d --wait postgres redis

.PHONY: test-api
test-api: test-deps ## Run backend tests with coverage
	DATABASE_URL=$(TEST_DATABASE_URL) REDIS_URL=$(TEST_REDIS_URL) APP_ENV=test \
		$(UV) run pytest --cov --cov-report=term-missing

.PHONY: test-web
test-web: ## Run frontend unit tests
	$(PNPM) test

.PHONY: e2e
e2e: ## Run Playwright functional and accessibility tests (starts the dev server if needed)
	$(PNPM) exec playwright test --project=functional

# Screenshot baselines exist only for the pinned Linux image (DECISIONS D-007). The container keeps its own
# node_modules and .next so it never touches the host's Windows builds.
PLAYWRIGHT_IMAGE := mcr.microsoft.com/playwright:v1.64.1-noble
VISUAL_RUN = MSYS_NO_PATHCONV=1 docker run --rm --ipc=host -e CI=1 	-v "$(CURDIR)/$(WEB_DIR):/work" -v smartazmiu-visual-node-modules:/work/node_modules 	-v smartazmiu-visual-next:/work/.next -w /work $(PLAYWRIGHT_IMAGE) 	bash -c "npm install --global --silent pnpm@12.15.0 && pnpm install --frozen-lockfile --silent && pnpm exec playwright test --project=visual $(1)"

.PHONY: visual
visual: ## Compare screenshots with the baselines (Docker)
	$(call VISUAL_RUN)

.PHONY: visual-update
visual-update: ## Re-record screenshot baselines after an intended UI change (Docker)
	$(call VISUAL_RUN,--update-snapshots)
