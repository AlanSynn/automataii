#!/usr/bin/env bash

set -euo pipefail

# Run Vulture dead-code analysis using uv so dependencies stay ephemeral.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

TIMESTAMP="$(date +%Y-%m-%d)"
REPORT_PATH="docs/prd/vulture_${TIMESTAMP}.txt"

CACHE_DIR="$REPO_ROOT/.uv-cache"
mkdir -p "$CACHE_DIR"
export UV_CACHE_DIR="$CACHE_DIR"

echo "Running Vulture dead-code scan..."
uv run --with vulture vulture \
  src/automataii \
  --exclude src/automataii/core/blueprint_manager.py \
  > "$REPORT_PATH"

echo "Report written to $REPORT_PATH"
