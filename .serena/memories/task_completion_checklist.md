# Task Completion Checklist

When completing any coding task in Automataii, follow these steps:

## 1. Code Quality Checks
```bash
# Run linting
make lint
# OR
uv run ruff check src/

# Fix linting issues automatically
uv run ruff check src/ --fix

# Format code
make format
# OR
uv run ruff format src/
```

## 2. Type Checking
```bash
# Run mypy type checking
make type-check
# OR
uv run mypy src/automataii
```

## 3. Run Tests
```bash
# Run all tests
make test
# OR
uv run pytest

# Run specific test file
uv run pytest tests/test_specific.py

# Run with coverage
make test-coverage
```

## 4. Combined Quality Check
```bash
# Run all quality checks at once
make quality
```

## 5. Before Committing
```bash
# This runs quality checks automatically
make commit
```

## Important Notes
- NEVER commit without running lint and type checks
- Always run tests after making changes
- If lint/type errors are found, fix them before proceeding
- The codebase maintains strict type safety - all functions must have type annotations
- Code must pass all quality checks before being merged