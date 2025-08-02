"""
Qt-compatible styling utilities for the Enhanced Mechanism Dictionary Tab.
Replaces CSS properties not supported by Qt with Qt-native alternatives.
"""

from PyQt6.QtWidgets import QGraphicsDropShadowEffect
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt


class ModernStyling:
    """Modern styling system with Qt-compatible CSS and effects."""
    
    # Color Palette - Material Design 3.0 inspired
    COLORS = {
        # Primary colors
        'primary': '#1976D2',
        'primary_light': '#42A5F5', 
        'primary_dark': '#0D47A1',
        'primary_container': '#E3F2FD',
        
        # Secondary colors
        'secondary': '#FFC107',
        'secondary_light': '#FFEB3B',
        'secondary_dark': '#FF8F00',
        'secondary_container': '#FFF8E1',
        
        # Surface colors
        'surface': '#FFFFFF',
        'surface_variant': '#F5F5F5',
        'surface_container': '#FAFAFA',
        'surface_container_high': '#F0F0F0',
        'background': '#FAFAFA',
        
        # Content colors
        'on_surface': '#212121',
        'on_surface_variant': '#757575',
        'on_background': '#424242',
        'on_primary': '#FFFFFF',
        'on_primary_container': '#1976D2',
        
        # Outline colors
        'outline': '#E0E0E0',
        'outline_variant': '#EEEEEE',
        
        # State colors
        'success': '#4CAF50',
        'warning': '#FF9800', 
        'error': '#F44336',
        'info': '#2196F3'
    }
    
    # Spacing system
    SPACING = {
        'xs': 4,
        'sm': 8,
        'md': 16,
        'lg': 24,
        'xl': 32,
        'xxl': 48
    }
    
    # Typography
    TYPOGRAPHY = {
        'font_family': 'system-ui, -apple-system, sans-serif',
        'font_size_h1': 24,
        'font_size_h2': 20,
        'font_size_h3': 16,
        'font_size_body': 14,
        'font_size_caption': 12,
        'font_size_small': 11
    }
    
    @classmethod
    def get_card_style(cls, hover_enabled: bool = True) -> str:
        """Get Qt-compatible card styling."""
        base_style = f"""
        QFrame {{
            background-color: {cls.COLORS['surface']};
            border: 1px solid {cls.COLORS['outline']};
            border-radius: 8px;
            padding: {cls.SPACING['md']}px;
        }}
        """
        
        if hover_enabled:
            base_style += f"""
            QFrame:hover {{
                border-color: {cls.COLORS['primary_light']};
                background-color: {cls.COLORS['primary_container']};
            }}
            """
        
        return base_style
    
    @classmethod
    def get_button_style(cls, variant: str = 'primary') -> str:
        """Get Qt-compatible button styling."""
        if variant == 'primary':
            return f"""
            QPushButton {{
                background-color: {cls.COLORS['primary']};
                color: {cls.COLORS['on_primary']};
                border: none;
                border-radius: 6px;
                padding: {cls.SPACING['sm']}px {cls.SPACING['md']}px;
                font-weight: 600;
                font-size: {cls.TYPOGRAPHY['font_size_body']}px;
                min-height: 32px;
            }}
            QPushButton:hover {{
                background-color: {cls.COLORS['primary_light']};
            }}
            QPushButton:pressed {{
                background-color: {cls.COLORS['primary_dark']};
            }}
            QPushButton:disabled {{
                background-color: {cls.COLORS['on_surface_variant']};
                color: {cls.COLORS['surface']};
            }}
            """
        
        elif variant == 'secondary':
            return f"""
            QPushButton {{
                background-color: transparent;
                color: {cls.COLORS['primary']};
                border: 2px solid {cls.COLORS['primary']};
                border-radius: 6px;
                padding: {cls.SPACING['sm']}px {cls.SPACING['md']}px;
                font-weight: 600;
                font-size: {cls.TYPOGRAPHY['font_size_body']}px;
                min-height: 32px;
            }}
            QPushButton:hover {{
                background-color: {cls.COLORS['primary_container']};
                border-color: {cls.COLORS['primary_light']};
            }}
            QPushButton:pressed {{
                background-color: {cls.COLORS['primary']};
                color: {cls.COLORS['on_primary']};
            }}
            """
        
        elif variant == 'text':
            return f"""
            QPushButton {{
                background-color: transparent;
                color: {cls.COLORS['primary']};
                border: none;
                border-radius: 6px;
                padding: {cls.SPACING['sm']}px {cls.SPACING['md']}px;
                font-weight: 500;
                font-size: {cls.TYPOGRAPHY['font_size_body']}px;
            }}
            QPushButton:hover {{
                background-color: {cls.COLORS['primary_container']};
            }}
            QPushButton:pressed {{
                background-color: {cls.COLORS['primary_light']};
                color: {cls.COLORS['on_primary']};
            }}
            """
        
        return ""
    
    @classmethod
    def get_input_style(cls) -> str:
        """Get Qt-compatible input field styling."""
        return f"""
        QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
            border: 2px solid {cls.COLORS['outline']};
            border-radius: 6px;
            padding: {cls.SPACING['sm']}px {cls.SPACING['sm']}px;
            background-color: {cls.COLORS['surface']};
            color: {cls.COLORS['on_surface']};
            font-size: {cls.TYPOGRAPHY['font_size_body']}px;
            selection-background-color: {cls.COLORS['primary_container']};
        }}
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
            border-color: {cls.COLORS['primary']};
            background-color: {cls.COLORS['surface']};
        }}
        QLineEdit:hover, QTextEdit:hover, QComboBox:hover {{
            border-color: {cls.COLORS['primary_light']};
        }}
        """
    
    @classmethod
    def get_tab_style(cls) -> str:
        """Get Qt-compatible tab widget styling."""
        return f"""
        QTabWidget::pane {{
            border: 1px solid {cls.COLORS['outline']};
            background-color: {cls.COLORS['surface']};
            border-radius: 6px;
        }}
        QTabBar::tab {{
            background-color: {cls.COLORS['surface_variant']};
            border: 1px solid {cls.COLORS['outline']};
            border-bottom: none;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
            padding: {cls.SPACING['sm']}px {cls.SPACING['md']}px;
            margin-right: 2px;
            font-weight: 500;
            font-size: {cls.TYPOGRAPHY['font_size_body']}px;
            min-width: 80px;
        }}
        QTabBar::tab:selected {{
            background-color: {cls.COLORS['surface']};
            color: {cls.COLORS['primary']};
            border-bottom: 3px solid {cls.COLORS['primary']};
            font-weight: 600;
        }}
        QTabBar::tab:hover:!selected {{
            background-color: {cls.COLORS['primary_container']};
            color: {cls.COLORS['primary']};
        }}
        """
    
    @classmethod
    def get_scroll_area_style(cls) -> str:
        """Get Qt-compatible scroll area styling."""
        return f"""
        QScrollArea {{
            border: 1px solid {cls.COLORS['outline']};
            border-radius: 6px;
            background-color: {cls.COLORS['surface']};
        }}
        QScrollBar:vertical {{
            background-color: {cls.COLORS['surface_variant']};
            width: 12px;
            border-radius: 6px;
            margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background-color: {cls.COLORS['outline']};
            border-radius: 6px;
            min-height: 20px;
            margin: 2px;
        }}
        QScrollBar::handle:vertical:hover {{
            background-color: {cls.COLORS['on_surface_variant']};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        """
    
    @classmethod
    def get_tree_style(cls) -> str:
        """Get Qt-compatible tree widget styling."""
        return f"""
        QTreeWidget, QTreeView {{
            border: 1px solid {cls.COLORS['outline']};
            border-radius: 6px;
            background-color: {cls.COLORS['surface']};
            alternate-background-color: {cls.COLORS['surface_variant']};
            color: {cls.COLORS['on_surface']};
            font-size: {cls.TYPOGRAPHY['font_size_body']}px;
        }}
        QTreeWidget::item, QTreeView::item {{
            padding: {cls.SPACING['sm']}px;
            border: none;
            border-bottom: 1px solid {cls.COLORS['outline_variant']};
        }}
        QTreeWidget::item:selected, QTreeView::item:selected {{
            background-color: {cls.COLORS['primary_container']};
            color: {cls.COLORS['primary']};
        }}
        QTreeWidget::item:hover, QTreeView::item:hover {{
            background-color: {cls.COLORS['surface_container']};
        }}
        QTreeWidget::branch, QTreeView::branch {{
            background-color: transparent;
        }}
        """
    
    @classmethod
    def create_card_shadow(cls, widget) -> QGraphicsDropShadowEffect:
        """Create Qt-native drop shadow effect for cards."""
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(12)
        shadow.setColor(QColor(0, 0, 0, 25))  # 25% opacity black
        shadow.setOffset(0, 2)
        return shadow
    
    @classmethod
    def create_elevated_shadow(cls, widget) -> QGraphicsDropShadowEffect:
        """Create Qt-native elevated shadow effect."""
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 40))  # 40% opacity black  
        shadow.setOffset(0, 4)
        return shadow
    
    @classmethod
    def get_complexity_badge_style(cls, complexity: str) -> str:
        """Get styling for complexity badges."""
        color_map = {
            'beginner': cls.COLORS['success'],
            'intermediate': cls.COLORS['warning'], 
            'advanced': cls.COLORS['error']
        }
        
        bg_color = color_map.get(complexity, cls.COLORS['on_surface_variant'])
        
        return f"""
        QLabel {{
            background-color: {bg_color};
            color: {cls.COLORS['on_primary']};
            border-radius: 12px;
            padding: 4px 12px;
            font-weight: bold;
            font-size: {cls.TYPOGRAPHY['font_size_small']}px;
            border: none;
        }}
        """
    
    @classmethod
    def get_slider_style(cls) -> str:
        """Get Qt-compatible slider styling.""" 
        return f"""
        QSlider::groove:horizontal {{
            border: 1px solid {cls.COLORS['outline']};
            height: 6px;
            background-color: {cls.COLORS['surface_variant']};
            border-radius: 3px;
        }}
        QSlider::handle:horizontal {{
            background-color: {cls.COLORS['primary']};
            border: 2px solid {cls.COLORS['primary_dark']};
            width: 20px;
            height: 20px;
            border-radius: 12px;
            margin: -8px 0;
        }}
        QSlider::handle:horizontal:hover {{
            background-color: {cls.COLORS['primary_light']};
        }}
        QSlider::handle:horizontal:pressed {{
            background-color: {cls.COLORS['primary_dark']};
        }}
        QSlider::sub-page:horizontal {{
            background-color: {cls.COLORS['primary']};
            border-radius: 3px;
        }}
        """