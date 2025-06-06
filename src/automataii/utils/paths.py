import tempfile
from pathlib import Path
import shutil
import logging
import uuid
from typing import Optional

logger = logging.getLogger(__name__)


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


def get_session_temp_dir(
    session_id: Optional[str] = None, clear_existing: bool = False
) -> Path:
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
    safe_session_id = "".join(
        c for c in session_id if c.isalnum() or c in ("_", "-")
    ).strip()
    if not safe_session_id:  # If sanitization results in empty string, use a UUID
        safe_session_id = str(uuid.uuid4())
        logger.warning(
            f"Provided session_id ('{session_id}') sanitized to empty. Using UUID: {safe_session_id}"
        )

    project_temp_dir = base_temp_dir / safe_session_id

    if project_temp_dir.exists() and clear_existing:
        logger.debug(
            f"Clearing existing temporary session directory: {project_temp_dir}"
        )
        try:
            shutil.rmtree(project_temp_dir)
        except OSError as e:
            logger.error(
                f"Error removing directory {project_temp_dir}: {e}", exc_info=True
            )
            # Proceed to try creating it, maybe it was partially deleted or permissions issue

    project_temp_dir.mkdir(parents=True, exist_ok=True)

    # Log the path if in debug mode (check current logger effective level)
    if logger.getEffectiveLevel() <= logging.DEBUG:
        logger.debug(f"Temporary session directory: {project_temp_dir.resolve()}")

    return project_temp_dir


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

    print("Path utility tests completed.")
