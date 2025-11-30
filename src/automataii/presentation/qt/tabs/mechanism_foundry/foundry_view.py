"""
Mechanism Foundry View - Clean UI for interactive mechanism visualization
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QEvent, QObject, QPoint, Qt, QTimer
from PyQt6.QtGui import QAction, QBrush, QColor, QMouseEvent, QPen
from PyQt6.QtWidgets import (
    QComboBox,
    QGraphicsScene,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QSplitter,
    QStackedWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from automataii.application.mechanism_foundry import (
    ContentLoader,
    MechanismFoundryController,
    ParameterSpec,
)
from automataii.presentation.qt.tabs.mechanism_foundry.educational_info_panel import (
    EducationalInfoPanel,
)
from automataii.presentation.qt.tabs.mechanism_foundry.gallery_view import GalleryView

if TYPE_CHECKING:
    from automataii.application.mechanism_foundry.path_cache import PathCache
    from automataii.domain.mechanisms.cam.compute import CamFollowerMechanism
    from automataii.domain.mechanisms.core.protocols import Mechanism
    from automataii.domain.mechanisms.core.state import MechanismState, RenderConfig, SafetyLevel
    from automataii.domain.mechanisms.linkages.fourbar.compute import FourBarMechanism
    from automataii.presentation.qt.mechanisms.renderers import LinkageRenderer
    from automataii.presentation.qt.tabs.mechanism_foundry.path_preview import PathPreviewOverlay
else:
    from automataii.application.mechanism_foundry.path_cache import PathCache
    from automataii.domain.mechanisms.cam.compute import CamFollowerMechanism
    from automataii.domain.mechanisms.core.state import MechanismState, RenderConfig, SafetyLevel
    from automataii.domain.mechanisms.linkages.fourbar.compute import FourBarMechanism
    from automataii.presentation.qt.mechanisms.renderers import LinkageRenderer
    from automataii.presentation.qt.tabs.mechanism_foundry.path_preview import PathPreviewOverlay


class MechanismFoundryView(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self.controller = MechanismFoundryController()
        self.current_mechanism: Mechanism | None = None
        self.current_parameters: dict[str, float] = {}
        self.current_angle: float = 30.0

        self.fourbar_renderer = LinkageRenderer()
        self.render_config = RenderConfig(
            show_forces=True, show_labels=True, show_safety_zones=True
        )

        self.show_forces = True
        self.show_velocity = False
        self.show_trail = False

        self.scene = QGraphicsScene()
        self.scene.setSceneRect(-400, -300, 800, 600)
        self.scene.setBackgroundBrush(QBrush(QColor(250, 250, 250)))

        self.graphics_view = QGraphicsView(self.scene)
        self.graphics_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.graphics_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.graphics_view.setMouseTracking(True)
        self.graphics_view.viewport().installEventFilter(self)

        self.parameter_sliders: dict[str, tuple[QSlider, QLabel]] = {}
        self.mechanism_selector: QComboBox | None = None
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._on_animation_tick)
        self.is_playing = False

        self.path_cache = PathCache()
        self.path_preview_overlay = PathPreviewOverlay(self.scene, self.path_cache)
        self.content_loader = ContentLoader()

        self.gallery_view: GalleryView | None = None
        self.editor_widget: QWidget | None = None
        self.stacked_widget: QStackedWidget | None = None
        self.info_text = None  # Back-compat for tests expecting info_text attribute

        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.stacked_widget = QStackedWidget()

        self.gallery_view = GalleryView(self)
        self.gallery_view.mechanism_selected.connect(self._on_gallery_mechanism_selected)
        self.stacked_widget.addWidget(self.gallery_view)

        self.editor_widget = self._create_editor_widget()
        self.stacked_widget.addWidget(self.editor_widget)

        main_layout.addWidget(self.stacked_widget)

        self.stacked_widget.setCurrentIndex(0)

    def _create_editor_widget(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(8)
        splitter.setChildrenCollapsible(False)

        controls_widget = self._create_controls_panel()
        splitter.addWidget(controls_widget)

        viz_container = QWidget()
        viz_layout = QVBoxLayout(viz_container)
        viz_layout.setContentsMargins(0, 0, 0, 0)
        viz_layout.addWidget(self.graphics_view)
        splitter.addWidget(viz_container)

        info_panel = self._create_info_panel()
        splitter.addWidget(info_panel)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 1)
        splitter.setSizes([350, 600, 300])

        layout.addWidget(splitter)

        self._draw_grid()
        self._select_initial_mechanism()

        return widget

    def _on_gallery_mechanism_selected(self, mechanism_type: str) -> None:
        self._load_mechanism(mechanism_type)
        if self.stacked_widget:
            self.stacked_widget.setCurrentIndex(1)

    def _go_back_to_gallery(self) -> None:
        if self.is_playing:
            self._toggle_play()
        if self.stacked_widget:
            self.stacked_widget.setCurrentIndex(0)

    def _create_toolbar(self) -> QToolBar:
        toolbar = QToolBar()
        toolbar.setMovable(False)

        back_action = QAction("← Back to Gallery", self)
        back_action.triggered.connect(self._go_back_to_gallery)
        toolbar.addAction(back_action)

        toolbar.addSeparator()

        self.play_action = QAction("▶ Play", self)
        self.play_action.setCheckable(True)
        self.play_action.triggered.connect(self._toggle_play)
        toolbar.addAction(self.play_action)

        toolbar.addSeparator()

        self.forces_action = QAction("🔧 Forces", self)
        self.forces_action.setCheckable(True)
        self.forces_action.setChecked(True)
        self.forces_action.triggered.connect(self._toggle_forces)
        toolbar.addAction(self.forces_action)

        self.velocity_action = QAction("➡ Velocity", self)
        self.velocity_action.setCheckable(True)
        self.velocity_action.setChecked(False)
        self.velocity_action.triggered.connect(self._toggle_velocity)
        toolbar.addAction(self.velocity_action)

        self.trail_action = QAction("〰 Trail", self)
        self.trail_action.setCheckable(True)
        self.trail_action.setChecked(False)
        self.trail_action.triggered.connect(self._toggle_trail)
        toolbar.addAction(self.trail_action)

        toolbar.addSeparator()

        self.path_preview_action = QAction("🔍 Path Preview", self)
        self.path_preview_action.setCheckable(True)
        self.path_preview_action.setChecked(True)
        self.path_preview_action.triggered.connect(self._toggle_path_preview)
        toolbar.addAction(self.path_preview_action)

        toolbar.addSeparator()

        reset_action = QAction("🔄 Reset", self)
        reset_action.triggered.connect(self._reset_animation)
        toolbar.addAction(reset_action)

        return toolbar

    def _create_info_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMinimumWidth(250)
        panel.setMaximumWidth(350)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        self.info_panel = EducationalInfoPanel()
        # Back-compat: expose underlying text widget for tests
        self.info_text = getattr(self.info_panel, "_text_display", None)
        layout.addWidget(self.info_panel)

        return panel

    def _toggle_forces(self) -> None:
        self.show_forces = self.forces_action.isChecked()
        self.render_config = RenderConfig(
            show_forces=self.show_forces,
            show_labels=self.render_config.show_labels,
            show_safety_zones=self.render_config.show_safety_zones,
        )
        self._render_mechanism()

    def _toggle_velocity(self) -> None:
        self.show_velocity = self.velocity_action.isChecked()
        self._render_mechanism()

    def _toggle_trail(self) -> None:
        self.show_trail = self.trail_action.isChecked()
        self._render_mechanism()

    def _toggle_path_preview(self) -> None:
        self.path_preview_overlay.set_enabled(self.path_preview_action.isChecked())

    def _create_controls_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMinimumWidth(300)
        panel.setMaximumWidth(400)
        layout = QVBoxLayout(panel)

        selector_group = QGroupBox("Mechanism Selection")
        selector_layout = QVBoxLayout()
        self.mechanism_selector = QComboBox()
        self.mechanism_selector.currentIndexChanged.connect(self._on_mechanism_changed)
        selector_layout.addWidget(self.mechanism_selector)
        selector_group.setLayout(selector_layout)
        layout.addWidget(selector_group)

        params_group = QGroupBox("Parameters")
        self.params_layout = QVBoxLayout()
        params_group.setLayout(self.params_layout)
        layout.addWidget(params_group)

        animation_group = QGroupBox("Animation")
        animation_layout = QVBoxLayout()

        angle_layout = QHBoxLayout()
        angle_layout.addWidget(QLabel("Angle:"))
        self.angle_label = QLabel("30°")
        angle_layout.addWidget(self.angle_label)
        angle_layout.addStretch()
        animation_layout.addLayout(angle_layout)

        self.angle_slider = QSlider(Qt.Orientation.Horizontal)
        self.angle_slider.setMinimum(0)
        self.angle_slider.setMaximum(360)
        self.angle_slider.setValue(30)
        self.angle_slider.valueChanged.connect(self._on_angle_changed)
        animation_layout.addWidget(self.angle_slider)

        animation_group.setLayout(animation_layout)
        layout.addWidget(animation_group)

        display_group = QGroupBox("Display Options")
        display_layout = QVBoxLayout()
        self.safety_label = QLabel("Status: Unknown")
        display_layout.addWidget(self.safety_label)
        display_group.setLayout(display_layout)
        layout.addWidget(display_group)

        layout.addStretch()

        return panel

    def _populate_mechanism_selector(self) -> None:
        if self.mechanism_selector is None:
            return

        self.mechanism_selector.blockSignals(True)
        self.mechanism_selector.clear()

        for item in self.controller.list_mechanisms():
            self.mechanism_selector.addItem(item.display_name, item.mechanism_type)

        self.mechanism_selector.blockSignals(False)

    def _select_initial_mechanism(self) -> None:
        self._populate_mechanism_selector()
        if self.mechanism_selector and self.mechanism_selector.count() > 0:
            self.mechanism_selector.setCurrentIndex(0)
            self._on_mechanism_changed(0)

    def _on_mechanism_changed(self, index: int) -> None:
        if not self.mechanism_selector or index < 0:
            return

        mechanism_type = self.mechanism_selector.itemData(index)
        if not mechanism_type:
            return

        self._load_mechanism(mechanism_type)

    def _load_mechanism(self, mechanism_type: str) -> None:
        if mechanism_type == "four_bar":
            self.current_mechanism = FourBarMechanism()
        elif mechanism_type == "cam_follower":
            self.current_mechanism = CamFollowerMechanism()
        else:
            self.current_mechanism = None
            return

        config = self.controller.get_configuration(mechanism_type)
        if not config:
            return

        self.current_parameters = config.initial_parameters()
        self._rebuild_parameter_sliders(config.parameter_specs)
        self._update_info_panel(mechanism_type, config)
        self._render_mechanism()

    def _update_info_panel(self, mechanism_type: str, config) -> None:
        content = self.content_loader.load_content(mechanism_type)
        self.info_panel.set_content(content)

    def _rebuild_parameter_sliders(self, specs: tuple[ParameterSpec, ...]) -> None:
        for slider, label in self.parameter_sliders.values():
            slider.deleteLater()
            label.deleteLater()

        self.parameter_sliders.clear()

        while self.params_layout.count():
            item = self.params_layout.takeAt(0)
            if item.layout():
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
                item.layout().deleteLater()
            elif item.widget():
                item.widget().deleteLater()

        for spec in specs:
            row_layout = QHBoxLayout()

            label_text = spec.key.replace("_", " ").title()
            if spec.unit:
                label_text = f"{label_text} ({spec.unit})"
            label = QLabel(f"{label_text}:")
            row_layout.addWidget(label)

            if spec.is_integer:
                value_str = f"{int(spec.default_value)}"
            else:
                value_str = f"{spec.default_value:.1f}"

            value_label = QLabel(value_str)
            value_label.setMinimumWidth(60)
            row_layout.addWidget(value_label)

            self.params_layout.addLayout(row_layout)

            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setMinimum(int(spec.min_value / spec.step))
            slider.setMaximum(int(spec.max_value / spec.step))
            slider.setValue(int(spec.default_value / spec.step))
            slider.valueChanged.connect(
                lambda val,
                k=spec.key,
                s=spec.step,
                lbl=value_label,
                is_int=spec.is_integer: self._on_parameter_changed(k, val * s, lbl, is_int)
            )

            self.params_layout.addWidget(slider)
            self.parameter_sliders[spec.key] = (slider, value_label)

    def _on_parameter_changed(
        self, param_key: str, value: float, label: QLabel, is_integer: bool = False
    ) -> None:
        self.current_parameters[param_key] = value
        if is_integer:
            label.setText(f"{int(value)}")
        else:
            label.setText(f"{value:.1f}")
        self._render_mechanism()

        if self.current_mechanism:
            config = self.controller.get_configuration(self.current_mechanism.mechanism_type)
            if config:
                self._update_info_panel(self.current_mechanism.mechanism_type, config)

    def _on_angle_changed(self, value: int) -> None:
        self.current_angle = float(value)
        self.angle_label.setText(f"{value}°")
        self._render_mechanism()

    def _toggle_play(self) -> None:
        if self.is_playing:
            self.animation_timer.stop()
            self.play_action.setText("▶ Play")
            self.play_action.setChecked(False)
            self.is_playing = False
        else:
            self.animation_timer.start(33)
            self.play_action.setText("⏸ Pause")
            self.play_action.setChecked(True)
            self.is_playing = True

    def _reset_animation(self) -> None:
        self.current_angle = 30.0
        self.angle_slider.setValue(30)
        if self.is_playing:
            self._toggle_play()

    def _on_animation_tick(self) -> None:
        self.current_angle = (self.current_angle + 4.0) % 360.0
        self.angle_slider.blockSignals(True)
        self.angle_slider.setValue(int(self.current_angle))
        self.angle_slider.blockSignals(False)
        self.angle_label.setText(f"{int(self.current_angle)}°")
        self._render_mechanism()

    def _render_mechanism(self) -> None:
        if not self.current_mechanism:
            return

        for item in list(self.scene.items()):
            if hasattr(item, "data") and item.data(0) == "mechanism_item":
                self.scene.removeItem(item)

        try:
            state = self.current_mechanism.compute_state(
                self.current_parameters, self.current_angle
            )
            self._draw_mechanism_state(state)
            self._update_safety_display(state)
        except Exception as e:
            self.safety_label.setText(f"Error: {str(e)}")

    def _draw_mechanism_state(self, state: MechanismState) -> None:
        mechanism_type = self.current_mechanism.mechanism_type if self.current_mechanism else None

        if mechanism_type == "fourbar":
            items = self.fourbar_renderer.render(state, self.scene, self.render_config)
            for item in items:
                if item:
                    item.setData(0, "mechanism_item")
            self._show_default_paths(state)
        elif mechanism_type == "cam_follower":
            self._draw_cam_mechanism(state)

    def _draw_cam_mechanism(self, state: MechanismState) -> None:
        positions = state.positions
        cam_center = positions.get("cam_center", (0, 0))
        contact_point = positions.get("contact_point", (0, 0))
        follower_base = positions.get("follower_base", (0, 0))
        follower_end = positions.get("follower_end", (0, 0))

        cam_profile = state.metadata.get("cam_profile", [])
        if cam_profile:
            cam_pen = QPen(QColor(70, 130, 180), 3)
            QBrush(QColor(70, 130, 180, 100))
            for i, (x, y) in enumerate(cam_profile):
                next_idx = (i + 1) % len(cam_profile)
                nx, ny = cam_profile[next_idx]
                line = self.scene.addLine(x, y, nx, ny, cam_pen)
                line.setData(0, "mechanism_item")

        cam_center_item = self.scene.addEllipse(
            cam_center[0] - 8,
            cam_center[1] - 8,
            16,
            16,
            QPen(QColor(255, 0, 0), 2),
            QBrush(QColor(255, 100, 100)),
        )
        cam_center_item.setData(0, "mechanism_item")

        contact_pen = QPen(QColor(220, 20, 60), 3)
        contact_item = self.scene.addEllipse(
            contact_point[0] - 5,
            contact_point[1] - 5,
            10,
            10,
            contact_pen,
            QBrush(QColor(220, 20, 60)),
        )
        contact_item.setData(0, "mechanism_item")

        follower_pen = QPen(QColor(80, 80, 80), 6)
        follower_line = self.scene.addLine(
            follower_base[0], follower_base[1], follower_end[0], follower_end[1], follower_pen
        )
        follower_line.setData(0, "mechanism_item")

        follower_width = 30
        follower_height = 15
        follower_rect = self.scene.addRect(
            follower_end[0] - follower_width / 2,
            follower_end[1] - follower_height / 2,
            follower_width,
            follower_height,
            QPen(QColor(50, 50, 50), 2),
            QBrush(QColor(120, 120, 120)),
        )
        follower_rect.setData(0, "mechanism_item")

        guide_pen = QPen(QColor(150, 150, 150), 2, Qt.PenStyle.DashLine)
        guide_line = self.scene.addLine(
            follower_base[0],
            follower_base[1] - 50,
            follower_base[0],
            cam_center[1] + 150,
            guide_pen,
        )
        guide_line.setData(0, "mechanism_item")

        base_width = 60
        base_height = 30
        base_rect = self.scene.addRect(
            follower_base[0] - base_width / 2,
            follower_base[1] - base_height / 2,
            base_width,
            base_height,
            QPen(QColor(80, 80, 80), 3),
            QBrush(QColor(100, 100, 100)),
        )
        base_rect.setData(0, "mechanism_item")

    def _update_safety_display(self, state: MechanismState) -> None:
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

        self.safety_label.setText(f"<span style='color:{color}'>{prefix} {safety.message}</span>")

    def _draw_grid(self) -> None:
        major_grid = 100
        major_color = QColor(150, 150, 150, 120)
        axis_color = QColor(100, 100, 100, 200)

        rect = self.scene.sceneRect()
        pen = QPen(major_color, 1, Qt.PenStyle.SolidLine)

        for x in range(int(rect.left()), int(rect.right()), major_grid):
            line = self.scene.addLine(x, rect.top(), x, rect.bottom(), pen)
            line.setZValue(-99)

        for y in range(int(rect.top()), int(rect.bottom()), major_grid):
            line = self.scene.addLine(rect.left(), y, rect.right(), y, pen)
            line.setZValue(-99)

        axis_pen = QPen(axis_color, 2, Qt.PenStyle.SolidLine)
        x_axis = self.scene.addLine(rect.left(), 0, rect.right(), 0, axis_pen)
        y_axis = self.scene.addLine(0, rect.top(), 0, rect.bottom(), axis_pen)
        x_axis.setZValue(-98)
        y_axis.setZValue(-98)

        origin = self.scene.addEllipse(-3, -3, 6, 6, axis_pen, QBrush(axis_color))
        origin.setZValue(-97)

    def _show_default_paths(self, state: MechanismState) -> None:
        """Show default paths for all tracked points."""
        if not self.current_mechanism or not self.path_preview_overlay.enabled:
            return

        mechanism_type = self.current_mechanism.mechanism_type
        if mechanism_type == "fourbar":
            default_points = ["A", "B"]
        elif mechanism_type == "cam_follower":
            default_points = ["follower_end", "contact_point"]
        else:
            return

        for point_name in default_points:
            if point_name in state.positions:
                self.path_preview_overlay.show_path(
                    self.current_mechanism, self.current_parameters, point_name
                )

    def eventFilter(self, a0: QObject | None, a1: QEvent | None) -> bool:
        if a1 and a1.type() == QEvent.Type.MouseMove:
            if self.current_mechanism and self.path_preview_overlay.enabled:
                if isinstance(a1, QMouseEvent):
                    point_name = self._get_hovered_point_name(a1.pos())
                    if point_name:
                        self.path_preview_overlay.show_path(
                            self.current_mechanism,
                            self.current_parameters,
                            point_name,
                            auto_fade=True,
                        )
                    else:
                        pass
        return super().eventFilter(a0, a1)

    def _get_hovered_point_name(self, view_pos: QPoint) -> str | None:
        scene_pos = self.graphics_view.mapToScene(view_pos)
        threshold = 20.0

        if not self.current_mechanism:
            return None

        try:
            state = self.current_mechanism.compute_state(
                self.current_parameters, self.current_angle
            )
        except Exception:
            return None

        mechanism_type = self.current_mechanism.mechanism_type

        if mechanism_type == "fourbar":
            test_points = ["A", "B"]
        elif mechanism_type == "cam_follower":
            test_points = ["follower_end", "contact_point"]
        else:
            return None

        for point_name in test_points:
            position = state.positions.get(point_name)
            if position:
                px, py = position
                distance = ((scene_pos.x() - px) ** 2 + (scene_pos.y() - py) ** 2) ** 0.5
                if distance < threshold:
                    return point_name

        return None
