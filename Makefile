# Automataii Makefile
# Uses uv for dependency management and development workflow

.PHONY: help sync dev update deps run test test-verbose test-coverage \
        lint lint-fix format format-check type-check quality \
        build build-experiment build-experiment-arm64 build-experiment-x86_64 \
        build-macos build-macos-native build-macos-arm64 build-macos-x86_64 \
        build-windows build-linux release-macos \
        store-notary-profile verify-macos-release \
        clean clean-all info

# Default target
help:
	@echo "Automataii Development Makefile"
	@echo ""
	@echo "Dependencies:"
	@echo "  sync          - Install/sync dependencies from lock file"
	@echo "  dev           - Install with development dependencies"
	@echo "  update        - Update and re-lock dependencies"
	@echo "  deps          - Show dependency tree"
	@echo ""
	@echo "Run:"
	@echo "  run           - Run the application"
	@echo ""
	@echo "Quality:"
	@echo "  test          - Run tests with pytest"
	@echo "  test-verbose  - Run tests with verbose output"
	@echo "  test-coverage - Run tests with coverage report"
	@echo "  lint          - Run ruff linter"
	@echo "  lint-fix      - Run ruff linter with autofix"
	@echo "  format        - Format code with ruff"
	@echo "  format-check  - Check formatting without changes"
	@echo "  type-check    - Run mypy type checking"
	@echo "  quality       - lint + format-check + type-check"
	@echo ""
	@echo "Build:"
	@echo "  build                  - Build for current platform (macOS: signed + notarized)"
	@echo "  build-macos            - Signed + notarized universal macOS release"
	@echo "  build-macos-native     - Signed + notarized macOS release (host arch)"
	@echo "  build-macos-arm64      - Signed + notarized macOS release (arm64)"
	@echo "  build-macos-x86_64     - Signed + notarized macOS release (x86_64)"
	@echo "  build-experiment       - Build experiment version"
	@echo "  build-windows          - Build signed Windows distribution zip"
	@echo "  build-linux            - Build Linux executable"
	@echo "  release-macos          - Alias for build-macos"
	@echo ""
	@echo "macOS Distribution:"
	@echo "  store-notary-profile   - Store notarytool credentials in keychain"
	@echo "  verify-macos-release   - Verify a signed macOS release artifact"
	@echo ""
	@echo "Misc:"
	@echo "  clean         - Clean build artifacts"
	@echo "  clean-all     - Clean everything including caches"
	@echo "  info          - Show environment info"

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
PYTHON := uv run python
UV := uv
PROJECT_NAME := automataii
MACOS_SIGN_ARG := $(if $(SIGN_ID),--sign "$(SIGN_ID)")

# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------
sync:
	$(UV) sync

dev:
	$(UV) sync --group dev

update:
	$(UV) lock --upgrade

deps:
	$(UV) tree

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
run:
	$(UV) run $(PROJECT_NAME)

# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------
test:
	$(UV) run pytest

test-verbose:
	$(UV) run pytest -v

test-coverage:
	$(UV) run pytest --cov=$(PROJECT_NAME) --cov-report=html

lint:
	$(UV) run ruff check src/

lint-fix:
	$(UV) run ruff check src/ --fix

format:
	$(UV) run ruff format src/

format-check:
	$(UV) run ruff format src/ --check

type-check:
	$(PYTHON) scripts/check_mypy_baseline.py

quality: lint format-check type-check

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
build:
	@echo "Building distribution artifact for current platform..."
	@if [ "$$(uname -s)" = "Darwin" ]; then \
		$(PYTHON) scripts/release_macos.py $(MACOS_SIGN_ARG) $(OPTS); \
	else \
		$(PYTHON) scripts/build.py $(OPTS); \
	fi

build-experiment:
	@echo "Building experiment version for current platform..."
	$(PYTHON) scripts/build_experiment.py $(MACOS_SIGN_ARG) $(OPTS)

build-experiment-arm64:
	@echo "Building experiment version for macOS arm64..."
	$(PYTHON) scripts/build_experiment.py --arch arm64 $(MACOS_SIGN_ARG) $(OPTS)

build-experiment-x86_64:
	@echo "Building experiment version for macOS x86_64..."
	$(PYTHON) scripts/build_experiment.py --arch x86_64 $(MACOS_SIGN_ARG) $(OPTS)

build-macos:
	@echo "Building signed + notarized universal macOS release..."
	$(PYTHON) scripts/release_macos.py --arch universal2 $(MACOS_SIGN_ARG) $(OPTS)

build-macos-native:
	@echo "Building signed + notarized macOS release for current host architecture..."
	$(PYTHON) scripts/release_macos.py --arch auto $(MACOS_SIGN_ARG) $(OPTS)

build-macos-arm64:
	@echo "Building signed + notarized macOS release for arm64..."
	$(PYTHON) scripts/release_macos.py --arch arm64 $(MACOS_SIGN_ARG) $(OPTS)

build-macos-x86_64:
	@echo "Building signed + notarized macOS release for x86_64..."
	$(PYTHON) scripts/release_macos.py --arch x86_64 $(MACOS_SIGN_ARG) $(OPTS)

# Alias kept for documentation compatibility (docs/macos-distribution.md)
release-macos: build-macos

build-windows:
	@echo "Building signed Windows distribution zip..."
	@test -n "$(WINDOWS_CERTIFICATE)" || (echo "WINDOWS_CERTIFICATE is required, e.g. make build-windows WINDOWS_CERTIFICATE=windows-cert.pfx" && exit 1)
	@test -n "$${WINDOWS_CERT_PASSWORD}" || (echo "WINDOWS_CERT_PASSWORD is required in the environment" && exit 1)
	$(UV) sync --group build
	$(PYTHON) scripts/build_windows.py --sign --certificate "$(WINDOWS_CERTIFICATE)" --cert-password-env WINDOWS_CERT_PASSWORD --verify-signature

build-linux:
	@echo "Building Linux executable..."
	$(PYTHON) scripts/build_linux.py

# ---------------------------------------------------------------------------
# macOS Distribution Utilities
# ---------------------------------------------------------------------------
store-notary-profile:
	@test -n "$(PROFILE)" || (echo "PROFILE is required, e.g. make store-notary-profile PROFILE=MotionSmith APPLE_ID=... APPLE_TEAM_ID=..." && exit 1)
	@test -n "$(APPLE_ID)" || (echo "APPLE_ID is required" && exit 1)
	@test -n "$(APPLE_TEAM_ID)" || (echo "APPLE_TEAM_ID is required" && exit 1)
	@if [ -n "$$APPLE_APP_SPECIFIC_PASSWORD" ]; then \
		xcrun notarytool store-credentials "$$PROFILE" --apple-id "$$APPLE_ID" --team-id "$$APPLE_TEAM_ID" --password "$$APPLE_APP_SPECIFIC_PASSWORD"; \
	else \
		xcrun notarytool store-credentials "$$PROFILE" --apple-id "$$APPLE_ID" --team-id "$$APPLE_TEAM_ID"; \
	fi
	@echo "Stored notarytool profile. Use APPLE_NOTARY_PROFILE=$(PROFILE) with build-macos."

verify-macos-release:
	@test -n "$(ARTIFACT)" || (echo "ARTIFACT is required, e.g. make verify-macos-release ARTIFACT=dist/MotionSmith.app" && exit 1)
	$(PYTHON) scripts/verify_macos_release.py "$(ARTIFACT)" $(OPTS)

# ---------------------------------------------------------------------------
# Cleaning
# ---------------------------------------------------------------------------
clean:
	@echo "Cleaning build artifacts..."
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf src/$(PROJECT_NAME).egg-info/
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete

clean-all: clean
	@echo "Cleaning logs and caches..."
	rm -rf logs/
	rm -rf src/logs/
	find . -name "*.log" -delete
	rm -rf .pytest_cache/
	rm -rf .ruff_cache/
	rm -rf .mypy_cache/
	$(UV) cache clean

# ---------------------------------------------------------------------------
# Info
# ---------------------------------------------------------------------------
info:
	@echo "Project: $(PROJECT_NAME)"
	@echo "UV version: $$($(UV) --version)"
	@echo "Python version: $$($(PYTHON) --version)"
	@echo "Project root: $$(pwd)"
