# src/automataii/ui/views/image_processing/state_manager.py

import logging
from enum import Enum

from PyQt6.QtCore import QObject, QPointF, pyqtSignal
from PyQt6.QtGui import QPixmap

logger = logging.getLogger(__name__)


class ImageProcessingMode(Enum):
    """Available interaction modes for the image processing view."""

    PAN_ZOOM = "pan_zoom"
    JOINT_DRAG = "joint_drag"
    HOVER = "hover"
    DEBUG = "debug"


class ImageProcessingViewState(QObject):
    """
    Manages state for the ImageProcessingView.
    Handles display settings, interaction modes, and data state.
    """

    # Signals for state changes
    mode_changed = pyqtSignal(ImageProcessingMode)
    zoom_changed = pyqtSignal(float)
    display_unit_changed = pyqtSignal(str)
    debug_mode_changed = pyqtSignal(bool)
    image_loaded = pyqtSignal(str)  # image path
    skeleton_loaded = pyqtSignal(dict)  # skeleton data
    state_changed = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        # Current interaction mode
        self.current_mode: ImageProcessingMode = ImageProcessingMode.PAN_ZOOM

        # Display settings
        self.zoom_level: float = 1.0
        self.display_unit: str = "cm"
        self.dpi: float = 96.0

        # Debug settings
        self.debug_mode: bool = False

        # Image state
        self.current_image_path: str | None = None
        self.current_image_pixmap: QPixmap | None = None

        # Skeleton state
        self.original_skeleton_data: dict | None = None
        self.skeleton_loaded: bool = False

        # Bounding box state
        self.bounding_box: dict | None = None
        self.bb_center: tuple[float, float] | None = None

        # Joint dragging state
        self.dragged_joint_item = None
        self.drag_start_pos: QPointF | None = None
        self.drag_start_pos_offset: QPointF | None = None

        # Character parts state
        self.part_items: dict[str, object] = {}  # CharacterPartItem objects
        self.joint_to_part_map: dict[str, object] = {}
        self.skeleton_to_part_map: dict[str, str] = {}

        # Hover state
        self.hover_controls_visible: bool = False
        self.last_hover_position: QPointF | None = None

        # Guide lines state
        self.current_guide_lines: list = []
        self.last_active_joint_for_guide = None

    def set_mode(self, mode: ImageProcessingMode) -> None:
        """Set the current interaction mode."""
        if self.current_mode != mode:
            old_mode = self.current_mode
            self.current_mode = mode
            self.mode_changed.emit(mode)
            self.state_changed.emit()
            logger.info(f"ImageProcessing mode changed from {old_mode.value} to {mode.value}")

            # Reset mode-specific state when changing modes
            self._reset_mode_state(old_mode)

    def _reset_mode_state(self, old_mode: ImageProcessingMode) -> None:
        """Reset state when exiting a mode."""
        if old_mode == ImageProcessingMode.JOINT_DRAG:
            self.dragged_joint_item = None
            self.drag_start_pos = None
            self.drag_start_pos_offset = None
        elif old_mode == ImageProcessingMode.HOVER:
            self.hover_controls_visible = False
            self.last_hover_position = None

    def set_zoom_level(self, zoom: float) -> None:
        """Set the current zoom level."""
        if self.zoom_level != zoom:
            self.zoom_level = zoom
            self.zoom_changed.emit(zoom)
            self.state_changed.emit()

    def set_display_unit(self, unit: str) -> None:
        """Set the display unit."""
        if unit.lower() in ["cm", "inch", "px"] and self.display_unit != unit.lower():
            self.display_unit = unit.lower()
            self.display_unit_changed.emit(unit.lower())
            self.state_changed.emit()

    def set_debug_mode(self, enabled: bool) -> None:
        """Set debug mode state."""
        if self.debug_mode != enabled:
            self.debug_mode = enabled
            self.debug_mode_changed.emit(enabled)
            self.state_changed.emit()

    def set_image_data(self, image_path: str, pixmap: QPixmap) -> None:
        """Set the current image data."""
        self.current_image_path = image_path
        self.current_image_pixmap = pixmap
        self.image_loaded.emit(image_path)
        self.state_changed.emit()

    def set_skeleton_data(self, skeleton_data: dict | None) -> None:
        """Set the current skeleton data."""
        self.original_skeleton_data = skeleton_data
        self.skeleton_loaded = skeleton_data is not None
        if skeleton_data:
            self.skeleton_loaded.emit(skeleton_data)
        self.state_changed.emit()

    def set_bounding_box(self, bounding_box: dict | None) -> None:
        """Set the bounding box data."""
        self.bounding_box = bounding_box
        if bounding_box:
            self.bb_center = (
                (bounding_box["left"] + bounding_box["right"]) / 2,
                (bounding_box["top"] + bounding_box["bottom"]) / 2,
            )
        else:
            self.bb_center = None
        self.state_changed.emit()

    def start_joint_drag(self, joint_item, start_pos: QPointF, offset: QPointF) -> None:
        """Start joint dragging mode."""
        self.dragged_joint_item = joint_item
        self.drag_start_pos = start_pos
        self.drag_start_pos_offset = offset
        self.set_mode(ImageProcessingMode.JOINT_DRAG)

    def stop_joint_drag(self) -> None:
        """Stop joint dragging and return to pan/zoom mode."""
        self.dragged_joint_item = None
        self.drag_start_pos = None
        self.drag_start_pos_offset = None
        self.set_mode(ImageProcessingMode.PAN_ZOOM)

    def get_current_mode(self) -> ImageProcessingMode:
        """Get the current interaction mode."""
        return self.current_mode

    def is_in_mode(self, mode: ImageProcessingMode) -> bool:
        """Check if currently in the specified mode."""
        return self.current_mode == mode

    def clear_all_state(self) -> None:
        """Clear all state data."""
        self.current_image_path = None
        self.current_image_pixmap = None
        self.original_skeleton_data = None
        self.skeleton_loaded = False
        self.bounding_box = None
        self.bb_center = None
        self.dragged_joint_item = None
        self.drag_start_pos = None
        self.drag_start_pos_offset = None
        self.part_items.clear()
        self.joint_to_part_map.clear()
        self.skeleton_to_part_map.clear()
        self.current_guide_lines.clear()
        self.last_active_joint_for_guide = None
        logger.info("All ImageProcessing state cleared")

    def refresh_display(self) -> None:
        """Refresh the display when tab is activated."""
        # Force a state change event to trigger UI updates
        self.state_changed.emit()
        
        # Update zoom and display settings
        if hasattr(self, 'zoom_level'):
            self.zoom_changed.emit(self.zoom_level)
        
        # Update display unit
        if hasattr(self, 'display_unit'):
            self.display_unit_changed.emit(self.display_unit)
        
        # Update debug mode
        if hasattr(self, 'debug_mode'):
            self.debug_mode_changed.emit(self.debug_mode)
        
        logger.debug("ImageProcessingViewState display refreshed")
