"""
Golden Master Test Configuration and Fixtures.

Provides snapshot comparison utilities for golden master testing.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

SNAPSHOTS_DIR = Path(__file__).parent / "snapshots"


def ensure_snapshots_dir() -> None:
    """Ensure snapshots directory exists."""
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def snapshot_path(name: str) -> Path:
    """Get path for a named snapshot."""
    ensure_snapshots_dir()
    return SNAPSHOTS_DIR / f"{name}.json"


def normalize_floats(obj: Any, precision: int = 6) -> Any:
    """Normalize floats to fixed precision for stable comparison."""
    if isinstance(obj, float):
        return round(obj, precision)
    elif isinstance(obj, dict):
        return {k: normalize_floats(v, precision) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [normalize_floats(v, precision) for v in obj]
    elif isinstance(obj, tuple):
        return tuple(normalize_floats(v, precision) for v in obj)
    return obj


def compute_hash(data: Any) -> str:
    """Compute stable hash of data."""
    normalized = normalize_floats(data)
    json_str = json.dumps(normalized, sort_keys=True, default=str)
    return hashlib.sha256(json_str.encode()).hexdigest()[:16]


class GoldenMaster:
    """Golden master snapshot manager."""

    def __init__(self, name: str, update_mode: bool = False):
        self.name = name
        self.update_mode = update_mode
        self.path = snapshot_path(name)

    def save(self, data: Any) -> None:
        """Save snapshot to disk."""
        normalized = normalize_floats(data)
        with open(self.path, "w") as f:
            json.dump(
                {
                    "name": self.name,
                    "hash": compute_hash(data),
                    "data": normalized,
                },
                f,
                indent=2,
                default=str,
            )

    def load(self) -> dict[str, Any] | None:
        """Load snapshot from disk."""
        if not self.path.exists():
            return None
        with open(self.path) as f:
            return json.load(f)

    def assert_matches(self, actual: Any, message: str = "") -> None:
        """Assert that actual data matches the golden master."""
        normalized_actual = normalize_floats(actual)
        actual_hash = compute_hash(actual)

        snapshot = self.load()

        if snapshot is None:
            if self.update_mode:
                self.save(actual)
                pytest.skip(f"Created new snapshot: {self.name}")
            else:
                self.save(actual)
                pytest.fail(
                    f"No snapshot found for '{self.name}'. "
                    f"Created initial snapshot. Run again to verify."
                )

        expected_hash = snapshot.get("hash")
        expected_data = snapshot.get("data")

        if actual_hash != expected_hash:
            if self.update_mode:
                self.save(actual)
                pytest.skip(f"Updated snapshot: {self.name}")
            else:
                # Provide detailed diff
                diff_msg = f"\n{message}\n" if message else "\n"
                diff_msg += f"Snapshot: {self.name}\n"
                diff_msg += f"Expected hash: {expected_hash}\n"
                diff_msg += f"Actual hash: {actual_hash}\n"

                # Find differences
                if isinstance(expected_data, dict) and isinstance(normalized_actual, dict):
                    for key in set(expected_data.keys()) | set(normalized_actual.keys()):
                        exp_val = expected_data.get(key)
                        act_val = normalized_actual.get(key)
                        if exp_val != act_val:
                            diff_msg += f"  Key '{key}': expected {exp_val}, got {act_val}\n"

                pytest.fail(f"Golden master mismatch:{diff_msg}")


@pytest.fixture
def golden_master(request):
    """Fixture to create golden master for a test."""
    update_mode = request.config.getoption("--update-snapshots", default=False)

    def _create(name: str) -> GoldenMaster:
        # Use test name as prefix if not provided
        full_name = f"{request.node.name}_{name}" if name else request.node.name
        return GoldenMaster(full_name, update_mode=update_mode)

    return _create


def pytest_addoption(parser):
    """Add --update-snapshots option."""
    parser.addoption(
        "--update-snapshots",
        action="store_true",
        default=False,
        help="Update golden master snapshots",
    )
