"""
GUI components for automata base module.

This package provides PyQt5/PyQt6 compatible widgets for
interactive base design and configuration.
"""

# Check which Qt binding is available
try:
    from PyQt6 import QtCore, QtWidgets, QtGui
    QT_VERSION = 6
    print("Using PyQt6")
except ImportError:
    try:
        from PyQt5 import QtCore, QtWidgets, QtGui
        QT_VERSION = 5
        print("Using PyQt5")
    except ImportError:
        QT_VERSION = None
        print("WARNING: Neither PyQt5 nor PyQt6 is installed")

# Only import GUI components if Qt is available
if QT_VERSION is not None:
    from automataii.modules.automata_base.gui.base_selection_widget import BaseSelectionWidget
    from automataii.modules.automata_base.gui.base_preview_widget import BasePreviewWidget
    from automataii.modules.automata_base.gui.material_selection_widget import MaterialSelectionWidget
    from automataii.modules.automata_base.gui.dimension_input_widget import DimensionInputWidget
    from automataii.modules.automata_base.gui.base_designer_dialog import BaseDesignerDialog
    
    __all__ = [
        "BaseSelectionWidget",
        "BasePreviewWidget", 
        "MaterialSelectionWidget",
        "DimensionInputWidget",
        "BaseDesignerDialog",
        "QT_VERSION"
    ]
else:
    __all__ = ["QT_VERSION"]