# Automataii

Interactive mechanism design and animation platform.

## Quick Start

```bash
# Install
git clone https://github.com/automataii/automataii.git
cd automataii
uv sync

# Run
uv run automataii
```

## Commands

```bash
uv run automataii              # Launch GUI
uv run automataii --debug      # Debug mode
uv run automataii --experiment # Experiment mode
uv run pytest                  # Run tests
uv run mypy src/automataii     # Type check
uv run ruff check              # Lint
```

## Structure

```
src/automataii/
├── domain/          # Core logic (mechanisms, kinematics, animation)
├── application/     # Use cases, services
├── presentation/    # Qt UI (tabs, views, dialogs)
└── infrastructure/  # IO, state, events
```

## License

MIT
