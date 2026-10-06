# Gwylio task runner. Run every target from the repository root.
#
# Backend commands run inside the uv project in backend/ (uv run --directory
# backend, so tool configuration in backend/pyproject.toml resolves correctly).
# Frontend commands run with pnpm -C frontend.

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

UV := uv run --directory backend
PNPM := pnpm -C frontend
SEED_DIR := backend/tests/fixtures/seed
SEED_SUBMISSIONS := $(CURDIR)/backend/tests/fixtures/seed_submissions
SEED_ENV := GWYLIO_DATA_DIR=$(SEED_DIR) GWYLIO_DB_PATH= GWYLIO_ACADEMIC=

.PHONY: help setup check test e2e ci build schema seed dev collect ingest publish

help: ## List the targets
	@grep -E '^[a-z][a-z-]*:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

setup: ## Install backend and frontend dependencies from the lock files
	uv sync --directory backend --locked
	$(PNPM) install --frozen-lockfile

check: ## Lint, format check, type check, validate config and check generated files
	$(UV) ruff check .
	$(UV) ruff format --check .
	$(UV) mypy
	$(UV) gwylio check
	$(UV) gwylio schema --check
	$(PNPM) check

test: ## Run the backend and frontend unit test suites
	$(UV) pytest
	$(PNPM) test

build: ## Build the static site into frontend/build
	$(PNPM) build

e2e: ## Build the site, serve it with vite preview and run Playwright
	$(PNPM) e2e

ci: check test build ## Everything continuous integration runs, except end to end

schema: ## Generate JSON Schema, TypeScript types, the glossary and the skill reference
	$(UV) gwylio schema

seed: ## Recreate the seed data under backend/tests/fixtures/seed: two fake runs, two submissions
	rm -rf $(SEED_DIR)
	$(SEED_ENV) $(UV) gwylio migrate
	$(SEED_ENV) $(UV) gwylio collect --fake --at 2026-09-01T09:00:00+0000
	$(SEED_ENV) $(UV) gwylio ingest $(SEED_SUBMISSIONS)/20260901T0900Z-0000__1.json
	$(SEED_ENV) $(UV) gwylio collect --fake --at 2026-10-01T09:00:00+0000
	$(SEED_ENV) $(UV) gwylio ingest $(SEED_SUBMISSIONS)/20261001T0900Z-0000__1.json
	$(SEED_ENV) $(UV) gwylio datecheck --today 2026-10-06

dev: ## Run the read API and the dev server together
	@echo "dev: not yet implemented (WP7)"

collect: ## Run a scan and write a candidates file (web and site need a Brave key)
	$(UV) gwylio collect

ingest: ## Ingest an analyst submission: make ingest FILE=data/submissions/<run_id>__<n>.json
	@test -n "$(FILE)" || { echo "ingest: name the submission, make ingest FILE=path"; exit 2; }
	$(UV) gwylio ingest $(abspath $(FILE))

publish: ## Publish the snapshot the static site reads
	@echo "publish: not yet implemented (WP7)"
