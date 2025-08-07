# Code Style and Conventions

## Python Version
- Requires Python 3.13+
- Uses modern Python features and type hints

## Code Quality Tools
- **Linter**: ruff (replaces flake8, isort, and other tools)
- **Formatter**: ruff format (replaces black)  
- **Type Checker**: mypy with strict settings
- **Line Length**: 100 characters
- **Target Version**: py313

## Type Hints
- Full type annotation required (`disallow_untyped_defs = true`)
- Return type hints mandatory
- Generic types used appropriately

## Import Style
- Managed by ruff
- Standard library first, third-party second, local imports last
- Absolute imports preferred

## Project Structure
- Source code in `src/automataii/`
- Tests in `tests/`
- Configuration in `config/`
- Scripts in `scripts/`
- Documentation in `docs/`

## Naming Conventions
- Snake_case for variables, functions, modules
- PascalCase for classes
- UPPER_CASE for constants
- Private members prefixed with underscore

## Documentation
- Docstrings for all public APIs
- Type hints serve as inline documentation
- README.md provides comprehensive overview