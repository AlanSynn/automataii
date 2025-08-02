# Automataii Code Style and Conventions

## General Principles
- **Type Safety**: Full type annotations required (mypy enforced)
- **Line Length**: 100 characters maximum (enforced by ruff)
- **Python Version**: Target Python 3.13+
- **Import Style**: Explicit imports, no wildcards

## Code Organization
- Source code in `src/automataii/`
- Tests in `tests/`
- Build scripts in `scripts/`
- Configuration in `pyproject.toml`

## Naming Conventions
- **Classes**: PascalCase (e.g., `AutomataDesigner`, `EventHandler`)
- **Functions/Methods**: snake_case (e.g., `setup_logging`, `create_action`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `LIGHT_STYLE`)
- **Private**: Leading underscore (e.g., `_generate_fallback_blueprint_svg`)

## Documentation
- Comprehensive docstrings for all public APIs
- Use triple quotes for docstrings
- Include type information in function signatures, not docstrings

## Design Patterns
- **Dependency Injection**: Using container pattern for service management
- **Event-Driven Architecture**: Events are immutable dataclasses
- **Redux-like State Management**: Actions and reducers pattern
- **Factory Pattern**: For creating visual components
- **Strategy Pattern**: For parametric editing behaviors

## Data Classes
- Use `@dataclass` with `frozen=True` for immutable data structures
- Use Pydantic models for validation and serialization

## File Structure
- Keep files under 500 lines
- Hierarchical directory organization
- One class/concept per file preferred

## Testing
- Test files named `test_*.py`
- Use pytest fixtures
- Aim for high coverage
- Test both success and error cases