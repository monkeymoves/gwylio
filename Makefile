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
SEED_HITS := $(CURDIR)/backend/tests/fixtures/seed_hits.json
SEED_ENV := GWYLIO_DATA_DIR=$(SEED_DIR) GWYLIO_DB_PATH= GWYLIO_ACADEMIC=

.PHONY: help setup check test e2e ci build schema seed dev serve frontend-dev collect ingest publish

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

seed: ## Recreate the seed data under backend/tests/fixtures/seed: four fake runs, three submissions, a sweep, two products
	rm -rf $(SEED_DIR)
	$(SEED_ENV) $(UV) gwylio migrate
	$(SEED_ENV) $(UV) gwylio collect --fake --at 2026-09-01T09:00:00+0000
	$(SEED_ENV) $(UV) gwylio ingest $(SEED_SUBMISSIONS)/20260901T0900Z-0000__1.json
	$(SEED_ENV) $(UV) gwylio collect --fake --at 2026-10-01T09:00:00+0000
	$(SEED_ENV) $(UV) gwylio ingest $(SEED_SUBMISSIONS)/20261001T0900Z-0000__1.json
	$(SEED_ENV) $(UV) gwylio collect --fake --hits $(SEED_HITS) --at 2026-10-03T09:00:00+0000
	$(SEED_ENV) $(UV) gwylio ingest $(SEED_SUBMISSIONS)/20261003T0900Z-0000__1.json
	$(SEED_ENV) $(UV) gwylio collect --fake --hits $(SEED_HITS) --at 2026-10-04T09:00:00+0000
	$(SEED_ENV) $(UV) gwylio sweep --today 2026-10-05
	$(SEED_ENV) $(UV) gwylio product --level operational --period 2026-10 --today 2026-10-06
	$(SEED_ENV) $(UV) gwylio product --level strategic --period 2026 --today 2026-10-06
	$(SEED_ENV) $(UV) gwylio datecheck --today 2026-10-06

dev: ## Run the read API (port 8000) and the Vite dev server together; Ctrl+C stops both
	$(UV) gwylio serve & api=$$!; trap 'kill $$api 2>/dev/null || true' EXIT; $(PNPM) dev

serve: ## Run only the read API on http://localhost:8000/api/v1
	$(UV) gwylio serve

frontend-dev: ## Run only the Vite dev server
	$(PNPM) dev

collect: ## Run a scan and write a candidates file (web and site need a Brave key)
	$(UV) gwylio collect

ingest: ## Ingest an analyst submission: make ingest FILE=data/submissions/<run_id>__<n>.json
	@test -n "$(FILE)" || { echo "ingest: name the submission, make ingest FILE=path"; exit 2; }
	$(UV) gwylio ingest $(abspath $(FILE))

publish: ## Publish the snapshot the static site reads (frontend/static/data and data/snapshots)
	$(UV) gwylio publish
