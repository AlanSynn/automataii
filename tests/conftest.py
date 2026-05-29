"""
pytest configuration and fixtures
"""
import os
import sys
from pathlib import Path

import pytest

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))
tests_path = Path(__file__).parent
sys.path.insert(0, str(tests_path))

# Default Qt tests to headless mode to prevent platform plugin crashes
# in environments without a window server (e.g., CI/sandbox runs).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def sample_test_data():
    """Provide sample test data"""
    return {
        "test_string": "Test Value",
        "test_number": 42,
        "test_list": [1, 2, 3]
    }


@pytest.fixture
def mock_file_path(tmp_path):
    """Provide a temporary file path for testing"""
    return tmp_path / "test_file.txt"
