# Stylesheets for the Automata Designer application

LIGHT_STYLE = """
    QMainWindow {
        background-color: #f0f0f0;
    }
    QWidget {
        font-family: sans-serif; /* Use default system sans-serif */
        font-size: 11pt;         /* Increased base font size */
        color: #333;
        background-color: transparent; /* Prevent unwanted background inheritance */
    }
    QToolBar {
        background-color: #e8e8e8;
        border-bottom: 1px solid #dcdcdc;
        padding: 4px;
        spacing: 5px;
    }
    QToolButton {
        background-color: transparent;
        border: none;
        padding: 5px;
    }
    QToolButton:hover {
        background-color: #dcdcdc;
    }
     QToolButton:pressed {
         background-color: #c8c8c8;
     }
    QTabWidget::pane {
        border-top: 1px solid #dcdcdc;
        background: white; /* Explicit white background */
    }
    QTabWidget::tab-bar {
        alignment: left;
    }
    QTabBar::tab {
        background: #e8e8e8;
        border: 1px solid #dcdcdc;
        border-bottom-color: #dcdcdc;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
        min-width: 8ex;
        padding: 5px 10px;
        margin-right: 2px;
        color: #333;
    }
    QTabBar::tab:selected, QTabBar::tab:hover {
        background: white;
        border-bottom-color: white;
    }
    QTabBar::tab:!selected {
        margin-top: 2px;
    }
    QGroupBox {
        background-color: #f8f8f8; /* Explicit light background */
        border: 1px solid #dcdcdc;
        border-radius: 4px;
        margin-top: 1ex;
        font-weight: bold;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 3px;
        left: 10px;
        background-color: transparent;
        color: #333;
    }
    QPushButton {
        background-color: #e0e0e0;
        border: 1px solid #c0c0c0;
        padding: 5px 10px;
        border-radius: 3px;
        color: #333;
    }
    QPushButton:hover {
        background-color: #d8d8d8;
        border-color: #b0b0b0;
    }
    QPushButton:pressed {
        background-color: #c8c8c8;
    }
    QPushButton:checked {
        background-color: #c8e6c9; /* Light green */
        border-color: #a5d6a7;
    }
    QPushButton:disabled {
         background-color: #f5f5f5;
         color: #aaa;
         border-color: #e0e0e0;
     }
    QLabel {
        background-color: transparent;
        color: #333;
    }
    QLabel[section="true"] { /* For consistency if used */
        background-color: #e8e8e8;
        color: #555;
        border-radius: 4px;
        padding: 6px;
        margin-top: 8px;
        margin-bottom: 4px;
        font-weight: bold;
    }
    QListWidget {
        border: 1px solid #dcdcdc;
        background-color: white;
        color: #333;
    }
    QListWidget::item:selected {
         background-color: #a6d5fa;
         color: #111;
     }
    QDoubleSpinBox, QLineEdit, QComboBox {
        border: 1px solid #c0c0c0;
        padding: 3px;
        background-color: white;
        border-radius: 3px;
        color: #333;
    }
     QDoubleSpinBox:disabled, QLineEdit:disabled, QComboBox:disabled {
         background-color: #f5f5f5;
         color: #aaa;
     }
    QComboBox::drop-down {
         border: 1px solid #c0c0c0;
         background: #e8e8e8;
    }
    QComboBox QAbstractItemView {
         background-color: white;
         border: 1px solid #c0c0c0;
         selection-background-color: #a6d5fa;
         color: #333;
         outline: 0px;
     }
    QCheckBox {
         color: #333;
     }
    QCheckBox::indicator {
        width: 13px;
        height: 13px;
        border: 1px solid #c0c0c0;
        border-radius: 2px;
        background-color: white;
    }
    QCheckBox::indicator:checked {
         background-color: #5cb85c; /* Green check */
         border-color: #4cae4c;
         image: url(icons/checkmark_light.png); /* Needs a checkmark icon */
     }
    QCheckBox::indicator:disabled {
        border: 1px solid #e0e0e0;
        background-color: #f5f5f5;
    }
    QCheckBox:disabled {
         color: #aaa;
    }
    QSplitter::handle {
        background: #dcdcdc;
    }
    QSplitter::handle:horizontal {
        width: 1px;
    }
    QSplitter::handle:vertical {
        height: 1px;
    }
    QGraphicsView {
        border: 1px solid #c0c0c0;
        background-color: white;
    }
    QStatusBar {
        color: #333;
    }
    QMenuBar {
         background-color: #e8e8e8;
         color: #333;
         border-bottom: 1px solid #dcdcdc;
    }
     QMenuBar::item:selected {
         background: #dcdcdc;
     }
     QMenu {
         background-color: #f8f8f8;
         border: 1px solid #c0c0c0;
         color: #333;
     }
     QMenu::item:selected {
         background-color: #a6d5fa;
         color: #111;
     }
     QMenu::separator {
        height: 1px;
        background-color: #dcdcdc;
        margin: 4px 0px;
    }
     QScrollBar:vertical {
        border: none;
        background-color: #f0f0f0;
        width: 12px;
        margin: 0px;
    }
    QScrollBar::handle:vertical {
        background-color: #c0c0c0;
        border-radius: 6px;
        min-height: 25px;
    }
    QScrollBar::handle:vertical:hover {
        background-color: #a8a8a8;
    }
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {
        height: 0px;
        border: none;
        background: none;
    }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        background: none;
    }
"""

# Modern dark stylesheet (Previously MODERN_STYLE)
DARK_STYLE = """
QMainWindow {
    background-color: #2b2b2b;
}

QWidget {
    font-family: sans-serif;
    font-size: 11pt;
    color: #cccccc;
    background-color: transparent;
    border: none;
}

/* General Labels */
QLabel {
    color: #cccccc;
    padding: 2px;
}

/* Section Header Labels (matched padding) */
QLabel[section="true"] {
    background-color: #3c3f41;
    color: #a9b7c6;
    border-radius: 4px;
    padding: 6px; /* Matched Light */
    margin-top: 8px;
    margin-bottom: 4px;
    font-weight: bold;
}

/* Buttons (matched padding, radius, no min-height) */
QPushButton {
    background-color: #3c3f41;
    border: 1px solid #555555;
    border-radius: 3px;  /* Matched Light */
    padding: 5px 10px; /* Matched Light */
    color: #cccccc;
    /* min-height: 20px; Removed */
}

QPushButton:hover {
    background-color: #4b5052;
}

QPushButton:pressed {
    background-color: #313335;
}

QPushButton:checked {
    background-color: #0d47a1; /* Blue when checked - Dark theme specific */
    border-color: #0d47a1;
    color: #ffffff;
}

QPushButton:disabled {
    background-color: #3a3a3a;
    border-color: #4a4a4a;
    color: #777777;
}

/* List Widget (no radius, no item padding) */
QListWidget {
    background-color: #313335;
    border: 1px solid #45494a;
    /* border-radius: 4px; Removed */
    color: #cccccc;
}

QListWidget::item {
    /* padding: 6px; Removed */
}

QListWidget::item:selected {
    background-color: #4a6d8c; /* Darker blue selection */
    color: #fff;
}

/* Spin Box & Double Spin Box (matched padding, radius, no min-height) */
QSpinBox, QDoubleSpinBox {
    background-color: #3c3f41;
    border: 1px solid #555555;
    border-radius: 3px;  /* Matched Light */
    padding: 3px;        /* Matched Light */
    color: #cccccc;
    /* min-height: 20px; Removed */
}

QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {
    /* No change */
}

/* Check Box (matched indicator size, radius) */
QCheckBox {
    spacing: 5px;
    color: #cccccc;
}

QCheckBox::indicator {
    width: 13px;  /* Matched Light */
    height: 13px; /* Matched Light */
}

QCheckBox::indicator:unchecked {
    border: 1px solid #555555;
    background-color: #3c3f41;
    border-radius: 2px; /* Matched Light */
}

QCheckBox::indicator:checked {
    border: 1px solid #0d47a1;
    background-color: #0d47a1; /* Dark theme check color */
    border-radius: 2px; /* Matched Light */
    image: url(icons/checkmark_dark.png); /* Needs a different checkmark icon */
}

QCheckBox::indicator:disabled {
    border: 1px solid #4a4a4a;
    background-color: #3a3a3a;
}

QCheckBox:disabled {
     color: #777777;
}

/* ComboBox (matched padding, radius, no min-height) */
QComboBox {
    background-color: #3c3f41;
    border: 1px solid #555555;
    border-radius: 3px;  /* Matched Light */
    padding: 3px;        /* Matched Light */
    color: #cccccc;
    /* min-height: 20px; Removed */
}
QComboBox:disabled {
    background-color: #3a3a3a;
    border-color: #4a4a4a;
    color: #777777;
}
QComboBox::drop-down {
    border: 1px solid #555555; /* Add border like light */
    background: #3c3f41;    /* Match background */
    width: 15px;
}
QComboBox QAbstractItemView {
    background-color: #3c3f41;
    border: 1px solid #555555;
    selection-background-color: #4a6d8c; /* Darker blue */
    color: #cccccc;
    outline: 0px;
}

/* Tab Widget (matched pane border, no radius/margin, matched tab padding) */
QTabWidget::pane {
    /* border: 1px solid #45494a; */
    border-top: 1px solid #45494a; /* Matched Light - only top */
    /* border-radius: 4px; Removed */
    background-color: #2b2b2b;
    /* margin-top: -1px; Removed */
}

QTabBar::tab {
    background-color: #3c3f41;
    border: 1px solid #45494a;
    border-bottom: none; /* Keep bottom none for overlap effect */
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 5px 10px; /* Matched Light */
    color: #a9b7c6;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #2b2b2b;
    color: #ffffff;
    border-color: #45494a;
    border-bottom: 1px solid #2b2b2b;
}

QTabBar::tab:hover:!selected {
    background-color: #4b5052;
}

/* Menu Bar */
QMenuBar {
    background-color: #2b2b2b;
    color: #cccccc;
    border-bottom: 1px solid #45494a;
}

QMenuBar::item {
    padding: 5px 10px;
    background-color: transparent;
}

QMenuBar::item:selected {
    background-color: #0d47a1;
    color: white;
}

/* Menu (no item padding) */
QMenu {
    background-color: #3c3f41;
    border: 1px solid #45494a;
    color: #cccccc;
    padding: 5px;
}

QMenu::item {
    /* padding: 6px 25px; Removed */
    padding: 2px 15px; /* Approximate light theme implicit padding */
}

QMenu::item:selected {
    background-color: #4a6d8c; /* Darker blue */
    color: #fff;
}

QMenu::separator {
    height: 1px;
    background-color: #45494a;
    margin: 4px 0px;
}

/* Status Bar (no border) */
QStatusBar {
    background-color: #2b2b2b;
    color: #a9b7c6;
    /* border-top: 1px solid #45494a; Removed */
}

/* Graphics View (no radius) */
QGraphicsView {
    background-color: #1e1e1e;
    border: 1px solid #45494a;
    /* border-radius: 4px; Removed */
}

/* Scroll Bars */
QScrollBar:vertical {
    border: none;
    background-color: #2b2b2b;
    width: 12px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background-color: #4b5052;
    border-radius: 6px;
    min-height: 25px;
}

QScrollBar::handle:vertical:hover {
    background-color: #5f6366;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0px;
    border: none;
    background: none;
}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}

/* Group Box (matched margin, no padding, transparent title bg) */
QGroupBox {
    border: 1px solid #45494a;
    border-radius: 4px;
    margin-top: 1ex; /* Matched Light */
    /* padding: 10px 5px 5px 5px; Removed */
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 3px; /* Matched Light */
    left: 10px;     /* Matched Light */
    background-color: transparent; /* Matched Light */
    color: #a9b7c6;
}

/* ToolBar (matched button padding) */
QToolBar {
    background-color: #313335;
    border-bottom: 1px solid #45494a;
    padding: 4px;
    spacing: 5px;
}

QToolBar QToolButton {
    padding: 5px; /* Matched Light */
    color: #cccccc;
    border: none; /* Matched Light */
    /* border-radius: 3px; Removed */
}

QToolBar QToolButton:hover {
    background-color: #4b5052;
}

QToolBar QToolButton:pressed {
    background-color: #313335;
}

QToolBar QToolButton:checked {
    background-color: #0d47a1;
}

QToolBar QToolButton:disabled {
    color: #777777;
    background-color: transparent;
}

/* Splitter (matched handle thickness) */
QSplitter::handle {
    background-color: #45494a;
}
QSplitter::handle:horizontal {
    width: 1px; /* Matched Light */
}
QSplitter::handle:vertical {
    height: 1px; /* Matched Light */
}

"""