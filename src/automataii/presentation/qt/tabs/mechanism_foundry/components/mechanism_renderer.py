"""
Mechanism Renderer - Rendering logic for mechanism visualization.

Extracted from MechanismFoundryView. Handles mechanism state rendering,
cam mechanism drawing, and grid visualization.

Design Pattern: Renderer (dedicated rendering responsibilities)
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QPen

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QGraphicsScene, QLabel

    from automataii.domain.mechanisms.core.state import MechanismState, RenderConfig, SafetyLevel
    from automataii.domain.mechanisms.linkages.fourbar.render import LinkageRenderer
    from automataii.presentation.qt.tabs.mechanism_foundry.path_preview import PathPreviewOverlay


class MechanismRenderer:
    """
    Handles mechanism rendering and visualization.

    Responsibilities:
    - Render mechanism state to scene
    - Draw cam mechanism components
    - Draw grid overlay
    - Update safety status display

    Time Complexity: O(n) where n = number of mechanism points/links
    """

    def __init__(
        self,
        scene: QGraphicsScene,
        fourbar_renderer: LinkageRenderer,
    ) -> None:
        """
        Initialize mechanism renderer.

        Args:
            scene: Qt graphics scene to render to
            fourbar_renderer: Renderer for four-bar linkage mechanisms
        """
        self._scene = scene
        self._fourbar_renderer = fourbar_renderer

        # Render settings
        self._render_config: RenderConfig | None = None
        self._show_forces: bool = True
        self._show_velocity: bool = False
        self._show_trail: bool = False

        # Callbacks for external state
        self._get_mechanism: Callable[[], Any] = lambda: None
        self._get_parameters: Callable[[], dict[str, float]] = dict
        self._get_angle: Callable[[], float] = lambda: 0.0
        self._get_path_overlay: Callable[[], PathPreviewOverlay | None] = lambda: None
        self._get_safety_label: Callable[[], QLabel | None] = lambda: None

    def configure(
        self,
        render_config: RenderConfig,
        show_forces: bool = True,
        show_velocity: bool = False,
        show_trail: bool = False,
    ) -> None:
        """Configure render settings."""
        self._render_config = render_config
        self._show_forces = show_forces
        self._show_velocity = show_velocity
        self._show_trail = show_trail

    def configure_callbacks(
        self,
        get_mechanism: Callable[[], Any],
        get_parameters: Callable[[], dict[str, float]],
        get_angle: Callable[[], float],
        get_path_overlay: Callable[[], PathPreviewOverlay | None],
        get_safety_label: Callable[[], QLabel | None],
    ) -> None:
        """Configure callback functions for external state access."""
        self._get_mechanism = get_mechanism
        self._get_parameters = get_parameters
        self._get_angle = get_angle
        self._get_path_overlay = get_path_overlay
        self._get_safety_label = get_safety_label

    def set_render_config(self, config: RenderConfig) -> None:
        """Update render configuration."""
        self._render_config = config

    def set_show_forces(self, enabled: bool) -> None:
        """Enable/disable force visualization."""
        self._show_forces = enabled

    def set_show_velocity(self, enabled: bool) -> None:
        """Enable/disable velocity visualization."""
        self._show_velocity = enabled

    def set_show_trail(self, enabled: bool) -> None:
        """Enable/disable trail visualization."""
        self._show_trail = enabled

    def render_mechanism(self) -> None:
        """
        Render current mechanism state.

        Clears existing mechanism items and redraws based on current state.
        """
        mechanism = self._get_mechanism()
        if not mechanism:
            return

        # Clear existing mechanism items
        for item in list(self._scene.items()):
            if hasattr(item, "data") and item.data(0) == "mechanism_item":
                self._scene.removeItem(item)

        try:
            parameters = self._get_parameters()
            angle = self._get_angle()
            state = mechanism.compute_state(parameters, angle)
            self._draw_mechanism_state(state, mechanism.mechanism_type)
            self._update_safety_display(state)
        except Exception as e:
            logging.warning(f"MechanismRenderer: Render error: {e}")
            safety_label = self._get_safety_label()
            if safety_label:
                safety_label.setText(f"Error: {str(e)}")

    def _draw_mechanism_state(
        self, state: MechanismState, mechanism_type: str | None
    ) -> None:
        """
        Draw mechanism based on state and type.

        Args:
            state: Computed mechanism state
            mechanism_type: Type identifier for mechanism
        """
        if mechanism_type == "fourbar":
            items = self._fourbar_renderer.render(
                state, self._scene, self._render_config
            )
            for item in items:
                if item:
                    item.setData(0, "mechanism_item")
            self._show_default_paths(state, mechanism_type)
        elif mechanism_type == "cam_follower":
            self._draw_cam_mechanism(state)

    def _draw_cam_mechanism(self, state: MechanismState) -> None:
        """
        Draw cam-follower mechanism.

        Args:
            state: Computed cam mechanism state
        """
        positions = state.positions
        cam_center = positions.get("cam_center", (0, 0))
        contact_point = positions.get("contact_point", (0, 0))
        follower_base = positions.get("follower_base", (0, 0))
        follower_end = positions.get("follower_end", (0, 0))

        # Draw cam profile
        cam_profile = state.metadata.get("cam_profile", [])
        if cam_profile:
            cam_pen = QPen(QColor(70, 130, 180), 3)
            for i, (x, y) in enumerate(cam_profile):
                next_idx = (i + 1) % len(cam_profile)
                nx, ny = cam_profile[next_idx]
                line = self._scene.addLine(x, y, nx, ny, cam_pen)
                line.setData(0, "mechanism_item")

        # Cam center
        cam_center_item = self._scene.addEllipse(
            cam_center[0] - 8,
            cam_center[1] - 8,
            16,
            16,
            QPen(QColor(255, 0, 0), 2),
            QBrush(QColor(255, 100, 100)),
        )
        cam_center_item.setData(0, "mechanism_item")

        # Contact point
        contact_pen = QPen(QColor(220, 20, 60), 3)
        contact_item = self._scene.addEllipse(
            contact_point[0] - 5,
            contact_point[1] - 5,
            10,
            10,
            contact_pen,
            QBrush(QColor(220, 20, 60)),
        )
        contact_item.setData(0, "mechanism_item")

        # Follower rod
        follower_pen = QPen(QColor(80, 80, 80), 6)
        follower_line = self._scene.addLine(
            follower_base[0],
            follower_base[1],
            follower_end[0],
            follower_end[1],
            follower_pen,
        )
        follower_line.setData(0, "mechanism_item")

        # Follower head
        follower_width = 30
        follower_height = 15
        follower_rect = self._scene.addRect(
            follower_end[0] - follower_width / 2,
            follower_end[1] - follower_height / 2,
            follower_width,
            follower_height,
            QPen(QColor(50, 50, 50), 2),
            QBrush(QColor(120, 120, 120)),
        )
        follower_rect.setData(0, "mechanism_item")

        # Guide line
        guide_pen = QPen(QColor(150, 150, 150), 2, Qt.PenStyle.DashLine)
        guide_line = self._scene.addLine(
            follower_base[0],
            follower_base[1] - 50,
            follower_base[0],
            cam_center[1] + 150,
            guide_pen,
        )
        guide_line.setData(0, "mechanism_item")

        # Base mount
        base_width = 60
        base_height = 30
        base_rect = self._scene.addRect(
            follower_base[0] - base_width / 2,
            follower_base[1] - base_height / 2,
            base_width,
            base_height,
            QPen(QColor(80, 80, 80), 3),
            QBrush(QColor(100, 100, 100)),
        )
        base_rect.setData(0, "mechanism_item")

    def _update_safety_display(self, state: MechanismState) -> None:
        """
        Update safety status label.

        Args:
            state: Mechanism state with safety information
        """
        from automataii.domain.mechanisms.core.state import SafetyLevel

        safety_label = self._get_safety_label()
        if not safety_label:
            return

        safety = state.safety_status
        level = safety.level

        if level == SafetyLevel.SAFE:
            color = "green"
            prefix = "✓"
        elif level == SafetyLevel.WARNING:
            color = "orange"
            prefix = "⚠"
        else:
            color = "red"
            prefix = "✗"

        safety_label.setText(
            f"<span style='color:{color}'>{prefix} {safety.message}</span>"
        )

    def _show_default_paths(
        self, state: MechanismState, mechanism_type: str
    ) -> None:
        """
        Show default paths for tracked points.

        Args:
            state: Current mechanism state
            mechanism_type: Type of mechanism
        """
        path_overlay = self._get_path_overlay()
        if not path_overlay or not path_overlay.enabled:
            return

        mechanism = self._get_mechanism()
        if not mechanism:
            return

        if mechanism_type == "fourbar":
            default_points = ["A", "B"]
        elif mechanism_type == "cam_follower":
            default_points = ["follower_end", "contact_point"]
        else:
            return

        parameters = self._get_parameters()
        for point_name in default_points:
            if point_name in state.positions:
                path_overlay.show_path(mechanism, parameters, point_name)

    def draw_grid(self) -> None:
        """
        Draw coordinate grid on the scene.

        Draws major grid lines at 100px intervals and axes.
        """
        major_grid = 100
        major_color = QColor(150, 150, 150, 120)
        axis_color = QColor(100, 100, 100, 200)

        rect = self._scene.sceneRect()
        pen = QPen(major_color, 1, Qt.PenStyle.SolidLine)

        # Vertical grid lines
        for x in range(int(rect.left()), int(rect.right()), major_grid):
            line = self._scene.addLine(x, rect.top(), x, rect.bottom(), pen)
            line.setZValue(-99)

        # Horizontal grid lines
        for y in range(int(rect.top()), int(rect.bottom()), major_grid):
            line = self._scene.addLine(rect.left(), y, rect.right(), y, pen)
            line.setZValue(-99)

        # Axes
        axis_pen = QPen(axis_color, 2, Qt.PenStyle.SolidLine)
        x_axis = self._scene.addLine(rect.left(), 0, rect.right(), 0, axis_pen)
        y_axis = self._scene.addLine(0, rect.top(), 0, rect.bottom(), axis_pen)
        x_axis.setZValue(-98)
        y_axis.setZValue(-98)

        # Origin marker
        origin = self._scene.addEllipse(
            -3, -3, 6, 6, axis_pen, QBrush(axis_color)
        )
        origin.setZValue(-97)
