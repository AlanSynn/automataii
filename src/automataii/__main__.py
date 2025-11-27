import argparse
import logging
import os
import platform
import sys
from pathlib import Path

try:
    from PyQt6.QtCore import QStandardPaths, Qt
    from PyQt6.QtWidgets import QApplication
except ImportError:
    try:
        from PySide6.QtCore import QStandardPaths, Qt
        from PySide6.QtWidgets import QApplication
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
from automataii.utils.paths import get_base_path, get_project_root
from automataii.utils.styling import LIGHT_STYLE


def main():
    """Main function to initialize and run the Automataii application."""
    # Handle PyInstaller bundle environment
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # We're running from a PyInstaller bundle
        bundle_dir = Path(sys._MEIPASS)
        logging.info(f"Running from PyInstaller bundle: {bundle_dir}")

        # Force macOS to use light theme for title bar
        if platform.system() == "Darwin":
            # This doesn't work for .app bundles, but kept for reference
            os.environ["QT_MAC_WANTS_LAYER"] = "1"
            os.environ["QT_QPA_PLATFORM"] = "cocoa"

            # Change working directory to the bundle directory to ensure relative paths work
            os.chdir(bundle_dir)
            logging.info(f"Changed working directory to: {os.getcwd()}")
    else:
        # We're running from source
        logging.info(f"Running from source: {get_project_root()}")

    parser = argparse.ArgumentParser(description="Automataii Application")
    parser.add_argument(
        "--debug", action="store_true", help="Enable debug logging and features."
    )
    parser.add_argument(
        "--experiment", action="store_true", help="Enable experimental mode (hides Mechanism Foundry and Options tabs)."
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
        help="Destination directory for scenario artifacts (defaults to ./artifacts/<scenario>).",
    )
    args = parser.parse_args()

    log_level = logging.DEBUG if args.debug else logging.INFO
    setup_logging(console_log_level=log_level)

    if args.scenario:
        _run_scenario(args)
        return

    try:
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)
        os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
        logging.info(
            "High DPI environment variables set (QT_AUTO_SCREEN_SCALE_FACTOR=1)."
        )
    except AttributeError:
        logging.warning(
            "Could not set High DPI attributes (Qt version might be too old or attributes moved)."
        )

    app = QApplication(sys.argv)

    # Set application metadata
    app.setApplicationName("Automataii")
    app.setOrganizationName("Alan Synn")
    app.setOrganizationDomain("alansynn.com")

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
        debug_mode=args.debug,
        experiment_mode=args.experiment,
        editing_mode=args.editing
    )

    # Pass updater to main window if available
    if updater and hasattr(main_window, 'set_updater'):
        main_window.set_updater(updater)

    main_window.show()

    # macOS specific: Bring window to front
    if platform.system() == "Darwin":
        main_window.raise_()
        main_window.activateWindow()

    logging.info("Application started.")

    sys.exit(app.exec())


def _run_scenario(args) -> None:
    scenario_name = args.scenario
    output_root = Path(args.scenario_output) if args.scenario_output else Path("artifacts") / scenario_name
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
