import os
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


def test_cleanup_old_app_temp_dirs_only_removes_stale_marked_session_dirs(tmp_path: Path) -> None:
    temp_root = tmp_path / "automataii"
    temp_root.mkdir()
    stale_marked_session = temp_root / "stale-marked"
    stale_unmarked_session = temp_root / "stale-unmarked"
    fresh_session = temp_root / "fresh"
    loose_file = temp_root / "loose.txt"
    marker_file = ".automataii-image-session"
    stale_marked_session.mkdir()
    stale_unmarked_session.mkdir()
    fresh_session.mkdir()
    (stale_marked_session / marker_file).write_text("", encoding="utf-8")
    (fresh_session / marker_file).write_text("", encoding="utf-8")
    loose_file.write_text("not a session directory", encoding="utf-8")

    now = 2_000_000.0
    stale_time = now - 120.0
    fresh_time = now - 10.0
    os.utime(stale_marked_session, (stale_time, stale_time))
    os.utime(stale_unmarked_session, (stale_time, stale_time))
    os.utime(fresh_session, (fresh_time, fresh_time))

    removed = paths.cleanup_old_app_temp_dirs(
        max_age_seconds=60,
        now=now,
        base_temp_dir=temp_root,
        marker_file=marker_file,
    )

    assert removed == 1
    assert not stale_marked_session.exists()
    assert stale_unmarked_session.exists()
    assert fresh_session.exists()
    assert loose_file.exists()


def test_cleanup_old_app_temp_dirs_requires_marker_file(tmp_path: Path) -> None:
    temp_root = tmp_path / "automataii"
    stale_session = temp_root / "stale"
    stale_session.mkdir(parents=True)
    now = 2_000_000.0
    stale_time = now - 120.0
    os.utime(stale_session, (stale_time, stale_time))

    removed = paths.cleanup_old_app_temp_dirs(
        max_age_seconds=60,
        now=now,
        base_temp_dir=temp_root,
    )

    assert removed == 0
    assert stale_session.exists()
