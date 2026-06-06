# Automataii Makefile
# Uses uv for dependency management and development workflow

.PHONY: help install dev clean test lint format type-check build run sync update deps build-macos build-windows build-linux build-experiment release-macos

# Default target
help:
	@echo "Automataii Development Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  install       - Install dependencies with uv"
	@echo "  dev           - Install development dependencies"
	@echo "  sync          - Sync dependencies from lock file"
	@echo "  update        - Update dependencies"
	@echo "  deps          - Show dependency tree"
	@echo ""
	@echo "  run           - Run the application"
	@echo "  test          - Run tests with pytest"
	@echo "  lint          - Run ruff linter"
	@echo "  format        - Format code with ruff"
	@echo "  type-check    - Run mypy type checking"
	@echo ""
	@echo "  build         - Build distribution artifact for current platform (macOS: universal signed + notarized release)"
	@echo "  build-experiment - Build experiment version (macOS requires signed + notarized release)"
	@echo "  build-macos   - Build signed + notarized universal macOS release"
	@echo "  build-macos-native - Build signed + notarized macOS release for current host architecture"
	@echo "  build-macos-signed - Alias for signed + notarized universal macOS release"
	@echo "  build-macos-release - Build signed + notarized universal macOS release"
	@echo "  release-macos - Alias for build-macos-release"
	@echo "  store-notary-profile - Store notarytool credentials in the macOS keychain"
	@echo "  build-windows - Build Windows executable"
	@echo "  build-linux   - Build Linux executable"
	@echo ""
	@echo "  clean         - Clean build artifacts"
	@echo "  clean-all     - Clean everything including cache"

# Environment setup
PYTHON := uv run python
UV := uv
PROJECT_NAME := automataii
MACOS_SIGN_ARG := $(if $(SIGN_ID),--sign "$(SIGN_ID)")

# Install base dependencies
install:
	$(UV) sync

# Install with development dependencies
dev:
	$(UV) sync --group dev

# Sync dependencies from lock file
sync:
	$(UV) sync

# Update all dependencies
update:
	$(UV) lock --upgrade

# Show dependency tree
deps:
	$(UV) tree

# Run the application
run:
	$(UV) run $(PROJECT_NAME)

# Run with specific module
run-animate:
	$(UV) run python -m $(PROJECT_NAME).animate.image_to_annotations

# Testing
test:
	$(UV) run pytest

test-verbose:
	$(UV) run pytest -v

test-coverage:
	$(UV) run pytest --cov=$(PROJECT_NAME) --cov-report=html

# Code quality
lint:
	$(UV) run ruff check src/

lint-fix:
	$(UV) run ruff check src/ --fix

format:
	$(UV) run ruff format src/

format-check:
	$(UV) run ruff format src/ --check

type-check:
	$(UV) run mypy src/$(PROJECT_NAME)

# Combined quality check
quality: lint format-check type-check

# Building
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

.PHONY: build-experiment-arm64 build-experiment-x86_64

build-experiment-arm64:
	@echo "Building experiment version for macOS arm64..."
	$(PYTHON) scripts/build_experiment.py --arch arm64 $(MACOS_SIGN_ARG) $(OPTS)

build-experiment-x86_64:
	@echo "Building experiment version for macOS x86_64..."
	$(PYTHON) scripts/build_experiment.py --arch x86_64 $(MACOS_SIGN_ARG) $(OPTS)

build-macos:
	@echo "Building signed + notarized universal macOS release..."
	$(PYTHON) scripts/release_macos.py --arch universal2 $(MACOS_SIGN_ARG) $(OPTS)

.PHONY: build-macos-native build-macos-universal build-macos-signed build-macos-signed-native build-macos-release build-macos-release-native release-macos verify-macos-release store-notary-profile build-macos-arm64 build-macos-x86_64

build-macos-native:
	@echo "Building signed + notarized macOS release for current host architecture..."
	$(PYTHON) scripts/release_macos.py --arch auto $(MACOS_SIGN_ARG) $(OPTS)

build-macos-universal:
	@echo "Building signed + notarized universal macOS release..."
	$(PYTHON) scripts/release_macos.py --arch universal2 $(MACOS_SIGN_ARG) $(OPTS)

build-macos-signed:
	@echo "Building signed + notarized universal macOS release..."
	$(PYTHON) scripts/release_macos.py --arch universal2 $(MACOS_SIGN_ARG) $(OPTS)

build-macos-signed-native:
	@echo "Building signed + notarized macOS release for current host architecture..."
	$(PYTHON) scripts/release_macos.py --arch auto $(MACOS_SIGN_ARG) $(OPTS)

build-macos-release:
	@echo "Building signed and notarized universal macOS release..."
	$(PYTHON) scripts/release_macos.py --arch universal2 $(MACOS_SIGN_ARG) $(OPTS)

release-macos: build-macos-release

build-macos-release-native:
	@echo "Building signed and notarized native macOS release..."
	$(PYTHON) scripts/release_macos.py --arch auto $(MACOS_SIGN_ARG) $(OPTS)

store-notary-profile:
	@test -n "$(PROFILE)" || (echo "PROFILE is required, e.g. make store-notary-profile PROFILE=MotionSmith APPLE_ID=... APPLE_TEAM_ID=..." && exit 1)
	@test -n "$(APPLE_ID)" || (echo "APPLE_ID is required" && exit 1)
	@test -n "$(APPLE_TEAM_ID)" || (echo "APPLE_TEAM_ID is required" && exit 1)
	@if [ -n "$$APPLE_APP_SPECIFIC_PASSWORD" ]; then \
		xcrun notarytool store-credentials "$$PROFILE" --apple-id "$$APPLE_ID" --team-id "$$APPLE_TEAM_ID" --password "$$APPLE_APP_SPECIFIC_PASSWORD"; \
	else \
		xcrun notarytool store-credentials "$$PROFILE" --apple-id "$$APPLE_ID" --team-id "$$APPLE_TEAM_ID"; \
	fi
	@echo "Stored notarytool profile. Use APPLE_NOTARY_PROFILE=$(PROFILE) with build-macos-release."

verify-macos-release:
	@test -n "$(ARTIFACT)" || (echo "ARTIFACT is required, e.g. make verify-macos-release ARTIFACT=dist/MotionSmith.app" && exit 1)
	$(PYTHON) scripts/verify_macos_release.py "$(ARTIFACT)" $(OPTS)

build-macos-arm64:
	@echo "Building signed + notarized macOS release for arm64..."
	$(PYTHON) scripts/release_macos.py --arch arm64 $(MACOS_SIGN_ARG) $(OPTS)

build-macos-x86_64:
	@echo "Building signed + notarized macOS release for x86_64..."
	$(PYTHON) scripts/release_macos.py --arch x86_64 $(MACOS_SIGN_ARG) $(OPTS)

build-windows:
	@echo "Building Windows executable..."
	$(UV) sync --group build-windows
	$(PYTHON) scripts/build_windows.py

build-linux:
	@echo "Building Linux executable..."
	$(PYTHON) scripts/build_linux.py

# PyInstaller direct (alternative to scripts)
pyinstaller:
	$(UV) run pyinstaller automataii.spec

# Dataset generation
generate-dataset:
	$(UV) run python -m $(PROJECT_NAME).generate_comprehensive_dataset

generate-animations:
	$(UV) run python -m $(PROJECT_NAME).generate_animations

# Development utilities
shell:
	$(UV) run python

jupyter:
	$(UV) run jupyter lab

# Cleaning
clean:
	@echo "Cleaning build artifacts..."
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf src/$(PROJECT_NAME).egg-info/
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete

clean-logs:
	@echo "Cleaning log files..."
	rm -rf logs/
	rm -rf src/logs/
	find . -name "*.log" -delete

clean-cache:
	@echo "Cleaning cache..."
	rm -rf .pytest_cache/
	rm -rf .ruff_cache/
	rm -rf .mypy_cache/

clean-all: clean clean-logs clean-cache
	@echo "Cleaning UV cache..."
	$(UV) cache clean

# Git helpers
git-status:
	git status

git-add-all:
	git add .

commit: lint format
	@echo "Running quality checks before commit..."
	$(MAKE) quality
	@echo "Quality checks passed. Ready to commit."

# Environment info
info:
	@echo "Project: $(PROJECT_NAME)"
	@echo "UV version: $$($(UV) --version)"
	@echo "Python version: $$($(PYTHON) --version)"
	@echo "Project root: $$(pwd)"

# Check if uv is installed
check-uv:
	@which uv > /dev/null || (echo "uv is not installed. Please install it from https://docs.astral.sh/uv/" && exit 1)

# Setup development environment
setup: check-uv
	@echo "Setting up development environment..."
	$(MAKE) dev
	@echo "Development environment ready!"

# CI/CD targets
ci-test: dev
	$(MAKE) test

ci-lint: dev
	$(MAKE) lint
	$(MAKE) format-check

ci-type-check: dev
	$(MAKE) type-check

ci-all: ci-lint ci-type-check ci-test
