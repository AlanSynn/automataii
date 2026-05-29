from pathlib import Path

from automataii.utils import paths


def _macos_bundle(tmp_path: Path) -> tuple[Path, Path]:
    contents = tmp_path / "AutomataII.app" / "Contents"
    macos = contents / "MacOS"
    resources = contents / "Resources"
    (resources / "resources" / "data").mkdir(parents=True)
    (resources / "resources" / "data" / "mechanism_catalog.json").write_text("{}", encoding="utf-8")
    macos.mkdir(parents=True)
    executable = macos / "AutomataII"
    executable.write_text("", encoding="utf-8")
    return executable, resources


def test_frozen_macos_bundle_uses_contents_resources(monkeypatch, tmp_path) -> None:
    executable, resources = _macos_bundle(tmp_path)

    monkeypatch.setattr(paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths.sys, "_MEIPASS", str(executable.parent), raising=False)
    monkeypatch.setattr(paths.sys, "executable", str(executable))

    assert paths.get_project_root() == resources
    assert paths.get_base_path() == resources
    assert (
        paths.resolve_path("resources/data/mechanism_catalog.json")
        == resources / "resources" / "data" / "mechanism_catalog.json"
    )


def test_frozen_bundle_prefers_resources_over_enclosing_source_tree(monkeypatch, tmp_path) -> None:
    project_root = tmp_path / "checkout"
    (project_root / "src" / "automataii").mkdir(parents=True)
    executable, resources = _macos_bundle(project_root / "dist")

    monkeypatch.setattr(paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths.sys, "_MEIPASS", str(executable.parent), raising=False)
    monkeypatch.setattr(paths.sys, "executable", str(executable))

    assert paths.get_project_root() == resources
    assert paths.get_project_root() != project_root


def test_app_data_dir_is_user_writable(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(paths.platform, "system", lambda: "Linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))

    app_data_dir = paths.get_app_data_dir()

    assert app_data_dir == tmp_path / "AutomataII"
    assert app_data_dir.exists()
