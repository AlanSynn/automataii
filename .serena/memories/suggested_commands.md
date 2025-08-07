# Suggested Commands for Development

## Running the Application
- `uv run automataii` - Launch the GUI application
- `make run` - Alternative way to run the application
- `python app.py` - Direct execution

## Development Workflow
- `make dev` - Install development dependencies
- `make sync` - Sync dependencies from lock file
- `make update` - Update all dependencies

## Code Quality
- `make lint` - Run ruff linter
- `make format` - Format code with ruff
- `make type-check` - Run mypy type checking
- `make quality` - Run all quality checks (lint + format + type-check)

## Testing
- `make test` - Run pytest tests
- `make test-verbose` - Run tests with verbose output
- `make test-coverage` - Run tests with coverage report

## Building
- `make build` - Build for current platform
- `make build-macos` - Build macOS app bundle
- `make build-experiment` - Build experiment version

## Cleaning
- `make clean` - Clean build artifacts
- `make clean-all` - Clean everything including cache

## Essential Commands When Task Complete
1. `make quality` - Ensures code passes all quality checks
2. `make test` - Runs all tests
3. Commit only after both pass