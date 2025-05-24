import sys
import logging
import argparse
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QStandardPaths, Qt
import os
# QPalette, QColor, Qt removed from here if no longer directly used

# Automataii specific imports
from automataii.gui.main_window import AutomataDesigner
from automataii.utils.config import AppConfig
from automataii.gui.styling import LIGHT_STYLE

# Import qtreload
from qtreload import install_hot_reload

def main():
    """Main function to initialize and run the Automataii application."""
    # MODIFIED: Add argument parsing
    parser = argparse.ArgumentParser(description="Automataii Application")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging and features."
    )
    args = parser.parse_args()

    # MODIFIED: Configure logging based on --debug flag
    log_format = '%(asctime)s - %(levelname)s - %(name)s - %(module)s - %(funcName)s - %(lineno)d - %(message)s'
    if args.debug:
        logging.basicConfig(level=logging.DEBUG, format=log_format)
        logging.debug("Debug mode enabled.")
    else:
        logging.basicConfig(level=logging.INFO, format=log_format)

    # Attempt to set High DPI scaling attributes (optional, but good for modern displays)
    try:
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)
        os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
        logging.info("High DPI environment variables set (QT_AUTO_SCREEN_SCALE_FACTOR=1).")
    except AttributeError:
        logging.warning("Could not set High DPI attributes (Qt version might be too old or attributes moved).")

    # Create application instance
    app = QApplication(sys.argv)

    # Apply Dark Theme Palette
    # apply_dark_theme(app)
    app.setStyleSheet(LIGHT_STYLE)

    # Initialize configuration (if any)
    # AppConfig.initialize() # Assuming AppConfig is part of your structure

    # Create and show the main window
    logging.info("Creating main window...")
    main_window = AutomataDesigner(debug_mode=args.debug)

    # --- Install Hot Reload ---
    # Define modules to watch (adjust as needed - e.g., your main package)
    # modules_to_reload = ["gui.main_window", "gui.editor_view", "gui.image_processing_view"]
    # logging.info(f"Installing hot-reloader for modules: {modules_to_reload}")
    # # Keep a reference to the widget to prevent garbage collection
    # main_window.reloader_widget = install_hot_reload(modules_to_reload)
    # --------------------------

    main_window.show()
    logging.info("Application started.")

    # Start the application event loop
    sys.exit(app.exec())

if __name__ == "__main__":
    main()