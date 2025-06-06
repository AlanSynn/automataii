import sys
import logging
import argparse
import os

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

from automataii.utils.logging_config import setup_logging


def main():
    """Main function to initialize and run the Automataii application."""
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

    app.setStyleSheet(LIGHT_STYLE)

    AppConfig.initialize()

    logging.info("Creating main window...")
    main_window = AutomataDesigner(debug_mode=args.debug)

    main_window.show()
    logging.info("Application started.")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
