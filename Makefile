# LeoMoon LightStudio — dev/build Makefile
#
# Common tasks:
#   make            # show this help
#   make venv       # create .venv and install ruff/mypy/pytest
#   make lint       # ruff check
#   make fix        # ruff check --fix
#   make test       # pytest (pure Python tests)
#   make check      # lint + test
#   make wheels     # placeholder; no Python wheels are bundled today
#   make build      # build the extension .zip into ./dist/
#   make install    # build then install into the Blender user profile
#   make headless-test  # run Blender-in-process tests (script lands in step 17)
#   make tag        # create an annotated git tag from the manifest version
#   make clean      # remove dist/, caches, built zips
#
# Override the Blender binary if it isn't on PATH:
#   make build BLENDER=/path/to/blender

BLENDER ?= /mnt/usrdrv/Portables-Lin/Graphic/blender-5.1.1-linux-x64/blender
PKG_DIR := lightstudio
DIST_DIR := dist
VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
RUFF := $(VENV)/bin/ruff
PYTEST := $(VENV)/bin/pytest
ARGS ?=

.DEFAULT_GOAL := help

.PHONY: help venv lint fix test check wheels build install headless-test tag clean

help:
	@awk 'BEGIN{FS=":.*##"; printf "Targets:\n"} /^[a-zA-Z_-]+:.*##/ {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

venv: ## Create .venv and install dev tools
	python -m venv $(VENV)
	$(PIP) install --quiet --upgrade pip
	$(PIP) install --quiet ruff mypy pytest
	@echo "venv ready: $(VENV)"

lint: ## Run ruff
	$(RUFF) check $(PKG_DIR) tests

fix: ## Run ruff with --fix
	$(RUFF) check --fix $(PKG_DIR) tests

test: ## Run pytest (pure Python)
	$(PYTEST) -q tests

check: lint test ## Lint + test

wheels: ## Placeholder — no Python wheels are bundled in this extension
	@echo "No external Python dependencies — nothing to vendor."
	@echo "If wheels are ever needed, drop them in $(PKG_DIR)/wheels/ and add them to blender_manifest.toml."

build: check ## Build the extension .zip into ./dist/ as leomoon-lightstudio-<ver>_blender-<min>.zip
	@mkdir -p $(DIST_DIR)
	@which $(BLENDER) >/dev/null 2>&1 || { echo "blender not found — set BLENDER=/path/to/blender"; exit 1; }
	cd $(PKG_DIR) && $(BLENDER) --factory-startup --command extension build --output-dir ../$(DIST_DIR)
	@PLUGIN_VERSION=$$(grep -E '^version' $(PKG_DIR)/blender_manifest.toml | head -1 | sed -E 's/.*"([^"]+)".*/\1/'); \
	BLENDER_VERSION=$$(grep -E '^blender_version_min' $(PKG_DIR)/blender_manifest.toml | head -1 | sed -E 's/.*"([^"]+)".*/\1/'); \
	SRC="$(DIST_DIR)/leomoon_lightstudio-$$PLUGIN_VERSION.zip"; \
	DST="$(DIST_DIR)/leomoon-lightstudio-$${PLUGIN_VERSION}_blender-$${BLENDER_VERSION}.zip"; \
	mv -f "$$SRC" "$$DST"; \
	ls -lh "$$DST"

install: build ## Build then install into the running Blender user profile
	@ZIP=$$(ls -1t $(DIST_DIR)/leomoon-lightstudio-*_blender-*.zip | head -1); \
	echo "Installing $$ZIP …"; \
	$(BLENDER) --command extension install-file --repo user_default --enable "$$ZIP"

headless-test: ## Run Blender-in-process tests (one fresh subprocess per test)
	@which $(BLENDER) >/dev/null 2>&1 || { echo "blender not found — set BLENDER=/path/to/blender"; exit 1; }
	@if [ ! -f tests/run_headless.py ]; then \
		echo "tests/run_headless.py not present yet — this target activates in step 17."; \
	else \
		BLENDER="$(BLENDER)" $(PY) tests/run_headless.py $(ARGS); \
	fi

tag: ## Create an annotated git tag from the manifest version (does NOT push)
	@VERSION=$$(grep -E '^version' $(PKG_DIR)/blender_manifest.toml | head -1 | sed -E 's/.*"([^"]+)".*/\1/'); \
	echo "Tagging v$$VERSION …"; \
	git tag -a "v$$VERSION" -m "LeoMoon LightStudio v$$VERSION"; \
	echo "Done. Push with: git push origin v$$VERSION"

clean: ## Remove build artifacts and caches
	rm -rf $(DIST_DIR) .ruff_cache .mypy_cache .pytest_cache
	rm -f $(PKG_DIR)/*.zip
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
