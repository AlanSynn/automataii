from __future__ import annotations

from pathlib import Path


def test_mechanism_blueprint_manual_covers_cam_4bar_and_gears() -> None:
    manual_path = Path("docs/mechanism-blueprint-manual.md")

    assert manual_path.exists()
    text = manual_path.read_text(encoding="utf-8").lower()

    for required in (
        "cam",
        "contact point",
        "follower base",
        "reverse direction",
        "4-bar",
        "coupler point",
        "gear",
        "mesh",
        "metric",
        "imperial",
    ):
        assert required in text
