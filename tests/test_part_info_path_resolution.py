from pathlib import Path

from automataii.domain.project.models import PartInfoModel
from automataii.presentation.qt.models import PartInfo


def test_from_pydantic_prefers_existing_relative_path(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    relative_asset = Path("assets/head.png")
    relative_asset.parent.mkdir(parents=True, exist_ok=True)
    relative_asset.write_bytes(b"png")

    project_dir = tmp_path / "project"
    project_dir.mkdir(parents=True, exist_ok=True)

    model = PartInfoModel(name="head", image_path=str(relative_asset))
    part = PartInfo.from_pydantic(model, project_dir=project_dir)

    assert part.image_path is not None
    assert Path(part.image_path) == (tmp_path / relative_asset).resolve()


def test_from_pydantic_falls_back_to_project_relative_path(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_asset = project_dir / "assets/head.png"
    project_asset.parent.mkdir(parents=True, exist_ok=True)
    project_asset.write_bytes(b"png")

    model = PartInfoModel(name="head", image_path="assets/head.png")
    part = PartInfo.from_pydantic(model, project_dir=project_dir)

    assert part.image_path is not None
    assert Path(part.image_path) == project_asset.resolve()
