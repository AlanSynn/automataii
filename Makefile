# Automataii Makefile
# Uses uv for dependency management and development workflow

.PHONY: help install dev clean test lint format type-check build run sync update deps build-macos build-windows build-linux build-experiment

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
	@echo "  build         - Build for current platform"
	@echo "  build-experiment - Build experiment version (hides Options tab)"
	@echo "  build-macos   - Build macOS app bundle"
	@echo "  build-windows - Build Windows executable"
	@echo "  build-linux   - Build Linux executable"
	@echo ""
	@echo "  clean         - Clean build artifacts"
	@echo "  clean-all     - Clean everything including cache"

# Environment setup
PYTHON := uv run python
UV := uv
PROJECT_NAME := automataii

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
	@echo "Building for current platform..."
	$(PYTHON) scripts/build.py

build-experiment:
	@echo "Building experiment version for current platform..."
	$(PYTHON) scripts/build_experiment.py

build-macos:
	@echo "Building macOS app bundle..."
	$(UV) sync --group build-macos
	$(PYTHON) scripts/build_macos.py

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