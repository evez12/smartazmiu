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
DATABASE_URL ?= postgresql+asyncpg://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@localhost:$(POSTGRES_PORT)/$(POSTGRES_DB)
TEST_DATABASE_URL ?= postgresql+asyncpg://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@localhost:$(POSTGRES_PORT)/smartazmiu_test
REDIS_URL ?= redis://localhost:$(REDIS_PORT)/0
TEST_REDIS_URL ?= redis://localhost:$(REDIS_PORT)/15
OIDC_ISSUER ?= $(OIDC_PUBLIC_URL)/realms/$(KEYCLOAK_REALM)
OIDC_INTERNAL_URL ?= $(OIDC_ISSUER)
OIDC_JWKS_URL ?= $(OIDC_INTERNAL_URL)/protocol/openid-connect/certs
APP_URL ?= $(WEB_DEV_URL)
API_INTERNAL_URL ?= http://localhost:8000

.PHONY: help
help: ## Show available targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'

.env: .env.example
	@if [ -f .env ]; then echo ".env is older than .env.example; compare them manually." >&2; touch .env; exit 0; fi
	@cp .env.example .env
	@while grep -q '=generate$$' .env; do sed -i "0,/=generate$$/s//=$$(openssl rand -hex 24)/" .env; done
	@echo "Created .env with fresh local secrets."

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
