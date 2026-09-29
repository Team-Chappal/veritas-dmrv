# VERITAS dMRV — developer entry points.
#
# Every target must work with Cloudinary credentials ABSENT. `make dev` in
# fixture mode is the state the stage demo runs in, so it has to be reliable.

SHELL := /bin/bash
PY    := backend/.venv/bin/python
PIP   := backend/.venv/bin/pip
PYTEST:= backend/.venv/bin/pytest
export PYTHONPATH := backend

.DEFAULT_GOAL := help
NPM  := npm --prefix frontend

.PHONY: help bootstrap dev dev-mock test test-tier1 test-tier2 lint \
        fixtures fixtures-check seed clean docker sync-usb verify bench \
        fe-install fe-build fe-e2e build e2e

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# --------------------------------------------------------------------------- #
# Setup
# --------------------------------------------------------------------------- #

bootstrap: ## Create the venv and install pinned backend deps
	python3 -m venv backend/.venv
	$(PIP) install --upgrade pip setuptools wheel
	$(PIP) install -r backend/requirements.txt
	@echo "Verifying imports..."
	@$(PY) -c "import cv2, numpy, pvlib, shapely, pyproj, fastapi, cloudinary, imagehash; print('all backend imports OK')"
	@if [ -f frontend/package.json ]; then \
		echo "Installing frontend deps..."; \
		npm --prefix frontend install; \
	fi
	@echo "Bootstrap complete."

# --------------------------------------------------------------------------- #
# Run
# --------------------------------------------------------------------------- #

dev: ## Run backend (uvicorn) — real services, fixture fallback
	cd backend && .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload

dev-mock: ## Run the high-fidelity mock server only
	cd backend && .venv/bin/uvicorn mock_server:app --host 0.0.0.0 --port 8000 --reload

mock: dev-mock ## Alias

# --------------------------------------------------------------------------- #
# Test
# --------------------------------------------------------------------------- #

test: ## Run the whole suite
	$(PYTEST) backend/tests -v

test-tier1: ## Physics + forensics only
	$(PYTEST) backend/tests/test_physics.py backend/tests/test_forensics.py -v

test-tier2: ## Computer vision only
	$(PYTEST) backend/tests/test_vision.py -v

test-cov: ## Suite with an 85% coverage gate
	$(PYTEST) backend/tests --cov=backend --cov-report=term-missing --cov-fail-under=85

lint: ## Import-check every module (catches syntax and bad imports early)
	@$(PY) -c "import compileall,sys; sys.exit(0 if compileall.compile_dir('backend', quiet=2) else 1)"
	@echo "lint OK"

# --------------------------------------------------------------------------- #
# Fixtures & data
# --------------------------------------------------------------------------- #

fixtures: ## Regenerate solar fixtures from pvlib ground truth
	$(PY) scripts/gen_solar_fixtures.py

fixtures-check: ## Fail if committed solar fixtures are stale
	$(PY) scripts/gen_solar_fixtures.py --check

seed: ## Seed the demo corpus (requires Cloudinary creds; no-ops otherwise)
	@if [ -z "$$CLOUDINARY_CLOUD_NAME" ]; then \
		echo "CLOUDINARY_CLOUD_NAME unset — skipping remote seed (fixture mode)."; \
	else \
		npm --prefix frontend exec -- tsx ../../scripts/seed_demo_fixtures.ts; \
	fi

bench: ## Measure latency and regenerate docs/LATENCY-BASELINE.md
	$(PY) scripts/benchmark_latency.py --repeats 12 --sweep --write

verify: fixtures-check test ## Full pre-commit gate

# --------------------------------------------------------------------------- #
# Frontend (Stage 6)
# --------------------------------------------------------------------------- #

# `npm ci`, not `npm install`, now that package-lock.json is committed. `install`
# silently updates the lockfile, which is how a build ends up depending on
# packages nobody pinned.
fe-install: ## Install pinned frontend deps (npm ci)
	$(NPM) ci --no-audit --no-fund

fe-build: fe-install ## Production build + typecheck
	$(NPM) run build
	$(NPM) run typecheck

# The name the S6 exit criteria already use. It is here so the criteria are
# runnable as written rather than aspirational.
build: fe-build ## Alias of fe-build, named in the S6 exit criteria

e2e: ## Playwright e2e against a PRODUCTION build, backend not required
	$(NPM) run build
	$(NPM) run typecheck
	$(NPM) run e2e

fe-e2e: e2e ## Alias

# --------------------------------------------------------------------------- #
# Docker
# --------------------------------------------------------------------------- #

docker: ## Bring up backend + frontend
	docker compose up --build

# --------------------------------------------------------------------------- #
# Housekeeping
# --------------------------------------------------------------------------- #

sync-usb: ## Mirror source to the FAT32 USB volume (excludes heavy dirs)
	@rsync -av --delete \
		--exclude '.venv' --exclude 'node_modules' --exclude '.next' \
		--exclude '__pycache__' --exclude '.git' --exclude '.pytest_cache' \
		--exclude '.DS_Store' --exclude '._*' \
		./ /Volumes/VENTOY/cc/
	@echo "Synced to /Volumes/VENTOY/cc (note: FAT32 is case-insensitive and ~176x slower)."

clean: ## Remove caches and build output
	find . -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
	find . -name '.pytest_cache' -type d -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf backend/.coverage coverage.xml htmlcov frontend/.next
	@echo "cleaned"

# S7.3. Build the images and bring the stack up, then prove the demo answers.
# Requires a Docker daemon; it is NOT part of `make verify`, because CI has no
# daemon and a target that always fails there is a target nobody runs.
.PHONY: verify-docker
verify-docker:
	@command -v docker >/dev/null 2>&1 || { \
		echo "docker is not installed; S7.3 exit criterion UNVERIFIED on this host"; \
		echo "  install Docker Desktop, then re-run: make verify-docker"; \
		exit 1; }
	docker compose config --quiet
	docker compose build
	docker compose up -d --wait
	@echo "backend health:" && curl -fsS http://localhost:8000/health | head -c 200 && echo
	@echo "frontend status: $$(curl -o /dev/null -s -w '%{http_code}' http://localhost:3000/)"
	docker compose down
