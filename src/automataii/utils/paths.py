import logging
import os
import platform
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _frozen_base_candidates() -> list[Path]:
    """Return plausible PyInstaller resource roots in preference order."""
    candidates: list[Path] = []

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(str(meipass)).resolve())

    executable = getattr(sys, "executable", None)
    if executable:
        executable_parent = Path(str(executable)).resolve().parent
        candidates.append(executable_parent)

        # PyInstaller macOS app bundles place datas under
        # Contents/Resources, while sys._MEIPASS/sys.executable may point at
        # Contents/MacOS. Prefer the self-contained bundle Resources directory
        # over any source tree that happens to contain the bundle during local
        # development.
        for parent in (executable_parent, *executable_parent.parents):
            if parent.name == "Contents":
                candidates.append(parent / "Resources")
                break
            if parent.suffix == ".app":
                candidates.append(parent / "Contents" / "Resources")
                break

    # Deduplicate while preserving order.
    unique: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate not in seen:
            unique.append(candidate)
            seen.add(candidate)
    return unique


def _has_packaged_resources(path: Path) -> bool:
    return (path / "resources").exists() or (path / "models").exists()


def _frozen_base_path() -> Path | None:
    if not _is_frozen():
        return None

    candidates = _frozen_base_candidates()
    for candidate in candidates:
        if _has_packaged_resources(candidate):
            return candidate

    return candidates[0] if candidates else None


def get_project_root() -> Path:
    """Get the project root directory"""
    frozen_base = _frozen_base_path()
    if frozen_base is not None:
        return frozen_base

    # Start from this file and go up to find the project root
    current_path = Path(__file__).parent.resolve()

    # Try to find the project root by looking for src/automataii structure
    while current_path.parent != current_path:
        if (current_path / "src" / "automataii").exists():
            return current_path
        current_path = current_path.parent

    # Fallback: return the automataii package directory
    return Path(__file__).parent.parent


def get_app_temp_dir() -> Path:
    """
    Returns the base temporary directory for the Automataii application.
    Ensures that the directory exists.

    Returns:
        Path: The path to the application's temporary directory.
    """
    app_temp_dir = Path(tempfile.gettempdir()) / "automataii"
    app_temp_dir.mkdir(parents=True, exist_ok=True)
    return app_temp_dir


def get_app_data_dir() -> Path:
    """Return a user-writable application data directory.

    Packaged macOS apps are signed read-only bundles, so runtime files such as
    logs and default scenario output must not be written under bundled
    resources.
    """
    system = platform.system()
    if system == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    elif system == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))

    app_data_dir = base / "AutomataII"
    app_data_dir.mkdir(parents=True, exist_ok=True)
    return app_data_dir


def get_session_temp_dir(session_id: str | None = None, clear_existing: bool = False) -> Path:
    """
    Returns a unique temporary directory for a specific processing session or project instance.
    If no session_id is provided, a new UUID will be generated.
    Logs the path if logging level is DEBUG.

    Args:
        session_id (Optional[str]): A unique identifier for the session.
                                     If None, a new UUID is generated.
        clear_existing (bool): If True and the directory exists, it will be removed
                               and recreated. Defaults to False.

    Returns:
        Path: The path to the session-specific temporary directory.
    """
    base_temp_dir = get_app_temp_dir()

    if session_id is None:
        session_id = str(uuid.uuid4())
        logger.debug(f"No session_id provided, generated new UUID: {session_id}")

    # Sanitize session_id to be a valid directory name (simple sanitization)
    safe_session_id = "".join(c for c in session_id if c.isalnum() or c in ("_", "-")).strip()
    if not safe_session_id:  # If sanitization results in empty string, use a UUID
        safe_session_id = str(uuid.uuid4())
        logger.warning(
            f"Provided session_id ('{session_id}') sanitized to empty. Using UUID: {safe_session_id}"
        )

    project_temp_dir = base_temp_dir / safe_session_id

    if project_temp_dir.exists() and clear_existing:
        logger.debug(f"Clearing existing temporary session directory: {project_temp_dir}")
        try:
            shutil.rmtree(project_temp_dir)
        except OSError as e:
            logger.error(f"Error removing directory {project_temp_dir}: {e}", exc_info=True)
            # Proceed to try creating it, maybe it was partially deleted or permissions issue

    project_temp_dir.mkdir(parents=True, exist_ok=True)

    # Log the path if in debug mode (check current logger effective level)
    if logger.getEffectiveLevel() <= logging.DEBUG:
        logger.debug(f"Temporary session directory: {project_temp_dir.resolve()}")

    return project_temp_dir


def get_base_path() -> Path:
    """
    Returns the base path for resource resolution.
    For a bundled app, this is the _MEIPASS directory.
    For a regular script, this is the project root.

    Returns:
        Path: Base path for resource resolution
    """
    frozen_base = _frozen_base_path()
    if frozen_base is not None:
        return frozen_base

    # Otherwise, use project root
    return get_project_root()


def resolve_path(relative_path: str | Path) -> Path:
    """
    Resolve a resource path that works in both dev and frozen builds.

    Strategy:
    - Start with `get_base_path()` joined with the given path.
    - If not found, try adding/removing a leading `src/` component to bridge
      packaging-time relocations (e.g., PyInstaller `datas` placing files
      under `_MEIPASS/examples` instead of `_MEIPASS/src/examples`).
    - If none of the candidates exist, return the first candidate for callers
      that may create files.
    """
    base_path = get_base_path()

    # Normalize to Path
    rel = Path(relative_path) if not isinstance(relative_path, Path) else relative_path

    candidates: list[Path] = []
    candidates.append(base_path / rel)

    parts = rel.parts
    # If path starts with 'src', also try without it
    if parts and parts[0] == "src":
        without_src = Path(*parts[1:]) if len(parts) > 1 else Path(".")
        candidates.append(base_path / without_src)
    else:
        # Also try with a leading 'src' for dev environments
        candidates.append(base_path / "src" / rel)

    # Deduplicate while preserving order
    seen = set()
    unique_candidates = []
    for c in candidates:
        if c not in seen:
            unique_candidates.append(c)
            seen.add(c)

    for c in unique_candidates:
        try:
            if c.exists():
                logger.debug(f"Resolved path '{rel}' -> '{c}'")
                return c
        except Exception:
            # In case of permission or other filesystem issues, skip to next candidate
            continue

    # Fallback: return the first candidate even if it doesn't exist
    if not unique_candidates:
        # Should never happen, but guard against it
        logger.warning(f"No candidates found for path '{rel}', returning base_path / rel")
        return base_path / rel
    fallback = unique_candidates[0]
    logger.debug(f"Resolved path (fallback) '{rel}' -> '{fallback}'")
    return fallback


if __name__ == "__main__":
    # Configure logging for testing
    logging.basicConfig(level=logging.DEBUG)

    # Test get_app_temp_dir
    app_dir = get_app_temp_dir()
    print(f"Application temp dir: {app_dir}")
    assert app_dir.exists()
    assert app_dir.name == "automataii"

    # Test get_session_temp_dir with generated ID
    session_dir1 = get_session_temp_dir(clear_existing=True)
    print(f"Session temp dir 1 (auto-ID): {session_dir1}")
    assert session_dir1.exists()
    assert session_dir1.parent == app_dir
    (session_dir1 / "test_file.txt").write_text("hello")

    # Test get_session_temp_dir with provided ID
    custom_id = "my_test_session_123"
    session_dir2 = get_session_temp_dir(session_id=custom_id, clear_existing=True)
    print(f"Session temp dir 2 (custom-ID): {session_dir2}")
    assert session_dir2.exists()
    assert session_dir2.name == custom_id
    assert not (session_dir2 / "test_file.txt").exists()  # Should be cleared

    # Test clearing
    (session_dir2 / "another_file.txt").write_text("world")
    assert (session_dir2 / "another_file.txt").exists()
    session_dir3 = get_session_temp_dir(session_id=custom_id, clear_existing=True)
    print(f"Session temp dir 3 (cleared): {session_dir3}")
    assert session_dir3.exists()
    assert not (session_dir3 / "another_file.txt").exists()

    # Test with potentially problematic session_id
    problem_id = "../invalid/name?*"
    session_dir4 = get_session_temp_dir(session_id=problem_id)
    print(f"Session temp dir 4 (problem_id sanitized): {session_dir4}")
    assert session_dir4.exists()
    assert session_dir4.name != problem_id  # Name should be sanitized

    # Test resolve_path
    print(f"Base path: {get_base_path()}")
    test_path = resolve_path("models/onnx/test.onnx")
    print(f"Resolved path: {test_path}")

    print("Path utility tests completed.")
