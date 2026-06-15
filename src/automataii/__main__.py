import argparse
import logging
import os
import platform
import sys
from pathlib import Path

if not os.environ.get("QT_QPA_PLATFORM"):
    ci_mode_enabled = os.environ.get("CI", "").lower() in {
        "1",
        "true",
        "yes",
    } or os.environ.get("CODEX_CI", "").lower() in {"1", "true", "yes"}
    if ci_mode_enabled:
        # Avoid hard crashes from unavailable GUI services in CI/headless runs.
        os.environ["QT_QPA_PLATFORM"] = "offscreen"

try:
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtGui import QFont
    from PyQt6.QtWidgets import QApplication
except ImportError:
    try:
        from PySide6.QtCore import Qt, QTimer  # type: ignore[no-redef]
        from PySide6.QtGui import QFont  # type: ignore[no-redef]
        from PySide6.QtWidgets import QApplication  # type: ignore[no-redef]
    except ImportError:
        print(
            "This application requires PyQt6 or PySide6; please install one of these packages.",
            file=sys.stderr,
        )
        sys.exit(1)

from automataii.presentation.qt.main_window import AutomataDesigner
from automataii.scenarios import run_blueprint_export_scenario
from automataii.utils.auto_updater import setup_auto_updater
from automataii.utils.config import AppConfig
from automataii.utils.logging_config import setup_logging
from automataii.utils.paths import get_app_data_dir, get_base_path, get_project_root
from automataii.utils.styling import LIGHT_STYLE


def schedule_startup_update_check(
    updater: object | None,
    *,
    delay_ms: int = 3000,
    qtimer_cls: type[QTimer] = QTimer,
) -> bool:
    """Schedule a silent startup update check when the updater allows it."""
    if updater is None:
        return False

    can_check = getattr(updater, "can_check_for_updates_in_background", None)
    if not callable(can_check) or not can_check():
        return False

    check_for_updates = getattr(updater, "check_for_updates", None)
    if not callable(check_for_updates):
        return False

    qtimer_cls.singleShot(delay_ms, lambda: check_for_updates(show_ui=False))
    return True


def main() -> None:
    """Main function to initialize and run the MotionSmith application."""
    # Handle PyInstaller bundle environment
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # We're running from a PyInstaller bundle
        bundle_dir = get_base_path()
        logging.info(f"Running from PyInstaller bundle: {bundle_dir}")

        # Force macOS to use light theme for title bar
        if platform.system() == "Darwin":
            # This doesn't work for .app bundles, but kept for reference
            os.environ["QT_MAC_WANTS_LAYER"] = "1"
            os.environ["QT_QPA_PLATFORM"] = "cocoa"

            logging.info("Using bundled resource root without changing cwd: %s", bundle_dir)
    else:
        # We're running from source
        logging.info(f"Running from source: {get_project_root()}")

    parser = argparse.ArgumentParser(description="MotionSmith Application")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging and features.")
    parser.add_argument(
        "--experiment",
        action="store_true",
        help="Enable experimental mode (hides Mechanism Foundry tab; Options remain in the menu).",
    )
    parser.add_argument(
        "--editing", action="store_true", help="Enable interactive segmentation editing mode."
    )
    parser.add_argument(
        "--scenario",
        choices=["blueprint-export", "image-processing"],
        help="Run an automation scenario (non-interactive) and exit.",
    )
    parser.add_argument(
        "--scenario-output",
        type=Path,
        help="Destination directory for scenario artifacts (defaults to user app data/artifacts/<scenario>).",
    )
    args = parser.parse_args()

    log_level = logging.DEBUG if args.debug else logging.INFO
    setup_logging(console_log_level=log_level)

    if args.scenario:
        _run_scenario(args)
        return

    try:
        QApplication.setAttribute(
            Qt.ApplicationAttribute.AA_EnableHighDpiScaling  # type: ignore[attr-defined]
        )
        QApplication.setAttribute(
            Qt.ApplicationAttribute.AA_UseHighDpiPixmaps  # type: ignore[attr-defined]
        )
        os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
        logging.info("High DPI environment variables set (QT_AUTO_SCREEN_SCALE_FACTOR=1).")
    except AttributeError:
        logging.warning(
            "Could not set High DPI attributes (Qt version might be too old or attributes moved)."
        )

    app = QApplication(sys.argv)
    app.setFont(QFont("Arial"))

    # Set application metadata
    app.setApplicationName(AppConfig.APP_NAME)
    app.setOrganizationName(AppConfig.ORGANIZATION_NAME)
    app.setOrganizationDomain(AppConfig.ORGANIZATION_DOMAIN)

    # macOS specific: Ensure app comes to foreground
    if platform.system() == "Darwin":
        try:
            import AppKit

            AppKit.NSApp.activateIgnoringOtherApps_(True)
        except ImportError:
            # Fall back to Qt method
            app.setAttribute(Qt.ApplicationAttribute.AA_PluginApplication, False)

    app.setStyleSheet(LIGHT_STYLE)

    AppConfig.initialize()

    # Log important paths for debugging
    logging.info(f"Project root: {get_project_root()}")
    logging.info(f"Base path: {get_base_path()}")
    logging.info(f"Current working directory: {os.getcwd()}")

    # Setup auto-updater
    updater = setup_auto_updater(app)
    if updater:
        logging.info(f"Auto-updater initialized: {updater.get_update_info()['updater_type']}")
    else:
        logging.info("Auto-updater not available")

    logging.info("Creating main window...")
    main_window = AutomataDesigner(
        debug_mode=args.debug, experiment_mode=args.experiment, editing_mode=args.editing
    )

    # Pass updater to main window if available
    if updater and hasattr(main_window, "set_updater"):
        main_window.set_updater(updater)

    main_window.show()

    # macOS specific: Bring window to front
    if platform.system() == "Darwin":
        main_window.raise_()
        main_window.activateWindow()

    if schedule_startup_update_check(updater):
        logging.info("Scheduled startup update check.")
    elif updater:
        logging.info("Startup update check not scheduled.")

    logging.info("Application started.")

    sys.exit(app.exec())


def _run_scenario(args: argparse.Namespace) -> None:
    scenario_name = args.scenario
    output_root = (
        Path(args.scenario_output)
        if args.scenario_output
        else get_app_data_dir() / "artifacts" / scenario_name
    )
    output_root.mkdir(parents=True, exist_ok=True)

    if scenario_name == "blueprint-export":
        svg_path = run_blueprint_export_scenario(output_root)
        manifest_path = output_root / "foundry_blueprint_manifest.json"
        metrics_path = output_root / "foundry_blueprint_metrics.json"
        logging.info(
            "Blueprint export scenario completed: svg=%s manifest=%s metrics=%s",
            svg_path,
            manifest_path,
            metrics_path,
        )
        print(f"[scenario:{scenario_name}] artifacts={svg_path}, {manifest_path}, {metrics_path}")
    elif scenario_name == "image-processing":
        from automataii.scenarios import run_image_processing_scenario

        parts_dir = run_image_processing_scenario(output_root)
        manifest_path = output_root / "image_processing_manifest.json"
        metrics_path = output_root / "image_processing_metrics.json"
        logging.info(
            "Image-processing scenario completed: parts=%s manifest=%s metrics=%s",
            parts_dir,
            manifest_path,
            metrics_path,
        )
        print(f"[scenario:{scenario_name}] artifacts={parts_dir}, {manifest_path}, {metrics_path}")
    else:
        raise ValueError(f"Unsupported scenario: {scenario_name}")


if __name__ == "__main__":
    main()
