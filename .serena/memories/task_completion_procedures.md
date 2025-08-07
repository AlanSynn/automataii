# Task Completion Procedures

## Before Marking Any Task Complete

### 1. Code Quality Checks (MANDATORY)
```bash
make quality
```
This runs:
- `ruff check src/` - Linting 
- `ruff format src/ --check` - Format checking
- `mypy src/automataii` - Type checking

### 2. Testing (MANDATORY)
```bash
make test
```
Runs pytest with coverage reporting

### 3. Build Verification (if applicable)
```bash
make build
```
Ensures the application builds without errors

## Development Best Practices

### File Operations
- Always prefer editing existing files over creating new ones
- Never create documentation files unless explicitly requested
- Use type hints for all functions and methods

### Architecture Adherence
- Follow the modular, event-driven architecture
- Use dependency injection where appropriate
- Maintain separation of concerns between GUI, logic, and data layers

### Performance Considerations
- Parametric updates should be throttled (50ms as per current implementation)
- Use Qt's signal/slot system for efficient event handling
- Memory management is critical due to graphics items

### Error Handling
- Comprehensive exception handling in parametric systems
- Graceful degradation when mechanisms can't be solved
- User-friendly error messages

## Commit Guidelines
- Only commit after quality checks pass
- Use semantic commit messages
- Include rationale in commit description