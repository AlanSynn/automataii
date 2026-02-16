from pathlib import Path

from automataii.application.mechanism_foundry.content_loader import ContentLoader


def test_four_bar_content_includes_motions_and_gallery_summary() -> None:
    loader = ContentLoader()
    content = loader.load_content("four_bar")

    assert "Circular" in content.motions
    assert "Oscillatory" in content.motions
    assert content.gallery_summary is not None
    assert "swinging" in content.gallery_summary.lower()


def test_motion_derivation_from_tags_when_field_missing(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"
    content_dir.mkdir(parents=True, exist_ok=True)

    sample_path = content_dir / "derived_case.json"
    sample_path.write_text(
        """
{
  "title": "Derived",
  "goal": "Derived motion case",
  "parts": [],
  "advantages": [],
  "disadvantages": [],
  "materials": [],
  "cautions": [],
  "parameter_options": {},
  "diagram_path": null,
  "tags": ["rotary", "oscillating", "linear"]
}
""".strip(),
        encoding="utf-8",
    )

    loader = ContentLoader(content_dir=content_dir)
    content = loader.load_content("derived_case")

    assert content.motions == ("Circular", "Oscillatory", "Linear")
