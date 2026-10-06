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

seed: ## Seed the register from the legacy signals
	@echo "seed: not yet implemented (WP5)"

dev: ## Run the read API and the dev server together
	@echo "dev: not yet implemented (WP7)"

collect: ## Run a scan and write a candidates file
	@echo "collect: real collectors arrive in WP4; for a dry run on fakes use: $(UV) gwylio collect --dry-run"

ingest: ## Ingest an analyst submission
	@echo "ingest: not yet implemented (WP5)"

publish: ## Publish the snapshot the static site reads
	@echo "publish: not yet implemented (WP7)"
