"""
pytest configuration and fixtures
"""
import sys
import os
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

import pytest


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