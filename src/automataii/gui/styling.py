# Stylesheets for the Automata Designer application

LIGHT_STYLE = """
    /* Base Styling */
    QMainWindow {
        background-color: #fdfdfe; /* Near white */
    }
    QWidget {
        font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, system-ui, "Helvetica Neue", Arial, sans-serif; /* Use loaded Segoe UI first */
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
     QCheckBox::indicator:disabled {
        border-color: #dbe4f0;
        background-color: #eef2f7;
    }
    QCheckBox:disabled {
         color: #a0aab5;
    }

    /* Other */
    QListWidget {
        border: 1px solid #dbe4f0;
        background-color: white;
        padding: 6px;
    }
    QListWidget::item {
        padding: 9px 6px;
    }
    QListWidget::item:selected {
         background-color: #e0eaf7; /* Very light pastel blue selection */
         color: #5c85d6;
         border-radius: 5px;
     }
    QSplitter::handle {
        background: #dbe4f0;
        height: 4px;
        width: 4px;
    }
    QGraphicsView {
        border: 1px solid #dbe4f0;
        background-color: #f8fafd; /* Very light bg */
    }
    QStatusBar {
        color: #6c7a89;
        background-color: #eef2f7;
        border-top: 1px solid #dbe4f0;
    }
    QMenuBar {
         background-color: #eef2f7;
         color: #6c7a89;
         border-bottom: 1px solid #dbe4f0;
    }
     QMenuBar::item {
         padding: 7px 14px;
     }
     QMenuBar::item:selected {
         background: #dbe4f0;
     }
     QMenu {
         background-color: #ffffff;
         border: 1px solid #dbe4f0;
         color: #495057;
         padding: 7px;
     }
     QMenu::item {
         padding: 9px 28px;
         border-radius: 5px;
     }
     QMenu::item:selected {
         background-color: #a7c7e7;
         color: #ffffff;
     }
     QMenu::separator {
        height: 1px;
        background-color: #dbe4f0;
        margin: 7px 0px;
    }
     QScrollBar:vertical {
        border: none;
        background-color: #f8fafd;
        width: 14px;
        margin: 0px;
    }
    QScrollBar::handle:vertical {
        background-color: #c8d3e3;
        border-radius: 7px;
        min-height: 35px;
    }
    QScrollBar::handle:vertical:hover {
        background-color: #b4c2d4;
    }
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {
        height: 0px;
    }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        background: none;
    }

"""

# Modern dark stylesheet (Previously MODERN_STYLE)
DARK_STYLE = """
    /* Base Styling */
    QMainWindow {
        background-color: #2f343f; /* Softer dark background */
    }
    QWidget {
        font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, system-ui, "Helvetica Neue", Arial, sans-serif; /* Use loaded Segoe UI first */
        font-size: 13pt; /* Increased base font size AGAIN */
        color: #c3cdd9; /* Lighter, less harsh text */
        background-color: #2f343f; /* Explicit dark background for base widgets */
    }

    /* Toolbar */
    QToolBar {
        background-color: #3a404b;
        border-bottom: 1px solid #4a515c;
        padding: 7px;
        spacing: 12px;
    }
    QToolBar QToolButton {
        font-size: 11pt;
        color: #aab5c3;
        background-color: transparent;
        border: none;
        padding: 8px 12px;
        border-radius: 5px;
    }
    QToolBar QToolButton:hover {
        background-color: #4a515c;
        color: #e1e7ef;
    }
     QToolBar QToolButton:pressed {
         background-color: #5a616c;
     }
     QToolBar QToolButton:checked {
         background-color: #5a616c;
     }

    /* Tabs */
    QTabWidget::pane {
        border: 1px solid #4a515c;
        background: #3a404b; /* Dark pane */
    }
    QTabWidget::tab-bar {
        alignment: left;
        left: 15px;
    }
    QTabBar::tab {
        background: #3a404b;
        border: 1px solid #4a515c;
        border-bottom: none;
        border-top-left-radius: 7px;
        border-top-right-radius: 7px;
        padding: 12px 35px; /* Wider padding */
        margin-right: 5px;
        color: #9aa5b3;
        font-weight: bold;
        font-size: 12pt; /* Adjusted */
        min-width: 180px; /* Ensure minimum width */
    }
    QTabBar::tab:selected {
        background: #4a515c; /* Slightly lighter selected tab */
        color: #e1e7ef;
        border-bottom: 1px solid #4a515c;
    }
    QTabBar::tab:hover:!selected {
        background: #4a515c;
        color: #c3cdd9;
    }
    QTabBar::tab:!selected {
        margin-top: 3px;
    }

    /* Group Box */
    QGroupBox {
        background-color: #3a404b; /* Dark background */
        border: 1px solid #4a515c;
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
        color: #d2dbe6; /* Lighter title */
        background-color: #3a404b; /* Match groupbox background */
    }

    /* Buttons */
    QPushButton {
        background-color: #6c7a89; /* Muted gray-blue */
        border: 1px solid #6c7a89;
        padding: 12px 20px;
        border-radius: 7px;
        color: #f0f4f8;
        font-weight: bold;
        font-size: 12pt; /* Adjusted */
        min-height: 28px; /* Adjust min height */
    }
    QPushButton:hover {
        background-color: #5a6a7a;
        border-color: #5a6a7a;
    }
    QPushButton:pressed {
        background-color: #4a5a6a;
        border-color: #4a5a6a;
    }
    QPushButton:checked {
        background-color: #4a5a6a;
        border-color: #4a5a6a;
    }
    QPushButton:disabled {
         background-color: #4a515c;
         color: #8a95a3;
         border-color: #4a515c;
     }
     /* Special button types */
     QPushButton[flat="true"] {
        background-color: #4a515c;
        border: 1px solid #5a616c;
        color: #aab5c3;
     }
     QPushButton[flat="true"]:hover {
        background-color: #5a616c;
        border-color: #6c7a89;
     }
     QPushButton[flat="true"]:pressed {
        background-color: #6c7a89;
     }

    /* Input Fields */
    QLineEdit, QDoubleSpinBox, QComboBox {
        border: 1px solid #495057;
        padding: 9px 12px;
        background-color: #343a40;
        border-radius: 6px;
        color: #dee2e6;
        min-height: 26px;
    }
     QLineEdit:focus, QDoubleSpinBox:focus, QComboBox:focus {
          border-color: #8aa2c0; /* Muted blue focus */
     }
     QLineEdit:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {
         background-color: #4a515c;
         color: #8a95a3;
     }
    QComboBox::drop-down {
         subcontrol-origin: padding;
         subcontrol-position: top right;
         width: 28px;
         border-left: 1px solid #495057;
         border-top-right-radius: 5px;
         border-bottom-right-radius: 5px;
         background: #4a515c;
    }
    QComboBox::down-arrow {
         /* Use an SVG arrow */
         /* image: url(icons/down_arrow_dark.svg); */
    }
    QComboBox QAbstractItemView {
         background-color: #343a40;
         border: 1px solid #5c6a7a; /* Darker gray border for dropdown */
         selection-background-color: #6c7a89;
         selection-color: #ffffff;
         color: #dee2e6;
         outline: 0px;
         padding: 6px;
     }

    /* Checkbox */
    QCheckBox {
         spacing: 12px;
         color: #c3cdd9;
     }
    QCheckBox::indicator {
        width: 20px;
        height: 20px;
        border: 2px solid #6c7a89;
        border-radius: 5px;
        background-color: #3a404b;
    }
     QCheckBox::indicator:hover {
         border-color: #7a9cd1;
     }
    QCheckBox::indicator:checked {
         background-color: #5c85d6; /* Muted blue check */
         border-color: #5c85d6;
         /* image: url(icons/checkmark-white.svg); Needs white checkmark SVG */
     }
     QCheckBox::indicator:disabled {
        border-color: #4a515c;
        background-color: #4a515c;
    }
    QCheckBox:disabled {
         color: #8a95a3;
    }

    /* Other */
    QListWidget {
        border: 1px solid #4a515c;
        background-color: #3a404b;
        padding: 6px;
    }
    QListWidget::item {
        padding: 9px 6px;
        color: #c3cdd9;
    }
    QListWidget::item:selected {
         background-color: #4a5a7a; /* Darker muted blue selection */
         color: #ffffff;
         border-radius: 5px;
     }
    QSplitter::handle {
        background: #4a515c;
        height: 4px;
        width: 4px;
    }
    QGraphicsView {
        border: 1px solid #4a515c;
        background-color: #2f343f; /* Softer dark background */
    }
    QStatusBar {
        color: #aab5c3;
        background-color: #3a404b;
        border-top: 1px solid #4a515c;
    }
    QMenuBar {
         background-color: #3a404b;
         color: #aab5c3;
         border-bottom: 1px solid #4a515c;
    }
     QMenuBar::item {
         padding: 7px 14px;
     }
     QMenuBar::item:selected {
         background: #4a515c;
     }
     QMenu {
         background-color: #3a404b;
         border: 1px solid #6c7a89;
         color: #c3cdd9;
         padding: 7px;
     }
     QMenu::item {
         padding: 9px 28px;
         border-radius: 5px;
     }
     QMenu::item:selected {
         background-color: #5c85d6; /* Muted blue selection */
         color: #ffffff;
     }
     QMenu::separator {
        height: 1px;
        background-color: #4a515c;
        margin: 7px 0px;
    }
     QScrollBar:vertical {
        border: none;
        background-color: #2f343f;
        width: 14px;
        margin: 0px;
    }
    QScrollBar::handle:vertical {
        background-color: #4a515c;
        border-radius: 7px;
        min-height: 35px;
    }
    QScrollBar::handle:vertical:hover {
        background-color: #5a616c;
    }
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {
        height: 0px;
    }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        background: none;
    }
"""