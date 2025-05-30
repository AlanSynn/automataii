from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

class UIColors:
    COMPONENT_FRONT = QColor("#87CEEB")  # SkyBlue
    COMPONENT_BACK = QColor("#4682B4")  # SteelBlue
    COMPONENT_BORDER = QColor(Qt.GlobalColor.black)

    PIN_FRONT = QColor("#FFD700")  # Gold
    PIN_BACK = QColor("#DAA520")  # Goldenrod
    PIN_BORDER = QColor(Qt.GlobalColor.black)

    CAM_FRONT = QColor("#ADD8E6")  # LightBlue
    CAM_BACK = QColor("#5F9EA0")  # CadetBlue
    CAM_BORDER = QColor(Qt.GlobalColor.black)
    SHAFT_FRONT = QColor("#D3D3D3")  # LightGray
    SHAFT_BACK = QColor("#A9A9A9")  # DarkGray
    SHAFT_BORDER = QColor(Qt.GlobalColor.black)

    GEAR_BODY_FRONT = QColor("#C0C0C0")  # Silver
    GEAR_BODY_BACK = QColor("#708090")  # SlateGray
    GEAR_BODY_BORDER = QColor(Qt.GlobalColor.black)
    GEAR_TOOTH_FRONT = QColor("#DCDCDC")  # Gainsboro
    GEAR_TOOTH_BACK = QColor("#A9A9A9")  # DarkGray
    GEAR_TOOTH_BORDER = QColor(
        Qt.GlobalColor.darkGray
    )  # Slightly lighter border for teeth

    TEXT_PRIMARY = QColor("#E0E0E0")
    MOTION_PATH_COLOR = QColor(0, 255, 0, 150)
    DEBUG_HELPER_COLOR = QColor(255, 0, 255, 180)  # Magenta for helpers

def apply_dark_theme(app: QApplication) -> None:
    """Applies a dark theme palette to the QApplication instance."""
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))  # Darker base
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

# Stylesheets for the Automata Designer application

LIGHT_STYLE = """
    /* Base Styling */
    QMainWindow {
        background-color: #fdfdfe; /* Near white */
    }
    QWidget {
        font-family: "Helvetica Neue", Arial, sans-serif; /* Use loaded Segoe UI first */
        font-size: 13pt; /* Increased base font size AGAIN */
        color: #495057; /* Softer dark gray text */
        background-color: transparent;
    }

    /* Toolbar */
    QToolBar {
        background-color: #eef2f7; /* Light pastel blue-gray */
        border-bottom: 1px solid #dbe4f0;
        padding: 7px;
        spacing: 12px;
    }
    QToolBar QToolButton {
        font-size: 11pt; /* Adjusted */
        color: #5a6a7a;
        background-color: transparent;
        border: none;
        padding: 8px 12px;
        border-radius: 5px;
    }
    QToolBar QToolButton:hover {
        background-color: #dbe4f0;
        color: #343a40;
    }
     QToolBar QToolButton:pressed {
         background-color: #c8d3e3;
     }
     QToolBar QToolButton:checked {
         background-color: #dbe4f0;
     }

    /* Tabs */
    QTabWidget::pane {
        border: 1px solid #dbe4f0;
        background: #ffffff;
    }
    QTabWidget::tab-bar {
        alignment: left;
        left: 15px; /* Indent tab bar more */
    }
    QTabBar::tab {
        background: #eef2f7;
        border: 1px solid #dbe4f0;
        border-bottom: none;
        border-top-left-radius: 7px;
        border-top-right-radius: 7px;
        padding: 12px 35px; /* Wider padding */
        margin-right: 5px;
        color: #6c7a89;
        font-weight: bold;
        font-size: 12pt; /* Adjusted */
        min-width: 180px; /* Ensure minimum width */
    }
    QTabBar::tab:selected {
        background: #ffffff;
        color: #5c85d6; /* Pastel blue */
        border-color: #dbe4f0;
        border-bottom: 1px solid #ffffff;
    }
    QTabBar::tab:hover:!selected {
        background: #dbe4f0;
        color: #495057;
    }
    QTabBar::tab:!selected {
        margin-top: 3px;
    }

    /* Group Box */
    QGroupBox {
        background-color: #ffffff;
        border: 1px solid #e3e9f0;
        border-radius: 9px;
        padding: 18px;
        margin-top: 15px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 10px;
        margin-left: 15px;
        font-size: 12pt; /* Adjusted */
        font-weight: bold;
        color: #5c85d6; /* Pastel blue */
        background-color: #ffffff;
    }

    /* Buttons */
    QPushButton {
        background-color: #a7c7e7; /* Pastel blue */
        border: 1px solid #96b6d6;
        padding: 12px 20px;
        border-radius: 7px;
        color: #ffffff;
        font-weight: bold;
        font-size: 12pt; /* Adjusted */
        min-height: 28px; /* Adjust min height */
    }
    QPushButton:hover {
        background-color: #96b6d6;
        border-color: #85a5c5;
    }
    QPushButton:pressed {
        background-color: #85a5c5;
        border-color: #7494b4;
    }
    QPushButton:checked {
        background-color: #85a5c5;
        border-color: #7494b4;
    }
    QPushButton:disabled {
         background-color: #e0e6ed;
         color: #a0aab5;
         border-color: #dbe4f0;
     }
     /* Special button types (e.g., less important actions) */
     QPushButton[flat="true"] {
        background-color: #eef2f7;
        border: 1px solid #dbe4f0;
        color: #6c7a89;
     }
     QPushButton[flat="true"]:hover {
        background-color: #dbe4f0;
        border-color: #c8d3e3;
     }
     QPushButton[flat="true"]:pressed {
        background-color: #c8d3e3;
     }

    /* Input Fields */
    QLineEdit, QDoubleSpinBox, QComboBox {
        border: 1px solid #dbe4f0;
        padding: 9px 12px; /* Add more horizontal padding */
        background-color: #ffffff;
        border-radius: 6px;
        color: #495057;
        min-height: 26px; /* Slightly increase min-height */
    }
     QLineEdit:focus, QDoubleSpinBox:focus, QComboBox:focus {
          border-color: #a7c7e7; /* Pastel blue focus */
     }
     QLineEdit:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {
         background-color: #f8fafd;
         color: #a0aab5;
     }
    QComboBox::drop-down {
         subcontrol-origin: padding;
         subcontrol-position: top right;
         width: 28px; /* Slightly wider dropdown button */
         border-left: 1px solid #dbe4f0;
         border-top-right-radius: 5px;
         border-bottom-right-radius: 5px;
         background: #eef2f7;
    }
    QComboBox::down-arrow {
         /* Consider using a themed icon */
         /* image: url(:/qt-project.org/styles/commonstyle/images/downarraow-16.png); */
    }
    QComboBox QAbstractItemView {
         background-color: #ffffff;
         border: 1px solid #c8d3e3; /* Match focus border? or darker gray */
         selection-background-color: #a7c7e7; /* Pastel blue */
         selection-color: #ffffff;
         color: #495057;
         outline: 0px;
         padding: 6px; /* Slightly more padding for dropdown items */
     }

    /* Checkbox */
    QCheckBox {
         spacing: 12px;
         color: #495057;
     }
    QCheckBox::indicator {
        width: 20px;
        height: 20px;
        border: 2px solid #c8d3e3;
        border-radius: 5px;
        background-color: #ffffff;
    }
    QCheckBox::indicator:hover {
         border-color: #a7c7e7;
    }
    QCheckBox::indicator:checked {
         background-color: #a7c7e7;
         border-color: #a7c7e7;
         /* image: url(icons/checkmark-white.svg); Needs white checkmark SVG */
    }
"""

DARK_STYLE = """
    /* Base Styling */
    QMainWindow {
        background-color: #2b2b2b; /* Dark gray */
    }
    QWidget {
        font-family: "Helvetica Neue", Arial, sans-serif;
        font-size: 13pt;
        color: #e0e0e0; /* Light gray text */
        background-color: transparent;
    }

    /* Toolbar */
    QToolBar {
        background-color: #3c3f41; /* Darker gray for toolbar */
        border-bottom: 1px solid #4a4d4f;
        padding: 7px;
        spacing: 12px;
    }
    QToolBar QToolButton {
        font-size: 11pt;
        color: #c0c0c0;
        background-color: transparent;
        border: none;
        padding: 8px 12px;
        border-radius: 5px;
    }
    QToolBar QToolButton:hover {
        background-color: #4a4d4f;
        color: #ffffff;
    }
     QToolBar QToolButton:pressed {
         background-color: #5a5d5f;
     }
     QToolBar QToolButton:checked {
         background-color: #4a4d4f;
     }

    /* Tabs */
    QTabWidget::pane {
        border: 1px solid #4a4d4f;
        background: #3c3f41;
    }
    QTabWidget::tab-bar {
        alignment: left;
        left: 15px;
    }
    QTabBar::tab {
        background: #323232; /* Slightly lighter than pane */
        border: 1px solid #4a4d4f;
        border-bottom: none;
        border-top-left-radius: 7px;
        border-top-right-radius: 7px;
        padding: 12px 35px;
        margin-right: 5px;
        color: #b0b0b0;
        font-weight: bold;
        font-size: 12pt;
        min-width: 180px;
    }
    QTabBar::tab:selected {
        background: #3c3f41; /* Match pane background */
        color: #6fa3ef; /* Brighter blue */
        border-color: #4a4d4f;
        border-bottom: 1px solid #3c3f41;
    }
    QTabBar::tab:hover:!selected {
        background: #4a4d4f;
        color: #e0e0e0;
    }
    QTabBar::tab:!selected {
        margin-top: 3px;
    }

    /* Group Box */
    QGroupBox {
        background-color: #3c3f41;
        border: 1px solid #4f5254;
        border-radius: 9px;
        padding: 18px;
        margin-top: 15px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 10px;
        margin-left: 15px;
        font-size: 12pt;
        font-weight: bold;
        color: #6fa3ef;
        background-color: #3c3f41;
    }

    /* Buttons */
    QPushButton {
        background-color: #528beB; /* Vivid blue */
        border: 1px solid #417adc;
        padding: 12px 20px;
        border-radius: 7px;
        color: #ffffff;
        font-weight: bold;
        font-size: 12pt;
        min-height: 28px;
    }
    QPushButton:hover {
        background-color: #417adc;
        border-color: #3069cd;
    }
    QPushButton:pressed {
        background-color: #3069cd;
        border-color: #1f58bd;
    }
    QPushButton:checked {
        background-color: #3069cd;
        border-color: #1f58bd;
    }
    QPushButton:disabled {
         background-color: #3a3d3f;
         color: #707070;
         border-color: #4a4d4f;
     }
    QPushButton[flat="true"] {
        background-color: #3c3f41;
        border: 1px solid #4a4d4f;
        color: #b0b0b0;
     }
     QPushButton[flat="true"]:hover {
        background-color: #4a4d4f;
        border-color: #5a5d5f;
     }
     QPushButton[flat="true"]:pressed {
        background-color: #5a5d5f;
     }

    /* Input Fields */
    QLineEdit, QDoubleSpinBox, QComboBox {
        border: 1px solid #4f5254;
        padding: 9px 12px;
        background-color: #2b2b2b;
        border-radius: 6px;
        color: #e0e0e0;
        min-height: 26px;
    }
     QLineEdit:focus, QDoubleSpinBox:focus, QComboBox:focus {
          border-color: #528beB; /* Vivid blue focus */
     }
     QLineEdit:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {
         background-color: #35383a;
         color: #707070;
     }
    QComboBox::drop-down {
         subcontrol-origin: padding;
         subcontrol-position: top right;
         width: 28px;
         border-left: 1px solid #4f5254;
         border-top-right-radius: 5px;
         border-bottom-right-radius: 5px;
         background: #3c3f41;
    }
    QComboBox::down-arrow {
        /* image: url(icons/down-arrow-white.svg); Needs white arrow SVG */
    }
    QComboBox QAbstractItemView {
         background-color: #2b2b2b;
         border: 1px solid #5a5d5f;
         selection-background-color: #528beB;
         selection-color: #ffffff;
         color: #e0e0e0;
         outline: 0px;
         padding: 6px;
     }

    /* Checkbox */
    QCheckBox {
         spacing: 12px;
         color: #e0e0e0;
     }
    QCheckBox::indicator {
        width: 20px;
        height: 20px;
        border: 2px solid #5a5d5f;
        border-radius: 5px;
        background-color: #2b2b2b;
    }
    QCheckBox::indicator:hover {
         border-color: #528beB;
    }
    QCheckBox::indicator:checked {
         background-color: #528beB;
         border-color: #528beB;
         /* image: url(icons/checkmark-black.svg); Needs black checkmark for light blue bg */
    }
    QCheckBox::indicator:disabled {
        border-color: #404345;
        background-color: #35383a;
    }

    /* Label */
    QLabel {
        color: #e0e0e0;
        background-color: transparent;
    }
    QLabel:disabled {
        color: #707070;
    }

    /* Tree View */
    QTreeView {
        background-color: #3c3f41;
        alternate-background-color: #424547; /* Slightly different for rows */
        border: 1px solid #4f5254;
        border-radius: 6px;
        color: #e0e0e0;
    }
    QTreeView::item {
        padding: 6px;
        border-radius: 3px;
    }
    QTreeView::item:hover {
        background-color: #4a4d4f;
    }
    QTreeView::item:selected {
        background-color: #528beB; /* Vivid blue for selection */
        color: #ffffff;
    }
    QHeaderView::section {
        background-color: #424547;
        color: #e0e0e0;
        padding: 6px;
        border: 1px solid #4f5254;
        font-weight: bold;
    }

    /* ScrollBar */
    QScrollBar:vertical {
        border: 1px solid #4f5254;
        background: #3c3f41;
        width: 18px;
        margin: 20px 0 20px 0;
        border-radius: 9px;
    }
    QScrollBar::handle:vertical {
        background: #5a5d5f;
        min-height: 25px;
        border-radius: 8px;
        border: 1px solid #6a6d6f;
    }
    QScrollBar::handle:vertical:hover {
        background: #6a6d6f;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        border: none;
        background: none;
        height: 18px;
        subcontrol-position: top;
        subcontrol-origin: margin;
    }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        background: none;
    }

    QScrollBar:horizontal {
        border: 1px solid #4f5254;
        background: #3c3f41;
        height: 18px;
        margin: 0 20px 0 20px;
        border-radius: 9px;
    }
    QScrollBar::handle:horizontal {
        background: #5a5d5f;
        min-width: 25px;
        border-radius: 8px;
        border: 1px solid #6a6d6f;
    }
    QScrollBar::handle:horizontal:hover {
        background: #6a6d6f;
    }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
        border: none;
        background: none;
        width: 18px;
        subcontrol-position: left;
        subcontrol-origin: margin;
    }
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
        background: none;
    }

    /* Slider */
    QSlider::groove:horizontal {
        border: 1px solid #4f5254;
        background: #2b2b2b;
        height: 8px;
        border-radius: 4px;
    }
    QSlider::handle:horizontal {
        background: #528beB;
        border: 1px solid #417adc;
        width: 18px;
        margin: -5px 0; /* Center handle */
        border-radius: 9px;
    }
    QSlider::handle:horizontal:hover {
        background: #629bfB;
        border-color: #518aec;
    }

    /* TextEdit */
    QTextEdit, QPlainTextEdit {
        background-color: #2b2b2b;
        border: 1px solid #4f5254;
        color: #e0e0e0;
        padding: 8px;
        border-radius: 6px;
    }

    /* MenuBar */
    QMenuBar {
        background-color: #3c3f41;
        color: #e0e0e0;
        border-bottom: 1px solid #4a4d4f;
    }
    QMenuBar::item {
        background-color: transparent;
        padding: 6px 12px;
    }
    QMenuBar::item:selected {
        background-color: #528beB;
        color: #ffffff;
    }
    QMenuBar::item:pressed {
        background-color: #417adc;
    }

    /* Menu */
    QMenu {
        background-color: #3c3f41;
        border: 1px solid #4a4d4f;
        color: #e0e0e0;
        padding: 5px;
    }
    QMenu::item {
        padding: 8px 25px 8px 20px; /* Extra padding for submenu arrow */
        border-radius: 4px;
    }
    QMenu::item:selected {
        background-color: #528beB;
        color: #ffffff;
    }
    QMenu::separator {
        height: 1px;
        background-color: #4f5254;
        margin: 5px 0;
    }
    QMenu::indicator:non-exclusive:checked {
        /* Style for checkable menu items, if needed */
    }

    /* StatusBar */
    QStatusBar {
        background-color: #3c3f41;
        color: #c0c0c0;
        border-top: 1px solid #4a4d4f;
    }
    QStatusBar::item {
        border: none;
    }

    /* Dialogs */
    QDialog {
        background-color: #353535; /* Slightly different from main window */
        border: 1px solid #454545;
    }
    /* Specific styling for QColorDialog, QFontDialog might be needed if they don't inherit well */

    /* Splitter */
    QSplitter::handle {
        background-color: #4a4d4f; /* Handle color */
        border: 1px solid #5a5d5f;
    }
    QSplitter::handle:horizontal {
        width: 5px;
    }
    QSplitter::handle:vertical {
        height: 5px;
    }
    QSplitter::handle:pressed {
        background-color: #528beB;
    }

    /* GraphicsView */
    QGraphicsView {
        border: 1px solid #4f5254;
        background-color: #2b2b2b; /* Match TextEdit background */
        border-radius: 6px;
    }
"""