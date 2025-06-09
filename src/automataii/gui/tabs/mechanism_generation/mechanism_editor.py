"""Comprehensive mechanism editing system with interactive manipulation."""

import logging
import math
from typing import Optional, Dict, List, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum, auto

from PyQt6.QtCore import (
    Qt, QPointF, QRectF, QLineF, pyqtSignal, QObject,
    QPropertyAnimation, QEasingCurve, pyqtProperty
)
from PyQt6.QtWidgets import (
    QGraphicsItem, QGraphicsLineItem, QGraphicsEllipseItem,
    QGraphicsPathItem, QGraphicsSceneMouseEvent, QGraphicsScene,
    QGraphicsProxyWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QDoubleSpinBox, QPushButton, QCheckBox, QSlider,
    QGroupBox, QSpinBox, QComboBox, QApplication
)
from PyQt6.QtGui import (
    QPen, QBrush, QColor, QPainterPath, QTransform,
    QPainter, QFont, QPolygonF
)

from automataii.generators.base_generator import MechanismType

class EditMode(Enum):
    """Edit modes for mechanism manipulation."""
    VIEW = auto()
    EDIT_ANCHORS = auto()
    EDIT_LINKS = auto()
    EDIT_CONSTRAINTS = auto()


class ConstraintType(Enum):
    """Types of mechanism constraints."""
    FIXED_PIVOT = auto()
    LINK_LENGTH = auto()
    ANGLE_LIMIT = auto()
    PARALLEL = auto()
    PERPENDICULAR = auto()


@dataclass
class MechanismConstraint:
    """Represents a constraint on mechanism elements."""
    type: ConstraintType
    elements: List[str]  # IDs of constrained elements
    value: Optional[float] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    active: bool = True


@dataclass
class MechanismEditState:
    """Stores the editing state of a mechanism."""
    selected_elements: Set[str] = field(default_factory=set)
    hover_element: Optional[str] = None
    is_dragging: bool = False
    drag_start_pos: Optional[QPointF] = None
    original_positions: Dict[str, QPointF] = field(default_factory=dict)
    constraints: List[MechanismConstraint] = field(default_factory=list)
    snap_to_grid: bool = True
    grid_size: float = 10.0
    show_constraints: bool = True
    show_dimensions: bool = True


class MechanismEditorSignals(QObject):
    """Signals for mechanism editor."""
    mechanism_updated = pyqtSignal(dict)  # Updated mechanism data
    constraint_violated = pyqtSignal(str)  # Constraint violation message
    edit_completed = pyqtSignal()
    undo_requested = pyqtSignal()
    redo_requested = pyqtSignal()


class InteractiveAnchor(QGraphicsEllipseItem):
    """Enhanced interactive anchor with visual feedback and constraints."""

    def __init__(self, anchor_id: str, center: QPointF, radius: float = 10.0,
                 constraint_type: Optional[ConstraintType] = None):
        super().__init__(
            center.x() - radius, center.y() - radius,
            radius * 2, radius * 2
        )

        self.anchor_id = anchor_id
        self.radius = radius
        self.constraint_type = constraint_type
        self.is_hovered = False
        self.is_selected = False
        self.is_dragging = False

        # Visual properties
        self.default_color = QColor(100, 150, 255)
        self.hover_color = QColor(150, 200, 255)
        self.selected_color = QColor(255, 150, 100)
        self.constrained_color = QColor(255, 100, 100)
        self.drag_color = QColor(255, 200, 100)

        # Constraint visualization
        self.constraint_indicator = None
        if constraint_type == ConstraintType.FIXED_PIVOT:
            self._create_fixed_constraint_indicator()

        self._setup_appearance()
        self._setup_interactivity()

        # Animation support
        self._animation = QPropertyAnimation(self, b"opacity")
        self._animation.setDuration(200)

    def _setup_appearance(self):
        """Set up visual appearance."""
        pen = QPen(Qt.GlobalColor.black, 2)
        pen.setCosmetic(True)  # Keep constant width regardless of zoom
        self.setPen(pen)
        self.setBrush(QBrush(self.default_color))
        self.setZValue(1000)  # High z-value for visibility

    def _setup_interactivity(self):
        """Set up interactive properties."""
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def _create_fixed_constraint_indicator(self):
        """Create visual indicator for fixed constraint."""
        # Create a small lock icon or cross pattern
        path = QPainterPath()
        size = self.radius * 0.6
        path.moveTo(-size, -size)
        path.lineTo(size, size)
        path.moveTo(-size, size)
        path.lineTo(size, -size)

        self.constraint_indicator = QGraphicsPathItem(path, self)
        self.constraint_indicator.setPen(QPen(QColor(200, 50, 50), 2))
        self.constraint_indicator.setPos(self.radius, self.radius)

    def center_pos(self) -> QPointF:
        """Get center position in parent coordinates."""
        rect = self.rect()
        return self.mapToParent(rect.center())

    def set_center_pos(self, pos: QPointF):
        """Set center position."""
        self.setPos(pos - QPointF(self.radius, self.radius))

    def update_appearance(self):
        """Update visual appearance based on state."""
        if self.is_dragging:
            color = self.drag_color
        elif self.is_selected:
            color = self.selected_color
        elif self.is_hovered:
            color = self.hover_color
        elif self.constraint_type == ConstraintType.FIXED_PIVOT:
            color = self.constrained_color
        else:
            color = self.default_color

        self.setBrush(QBrush(color))

        # Update cursor
        if self.constraint_type == ConstraintType.FIXED_PIVOT:
            self.setCursor(Qt.CursorShape.ForbiddenCursor)
        elif self.is_dragging:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        elif self.is_hovered:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def hoverEnterEvent(self, event):
        """Handle hover enter."""
        self.is_hovered = True
        self.update_appearance()

        # Animate scale up slightly
        self.setScale(1.2)

        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        """Handle hover leave."""
        self.is_hovered = False
        self.update_appearance()

        # Animate scale back to normal
        self.setScale(1.0)

        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        """Handle mouse press."""
        if event.button() == Qt.MouseButton.LeftButton:
            if self.constraint_type != ConstraintType.FIXED_PIVOT:
                self.is_dragging = True
                self.update_appearance()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        """Handle mouse release."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = False
            self.update_appearance()
        super().mouseReleaseEvent(event)

    def itemChange(self, change, value):
        """Handle item changes."""
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedChange:
            self.is_selected = value
            self.update_appearance()
        return super().itemChange(change, value)


class InteractiveLink(QGraphicsLineItem):
    """Interactive link with length editing capabilities."""

    def __init__(self, link_id: str, start_anchor: InteractiveAnchor,
                 end_anchor: InteractiveAnchor):
        super().__init__()

        self.link_id = link_id
        self.start_anchor = start_anchor
        self.end_anchor = end_anchor
        self.is_hovered = False
        self.is_selected = False

        # Visual properties
        self.default_color = QColor(80, 80, 80)
        self.hover_color = QColor(120, 120, 255)
        self.selected_color = QColor(255, 120, 80)

        # Length constraint
        self.fixed_length = None
        self.min_length = 10.0
        self.max_length = None

        # Visual elements
        self.length_label = None
        self._create_length_label()

        self._setup_appearance()
        self._setup_interactivity()
        self.update_position()

    def _setup_appearance(self):
        """Set up visual appearance."""
        pen = QPen(self.default_color, 4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setCosmetic(False)
        self.setPen(pen)
        self.setZValue(500)  # Below anchors

    def _setup_interactivity(self):
        """Set up interactive properties."""
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _create_length_label(self):
        """Create label to show link length."""
        from PyQt6.QtWidgets import QGraphicsTextItem

        self.length_label = QGraphicsTextItem(self)
        self.length_label.setDefaultTextColor(QColor(60, 60, 60))
        font = QFont("Arial", 10)
        self.length_label.setFont(font)
        self.length_label.setZValue(self.zValue() + 1)

    def update_position(self):
        """Update link position based on anchor positions."""
        start_pos = self.start_anchor.center_pos()
        end_pos = self.end_anchor.center_pos()

        # Map to scene coordinates
        start_scene = self.start_anchor.mapToScene(start_pos)
        end_scene = self.end_anchor.mapToScene(end_pos)

        # Convert to item coordinates
        start_item = self.mapFromScene(start_scene)
        end_item = self.mapFromScene(end_scene)

        self.setLine(start_item.x(), start_item.y(), end_item.x(), end_item.y())

        # Update length label
        if self.length_label:
            length = self.get_length()
            self.length_label.setPlainText(f"{length:.1f}")

            # Position at midpoint
            mid_x = (start_item.x() + end_item.x()) / 2
            mid_y = (start_item.y() + end_item.y()) / 2
            self.length_label.setPos(mid_x - 20, mid_y - 20)

    def get_length(self) -> float:
        """Get current link length."""
        line = self.line()
        return math.sqrt(line.dx() ** 2 + line.dy() ** 2)

    def set_fixed_length(self, length: float):
        """Set fixed length constraint."""
        self.fixed_length = length
        self.enforce_length_constraint()

    def enforce_length_constraint(self):
        """Enforce length constraint on the link."""
        if self.fixed_length is None:
            return

        # Get current positions
        start_pos = self.start_anchor.center_pos()
        end_pos = self.end_anchor.center_pos()

        # Calculate current length and direction
        dx = end_pos.x() - start_pos.x()
        dy = end_pos.y() - start_pos.y()
        current_length = math.sqrt(dx ** 2 + dy ** 2)

        if current_length < 0.001:  # Avoid division by zero
            return

        # Adjust end position to maintain fixed length
        scale = self.fixed_length / current_length
        new_end_x = start_pos.x() + dx * scale
        new_end_y = start_pos.y() + dy * scale

        self.end_anchor.set_center_pos(QPointF(new_end_x, new_end_y))
        self.update_position()

    def update_appearance(self):
        """Update visual appearance based on state."""
        if self.is_selected:
            color = self.selected_color
            width = 6
        elif self.is_hovered:
            color = self.hover_color
            width = 5
        else:
            color = self.default_color
            width = 4

        pen = self.pen()
        pen.setColor(color)
        pen.setWidth(width)
        self.setPen(pen)

        # Show/hide length label based on state
        if self.length_label:
            self.length_label.setVisible(self.is_hovered or self.is_selected)

    def hoverEnterEvent(self, event):
        """Handle hover enter."""
        self.is_hovered = True
        self.update_appearance()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        """Handle hover leave."""
        self.is_hovered = False
        self.update_appearance()
        super().hoverLeaveEvent(event)

    def itemChange(self, change, value):
        """Handle item changes."""
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedChange:
            self.is_selected = value
            self.update_appearance()
        return super().itemChange(change, value)


class MechanismEditor:
    """Main editor for interactive mechanism manipulation."""

    def __init__(self, scene: QGraphicsScene):
        self.scene = scene
        self.signals = MechanismEditorSignals()
        self._logger = logging.getLogger(__name__)

        # Edit state
        self.edit_state = MechanismEditState()
        self.edit_mode = EditMode.VIEW

        # Mechanism elements
        self.anchors: Dict[str, InteractiveAnchor] = {}
        self.links: Dict[str, InteractiveLink] = {}
        self.mechanism_data: Optional[Dict] = None

        # Visual helpers
        self.grid_lines: List[QGraphicsLineItem] = []
        self.constraint_visuals: List[QGraphicsItem] = []
        self.dimension_labels: List[QGraphicsItem] = []

        # History for undo/redo
        self.history: List[Dict] = []
        self.history_index: int = -1

        # Property panel widget
        self.property_panel: Optional[QWidget] = None

    def set_mechanism(self, mechanism_data: Dict):
        """Set the mechanism to edit."""
        self.mechanism_data = mechanism_data.copy()
        self._create_interactive_elements()
        self._setup_constraints()
        self._save_to_history()

    def _create_interactive_elements(self):
        """Create interactive anchors and links from mechanism data."""
        self.clear_elements()

        if not self.mechanism_data:
            return

        mechanism_type = self.mechanism_data.get("type", "")

        # Create anchors based on mechanism type
        if mechanism_type == MechanismType.FOUR_BAR:
            self._create_four_bar_elements()
        elif mechanism_type == MechanismType.CAM_FOLLOWER:
            self._create_cam_elements()
        elif mechanism_type == MechanismType.GEAR_TRAIN:
            self._create_gear_elements()

    def _create_four_bar_elements(self):
        """Create elements for four-bar linkage."""
        data = self.mechanism_data

        # Create anchors
        anchors_data = [
            ("pivot_a", data.get("pivot_a", QPointF(0, 0)), ConstraintType.FIXED_PIVOT),
            ("pivot_d", data.get("pivot_d", QPointF(100, 0)), ConstraintType.FIXED_PIVOT),
            ("joint_b", data.get("joint_b", QPointF(50, 50)), None),
            ("joint_c", data.get("joint_c", QPointF(80, 50)), None),
        ]

        for anchor_id, pos, constraint in anchors_data:
            anchor = InteractiveAnchor(anchor_id, pos, constraint_type=constraint)
            anchor.signals = MechanismAnchorSignals()
            anchor.signals.position_changed.connect(self._on_anchor_moved)
            self.anchors[anchor_id] = anchor
            self.scene.addItem(anchor)

        # Create links
        link_pairs = [
            ("link_ab", "pivot_a", "joint_b"),
            ("link_bc", "joint_b", "joint_c"),
            ("link_cd", "joint_c", "pivot_d"),
            ("link_da", "pivot_d", "pivot_a"),  # Ground link (visual only)
        ]

        for link_id, start_id, end_id in link_pairs:
            if start_id in self.anchors and end_id in self.anchors:
                link = InteractiveLink(
                    link_id,
                    self.anchors[start_id],
                    self.anchors[end_id]
                )
                self.links[link_id] = link
                self.scene.addItem(link)

        # Set fixed lengths for links (except ground)
        for link_id in ["link_ab", "link_bc", "link_cd"]:
            if link_id in self.links:
                current_length = self.links[link_id].get_length()
                self.links[link_id].set_fixed_length(current_length)

    def _create_cam_elements(self):
        """Create elements for cam mechanism."""
        data = self.mechanism_data

        # Create cam center anchor
        cam_center = data.get("cam_center", QPointF(0, 0))
        anchor = InteractiveAnchor("cam_center", cam_center, ConstraintType.FIXED_PIVOT)
        anchor.signals = MechanismAnchorSignals()
        anchor.signals.position_changed.connect(self._on_anchor_moved)
        self.anchors["cam_center"] = anchor
        self.scene.addItem(anchor)

        # Create cam profile path
        profile = data.get("cam_profile", [])
        if profile:
            path = QPainterPath()
            path.moveTo(profile[0].x(), profile[0].y())
            for point in profile[1:]:
                path.lineTo(point.x(), point.y())
            path.closeSubpath()

            cam_item = QGraphicsPathItem(path)
            cam_item.setPen(QPen(QColor(100, 100, 200), 3))
            cam_item.setBrush(QBrush(QColor(150, 150, 255, 50)))
            self.scene.addItem(cam_item)

    def _create_gear_elements(self):
        """Create elements for gear train."""
        data = self.mechanism_data

        # Create gear centers
        gears = data.get("gears", [])
        for i, gear_data in enumerate(gears):
            center = gear_data.get("center", QPointF(i * 100, 0))
            anchor_id = f"gear_{i}_center"

            # First gear is usually the driver (fixed)
            constraint = ConstraintType.FIXED_PIVOT if i == 0 else None

            anchor = InteractiveAnchor(anchor_id, center, constraint_type=constraint)
            anchor.signals = MechanismAnchorSignals()
            anchor.signals.position_changed.connect(self._on_anchor_moved)
            self.anchors[anchor_id] = anchor
            self.scene.addItem(anchor)

            # Create gear visual
            radius = gear_data.get("radius", 30)
            gear_visual = QGraphicsEllipseItem(
                center.x() - radius, center.y() - radius,
                radius * 2, radius * 2
            )
            gear_visual.setPen(QPen(QColor(100, 100, 100), 2))
            gear_visual.setBrush(QBrush(QColor(200, 200, 200, 100)))
            self.scene.addItem(gear_visual)

    def _setup_constraints(self):
        """Set up mechanism constraints."""
        if not self.mechanism_data:
            return

        mechanism_type = self.mechanism_data.get("type", "")

        if mechanism_type == MechanismType.FOUR_BAR:
            # Add link length constraints
            for link_id, link in self.links.items():
                if link_id != "link_da":  # Skip ground link
                    constraint = MechanismConstraint(
                        type=ConstraintType.LINK_LENGTH,
                        elements=[link_id],
                        value=link.get_length()
                    )
                    self.edit_state.constraints.append(constraint)

    def _on_anchor_moved(self, anchor_id: str, new_pos: QPointF):
        """Handle anchor movement."""
        if anchor_id not in self.anchors:
            return

        # Apply grid snapping if enabled
        if self.edit_state.snap_to_grid:
            grid_size = self.edit_state.grid_size
            new_pos = QPointF(
                round(new_pos.x() / grid_size) * grid_size,
                round(new_pos.y() / grid_size) * grid_size
            )
            self.anchors[anchor_id].set_center_pos(new_pos)

        # Update connected links
        for link in self.links.values():
            if link.start_anchor.anchor_id == anchor_id or \
               link.end_anchor.anchor_id == anchor_id:
                link.update_position()

        # Enforce constraints
        self._enforce_constraints()

        # Update mechanism data
        self._update_mechanism_data()

        # Emit update signal
        self.signals.mechanism_updated.emit(self.mechanism_data)

    def _enforce_constraints(self):
        """Enforce all active constraints."""
        for constraint in self.edit_state.constraints:
            if not constraint.active:
                continue

            if constraint.type == ConstraintType.LINK_LENGTH:
                self._enforce_link_length_constraint(constraint)
            elif constraint.type == ConstraintType.ANGLE_LIMIT:
                self._enforce_angle_constraint(constraint)

    def _enforce_link_length_constraint(self, constraint: MechanismConstraint):
        """Enforce link length constraint."""
        for link_id in constraint.elements:
            if link_id in self.links and constraint.value is not None:
                self.links[link_id].set_fixed_length(constraint.value)

    def _update_mechanism_data(self):
        """Update mechanism data from current positions."""
        if not self.mechanism_data:
            return

        # Update anchor positions
        for anchor_id, anchor in self.anchors.items():
            pos = anchor.center_pos()
            scene_pos = anchor.mapToScene(pos)

            # Update in mechanism data based on type
            if "pivot" in anchor_id or "joint" in anchor_id:
                self.mechanism_data[anchor_id] = scene_pos
            elif anchor_id == "cam_center":
                self.mechanism_data["cam_center"] = scene_pos

    def set_edit_mode(self, mode: EditMode):
        """Set the editing mode."""
        self.edit_mode = mode

        # Update element interactivity based on mode
        if mode == EditMode.VIEW:
            self._set_elements_interactive(False)
        elif mode == EditMode.EDIT_ANCHORS:
            self._set_elements_interactive(True, anchors_only=True)
        elif mode == EditMode.EDIT_LINKS:
            self._set_elements_interactive(True, links_only=True)
        else:
            self._set_elements_interactive(True)

    def _set_elements_interactive(self, interactive: bool,
                                  anchors_only: bool = False,
                                  links_only: bool = False):
        """Set interactivity of elements."""
        if not links_only:
            for anchor in self.anchors.values():
                if anchor.constraint_type != ConstraintType.FIXED_PIVOT:
                    anchor.setFlag(
                        QGraphicsItem.GraphicsItemFlag.ItemIsMovable,
                        interactive
                    )
                    anchor.setFlag(
                        QGraphicsItem.GraphicsItemFlag.ItemIsSelectable,
                        interactive
                    )

        if not anchors_only:
            for link in self.links.values():
                link.setFlag(
                    QGraphicsItem.GraphicsItemFlag.ItemIsSelectable,
                    interactive
                )

    def toggle_grid(self, enabled: bool):
        """Toggle grid display."""
        self.edit_state.snap_to_grid = enabled
        self._update_grid_display()

    def set_grid_size(self, size: float):
        """Set grid size."""
        self.edit_state.grid_size = size
        if self.edit_state.snap_to_grid:
            self._update_grid_display()

    def _update_grid_display(self):
        """Update grid line display."""
        # Clear existing grid
        for line in self.grid_lines:
            self.scene.removeItem(line)
        self.grid_lines.clear()

        if not self.edit_state.snap_to_grid:
            return

        # Get scene bounds
        rect = self.scene.sceneRect()
        grid_size = self.edit_state.grid_size

        # Create grid lines
        pen = QPen(QColor(200, 200, 200), 0.5)
        pen.setCosmetic(True)

        # Vertical lines
        x = rect.left()
        while x <= rect.right():
            line = self.scene.addLine(x, rect.top(), x, rect.bottom(), pen)
            line.setZValue(-1000)  # Behind everything
            self.grid_lines.append(line)
            x += grid_size

        # Horizontal lines
        y = rect.top()
        while y <= rect.bottom():
            line = self.scene.addLine(rect.left(), y, rect.right(), y, pen)
            line.setZValue(-1000)
            self.grid_lines.append(line)
            y += grid_size

    def toggle_constraints_display(self, show: bool):
        """Toggle constraint visualization."""
        self.edit_state.show_constraints = show
        self._update_constraint_display()

    def _update_constraint_display(self):
        """Update constraint visualization."""
        # Clear existing visuals
        for item in self.constraint_visuals:
            self.scene.removeItem(item)
        self.constraint_visuals.clear()

        if not self.edit_state.show_constraints:
            return

        # Visualize constraints
        for constraint in self.edit_state.constraints:
            if constraint.type == ConstraintType.LINK_LENGTH:
                # Already shown on links
                pass
            elif constraint.type == ConstraintType.FIXED_PIVOT:
                # Already shown on anchors
                pass
            # Add more constraint visualizations as needed

    def toggle_dimensions_display(self, show: bool):
        """Toggle dimension labels."""
        self.edit_state.show_dimensions = show

        # Update link labels
        for link in self.links.values():
            if link.length_label:
                link.length_label.setVisible(show)

    def undo(self):
        """Undo last edit."""
        if self.history_index > 0:
            self.history_index -= 1
            self._restore_from_history(self.history_index)
            self.signals.mechanism_updated.emit(self.mechanism_data)

    def redo(self):
        """Redo last undone edit."""
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self._restore_from_history(self.history_index)
            self.signals.mechanism_updated.emit(self.mechanism_data)

    def _save_to_history(self):
        """Save current state to history."""
        # Remove any states after current index
        self.history = self.history[:self.history_index + 1]

        # Save current state
        state = {
            "mechanism_data": self.mechanism_data.copy() if self.mechanism_data else None,
            "anchor_positions": {
                aid: anchor.center_pos()
                for aid, anchor in self.anchors.items()
            }
        }
        self.history.append(state)
        self.history_index = len(self.history) - 1

        # Limit history size
        max_history = 50
        if len(self.history) > max_history:
            self.history = self.history[-max_history:]
            self.history_index = len(self.history) - 1

    def _restore_from_history(self, index: int):
        """Restore state from history."""
        if 0 <= index < len(self.history):
            state = self.history[index]

            # Restore mechanism data
            self.mechanism_data = state["mechanism_data"].copy() if state["mechanism_data"] else None

            # Restore anchor positions
            for aid, pos in state["anchor_positions"].items():
                if aid in self.anchors:
                    self.anchors[aid].set_center_pos(pos)

            # Update links
            for link in self.links.values():
                link.update_position()

    def create_property_panel(self) -> QWidget:
        """Create property panel for precise editing."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)

        # Edit mode selection
        mode_group = QGroupBox("Edit Mode")
        mode_layout = QVBoxLayout(mode_group)

        mode_combo = QComboBox()
        mode_combo.addItems(["View", "Edit Anchors", "Edit Links", "Edit Constraints"])
        mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_layout.addWidget(mode_combo)

        layout.addWidget(mode_group)

        # Grid settings
        grid_group = QGroupBox("Grid Settings")
        grid_layout = QVBoxLayout(grid_group)

        snap_check = QCheckBox("Snap to Grid")
        snap_check.setChecked(self.edit_state.snap_to_grid)
        snap_check.toggled.connect(self.toggle_grid)
        grid_layout.addWidget(snap_check)

        grid_size_layout = QHBoxLayout()
        grid_size_layout.addWidget(QLabel("Grid Size:"))
        grid_size_spin = QSpinBox()
        grid_size_spin.setRange(5, 50)
        grid_size_spin.setValue(int(self.edit_state.grid_size))
        grid_size_spin.valueChanged.connect(self.set_grid_size)
        grid_size_layout.addWidget(grid_size_spin)
        grid_layout.addLayout(grid_size_layout)

        layout.addWidget(grid_group)

        # Display options
        display_group = QGroupBox("Display Options")
        display_layout = QVBoxLayout(display_group)

        show_constraints_check = QCheckBox("Show Constraints")
        show_constraints_check.setChecked(self.edit_state.show_constraints)
        show_constraints_check.toggled.connect(self.toggle_constraints_display)
        display_layout.addWidget(show_constraints_check)

        show_dimensions_check = QCheckBox("Show Dimensions")
        show_dimensions_check.setChecked(self.edit_state.show_dimensions)
        show_dimensions_check.toggled.connect(self.toggle_dimensions_display)
        display_layout.addWidget(show_dimensions_check)

        layout.addWidget(display_group)

        # Selected element properties
        self.selection_group = QGroupBox("Selection Properties")
        self.selection_layout = QVBoxLayout(self.selection_group)
        layout.addWidget(self.selection_group)

        # History controls
        history_group = QGroupBox("History")
        history_layout = QHBoxLayout(history_group)

        undo_btn = QPushButton("Undo")
        undo_btn.clicked.connect(self.undo)
        history_layout.addWidget(undo_btn)

        redo_btn = QPushButton("Redo")
        redo_btn.clicked.connect(self.redo)
        history_layout.addWidget(redo_btn)

        layout.addWidget(history_group)

        layout.addStretch()

        self.property_panel = panel
        return panel

    def _on_mode_changed(self, index: int):
        """Handle edit mode change from combo box."""
        modes = [EditMode.VIEW, EditMode.EDIT_ANCHORS,
                 EditMode.EDIT_LINKS, EditMode.EDIT_CONSTRAINTS]
        if 0 <= index < len(modes):
            self.set_edit_mode(modes[index])

    def update_selection_properties(self):
        """Update property panel for selected elements."""
        # Clear existing widgets
        while self.selection_layout.count():
            child = self.selection_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        selected_anchors = [a for a in self.anchors.values() if a.is_selected]
        selected_links = [l for l in self.links.values() if l.is_selected]

        if selected_anchors:
            self._create_anchor_properties(selected_anchors[0])
        elif selected_links:
            self._create_link_properties(selected_links[0])

    def _create_anchor_properties(self, anchor: InteractiveAnchor):
        """Create property widgets for selected anchor."""
        # Position controls
        pos_label = QLabel(f"Anchor: {anchor.anchor_id}")
        self.selection_layout.addWidget(pos_label)

        pos = anchor.center_pos()

        x_layout = QHBoxLayout()
        x_layout.addWidget(QLabel("X:"))
        x_spin = QDoubleSpinBox()
        x_spin.setRange(-1000, 1000)
        x_spin.setValue(pos.x())
        x_spin.valueChanged.connect(
            lambda v: self._update_anchor_position(anchor, QPointF(v, pos.y()))
        )
        x_layout.addWidget(x_spin)
        self.selection_layout.addLayout(x_layout)

        y_layout = QHBoxLayout()
        y_layout.addWidget(QLabel("Y:"))
        y_spin = QDoubleSpinBox()
        y_spin.setRange(-1000, 1000)
        y_spin.setValue(pos.y())
        y_spin.valueChanged.connect(
            lambda v: self._update_anchor_position(anchor, QPointF(pos.x(), v))
        )
        y_layout.addWidget(y_spin)
        self.selection_layout.addLayout(y_layout)

    def _create_link_properties(self, link: InteractiveLink):
        """Create property widgets for selected link."""
        link_label = QLabel(f"Link: {link.link_id}")
        self.selection_layout.addWidget(link_label)

        length_layout = QHBoxLayout()
        length_layout.addWidget(QLabel("Length:"))
        length_spin = QDoubleSpinBox()
        length_spin.setRange(10, 500)
        length_spin.setValue(link.get_length())
        length_spin.valueChanged.connect(
            lambda v: self._update_link_length(link, v)
        )
        length_layout.addWidget(length_spin)
        self.selection_layout.addLayout(length_layout)

    def _update_anchor_position(self, anchor: InteractiveAnchor, new_pos: QPointF):
        """Update anchor position from property panel."""
        anchor.set_center_pos(new_pos)
        self._on_anchor_moved(anchor.anchor_id, new_pos)

    def _update_link_length(self, link: InteractiveLink, new_length: float):
        """Update link length from property panel."""
        link.set_fixed_length(new_length)

        # Update constraint
        for constraint in self.edit_state.constraints:
            if constraint.type == ConstraintType.LINK_LENGTH and \
               link.link_id in constraint.elements:
                constraint.value = new_length

        link.enforce_length_constraint()
        self._update_mechanism_data()
        self.signals.mechanism_updated.emit(self.mechanism_data)

    def clear_elements(self):
        """Clear all interactive elements."""
        # Remove anchors
        for anchor in self.anchors.values():
            self.scene.removeItem(anchor)
        self.anchors.clear()

        # Remove links
        for link in self.links.values():
            self.scene.removeItem(link)
        self.links.clear()

        # Clear visual helpers
        for item in self.grid_lines + self.constraint_visuals + self.dimension_labels:
            if item.scene():
                self.scene.removeItem(item)
        self.grid_lines.clear()
        self.constraint_visuals.clear()
        self.dimension_labels.clear()

        # Clear constraints
        self.edit_state.constraints.clear()

        # Clear history
        self.history.clear()
        self.history_index = -1


class MechanismAnchorSignals(QObject):
    """Signal holder for mechanism anchors."""
    position_changed = pyqtSignal(str, QPointF)  # anchor_id, new_position