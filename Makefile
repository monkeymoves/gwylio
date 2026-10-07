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
SEED_SITE := $(CURDIR)/.seed-site
SEED_SITE_ENV := GWYLIO_DATA_DIR=$(SEED_SITE)/data GWYLIO_DB_PATH= GWYLIO_ACADEMIC=

.PHONY: help setup check test e2e ci build schema seed dev serve frontend-dev collect ingest publish deploy site-password seed-screenshots

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

deploy: ## Publish the snapshot, build the static site and deploy it to Firebase Hosting
	@command -v firebase >/dev/null 2>&1 || { echo "deploy: the firebase command is missing; install the Firebase CLI (npm install -g firebase-tools), run firebase login and firebase use --add, then make deploy again" >&2; exit 1; }
	$(UV) gwylio publish
	$(PNPM) build
	firebase deploy --only hosting

site-password: ## Set the hosted site's password screen (prompts; keeps only a hash in the gitignored frontend/.env.production.local)
	@read -r -s -p "Site password: " pw; echo; \
	test -n "$$pw" || { echo "site-password: no password given, nothing changed" >&2; exit 1; }; \
	read -r -s -p "Same again: " again; echo; \
	test "$$pw" = "$$again" || { echo "site-password: the two entries differ, nothing changed" >&2; exit 1; }; \
	hash=$$(printf 'gwylio-site:%s' "$$pw" | shasum -a 256 | cut -d' ' -f1); \
	printf 'PUBLIC_GWYLIO_SITE_PASSWORD_SHA256=%s\n' "$$hash" > frontend/.env.production.local; \
	echo "site-password: hash written to frontend/.env.production.local; run make deploy to put the screen live"

seed-screenshots: ## Build a scratch copy of the site from the seed fixture, run Playwright on it, keep the screenshots in docs/evidence/seed
	@if (exec 3<>/dev/tcp/127.0.0.1/4173) 2>/dev/null; then echo "seed-screenshots: port 4173 is in use; stop that server first" >&2; exit 1; fi
	rm -rf $(SEED_SITE)
	mkdir -p $(SEED_SITE)/frontend
	cp -r $(SEED_DIR) $(SEED_SITE)/data
	rm -f $(SEED_SITE)/data/gwylio.sqlite*
	tar -C frontend --exclude=./node_modules --exclude=./build --exclude=./.svelte-kit --exclude=./static/data --exclude=./test-results -cf - . | tar -C $(SEED_SITE)/frontend -xf -
	ln -s $(CURDIR)/frontend/node_modules $(SEED_SITE)/frontend/node_modules
	$(SEED_SITE_ENV) $(UV) gwylio rebuild
	$(SEED_SITE_ENV) $(UV) gwylio publish --out $(SEED_SITE)/frontend/static/data --at 2026-10-06T09:00:00+0000
	status=0; pnpm -C $(SEED_SITE)/frontend e2e || status=$$?; \
	rm -rf docs/evidence/seed; mkdir -p docs/evidence/seed; \
	cp -r $(SEED_SITE)/docs/evidence/. docs/evidence/seed/; \
	rm -rf $(SEED_SITE); exit $$status
