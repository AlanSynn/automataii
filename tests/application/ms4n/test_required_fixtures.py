from pathlib import Path

REQUIRED_FIXTURES = (
    "episode_repaired.sample.json",
    "episode_unresolved.sample.json",
    "episodes.sample.jsonl",
    "coding_sheet.sample.csv",
    "autopsy_sheet.sample.md",
    "kit_manifest.sample.json",
    "project_with_ms4n_layer_payload.automataii.json",
)


def test_required_ms4n_fixture_set_exists():
    fixture_dir = Path(__file__).parents[2] / "fixtures" / "ms4n"
    missing = [name for name in REQUIRED_FIXTURES if not (fixture_dir / name).exists()]
    assert missing == []
