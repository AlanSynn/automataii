from __future__ import annotations

import tomllib
from pathlib import Path

from automataii.utils.config import AppConfig


def test_app_config_version_matches_package_metadata() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    project = tomllib.loads(pyproject.read_text())["project"]

    assert AppConfig.APP_VERSION == project["version"]
