# Automataii Development Commands

## Package Management (use `uv` NOT pip!)
```bash
# Install dependencies
uv sync

# Install with dev dependencies
uv sync --group dev

# Add new dependency
uv add package-name

# Update dependencies
uv lock --upgrade

# Show dependency tree
uv tree
```

## Running the Application
```bash
# Run the application
uv run automataii
# OR
make run

# Run from source
python -m automataii

# Run with debug mode
uv run automataii --debug

# Run experiment mode (hides Options tab)
uv run automataii --experiment
```

## Development Workflow
```bash
# Run tests
make test
uv run pytest

# Run tests with coverage
make test-coverage

# Run linting
make lint
uv run ruff check src/

# Format code
make format
uv run ruff format src/

# Type checking
make type-check
uv run mypy src/automataii

# Run all quality checks
make quality
```

## Building
```bash
# Build for current platform
make build

# Build macOS app
make build-macos

# Build Windows exe
make build-windows

# Build Linux executable
make build-linux

# Build experiment version
make build-experiment
```

## Git Commands (macOS/Darwin)
```bash
# Status
git status

# Add files
git add .

# Commit with quality checks
make commit

# Create branch
git checkout -b feature/branch-name

# Push branch
git push -u origin feature/branch-name
```

## Utility Commands
```bash
# Clean build artifacts
make clean

# Clean everything including cache
make clean-all

# Open Python shell with project context
make shell
uv run python

# Get project info
make info
```

## macOS Specific
- Use `ls` for listing files (same as Linux)
- Use `find` for searching files
- Use `grep` or better `rg` (ripgrep) for text search
- `open .` to open current directory in Finder
- `open file.txt` to open file with default application