# Supplementary Material: Source Code

## Source Code Availability

The complete source code for this project is available in anonymized form for review.

**Zenodo DOI**: [10.5281/zenodo.17830038](https://doi.org/10.5281/zenodo.17830038)

## How to Run

```bash
# Install dependencies
uv sync

# Run application
uv run automataii

# Run tests
uv run pytest
```

## Repository Structure

```
src/automataii/
├── domain/           # Core business logic (mechanisms, kinematics, animation)
├── application/      # Use case orchestration and services
├── presentation/     # Qt-based user interface
└── infrastructure/   # State management, events, file I/O
```

## Requirements

- Python 3.10+
- uv (package manager)

---

All personally identifiable information has been removed from the codebase to ensure anonymous review.
