#!/usr/bin/env bash
#
# Phase 2: Extract Domain Logic - Incremental Migration Script
#
# This script safely migrates mechanisms/ to domain/mechanisms/ using:
# 1. Git mv to preserve history
# 2. Compatibility re-exports in old locations
# 3. Validation after each step
#

set -e  # Exit on error

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=================================================="
echo "Phase 2: Extract Domain Logic (mechanisms/)"
echo "=================================================="

# Function to move a directory and create compatibility layer
move_with_compat() {
    local src="$1"
    local dst="$2"
    local compat_module="$3"

    echo ""
    echo "Moving: $src -> $dst"

    # Check if source exists
    if [ ! -d "$src" ]; then
        echo "  ⚠️  Source does not exist, skipping: $src"
        return
    fi

    # Check if destination already has content (not just __init__.py)
    if [ -d "$dst" ] && [ "$(find "$dst" -name '*.py' ! -name '__init__.py' | wc -l)" -gt 0 ]; then
        echo "  ⚠️  Destination already has content, skipping: $dst"
        return
    fi

    # Move files using git mv
    mkdir -p "$dst"
    for file in "$src"/*.py; do
        if [ -f "$file" ] && [ "$(basename "$file")" != "__init__.py" ]; then
            git mv "$file" "$dst/" 2>/dev/null || mv "$file" "$dst/"
            echo "  ✓ Moved: $(basename "$file")"
        fi
    done

    # Create compatibility __init__.py in old location
    cat > "$src/__init__.py" << EOF
"""
Compatibility layer: This module has moved to $compat_module

This file provides backwards compatibility by re-exporting from the new location.
This will be removed in a future version.
"""

# Re-export everything from new location
from $compat_module import *  # noqa: F401, F403

import warnings
warnings.warn(
    "Importing from '$src' is deprecated. "
    "Use '$compat_module' instead.",
    DeprecationWarning,
    stacklevel=2
)
EOF
    echo "  ✓ Created compatibility layer in $src/__init__.py"
}

# Step 1: Move mechanisms/core
echo ""
echo "Step 1: Move mechanisms/core -> domain/mechanisms/core"
move_with_compat \
    "src/automataii/mechanisms/core" \
    "src/automataii/domain/mechanisms/core" \
    "automataii.domain.mechanisms.core"

# Step 2: Move mechanisms/catalog
echo ""
echo "Step 2: Move mechanisms/catalog -> domain/mechanisms/catalog"
move_with_compat \
    "src/automataii/mechanisms/catalog" \
    "src/automataii/domain/mechanisms/catalog" \
    "automataii.domain.mechanisms.catalog"

# Step 3: Validate
echo ""
echo "=================================================="
echo "Validation"
echo "=================================================="

echo "Testing import..."
python3 -c "import automataii.mechanisms.core; import automataii.domain.mechanisms.core" 2>&1
if [ $? -eq 0 ]; then
    echo "✓ Imports work"
else
    echo "✗ Import validation failed"
    exit 1
fi

echo ""
echo "Testing application launch..."
timeout 10 uv run automataii > /dev/null 2>&1 &
APP_PID=$!
sleep 5
if ps -p $APP_PID > /dev/null; then
    echo "✓ Application started successfully"
    kill $APP_PID 2>/dev/null || true
else
    echo "✗ Application failed to start"
    exit 1
fi

echo ""
echo "=================================================="
echo "✓ Phase 2 (partial) completed successfully"
echo "=================================================="
echo ""
echo "Next steps:"
echo "1. Test the application manually: uv run automataii"
echo "2. If working, proceed with remaining migrations"
echo "3. Later, update imports to use new paths"
echo "4. Remove compatibility layers"
