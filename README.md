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

## Frontend-only web app

A static browser migration lives in `web/` and runs without a backend. Install once to fetch ONNX Runtime Web for optional browser-side model inference.

```bash
cd web
bun install --frozen-lockfile   # fastest path, installs ONNX Runtime Web
bun run check:bun               # lint + tests + smoke + browser smoke + build
bun run dev:bun                 # serve at http://localhost:5173

# npm fallback
npm ci
npm run check
```

See `web/PARITY_AUDIT.md` for the functional parity checklist, `arch/ui-ux-flow-audit.md` for UI/UX flow checks plus browser workaround proposals, and `web/DEPLOYMENT.md` for static hosting.

## License

MIT
