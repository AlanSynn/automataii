import sys
import os
import logging
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

# Import GUI and utilities
from automataii.gui.main_window import AutomataDesigner
from automataii.utils.helpers import setup_high_dpi_environment

# Import qtreload
from qtreload import install_hot_reload

def main():
    """Main application entry point."""
    # Set up environment (e.g., High DPI)
    setup_high_dpi_environment()

    # Create application instance
    app = QApplication(sys.argv)

    # --- Apply Dark Theme Palette (Optional but recommended) ---
    # You can customize this palette further
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35)) # Darker base
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.black)
    palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white) # White text on highlight
    # Set disabled colors
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(127, 127, 127))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(127, 127, 127))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(127, 127, 127))
    app.setPalette(palette)

    # Create and show the main window
    logging.info("Creating main window...")
    main_window = AutomataDesigner()

    # --- Install Hot Reload ---
    # Define modules to watch (adjust as needed - e.g., your main package)
    modules_to_reload = ["automataii"]
    logging.info(f"Installing hot-reloader for modules: {modules_to_reload}")
    # Keep a reference to the widget to prevent garbage collection
    main_window.reloader_widget = install_hot_reload(modules_to_reload)
    # Optional: Add the widget to the UI if you want the visual indicator
    # If your main window has a status bar:
    # main_window.statusBar().addPermanentWidget(main_window.reloader_widget)
    # Or add it to a layout somewhere.
    # For now, we just keep the reference.
    # --------------------------

    main_window.show()
    logging.info("Application started.")

    # Start the application event loop
    sys.exit(app.exec())

if __name__ == "__main__":
    main()