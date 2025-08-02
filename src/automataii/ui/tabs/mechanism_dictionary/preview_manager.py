"""
Preview manager for the Mechanism Dictionary tab.
Handles mechanism rendering and animation display.
"""

import logging
from typing import Optional
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QRectF
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QFont, QPixmap
from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsItem, QWidget

from automataii.domain.fabrication.mechanisms import BaseMechanism
from automataii.domain.fabrication.mechanisms.physics_calculator import MechanismPhysicsCalculator
from .enhanced_renderer import EnhancedMechanismRenderer

logger = logging.getLogger(__name__)


class MechanismGraphicsItem(QGraphicsItem):
    """
    Graphics item for rendering a mechanism in the preview scene.
    """
    
    def __init__(self, mechanism: BaseMechanism):
        super().__init__()
        self.mechanism = mechanism
        self.scale_factor = 1.0
        
        # Enhanced renderer for better visualization
        self.enhanced_renderer = EnhancedMechanismRenderer()
        self.use_enhanced_rendering = True
        
        # Physics calculator for force/velocity analysis
        self.physics_calculator = MechanismPhysicsCalculator()
        
        # Connect to mechanism signals
        self.mechanism.position_changed.connect(self.update)
        self.mechanism.position_changed.connect(self._update_physics)
        
        # Set item properties
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
    
    def boundingRect(self) -> QRectF:
        """Return the bounding rectangle of the mechanism."""
        if self.mechanism:
            min_x, min_y, width, height = self.mechanism.get_bounding_rect()
            return QRectF(min_x, min_y, width, height)
        return QRectF(0, 0, 100, 100)
    
    def paint(self, painter: QPainter, option, widget: Optional[QWidget] = None):
        """Paint the mechanism."""
        if self.mechanism:
            # Always use the mechanism's own render method
            # This allows each mechanism to have custom rendering
            self.mechanism.render(painter, self.scale_factor)
    
    def set_scale_factor(self, scale: float):
        """Set the rendering scale factor."""
        self.scale_factor = scale
        self.update()
    
    def _update_physics(self):
        """Update physics calculations and pass to renderer."""
        if self.mechanism and self.use_enhanced_rendering:
            # Calculate physics properties
            forces = self.physics_calculator.calculate_forces(self.mechanism)
            velocities = self.physics_calculator.calculate_velocities(self.mechanism)
            stresses = self.physics_calculator.calculate_link_stresses(self.mechanism)
            
            # Update renderer with physics data
            self.enhanced_renderer.update_physics_data(forces, velocities, stresses)
    
    def update_visualization_settings(self, settings: dict):
        """Update visualization settings from UI."""
        if self.enhanced_renderer:
            self.enhanced_renderer.show_forces = settings.get('show_forces', True)
            self.enhanced_renderer.show_velocity = settings.get('show_velocity', True)
            self.enhanced_renderer.show_constraints = settings.get('show_constraints', True)
            self.enhanced_renderer.show_grid = settings.get('show_grid', True)
            self.enhanced_renderer.show_dimensions = settings.get('show_dimensions', True)
            self.enhanced_renderer.force_scale = settings.get('force_scale', 0.5)
            self.enhanced_renderer.velocity_scale = settings.get('velocity_scale', 1.0)
            self.update()


class MechanismPreviewManager(QObject):
    """
    Manages the mechanism preview display with animation support.
    """
    
    # Signals
    mechanism_loaded = pyqtSignal(str)  # mechanism_id
    animation_started = pyqtSignal()
    animation_stopped = pyqtSignal()
    scale_changed = pyqtSignal(float)
    
    def __init__(self, graphics_view: QGraphicsView, parent=None):
        super().__init__(parent)
        
        self.graphics_view = graphics_view
        self.scene = QGraphicsScene()
        self.graphics_view.setScene(self.scene)
        
        # Current state
        self.current_mechanism: Optional[BaseMechanism] = None
        self.mechanism_item: Optional[MechanismGraphicsItem] = None
        self.scale_factor = 1.0
        
        # Refresh timer for smooth animation
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self._refresh_display)
        self.refresh_timer.setInterval(16)  # ~60 FPS
        
        # Configure graphics view
        self._setup_graphics_view()
        
        # Add background
        self._setup_background()
    
    def _setup_graphics_view(self):
        """Configure the graphics view for optimal mechanism display."""
        # Set background color
        self.graphics_view.setStyleSheet("background-color: #f8f9fa;")
        
        # Disable scrollbars (we'll handle scaling manually)
        from PyQt6.QtCore import Qt
        self.graphics_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.graphics_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Enable smooth rendering
        from PyQt6.QtCore import Qt
        self.graphics_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.graphics_view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        # Set view update mode
        self.graphics_view.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
    
    def _setup_background(self):
        """Setup background grid and labels."""
        # Add subtle grid
        self._add_background_grid()
        
        # Add coordinate system indicator
        self._add_coordinate_indicator()
    
    def _add_background_grid(self):
        """Add a subtle background grid."""
        grid_size = 20
        grid_color = QColor(220, 220, 220, 100)
        grid_pen = QPen(grid_color, 0.5)
        
        # Add grid lines
        scene_rect = QRectF(-200, -150, 400, 300)
        
        # Vertical lines
        for x in range(int(scene_rect.left()), int(scene_rect.right() + 1), grid_size):
            self.scene.addLine(x, scene_rect.top(), x, scene_rect.bottom(), grid_pen)
        
        # Horizontal lines
        for y in range(int(scene_rect.top()), int(scene_rect.bottom() + 1), grid_size):
            self.scene.addLine(scene_rect.left(), y, scene_rect.right(), y, grid_pen)
        
        self.scene.setSceneRect(scene_rect)
    
    def _add_coordinate_indicator(self):
        """Add coordinate system indicator."""
        # Add origin marker
        origin_brush = QBrush(QColor(100, 100, 100))
        self.scene.addEllipse(-2, -2, 4, 4, QPen(), origin_brush)
        
        # Add axis labels
        font = QFont("Arial", 8)
        text_color = QColor(120, 120, 120)
        
        x_label = self.scene.addText("X", font)
        x_label.setDefaultTextColor(text_color)
        x_label.setPos(15, -10)
        
        y_label = self.scene.addText("Y", font)
        y_label.setDefaultTextColor(text_color)
        y_label.setPos(-10, -20)
    
    def load_mechanism(self, mechanism: BaseMechanism):
        """Load a mechanism for preview."""
        # Clear previous mechanism
        self.clear_mechanism()
        
        # Set new mechanism
        self.current_mechanism = mechanism
        
        if mechanism:
            # Create graphics item
            self.mechanism_item = MechanismGraphicsItem(mechanism)
            self.mechanism_item.set_scale_factor(self.scale_factor)
            self.scene.addItem(self.mechanism_item)
            
            # Center the view on the mechanism
            self._center_on_mechanism()
            
            # Start refresh timer if mechanism is animating
            if mechanism.is_animating:
                self.refresh_timer.start()
            
            self.mechanism_loaded.emit(mechanism.mechanism_id)
            logger.debug(f"Loaded mechanism: {mechanism.mechanism_id}")
    
    def clear_mechanism(self):
        """Clear the current mechanism from preview."""
        if self.mechanism_item:
            self.scene.removeItem(self.mechanism_item)
            self.mechanism_item = None
        
        if self.current_mechanism:
            # Disconnect signals
            self.current_mechanism.position_changed.disconnect()
            self.current_mechanism = None
        
        # Stop refresh timer
        self.refresh_timer.stop()
    
    def _center_on_mechanism(self):
        """Center the view on the current mechanism."""
        if self.mechanism_item:
            # Get mechanism bounds
            bounds = self.mechanism_item.boundingRect()
            
            # Center the view
            self.graphics_view.centerOn(bounds.center())
            
            # Fit in view with some padding
            padding = 50
            padded_rect = bounds.adjusted(-padding, -padding, padding, padding)
            from PyQt6.QtCore import Qt
            self.graphics_view.fitInView(padded_rect, Qt.AspectRatioMode.KeepAspectRatio)
    
    def start_animation(self):
        """Start mechanism animation."""
        if self.current_mechanism:
            self.current_mechanism.start_animation()
            self.refresh_timer.start()
            self.animation_started.emit()
            logger.debug("Preview animation started")
    
    def stop_animation(self):
        """Stop mechanism animation."""
        if self.current_mechanism:
            self.current_mechanism.stop_animation()
            self.refresh_timer.stop()
            self.animation_stopped.emit()
            logger.debug("Preview animation stopped")
    
    def reset_animation(self):
        """Reset animation to beginning."""
        if self.current_mechanism:
            self.current_mechanism.reset_animation()
            self._refresh_display()
    
    def set_animation_speed(self, speed: float):
        """Set animation speed."""
        if self.current_mechanism:
            self.current_mechanism.set_animation_speed(speed)
    
    def set_scale_factor(self, scale: float):
        """Set the preview scale factor."""
        self.scale_factor = max(0.1, min(3.0, scale))
        
        if self.mechanism_item:
            self.mechanism_item.set_scale_factor(self.scale_factor)
        
        self.scale_changed.emit(self.scale_factor)
    
    def get_scale_factor(self) -> float:
        """Get the current scale factor."""
        return self.scale_factor
    
    def zoom_in(self):
        """Zoom in on the preview."""
        new_scale = min(3.0, self.scale_factor * 1.2)
        self.set_scale_factor(new_scale)
    
    def zoom_out(self):
        """Zoom out of the preview."""
        new_scale = max(0.1, self.scale_factor / 1.2)
        self.set_scale_factor(new_scale)
    
    def zoom_to_fit(self):
        """Zoom to fit the mechanism in the view."""
        if self.mechanism_item:
            self._center_on_mechanism()
    
    def _refresh_display(self):
        """Refresh the display for animation."""
        if self.mechanism_item:
            self.mechanism_item.update()
    
    def take_snapshot(self) -> QPixmap:
        """Take a snapshot of the current preview."""
        from PyQt6.QtCore import QSize
        
        # Get the scene rectangle
        rect = self.scene.itemsBoundingRect()
        if rect.isEmpty():
            rect = QRectF(0, 0, 200, 200)
        
        # Create pixmap
        pixmap = QPixmap(QSize(int(rect.width()), int(rect.height())))
        pixmap.fill(QColor(248, 249, 250))  # Match background
        
        # Render scene to pixmap
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.scene.render(painter, pixmap.rect(), rect)
        painter.end()
        
        return pixmap
    
    def export_animation_frames(self, duration_seconds: float = 2.0, fps: int = 30):
        """Export animation frames (placeholder for future implementation)."""
        # This would be implemented to export animation frames for GIF creation
        logger.info("Animation export not yet implemented")
        pass