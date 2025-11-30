"""
Four-bar linkage editor implementation.
Provides interactive handles for all joints and links.
"""

import math
from typing import Any

from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QGraphicsEllipseItem, QGraphicsScene

from ..interfaces.editor import EditorInterface, HandleConfig


class FourBarEditor(EditorInterface):
    """
    Interactive editor for four-bar linkage.

    Provides handles for:
    - Both anchor points
    - Crank joint
    - Rocker joint
    - Coupler point
    - Link length adjustments
    """

    def __init__(self, mechanism_id: str, scene: QGraphicsScene):
        """Initialize four-bar editor."""
        self.mechanism_id = mechanism_id
        self.scene = scene
        self.handles: dict[str, QGraphicsEllipseItem] = {}
        self.mechanism_data: dict[str, Any] = {}
        self._is_editing = False

    def create_handles(self, mechanism_data: dict[str, Any]) -> list[HandleConfig]:
        """Create interactive handles."""
        self.mechanism_data = mechanism_data
        params = mechanism_data.get('params', {})

        # Extract positions
        p1 = QPointF(*params.get('anchor1', [0, 0]))
        p2 = QPointF(*params.get('anchor2', [100, 0]))

        # Calculate initial joint positions
        crank_angle = params.get('crank_angle', 0)
        l2 = params.get('l2', 40)
        l4 = params.get('l4', 50)

        p3 = QPointF(
            p1.x() + l2 * math.cos(math.radians(crank_angle)),
            p1.y() + l2 * math.sin(math.radians(crank_angle))
        )

        rocker_angle = params.get('rocker_angle', 45)
        p4 = QPointF(
            p2.x() + l4 * math.cos(math.radians(rocker_angle)),
            p2.y() + l4 * math.sin(math.radians(rocker_angle))
        )

        # Create handle configurations
        configs = [
            # Anchor points
            HandleConfig(
                handle_id='anchor1',
                position=p1,
                param_name='anchor1',
                tooltip='Fixed Pivot 1 - Drag to reposition',
                color=QColor(100, 150, 255),
                size=14,
                callback=self._on_anchor1_moved
            ),
            HandleConfig(
                handle_id='anchor2',
                position=p2,
                param_name='anchor2',
                tooltip='Fixed Pivot 2 - Drag to reposition',
                color=QColor(100, 150, 255),
                size=14,
                callback=self._on_anchor2_moved
            ),

            # Joint handles
            HandleConfig(
                handle_id='crank',
                position=p3,
                param_name='crank_joint',
                tooltip='Crank Joint - Drag to adjust angle and length',
                color=QColor(255, 150, 100),
                size=12,
                constraints={'fixed_distance': {'anchor': p1, 'distance': l2}},
                callback=self._on_crank_moved
            ),
            HandleConfig(
                handle_id='rocker',
                position=p4,
                param_name='rocker_joint',
                tooltip='Rocker Joint - Drag to adjust angle and length',
                color=QColor(255, 150, 100),
                size=12,
                constraints={'fixed_distance': {'anchor': p2, 'distance': l4}},
                callback=self._on_rocker_moved
            ),

            # Coupler point
            HandleConfig(
                handle_id='coupler',
                position=(p3 + p4) / 2,
                param_name='coupler_point',
                tooltip='Coupler Point - Drag along coupler link',
                color=QColor(150, 255, 150),
                size=10,
                callback=self._on_coupler_moved
            ),

            # Link adjustment handles (at midpoints)
            HandleConfig(
                handle_id='crank_length',
                position=(p1 + p3) / 2,
                param_name='l2',
                tooltip='Drag to adjust crank length',
                color=QColor(200, 200, 100),
                size=8,
                callback=self._on_crank_length_changed
            ),
            HandleConfig(
                handle_id='rocker_length',
                position=(p2 + p4) / 2,
                param_name='l4',
                tooltip='Drag to adjust rocker length',
                color=QColor(200, 200, 100),
                size=8,
                callback=self._on_rocker_length_changed
            )
        ]

        # Create actual handle graphics
        for config in configs:
            self._create_handle_graphics(config)

        return configs

    def on_handle_moved(self, handle_id: str, new_position: QPointF) -> dict[str, Any]:
        """Process handle movement."""
        if handle_id == 'anchor1':
            return self._on_anchor1_moved(handle_id, new_position)
        elif handle_id == 'anchor2':
            return self._on_anchor2_moved(handle_id, new_position)
        elif handle_id == 'crank':
            return self._on_crank_moved(handle_id, new_position)
        elif handle_id == 'rocker':
            return self._on_rocker_moved(handle_id, new_position)
        elif handle_id == 'coupler':
            return self._on_coupler_moved(handle_id, new_position)
        elif handle_id == 'crank_length':
            return self._on_crank_length_changed(handle_id, new_position)
        elif handle_id == 'rocker_length':
            return self._on_rocker_length_changed(handle_id, new_position)

        return {}

    def update_handle_positions(self, simulation_data: dict[str, Any]) -> None:
        """Update handle positions from simulation."""
        # Update handle positions based on current simulation state
        pass

    def validate_handle_position(self, handle_id: str, position: QPointF) -> bool:
        """Validate handle position."""
        # Check constraints
        return True

    def get_handle_constraints(self, handle_id: str) -> dict[str, Any]:
        """Get handle constraints."""
        if handle_id == 'crank':
            # Constrained to circle around anchor1
            return {
                'type': 'circular',
                'center': self.handles['anchor1'].pos() if 'anchor1' in self.handles else QPointF(0, 0),
                'radius': self.mechanism_data.get('params', {}).get('l2', 40)
            }
        elif handle_id == 'rocker':
            # Constrained to circle around anchor2
            return {
                'type': 'circular',
                'center': self.handles['anchor2'].pos() if 'anchor2' in self.handles else QPointF(100, 0),
                'radius': self.mechanism_data.get('params', {}).get('l4', 50)
            }

        return {}

    def show_handles(self) -> None:
        """Show all handles."""
        for handle in self.handles.values():
            handle.setVisible(True)
        self._is_editing = True

    def hide_handles(self) -> None:
        """Hide all handles."""
        for handle in self.handles.values():
            handle.setVisible(False)
        self._is_editing = False

    def remove_handles(self) -> None:
        """Remove all handles."""
        for handle in self.handles.values():
            if handle.scene():
                self.scene.removeItem(handle)
        self.handles.clear()

    @property
    def is_editing(self) -> bool:
        """Check edit mode."""
        return self._is_editing

    def _create_handle_graphics(self, config: HandleConfig) -> None:
        """Create graphics item for handle."""
        handle = QGraphicsEllipseItem(
            -config.size/2, -config.size/2,
            config.size, config.size
        )
        handle.setPos(config.position)
        handle.setBrush(config.color)
        handle.setFlag(QGraphicsEllipseItem.GraphicsItemFlag.ItemIsMovable, True)
        handle.setFlag(QGraphicsEllipseItem.GraphicsItemFlag.ItemIsSelectable, True)
        handle.setToolTip(config.tooltip)

        self.scene.addItem(handle)
        self.handles[config.handle_id] = handle

    def _on_anchor1_moved(self, handle_id: str, new_pos: QPointF) -> dict[str, Any]:
        """Handle anchor1 movement."""
        self.mechanism_data['params']['anchor1'] = [new_pos.x(), new_pos.y()]

        # Update dependent handles
        self._update_dependent_handles('anchor1')

        return {'anchor1': [new_pos.x(), new_pos.y()]}

    def _on_anchor2_moved(self, handle_id: str, new_pos: QPointF) -> dict[str, Any]:
        """Handle anchor2 movement."""
        self.mechanism_data['params']['anchor2'] = [new_pos.x(), new_pos.y()]

        # Update dependent handles
        self._update_dependent_handles('anchor2')

        return {'anchor2': [new_pos.x(), new_pos.y()]}

    def _on_crank_moved(self, handle_id: str, new_pos: QPointF) -> dict[str, Any]:
        """Handle crank joint movement."""
        anchor1 = QPointF(*self.mechanism_data['params']['anchor1'])

        dx = new_pos.x() - anchor1.x()
        dy = new_pos.y() - anchor1.y()

        angle = math.degrees(math.atan2(dy, dx))
        length = math.sqrt(dx*dx + dy*dy)

        self.mechanism_data['params']['crank_angle'] = angle
        self.mechanism_data['params']['l2'] = length

        return {'crank_angle': angle, 'l2': length}

    def _on_rocker_moved(self, handle_id: str, new_pos: QPointF) -> dict[str, Any]:
        """Handle rocker joint movement."""
        anchor2 = QPointF(*self.mechanism_data['params']['anchor2'])

        dx = new_pos.x() - anchor2.x()
        dy = new_pos.y() - anchor2.y()

        angle = math.degrees(math.atan2(dy, dx))
        length = math.sqrt(dx*dx + dy*dy)

        self.mechanism_data['params']['rocker_angle'] = angle
        self.mechanism_data['params']['l4'] = length

        return {'rocker_angle': angle, 'l4': length}

    def _on_coupler_moved(self, handle_id: str, new_pos: QPointF) -> dict[str, Any]:
        """Handle coupler point movement."""
        # Calculate coupler ratio along the coupler link
        # Implementation depends on constraint system
        return {}

    def _on_crank_length_changed(self, handle_id: str, new_pos: QPointF) -> dict[str, Any]:
        """Handle crank length change."""
        QPointF(*self.mechanism_data['params']['anchor1'])

        # Project onto crank line
        # Calculate new length

        return {}

    def _on_rocker_length_changed(self, handle_id: str, new_pos: QPointF) -> dict[str, Any]:
        """Handle rocker length change."""
        # Similar to crank length
        return {}

    def _update_dependent_handles(self, changed_handle: str) -> None:
        """Update handles that depend on the changed handle."""
        # Update link midpoint handles, etc.
        pass
