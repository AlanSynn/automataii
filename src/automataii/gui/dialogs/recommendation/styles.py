"""Stylesheet definitions for recommendation dialog components."""


class StyleSheets:
    """Centralized stylesheets for recommendation dialog."""
    
    INSTRUCTION_LABEL = """
        QLabel {
            font-size: 18px;
            font-weight: bold;
            color: #333333;
            padding: 10px;
        }
    """
    
    SUBTITLE_LABEL = """
        QLabel {
            font-size: 14px;
            color: #666666;
            padding-bottom: 20px;
        }
    """
    
    TITLE_LABEL = """
        QLabel {
            font-size: 18px;
            font-weight: bold;
            color: #2c3e50;
            padding: 5px;
        }
    """
    
    MATCH_LABEL = """
        QLabel {
            font-size: 20px;
            font-weight: bold;
            color: #27ae60;
            padding: 10px;
        }
    """
    
    PREVIEW_WIDGET_NORMAL = """
        QGraphicsView {
            border: 3px solid transparent;
            border-radius: 8px;
            background-color: #ffffff;
        }
    """
    
    PREVIEW_WIDGET_SELECTED = """
        QGraphicsView {
            border: 3px solid #3498db;
            border-radius: 8px;
            background-color: #ffffff;
            box-shadow: 0 0 10px rgba(52, 152, 219, 0.5);
        }
    """
    
    CONTAINER_SELECTED = """
        PreviewContainer {
            background-color: #f0f8ff;
            border-radius: 10px;
        }
    """
    
    SELECT_BUTTON = """
        QPushButton {
            background-color: #3498db;
            color: white;
            border: none;
            border-radius: 4px;
            font-size: 14px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #2980b9;
        }
        QPushButton:pressed {
            background-color: #21618c;
        }
    """
    
    OK_BUTTON = """
        QPushButton {
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 4px;
            font-size: 12px;
        }
        QPushButton:hover {
            background-color: #45a049;
        }
        QPushButton:pressed {
            background-color: #3d8b40;
        }
        QPushButton:disabled {
            background-color: #cccccc;
            color: #666666;
        }
    """
    
    CANCEL_BUTTON = """
        QPushButton {
            background-color: #f44336;
            color: white;
            border: none;
            border-radius: 4px;
            font-size: 12px;
        }
        QPushButton:hover {
            background-color: #da190b;
        }
        QPushButton:pressed {
            background-color: #ba1a0d;
        }
    """
    
    PLACEHOLDER_LABEL = "background-color: #f0f0f0;"