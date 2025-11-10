"""
Golden Master Tests for Automataii.

These tests capture the current behavior of critical components as snapshots.
They ensure that refactoring doesn't change observable behavior.

Usage:
    # Run golden master tests
    pytest tests/golden_master/ -v

    # Update snapshots (after intentional changes)
    pytest tests/golden_master/ --update-snapshots
"""
