import sys
import logging
import argparse
import os
import platform
from pathlib import Path

try:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QStandardPaths, Qt
except ImportError:
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QStandardPaths, Qt
    except ImportError:
        print(
            "This application requires PyQt6 or PySide6; please install one of these packages.",
            file=sys.stderr,
        )
        sys.exit(1)

from automataii.gui.main_window import AutomataDesigner
from automataii.utils.config import AppConfig
from automataii.utils.styling import LIGHT_STYLE
from automataii.utils.auto_updater import setup_auto_updater
from automataii.utils.paths import get_project_root, get_base_path
from automataii.utils.logging_config import setup_logging


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
    args = parser.parse_args()

    log_level = logging.DEBUG if args.debug else logging.INFO
    setup_logging(console_log_level=log_level)

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
    main_window = AutomataDesigner(debug_mode=args.debug)

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


if __name__ == "__main__":
    main()
