"""
Mechanism Foundry View - Clean UI for interactive mechanism visualization
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, SupportsFloat, SupportsIndex, cast

from PyQt6.QtCore import QEvent, QObject, QPoint, QPointF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QBrush, QColor, QMouseEvent, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QComboBox,
    QGraphicsItem,
    QGraphicsScene,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSplitter,
    QStackedWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from automataii.application.mechanism_foundry import (
    ContentLoader,
    MechanismContent,
    MechanismFoundryController,
    ParameterSpec,
    SensemakingContext,
    SensemakingParameterChange,
    SensemakingPreviewSnapshot,
    SensemakingService,
)
from automataii.application.mechanism_foundry.mechanism_types import (
    canonical_mechanism_type,
    normalize_mechanism_type_key,
)
from automataii.presentation.qt.shared import blocked_signals, clear_layout
from automataii.presentation.qt.tabs.mechanism_foundry.gallery_view import GalleryView
from automataii.presentation.qt.tabs.mechanism_foundry.sensemaking_panel import (
    MechanismSensemakingPanel,
)

if TYPE_CHECKING:
    from automataii.application.mechanism_foundry.path_cache import PathCache
    from automataii.domain.mechanisms.cam.compute import CamFollowerMechanism
    from automataii.domain.mechanisms.core.protocols import Mechanism
    from automataii.domain.mechanisms.core.state import (
        MechanismState,
        RenderConfig,
        SafetyLevel,
        SafetyStatus,
    )
    from automataii.domain.mechanisms.linkages.fourbar.compute import FourBarMechanism
    from automataii.presentation.qt.mechanisms.renderers import LinkageRenderer
    from automataii.presentation.qt.tabs.mechanism_foundry.path_preview import PathPreviewOverlay
else:
    from automataii.application.mechanism_foundry.path_cache import PathCache
    from automataii.domain.mechanisms.cam.compute import CamFollowerMechanism
    from automataii.domain.mechanisms.core.state import (
        MechanismState,
        RenderConfig,
        SafetyLevel,
        SafetyStatus,
    )
    from automataii.domain.mechanisms.linkages.fourbar.compute import FourBarMechanism
    from automataii.presentation.qt.mechanisms.renderers import LinkageRenderer
    from automataii.presentation.qt.tabs.mechanism_foundry.path_preview import PathPreviewOverlay

_FloatPayload = str | bytes | bytearray | SupportsFloat | SupportsIndex


def _finite_float(value: object, default: float) -> float:
    if isinstance(value, bool):
        return default
    try:
        result = float(cast(_FloatPayload, value))
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _positive_finite_float(value: object, default: float, minimum: float = 0.0) -> float:
    result = _finite_float(value, default)
    return result if result > minimum else default


def _finite_point_pair(value: object) -> tuple[float, float] | None:
    if not isinstance(value, list | tuple) or len(value) < 2:
        return None
    x = _finite_float(value[0], math.nan)
    y = _finite_float(value[1], math.nan)
    if not math.isfinite(x) or not math.isfinite(y):
        return None
    return x, y


class _GearTrainPreviewMechanism:
    """Lightweight Foundry-only mechanism for gear train preview/export."""

    mechanism_type = "gear_train"
    _module = 3.0

    def compute_state(self, parameters: dict[str, float], input_angle: float) -> MechanismState:
        if not isinstance(parameters, dict):
            parameters = {}
        teeth1 = _positive_finite_float(parameters.get("gear1_teeth", 12.0), 12.0)
        teeth2 = _positive_finite_float(parameters.get("gear2_teeth", 18.0), 18.0)

        r1 = teeth1 * self._module
        r2 = teeth2 * self._module
        center_distance = r1 + r2 + 2.0

        g1 = (-center_distance / 2.0, 0.0)
        g2 = (center_distance / 2.0, 0.0)

        theta1 = math.radians(_finite_float(input_angle, 0.0))
        theta2 = -theta1 * (r1 / r2)

        p1 = (g1[0] + r1 * math.cos(theta1), g1[1] + r1 * math.sin(theta1))
        p2 = (g2[0] + r2 * math.cos(theta2), g2[1] + r2 * math.sin(theta2))

        return MechanismState(
            positions={
                "gear1_center": g1,
                "gear2_center": g2,
                "gear1_indicator_end": p1,
                "gear2_indicator_end": p2,
            },
            safety_status=SafetyStatus(SafetyLevel.SAFE, "Gear mesh nominal"),
            metadata={"r1": r1, "r2": r2, "theta1": theta1, "theta2": theta2},
        )


class _SliderCrankPreviewMechanism:
    """Lightweight Foundry-only mechanism for slider-crank preview/export."""

    mechanism_type = "slider_crank"

    def compute_state(self, parameters: dict[str, float], input_angle: float) -> MechanismState:
        if not isinstance(parameters, dict):
            parameters = {}
        crank = _positive_finite_float(parameters.get("crank_length", 80.0), 80.0)
        rod = max(crank + 1.0, _positive_finite_float(parameters.get("rod_length", 140.0), 140.0))

        theta = math.radians(_finite_float(input_angle, 0.0))
        crank_end = (crank * math.cos(theta), crank * math.sin(theta))

        inside = max(0.0, rod * rod - crank_end[1] * crank_end[1])
        slider_x = crank_end[0] + math.sqrt(inside)
        slider_pin = (slider_x, 0.0)

        warning = abs(crank_end[1]) > rod
        safety = (
            SafetyStatus(SafetyLevel.WARNING, "Rod too short for full stroke")
            if warning
            else SafetyStatus(SafetyLevel.SAFE, "Kinematics feasible")
        )

        return MechanismState(
            positions={
                "ground_pivot": (0.0, 0.0),
                "crank_end": crank_end,
                "slider_pin": slider_pin,
                "slider_center": slider_pin,
            },
            safety_status=safety,
            metadata={"crank_length": crank, "rod_length": rod},
        )


class MechanismFoundryView(QWidget):
    """Mechanism Foundry View - Interactive mechanism visualization and export."""

    # Signal emitted when user requests to export mechanism to Design tab
    # Carries: (mechanism_id: str, mechanism_type: str, parameters: dict, pivot_point: tuple)
    export_to_design_requested = pyqtSignal(str, str, dict, tuple)

    # Signal emitted when mechanism parameters change (for bidirectional sync)
    # Carries: (mechanism_id: str, mechanism_type: str, parameters: dict)
    mechanism_parameters_changed = pyqtSignal(str, str, dict)

    SIDE_PANEL_MIN_WIDTH = 220
    SIDE_PANEL_PREFERRED_WIDTH = 300
    SIDE_PANEL_MAX_WIDTH = 460
    INFO_PANEL_MIN_WIDTH = 240
    INFO_PANEL_PREFERRED_WIDTH = 340
    INFO_PANEL_MAX_WIDTH = 520
    OUTPUT_POINT_MODE_KEY = "output_point_mode"

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self.controller = MechanismFoundryController()
        self.current_mechanism: Mechanism | None = None
        self.current_parameters: dict[str, float] = {}
        self.current_angle: float = 30.0
        self._grid_system_enabled = True
        self._grid_cell_cm = 2.5
        self._grid_items: list[QGraphicsItem] = []
        self._parameter_specs_by_key: dict[str, ParameterSpec] = {}

        # Bidirectional sync: track mechanism ID shared with Design Tab
        self.synced_mechanism_id: str | None = None
        self._suppress_sync_signal: bool = False  # Prevent infinite loops

        self.fourbar_renderer = LinkageRenderer()
        self.render_config = RenderConfig(
            show_forces=True, show_labels=True, show_safety_zones=True
        )

        self.show_forces = True
        self.show_velocity = False
        self.show_trail = False
        self._last_rendered_state: MechanismState | None = None
        self._last_rendered_mechanism: Mechanism | None = None
        self._state_cache_valid = False
        self._last_safety_html: str | None = None

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
        self.sensemaking_service: SensemakingService = SensemakingService()
        self._last_sensemaking_context: SensemakingContext | None = None
        self._last_sensemaking_change: SensemakingParameterChange | None = None
        self._last_sensemaking_previous_positions: dict[str, object] | None = None

        # Cache for reusable visual items (performance optimization)
        # Dictionary mapping key -> QGraphicsItem
        self.visual_items_cache: dict[str, QGraphicsItem] = {}

        # Parameter debounce to avoid expensive renders during slider drag
        self._param_debounce_timer = QTimer()
        self._param_debounce_timer.setSingleShot(True)
        self._param_debounce_timer.setInterval(50)
        self._param_debounce_timer.timeout.connect(self._apply_pending_parameter)
        self._pending_param: tuple[str, float, QLabel, bool] | None = None

        self.gallery_view: GalleryView | None = None
        self.editor_widget: QWidget | None = None
        self.editor_splitter: QSplitter | None = None
        self.stacked_widget: QStackedWidget | None = None
        self.info_panel_container: QWidget | None = None
        self.info_panel: MechanismSensemakingPanel | None = None
        self.info_text = None  # Back-compat for tests expecting info_text attribute
        self.info_panel_action: QAction | None = None
        self.info_panel_collapsed: bool = True
        self.motion_modes_label: QLabel | None = None
        self.output_point_selector: QComboBox | None = None

        self._build_ui()

    @staticmethod
    def _normalize_mechanism_type_key(mechanism_type: str) -> str:
        """Normalize type strings received from catalog, Design tab, or tests."""
        return str(normalize_mechanism_type_key(mechanism_type))

    @classmethod
    def _to_controller_mechanism_type(cls, mechanism_type: str) -> str:
        """Normalize mechanism type aliases to controller configuration keys."""
        return str(canonical_mechanism_type(mechanism_type))

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
        self.editor_splitter = splitter
        splitter.setHandleWidth(8)
        splitter.setChildrenCollapsible(True)

        controls_widget = self._create_controls_panel()
        splitter.addWidget(controls_widget)

        viz_container = QWidget()
        viz_layout = QVBoxLayout(viz_container)
        viz_layout.setContentsMargins(0, 0, 0, 0)
        viz_layout.addWidget(self.graphics_view)
        splitter.addWidget(viz_container)

        info_panel = self._create_info_panel()
        self.info_panel_container = info_panel
        splitter.addWidget(info_panel)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 1)
        splitter.setCollapsible(0, True)
        splitter.setCollapsible(1, False)
        splitter.setCollapsible(2, True)
        splitter.setSizes([self.SIDE_PANEL_PREFERRED_WIDTH, 700, self.INFO_PANEL_PREFERRED_WIDTH])
        self._set_info_panel_collapsed(True)

        layout.addWidget(splitter)

        self._draw_grid()
        self._select_initial_mechanism()

        return widget

    def _on_gallery_mechanism_selected(self, mechanism_type: str) -> None:
        canonical_type = self._to_controller_mechanism_type(mechanism_type)
        if self.mechanism_selector:
            idx = self.mechanism_selector.findData(canonical_type)
            if idx >= 0:
                with blocked_signals(self.mechanism_selector):
                    self.mechanism_selector.setCurrentIndex(idx)
        self._load_mechanism(canonical_type)
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

        self.info_panel_action = QAction("🧠 Show Sensemaking", self)
        self.info_panel_action.setCheckable(True)
        self.info_panel_action.setChecked(False)
        self.info_panel_action.setToolTip(
            "Show or hide the explanation/sensemaking panel on the right"
        )
        self.info_panel_action.triggered.connect(self._toggle_info_panel)
        toolbar.addAction(self.info_panel_action)

        toolbar.addSeparator()

        reset_action = QAction("🔄 Reset", self)
        reset_action.triggered.connect(self._reset_animation)
        toolbar.addAction(reset_action)

        toolbar.addSeparator()

        export_action = QAction("📤 Add to Mechanism Tab", self)
        export_action.setToolTip(
            "Add this mechanism configuration to the Mechanism Tab for simulation"
        )
        export_action.triggered.connect(self._on_export_to_design)
        toolbar.addAction(export_action)

        return toolbar

    def _create_info_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMinimumWidth(self.INFO_PANEL_MIN_WIDTH)
        panel.setMaximumWidth(self.INFO_PANEL_MAX_WIDTH)
        panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        self.info_panel = MechanismSensemakingPanel(self.sensemaking_service)
        # Back-compat: expose underlying text widget for tests
        self.info_text = self.info_panel.legacy_text_display
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
        enabled = self.path_preview_action.isChecked()
        self.path_preview_overlay.set_enabled(enabled)
        if enabled:
            # Redraw immediately so toggle-on has visible feedback without extra user action.
            self._render_mechanism()

    def _toggle_info_panel(self, checked: bool = False) -> None:
        """Toggle the right sensemaking pane without destroying panel state."""
        self._set_info_panel_collapsed(not checked)

    def _set_info_panel_collapsed(self, collapsed: bool) -> None:
        """Collapse/expand the right pane while preserving its content model."""
        self.info_panel_collapsed = bool(collapsed)

        if self.info_panel_action is not None:
            old_blocked = self.info_panel_action.blockSignals(True)
            self.info_panel_action.setChecked(not self.info_panel_collapsed)
            self.info_panel_action.setText(
                "🧠 Show Sensemaking" if self.info_panel_collapsed else "🧠 Hide Sensemaking"
            )
            self.info_panel_action.blockSignals(old_blocked)

        if self.info_panel_container is not None:
            self.info_panel_container.setVisible(not self.info_panel_collapsed)

        if self.editor_splitter is None:
            return

        sizes = self.editor_splitter.sizes()
        left = sizes[0] if len(sizes) > 0 and sizes[0] > 0 else self.SIDE_PANEL_PREFERRED_WIDTH
        middle = sizes[1] if len(sizes) > 1 and sizes[1] > 0 else 700
        right = sizes[2] if len(sizes) > 2 and sizes[2] > 0 else self.INFO_PANEL_PREFERRED_WIDTH
        if self.info_panel_collapsed:
            self.editor_splitter.setSizes([left, middle + right, 0])
        else:
            self.editor_splitter.setSizes([left, max(400, middle), self.INFO_PANEL_PREFERRED_WIDTH])

    def _build_sync_payload_parameters(self) -> dict[str, object]:
        params: dict[str, object] = {}
        for raw_key, raw_value in self.current_parameters.items():
            key = str(raw_key).strip()
            if not key:
                continue
            if key == self.OUTPUT_POINT_MODE_KEY:
                output_mode = str(raw_value).strip() if isinstance(raw_value, str) else ""
                if output_mode:
                    params[key] = output_mode
                continue

            numeric_value = _finite_float(raw_value, math.nan)
            if math.isfinite(numeric_value):
                params[key] = numeric_value

        params["input_angle"] = _finite_float(self.current_angle, 0.0)
        params["grid_system_enabled"] = self._grid_system_enabled
        params["grid_cell_cm"] = _positive_finite_float(self._grid_cell_cm, 0.1, minimum=0.0)
        return params

    def _capture_export_snapshot(self) -> dict[str, object] | None:
        """Capture current rendered mechanism geometry for Design import fidelity."""
        if not self.current_mechanism:
            return None

        state = self._last_rendered_state
        if (
            not self._state_cache_valid
            or state is None
            or self._last_rendered_mechanism is not self.current_mechanism
        ):
            try:
                state = self.current_mechanism.compute_state(
                    self.current_parameters,
                    self.current_angle,
                )
            except Exception:
                return None

        if state is None:
            return None

        positions: dict[str, list[float]] = {}
        for key, value in state.positions.items():
            point = _finite_point_pair(value)
            if point is None:
                continue
            point_key = str(key).strip()
            if not point_key:
                continue
            positions[point_key] = [point[0], point[1]]

        if self.current_mechanism.mechanism_type == "fourbar":
            coupler_point = self._calculate_fourbar_coupler_point(state)
            finite_coupler_point = _finite_point_pair(coupler_point)
            if finite_coupler_point is not None:
                positions["coupler_point"] = [
                    finite_coupler_point[0],
                    finite_coupler_point[1],
                ]

        if not positions:
            return None

        return {
            "mechanism_type": str(self.current_mechanism.mechanism_type).strip(),
            "positions": positions,
        }

    def _on_export_to_design(self) -> None:
        """Export current mechanism configuration to Mechanism Design tab."""
        if not self.current_mechanism:
            return

        # Always export the actually loaded mechanism type, not stale selector UI state.
        mechanism_type = self._to_controller_mechanism_type(self.current_mechanism.mechanism_type)
        if not mechanism_type and self.mechanism_selector:
            mechanism_type = self.mechanism_selector.currentData()
        if not mechanism_type:
            return

        # Generate mechanism ID for bidirectional sync tracking
        import uuid

        mechanism_id = f"foundry_{uuid.uuid4().hex[:8]}"
        self.synced_mechanism_id = mechanism_id

        # Get current parameters + grid settings (copy to avoid mutation)
        parameters = self._build_sync_payload_parameters()
        export_snapshot = self._capture_export_snapshot()
        if export_snapshot:
            parameters["__foundry_snapshot__"] = export_snapshot

        # Default pivot at center of mechanism
        pivot_point = (0.0, 0.0)

        # Emit signal for main_window to route to Design tab (includes mechanism_id)
        self.export_to_design_requested.emit(mechanism_id, mechanism_type, parameters, pivot_point)

    def _create_controls_panel(self) -> QWidget:
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setMinimumWidth(self.SIDE_PANEL_MIN_WIDTH)
        scroll_area.setMaximumWidth(self.SIDE_PANEL_MAX_WIDTH)
        scroll_area.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        panel = QWidget()
        panel.setMinimumWidth(self.SIDE_PANEL_MIN_WIDTH - 20)
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

        output_point_row = QHBoxLayout()
        output_point_row.addWidget(QLabel("Motion Point:"))
        self.output_point_selector = QComboBox()
        self.output_point_selector.currentIndexChanged.connect(self._on_motion_point_mode_changed)
        output_point_row.addWidget(self.output_point_selector)
        animation_layout.addLayout(output_point_row)

        animation_group.setLayout(animation_layout)
        layout.addWidget(animation_group)

        display_group = QGroupBox("Display Options")
        display_layout = QVBoxLayout()
        self.motion_modes_label = QLabel("Motions: -")
        self.motion_modes_label.setTextFormat(Qt.TextFormat.PlainText)
        self.motion_modes_label.setWordWrap(True)
        self.motion_modes_label.setStyleSheet(
            """
            QLabel {
                color: #4f46e5;
                font-size: 12px;
                font-weight: 600;
                background-color: #eef2ff;
                border: 1px solid #c7d2fe;
                border-radius: 10px;
                padding: 6px 8px;
            }
            """
        )
        display_layout.addWidget(self.motion_modes_label)

        self.safety_label = QLabel("Status: Unknown")
        display_layout.addWidget(self.safety_label)
        display_group.setLayout(display_layout)
        layout.addWidget(display_group)

        layout.addStretch()

        scroll_area.setWidget(panel)
        return scroll_area

    def _populate_mechanism_selector(self) -> None:
        if self.mechanism_selector is None:
            return

        with blocked_signals(self.mechanism_selector):
            self.mechanism_selector.clear()
            for item in self.controller.list_mechanisms():
                self.mechanism_selector.addItem(item.display_name, item.mechanism_type)

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
        canonical_type = self._to_controller_mechanism_type(mechanism_type)

        if self.mechanism_selector:
            idx = self.mechanism_selector.findData(canonical_type)
            if idx >= 0 and self.mechanism_selector.currentIndex() != idx:
                with blocked_signals(self.mechanism_selector):
                    self.mechanism_selector.setCurrentIndex(idx)

        # Clear visual cache when switching mechanism types
        for item in self.visual_items_cache.values():
            if item.scene() == self.scene:
                self.scene.removeItem(item)
        self.visual_items_cache.clear()
        self._last_rendered_state = None
        self._last_rendered_mechanism = None
        self._state_cache_valid = False
        self._last_safety_html = None

        # Clear legacy items too just in case
        for item in list(self.scene.items()):
            if hasattr(item, "data") and item.data(0) == "mechanism_item":
                self.scene.removeItem(item)

        if canonical_type == "four_bar":
            self.current_mechanism = FourBarMechanism()
        elif canonical_type == "cam_follower":
            self.current_mechanism = CamFollowerMechanism()
        elif canonical_type == "gear_train":
            self.current_mechanism = _GearTrainPreviewMechanism()
        elif canonical_type == "slider_crank":
            self.current_mechanism = _SliderCrankPreviewMechanism()
        else:
            self.current_mechanism = None
            return

        config = self.controller.get_configuration(canonical_type)
        if not config:
            return

        self.current_parameters = config.initial_parameters()
        self._last_sensemaking_context = None
        self._last_sensemaking_change = None
        self._last_sensemaking_previous_positions = None
        self._refresh_motion_point_selector(canonical_type)
        self._rebuild_parameter_sliders(config.parameter_specs)
        self._update_info_panel(canonical_type, config, reset_change=True)
        self._render_mechanism()

    @staticmethod
    def _motion_point_options_for_mechanism(
        mechanism_type: str,
    ) -> list[tuple[str, str]]:
        options = SensemakingService.motion_point_options_for(mechanism_type)
        return [(option.label, option.value) for option in options]

    def _refresh_motion_point_selector(self, mechanism_type: str) -> None:
        if self.output_point_selector is None:
            return

        options = self._motion_point_options_for_mechanism(mechanism_type)
        selector = self.output_point_selector
        if not options:
            with blocked_signals(selector):
                selector.clear()
            selector.setEnabled(False)
            selector.setVisible(False)
            self.current_parameters.pop(self.OUTPUT_POINT_MODE_KEY, None)
            if self.info_panel is not None:
                self.info_panel.set_motion_point("preview trace")
            return

        selector.setEnabled(True)
        selector.setVisible(True)

        default_point = self.sensemaking_service.default_motion_point_for(mechanism_type)
        default_value = default_point.value if default_point else options[0][1]
        current_value = str(self.current_parameters.get(self.OUTPUT_POINT_MODE_KEY, default_value))
        if mechanism_type == "cam_follower" and current_value == "follower_end":
            current_value = "follower_base"

        with blocked_signals(selector):
            selector.clear()
            selected_index = 0
            for index, (label, value) in enumerate(options):
                selector.addItem(label, value)
                if value == current_value:
                    selected_index = index
            selector.setCurrentIndex(selected_index)

        selected_value = selector.currentData()
        if isinstance(selected_value, str) and selected_value:
            self.current_parameters[self.OUTPUT_POINT_MODE_KEY] = selected_value  # type: ignore[assignment]
            if self.info_panel is not None:
                self.info_panel.set_motion_point(selector.currentText())

    def _on_motion_point_mode_changed(self, index: int) -> None:
        if self.output_point_selector is None or index < 0:
            return

        value = self.output_point_selector.itemData(index)
        if not isinstance(value, str) or not value:
            return

        self.current_parameters[self.OUTPUT_POINT_MODE_KEY] = value  # type: ignore[assignment]
        if self.info_panel is not None:
            self.info_panel.set_motion_point(self.output_point_selector.currentText())
        self._state_cache_valid = False
        self._render_mechanism()

        if self.synced_mechanism_id and self.current_mechanism and not self._suppress_sync_signal:
            params = self._build_sync_payload_parameters()
            self.mechanism_parameters_changed.emit(
                self.synced_mechanism_id,
                self.current_mechanism.mechanism_type,
                params,
            )

    def _update_info_panel(
        self, mechanism_type: str, config: object, reset_change: bool = False
    ) -> None:
        content = self.content_loader.load_content(mechanism_type)
        if self.info_panel is not None:
            self.info_panel.set_content(content, mechanism_type, reset_change=reset_change)
        self._update_motion_modes(content)

    def _update_motion_modes(self, content: MechanismContent) -> None:
        if self.motion_modes_label is None:
            return

        raw_motions = getattr(content, "motions", ())
        motion_values: tuple[object, ...]
        if isinstance(raw_motions, str):
            motion_values = (raw_motions,)
        else:
            try:
                motion_values = tuple(raw_motions)
            except TypeError:
                motion_values = ()

        motions = [str(m).strip() for m in motion_values if str(m).strip()]
        if not motions:
            motions = ["Preview-based motion"]
        text = f"Motions: {' / '.join(motions[:6])}"
        if len(text) > 240:
            text = f"{text[:239]}…"
        self.motion_modes_label.setText(text)

    def _current_controller_mechanism_type(self) -> str:
        if self.current_mechanism is not None:
            return self._to_controller_mechanism_type(self.current_mechanism.mechanism_type)
        if self.mechanism_selector is not None:
            selected = self.mechanism_selector.currentData()
            if isinstance(selected, str):
                return self._to_controller_mechanism_type(selected)
        return "unknown"

    def _selected_motion_point_label(self) -> str:
        if self.output_point_selector is not None and self.output_point_selector.isVisible():
            text = self.output_point_selector.currentText().strip()
            if text:
                return text
        return "preview trace"

    def _selected_motion_point_key(self) -> str | None:
        if self.output_point_selector is None or not self.output_point_selector.isVisible():
            return None
        value = self.output_point_selector.currentData()
        return value if isinstance(value, str) and value else None

    def _display_parameter_label(self, spec: ParameterSpec | None, param_key: str) -> str:
        if spec is None:
            return param_key.replace("_", " ").title()
        label = spec.label.strip() or param_key.replace("_", " ").title()
        if spec.unit:
            suffix = f" ({spec.unit})"
            if label.endswith(suffix):
                label = label[: -len(suffix)]
        if label:
            label = label[0].upper() + label[1:].lower()
        return label

    def _format_parameter_value(self, param_key: str, value: object) -> str:
        spec = self._parameter_specs_by_key.get(param_key)
        unit = spec.unit if spec else None
        return str(SensemakingService.format_value(value, unit))

    def _update_sensemaking_parameter_change(
        self,
        param_key: str,
        before_value: object,
        after_value: object,
        previous_positions: dict[str, object] | None,
    ) -> None:
        if self.info_panel is None:
            return

        mechanism_type = self._current_controller_mechanism_type()
        spec = self._parameter_specs_by_key.get(param_key)
        change = SensemakingParameterChange(
            parameter_key=param_key,
            parameter_label=self._display_parameter_label(spec, param_key),
            before_value=self._format_parameter_value(param_key, before_value),
            after_value=self._format_parameter_value(param_key, after_value),
        )
        self._last_sensemaking_change = change
        self._last_sensemaking_previous_positions = previous_positions
        context = self._build_sensemaking_context(
            mechanism_type,
            change,
            previous_positions,
            geometry_pending=True,
        )
        self._last_sensemaking_context = context
        self.info_panel.set_context(context)

    def _refresh_sensemaking_context(self, mechanism_type: str | None = None) -> None:
        if self.info_panel is None:
            return

        current_type = mechanism_type or self._current_controller_mechanism_type()
        context = self._build_sensemaking_context(
            current_type,
            self._last_sensemaking_change,
            self._last_sensemaking_previous_positions,
            geometry_pending=False,
        )
        self._last_sensemaking_context = context
        self.info_panel.set_context(context)

    def _build_sensemaking_context(
        self,
        mechanism_type: str,
        change: SensemakingParameterChange | None,
        previous_positions: dict[str, object] | None,
        *,
        geometry_pending: bool = False,
    ) -> SensemakingContext:
        preview_snapshot = SensemakingPreviewSnapshot(
            current_parameters=self.current_parameters,
            current_positions=self._current_sensemaking_positions(),
            previous_positions=previous_positions,
            geometry_pending=geometry_pending,
        )
        return self.sensemaking_service.build_context(
            mechanism_type,
            selected_motion_point_key=self._selected_motion_point_key(),
            selected_motion_point_label=self._selected_motion_point_label(),
            parameter_change=change,
            preview_snapshot=preview_snapshot,
        )

    def _current_sensemaking_positions(self) -> dict[str, object] | None:
        state = self._last_rendered_state
        if state is None:
            return None
        return {str(key): value for key, value in state.positions.items()}

    def _rebuild_parameter_sliders(self, specs: tuple[ParameterSpec, ...]) -> None:
        for slider, label in self.parameter_sliders.values():
            slider.deleteLater()
            label.deleteLater()

        self.parameter_sliders.clear()
        self._parameter_specs_by_key = {}
        clear_layout(self.params_layout)

        for spec in specs:
            self._parameter_specs_by_key[spec.key] = spec
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

        self._apply_grid_snap_to_current_parameters()

    def _on_parameter_changed(
        self, param_key: str, value: float, label: QLabel, is_integer: bool = False
    ) -> None:
        """Queue parameter change with debounce. Label updates immediately."""
        adjusted_value = self._snap_parameter_value_if_needed(param_key, value)
        if adjusted_value != value and param_key in self.parameter_sliders:
            slider, _ = self.parameter_sliders[param_key]
            spec = self._parameter_specs_by_key.get(param_key)
            if spec and spec.step > 0:
                slider_value = int(round(adjusted_value / spec.step))
                with blocked_signals(slider):
                    slider.setValue(slider_value)

        previous_value = self.current_parameters.get(param_key)
        previous_positions = self._current_sensemaking_positions()
        self.current_parameters[param_key] = adjusted_value
        self._state_cache_valid = False
        if is_integer:
            label.setText(f"{int(adjusted_value)}")
        else:
            label.setText(f"{adjusted_value:.1f}")
        self._pending_param = (param_key, adjusted_value, label, is_integer)
        self._update_sensemaking_parameter_change(
            param_key,
            previous_value,
            adjusted_value,
            previous_positions,
        )
        self._param_debounce_timer.start()

    @property
    def _grid_step_mm(self) -> float:
        return max(0.1, _positive_finite_float(self._grid_cell_cm, 0.1) * 10.0)

    @staticmethod
    def _is_length_spec(spec: ParameterSpec | None) -> bool:
        if spec is None:
            return False
        unit = (spec.unit or "").strip().lower()
        return unit in {"mm", "millimeter", "millimeters"}

    def _snap_parameter_value_if_needed(self, param_key: str, value: float) -> float:
        spec = self._parameter_specs_by_key.get(param_key)
        default = _finite_float(spec.default_value, 0.0) if spec else 0.0
        raw_value = _finite_float(value, default)
        if not self._grid_system_enabled or not self._is_length_spec(spec):
            return raw_value

        step_mm = self._grid_step_mm
        if raw_value > 0.0:
            snapped_units = max(1, int((raw_value / step_mm) + 0.5))
            snapped = snapped_units * step_mm
        else:
            snapped = round(raw_value / step_mm) * step_mm

        if spec:
            min_value = _finite_float(spec.min_value, snapped)
            max_value = _finite_float(spec.max_value, snapped)
            if min_value > max_value:
                min_value, max_value = max_value, min_value
            snapped = min(max(snapped, min_value), max_value)
            if spec.is_integer:
                snapped = round(snapped)
        return float(snapped)

    def _apply_grid_snap_to_current_parameters(self) -> None:
        """Apply current grid snapping policy to all length parameters."""
        if not self._grid_system_enabled:
            return

        changed = False
        for key, spec in self._parameter_specs_by_key.items():
            if not self._is_length_spec(spec):
                continue

            current = self.current_parameters.get(key)
            if current is None:
                continue

            current_value = _finite_float(current, math.nan)
            if not math.isfinite(current_value):
                continue

            snapped = self._snap_parameter_value_if_needed(key, current_value)
            if abs(snapped - current_value) < 1e-6:
                continue

            self.current_parameters[key] = snapped
            changed = True

            if key in self.parameter_sliders and spec.step > 0:
                slider, label = self.parameter_sliders[key]
                slider_value = int(round(snapped / spec.step))
                with blocked_signals(slider):
                    slider.setValue(slider_value)
                if spec.is_integer:
                    label.setText(f"{int(snapped)}")
                else:
                    label.setText(f"{snapped:.1f}")

        if changed:
            self._state_cache_valid = False
            self._render_mechanism()

    def set_grid_system(self, enabled: bool, cell_cm: float) -> None:
        """Configure grid visibility and snapping in Foundry."""
        self._grid_system_enabled = bool(enabled)
        self._grid_cell_cm = _positive_finite_float(cell_cm, 0.1, minimum=0.0)
        self._draw_grid()
        self._apply_grid_snap_to_current_parameters()

    def _apply_pending_parameter(self) -> None:
        """Apply debounced parameter change."""
        self._render_mechanism()

        if self.current_mechanism:
            config_type = self._to_controller_mechanism_type(self.current_mechanism.mechanism_type)
            config = self.controller.get_configuration(config_type)
            if config:
                self._update_info_panel(config_type, config)
            self._refresh_sensemaking_context(config_type)

            # Emit sync signal if we have a synced mechanism (bidirectional sync)
            if self.synced_mechanism_id and not self._suppress_sync_signal:
                params = self._build_sync_payload_parameters()
                self.mechanism_parameters_changed.emit(
                    self.synced_mechanism_id,
                    self.current_mechanism.mechanism_type,
                    params,
                )

    def _on_angle_changed(self, value: int) -> None:
        self.current_angle = float(value)
        self.angle_label.setText(f"{value}°")
        self._state_cache_valid = False
        self._render_mechanism()

        # Emit sync signal for angle change (bidirectional sync)
        if self.synced_mechanism_id and self.current_mechanism and not self._suppress_sync_signal:
            params = self._build_sync_payload_parameters()
            self.mechanism_parameters_changed.emit(
                self.synced_mechanism_id,
                self.current_mechanism.mechanism_type,
                params,
            )

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
        with blocked_signals(self.angle_slider):
            self.angle_slider.setValue(int(self.current_angle))
        self.angle_label.setText(f"{int(self.current_angle)}°")
        self._render_mechanism()

    def _render_mechanism(self) -> None:
        if not self.current_mechanism:
            self._last_rendered_state = None
            self._last_rendered_mechanism = None
            self._state_cache_valid = False
            return

        # Optimization: Only clear items if mechanism type changed or explicit reset needed
        # For simple parameter updates, we reuse the items via the cache.
        # However, to be safe against topology changes, we rely on the renderer's update logic.
        # We NO LONGER clear the scene every frame.

        try:
            state = self.current_mechanism.compute_state(
                self.current_parameters, self.current_angle
            )
            self._last_rendered_state = state
            self._last_rendered_mechanism = self.current_mechanism
            self._state_cache_valid = True
            self._draw_mechanism_state(state)
            self._update_safety_display(state)
            self._refresh_sensemaking_context()
        except Exception as e:
            self._last_rendered_state = None
            self._last_rendered_mechanism = None
            self._state_cache_valid = False
            self._last_safety_html = None
            self.safety_label.setText(f"Error: {str(e)}")

    def _draw_mechanism_state(self, state: MechanismState) -> None:
        mechanism_type = self.current_mechanism.mechanism_type if self.current_mechanism else None

        if mechanism_type == "fourbar":
            # Use optimized update_scene method
            self.fourbar_renderer.update_scene(
                state, self.scene, self.render_config, self.visual_items_cache
            )
            self._update_fourbar_coupler_visual(state)
            self._show_default_paths(state)
        elif mechanism_type == "cam_follower":
            self._draw_cam_mechanism_optimized(state)
        elif mechanism_type == "gear_train":
            self._draw_gear_mechanism_optimized(state)
        elif mechanism_type == "slider_crank":
            self._draw_slider_crank_mechanism_optimized(state)

    def _calculate_fourbar_coupler_point(
        self,
        state: MechanismState,
    ) -> tuple[float, float] | None:
        positions = state.positions
        a = positions.get("A")
        b = positions.get("B")
        if (
            not isinstance(a, list | tuple)
            or len(a) < 2
            or not isinstance(b, list | tuple)
            or len(b) < 2
        ):
            return None

        try:
            p3x, p3y = float(a[0]), float(a[1])
            p4x, p4y = float(b[0]), float(b[1])
        except (TypeError, ValueError):
            return None

        coupler_x = self.current_parameters.get("coupler_point_x")
        coupler_y = self.current_parameters.get("coupler_point_y")
        if coupler_x is None:
            coupler_x = self.current_parameters.get("p_x", 0.0)
        if coupler_y is None:
            coupler_y = self.current_parameters.get("p_y", 0.0)
        try:
            cp_x = float(coupler_x)
            cp_y = float(coupler_y)
        except (TypeError, ValueError):
            cp_x = 0.0
            cp_y = 0.0

        dx = p4x - p3x
        dy = p4y - p3y
        link_length = math.hypot(dx, dy)
        if link_length <= 1e-9:
            return (p3x, p3y)

        unit_x = dx / link_length
        unit_y = dy / link_length
        normal_x = -unit_y
        normal_y = unit_x
        return (
            p3x + cp_x * unit_x + cp_y * normal_x,
            p3y + cp_x * unit_y + cp_y * normal_y,
        )

    def _update_fourbar_coupler_visual(self, state: MechanismState) -> None:
        positions = state.positions
        a = positions.get("A")
        b = positions.get("B")
        coupler = self._calculate_fourbar_coupler_point(state)
        if (
            not isinstance(a, list | tuple)
            or len(a) < 2
            or not isinstance(b, list | tuple)
            or len(b) < 2
            or coupler is None
        ):
            return

        p3 = QPointF(float(a[0]), float(a[1]))
        p4 = QPointF(float(b[0]), float(b[1]))
        p_c = QPointF(coupler[0], coupler[1])

        # Same semantics as Design tab: if coupler point is collinear, render only line.
        area = (
            abs(
                p3.x() * (p4.y() - p_c.y())
                + p4.x() * (p_c.y() - p3.y())
                + p_c.x() * (p3.y() - p4.y())
            )
            * 0.5
        )

        cache = self.visual_items_cache
        triangle_key = "fourbar_coupler_triangle"
        marker_key = "fourbar_coupler_point"

        if area > 1e-3:
            triangle = QPolygonF([p3, p4, p_c])
            if triangle_key not in cache:
                item = self.scene.addPolygon(
                    triangle,
                    QPen(QColor("#5dade2"), 2),
                    QBrush(QColor(124, 252, 176, 150)),
                )
                item.setZValue(8.0)
                item.setData(0, "mechanism_item")
                cache[triangle_key] = item
            else:
                cache[triangle_key].setPolygon(triangle)
                cache[triangle_key].setVisible(True)
        elif triangle_key in cache:
            cache[triangle_key].setVisible(False)

        if marker_key not in cache:
            marker = self.scene.addEllipse(
                p_c.x() - 5.0,
                p_c.y() - 5.0,
                10.0,
                10.0,
                QPen(QColor("#1e8449"), 2),
                QBrush(QColor("#27ae60")),
            )
            marker.setZValue(11.0)
            marker.setData(0, "mechanism_item")
            cache[marker_key] = marker
        else:
            marker = cache[marker_key]
            marker.setRect(p_c.x() - 5.0, p_c.y() - 5.0, 10.0, 10.0)
            marker.setVisible(True)

    def _draw_cam_mechanism_optimized(self, state: MechanismState) -> None:
        """Optimized drawing for Cam mechanism using item caching."""
        positions = state.positions
        cam_center = positions.get("cam_center", (0, 0))
        contact_point = positions.get("contact_point", (0, 0))
        follower_base = positions.get("follower_base", (0, 0))
        follower_end = positions.get("follower_end", (0, 0))

        cache = self.visual_items_cache

        # 1. Cam Profile
        cam_profile = state.metadata.get("cam_profile", [])
        if cam_profile:
            cam_pen = QPen(QColor(70, 130, 180), 3)
            # Reusing lines for cam profile is tricky because point count might change
            # But for a fixed resolution profile, we can reuse.
            # Simpler approach for now: Group profile as a Path or Polygon if possible,
            # or just manage lines dynamically.
            # Given cam profile rotates, a QGraphicsPolygonItem is better than many lines.

            poly_points = [QPointF(x, y) for x, y in cam_profile]
            if poly_points:
                polygon = QPolygonF(poly_points)
                if "cam_poly" not in cache:
                    item = self.scene.addPolygon(
                        polygon, cam_pen, QBrush(QColor(70, 130, 180, 100))
                    )
                    item.setData(0, "mechanism_item")
                    cache["cam_poly"] = item
                else:
                    cache["cam_poly"].setPolygon(polygon)

        # 2. Cam Center
        if "cam_center" not in cache:
            item = self.scene.addEllipse(
                0, 0, 16, 16, QPen(QColor(255, 0, 0), 2), QBrush(QColor(255, 100, 100))
            )
            item.setData(0, "mechanism_item")
            cache["cam_center"] = item
        cache["cam_center"].setRect(cam_center[0] - 8, cam_center[1] - 8, 16, 16)

        # 3. Contact Point
        if "contact_pt" not in cache:
            item = self.scene.addEllipse(
                0, 0, 10, 10, QPen(QColor(220, 20, 60), 3), QBrush(QColor(220, 20, 60))
            )
            item.setData(0, "mechanism_item")
            cache["contact_pt"] = item
        cache["contact_pt"].setRect(contact_point[0] - 5, contact_point[1] - 5, 10, 10)

        # 4. Follower Line (Rod)
        if "follower_rod" not in cache:
            item = self.scene.addLine(0, 0, 0, 0, QPen(QColor(80, 80, 80), 6))
            item.setData(0, "mechanism_item")
            cache["follower_rod"] = item
        cache["follower_rod"].setLine(
            float(follower_base[0]),
            float(follower_base[1]),
            float(follower_end[0]),
            float(follower_end[1]),
        )

        # 5. Follower Head
        follower_width, follower_height = 30, 15
        if "follower_head" not in cache:
            item = self.scene.addRect(
                0,
                0,
                follower_width,
                follower_height,
                QPen(QColor(50, 50, 50), 2),
                QBrush(QColor(120, 120, 120)),
            )
            item.setData(0, "mechanism_item")
            cache["follower_head"] = item
        cache["follower_head"].setRect(
            follower_end[0] - follower_width / 2,
            follower_end[1] - follower_height / 2,
            follower_width,
            follower_height,
        )

        # 6. Guide Line
        if "guide_line" not in cache:
            guide_pen = QPen(QColor(150, 150, 150), 2, Qt.PenStyle.DashLine)
            item = self.scene.addLine(0, 0, 0, 0, guide_pen)
            item.setData(0, "mechanism_item")
            cache["guide_line"] = item
        cache["guide_line"].setLine(
            float(follower_base[0]),
            float(follower_base[1] - 50),
            float(follower_base[0]),
            float(cam_center[1] + 150),
        )

        # 7. Base Rect
        base_width, base_height = 60, 30
        if "base_rect" not in cache:
            item = self.scene.addRect(
                0,
                0,
                base_width,
                base_height,
                QPen(QColor(80, 80, 80), 3),
                QBrush(QColor(100, 100, 100)),
            )
            item.setData(0, "mechanism_item")
            cache["base_rect"] = item
        cache["base_rect"].setRect(
            follower_base[0] - base_width / 2,
            follower_base[1] - base_height / 2,
            base_width,
            base_height,
        )

    def _draw_gear_mechanism_optimized(self, state: MechanismState) -> None:
        """Optimized drawing for gear train preview using item caching."""
        positions = state.positions
        metadata = state.metadata or {}
        cache = self.visual_items_cache

        g1 = positions.get("gear1_center", (-60.0, 0.0))
        g2 = positions.get("gear2_center", (60.0, 0.0))
        p1 = positions.get("gear1_indicator_end", (g1[0] + 30.0, g1[1]))
        p2 = positions.get("gear2_indicator_end", (g2[0] + 45.0, g2[1]))

        r1 = float(metadata.get("r1", 30.0))
        r2 = float(metadata.get("r2", 45.0))

        if "gear1_body" not in cache:
            item = self.scene.addEllipse(
                0, 0, 1, 1, QPen(QColor("#1f77b4"), 3), QBrush(QColor("#9ecae1"))
            )
            item.setData(0, "mechanism_item")
            cache["gear1_body"] = item
        cache["gear1_body"].setRect(g1[0] - r1, g1[1] - r1, r1 * 2.0, r1 * 2.0)

        if "gear2_body" not in cache:
            item = self.scene.addEllipse(
                0, 0, 1, 1, QPen(QColor("#2ca02c"), 3), QBrush(QColor("#b5e7a0"))
            )
            item.setData(0, "mechanism_item")
            cache["gear2_body"] = item
        cache["gear2_body"].setRect(g2[0] - r2, g2[1] - r2, r2 * 2.0, r2 * 2.0)

        if "gear1_indicator" not in cache:
            item = self.scene.addLine(0, 0, 0, 0, QPen(QColor("#ffffff"), 2))
            item.setData(0, "mechanism_item")
            cache["gear1_indicator"] = item
        cache["gear1_indicator"].setLine(g1[0], g1[1], p1[0], p1[1])

        if "gear2_indicator" not in cache:
            item = self.scene.addLine(0, 0, 0, 0, QPen(QColor("#ffffff"), 2))
            item.setData(0, "mechanism_item")
            cache["gear2_indicator"] = item
        cache["gear2_indicator"].setLine(g2[0], g2[1], p2[0], p2[1])

        if "gear_mesh_line" not in cache:
            mesh_pen = QPen(QColor(120, 120, 120), 1, Qt.PenStyle.DashLine)
            item = self.scene.addLine(0, 0, 0, 0, mesh_pen)
            item.setData(0, "mechanism_item")
            cache["gear_mesh_line"] = item
        cache["gear_mesh_line"].setLine(g1[0], g1[1], g2[0], g2[1])

    def _draw_slider_crank_mechanism_optimized(self, state: MechanismState) -> None:
        """Optimized drawing for slider-crank preview using item caching."""
        positions = state.positions
        cache = self.visual_items_cache

        ground = positions.get("ground_pivot", (0.0, 0.0))
        crank_end = positions.get("crank_end", (80.0, 0.0))
        slider_pin = positions.get("slider_pin", (180.0, 0.0))
        slider_center = positions.get("slider_center", slider_pin)

        if "slider_guide" not in cache:
            guide_pen = QPen(QColor(130, 130, 130), 2, Qt.PenStyle.DashLine)
            item = self.scene.addLine(-260, 0, 260, 0, guide_pen)
            item.setData(0, "mechanism_item")
            cache["slider_guide"] = item

        if "crank_link" not in cache:
            item = self.scene.addLine(0, 0, 0, 0, QPen(QColor("#1f77b4"), 4))
            item.setData(0, "mechanism_item")
            cache["crank_link"] = item
        cache["crank_link"].setLine(ground[0], ground[1], crank_end[0], crank_end[1])

        if "rod_link" not in cache:
            item = self.scene.addLine(0, 0, 0, 0, QPen(QColor("#ff7f0e"), 4))
            item.setData(0, "mechanism_item")
            cache["rod_link"] = item
        cache["rod_link"].setLine(crank_end[0], crank_end[1], slider_pin[0], slider_pin[1])

        if "ground_pivot" not in cache:
            item = self.scene.addEllipse(
                0, 0, 1, 1, QPen(QColor(40, 40, 40), 2), QBrush(QColor(110, 110, 110))
            )
            item.setData(0, "mechanism_item")
            cache["ground_pivot"] = item
        cache["ground_pivot"].setRect(ground[0] - 7, ground[1] - 7, 14, 14)

        if "crank_pin" not in cache:
            item = self.scene.addEllipse(
                0, 0, 1, 1, QPen(QColor(40, 40, 40), 2), QBrush(QColor(220, 120, 80))
            )
            item.setData(0, "mechanism_item")
            cache["crank_pin"] = item
        cache["crank_pin"].setRect(crank_end[0] - 6, crank_end[1] - 6, 12, 12)

        if "slider_block" not in cache:
            item = self.scene.addRect(
                0, 0, 1, 1, QPen(QColor(40, 40, 40), 2), QBrush(QColor(180, 180, 180))
            )
            item.setData(0, "mechanism_item")
            cache["slider_block"] = item
        cache["slider_block"].setRect(slider_center[0] - 18, slider_center[1] - 12, 36, 24)

    def _draw_mechanism_state_legacy(self, state: MechanismState) -> None:
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

        safety_html = f"<span style='color:{color}'>{prefix} {safety.message}</span>"
        if safety_html == self._last_safety_html:
            return
        self._last_safety_html = safety_html
        self.safety_label.setText(safety_html)
        if self.info_panel is not None:
            self.info_panel.set_safety_status(f"{prefix} {safety.message}", level.name.lower())

    def _draw_grid(self) -> None:
        for item in self._grid_items:
            if item.scene() == self.scene:
                self.scene.removeItem(item)
        self._grid_items.clear()

        if not self._grid_system_enabled:
            return

        cell_grid = max(1, int(round(self._grid_step_mm)))
        major_interval = max(1, int(round(100.0 / cell_grid)))
        minor_color = QColor(190, 190, 190, 75)
        major_color = QColor(145, 145, 145, 120)
        axis_color = QColor(100, 100, 100, 200)

        rect = self.scene.sceneRect()
        minor_pen = QPen(minor_color, 1, Qt.PenStyle.SolidLine)
        major_pen = QPen(major_color, 1, Qt.PenStyle.SolidLine)

        start_x = int(rect.left() // cell_grid) * cell_grid
        end_x = int(rect.right()) + cell_grid
        index_x = 0
        for x in range(start_x, end_x, cell_grid):
            pen = major_pen if index_x % major_interval == 0 else minor_pen
            line = self.scene.addLine(x, rect.top(), x, rect.bottom(), pen)
            line.setZValue(-99)
            self._grid_items.append(line)
            index_x += 1

        start_y = int(rect.top() // cell_grid) * cell_grid
        end_y = int(rect.bottom()) + cell_grid
        index_y = 0
        for y in range(start_y, end_y, cell_grid):
            pen = major_pen if index_y % major_interval == 0 else minor_pen
            line = self.scene.addLine(rect.left(), y, rect.right(), y, pen)
            line.setZValue(-99)
            self._grid_items.append(line)
            index_y += 1

        axis_pen = QPen(axis_color, 2, Qt.PenStyle.SolidLine)
        x_axis = self.scene.addLine(rect.left(), 0, rect.right(), 0, axis_pen)
        y_axis = self.scene.addLine(0, rect.top(), 0, rect.bottom(), axis_pen)
        x_axis.setZValue(-98)
        y_axis.setZValue(-98)
        self._grid_items.extend([x_axis, y_axis])

        origin = self.scene.addEllipse(-3, -3, 6, 6, axis_pen, QBrush(axis_color))
        origin.setZValue(-97)
        self._grid_items.append(origin)

    def _show_default_paths(self, state: MechanismState) -> None:
        """Show default paths for all tracked points."""
        if not self.current_mechanism or not self.path_preview_overlay.enabled:
            return

        mechanism_type = self.current_mechanism.mechanism_type
        if mechanism_type == "fourbar":
            default_points = ["A", "B"]
        elif mechanism_type == "cam_follower":
            default_points = ["follower_base", "contact_point"]
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
        threshold_sq = threshold * threshold

        if not self.current_mechanism:
            return None

        state = self._last_rendered_state
        if (
            not self._state_cache_valid
            or state is None
            or self._last_rendered_mechanism is not self.current_mechanism
        ):
            try:
                state = self.current_mechanism.compute_state(
                    self.current_parameters, self.current_angle
                )
            except Exception:
                return None
            self._last_rendered_state = state
            self._last_rendered_mechanism = self.current_mechanism
            self._state_cache_valid = True

        mechanism_type = self.current_mechanism.mechanism_type

        if mechanism_type == "fourbar":
            test_points = ["A", "B"]
        elif mechanism_type == "cam_follower":
            test_points = ["follower_base", "contact_point"]
        else:
            return None

        for point_name in test_points:
            position = state.positions.get(point_name)
            if position:
                px, py = position
                dx = scene_pos.x() - px
                dy = scene_pos.y() - py
                if (dx * dx + dy * dy) < threshold_sq:
                    return point_name

        return None

    # --- Bidirectional Sync Methods ---

    def _map_design_params_to_foundry(
        self,
        mechanism_type: str,
        parameters: dict,
    ) -> dict[str, object]:
        """Map Design-tab parameter schema to Foundry parameter schema."""
        mapped: dict[str, object] = {}
        if not isinstance(parameters, dict):
            return mapped

        def _pick_float(*keys: str) -> float | None:
            for key in keys:
                if key in parameters:
                    value = _finite_float(parameters[key], math.nan)
                    if not math.isfinite(value):
                        continue
                    return value
            return None

        mechanism_type = canonical_mechanism_type(mechanism_type)

        if mechanism_type == "four_bar":
            ground_link = _pick_float("l1", "L1")
            if ground_link is not None:
                mapped["ground_link"] = ground_link

            input_link = _pick_float("l2", "L2")
            if input_link is not None:
                mapped["input_link"] = input_link

            coupler_link = _pick_float("l3", "L3")
            if coupler_link is not None:
                mapped["coupler_link"] = coupler_link

            output_link = _pick_float("l4", "L4")
            if output_link is not None:
                mapped["output_link"] = output_link

            input_angle = _pick_float("input_angle", "crank_angle")
            if input_angle is not None:
                mapped["input_angle"] = input_angle

        elif mechanism_type == "cam_follower":
            cam_radius = _pick_float("base_radius")
            if cam_radius is not None:
                mapped["cam_radius"] = cam_radius
            cam_offset = _pick_float("eccentricity")
            if cam_offset is not None:
                mapped["cam_offset"] = cam_offset
            follower_length = _pick_float("follower_rod_length")
            if follower_length is not None:
                mapped["follower_length"] = follower_length
            cam_lobes = _pick_float("cam_lobes")
            if cam_lobes is not None:
                mapped["cam_lobes"] = cam_lobes
            profile_harmonic = _pick_float("profile_harmonic")
            if profile_harmonic is not None:
                mapped["profile_harmonic"] = profile_harmonic
            input_angle = _pick_float("input_angle")
            if input_angle is not None:
                mapped["input_angle"] = input_angle

        elif mechanism_type == "gear_train":
            # Prefer live radii from Design editing over stale tooth-count params.
            gear1_radius = _pick_float("gear1_radius", "r1")
            if gear1_radius is not None and gear1_radius > 0.0:
                mapped["gear1_teeth"] = float(round(gear1_radius / 3.0))
            else:
                gear1_teeth = _pick_float("gear1_teeth")
                if gear1_teeth is not None:
                    mapped["gear1_teeth"] = gear1_teeth

            gear2_radius = _pick_float("gear2_radius", "r2")
            if gear2_radius is not None and gear2_radius > 0.0:
                mapped["gear2_teeth"] = float(round(gear2_radius / 3.0))
            else:
                gear2_teeth = _pick_float("gear2_teeth")
                if gear2_teeth is not None:
                    mapped["gear2_teeth"] = gear2_teeth

            input_torque = _pick_float("input_torque")
            if input_torque is not None:
                mapped["input_torque"] = input_torque
            input_angle = _pick_float("input_angle")
            if input_angle is not None:
                mapped["input_angle"] = input_angle

        elif mechanism_type == "slider_crank":
            crank_length = _pick_float("crank_length", "l2")
            if crank_length is not None:
                mapped["crank_length"] = crank_length

            rod_length = _pick_float("rod_length", "l3", "l4")
            if rod_length is not None:
                mapped["rod_length"] = rod_length

            input_angle = _pick_float("input_angle", "crank_angle")
            if input_angle is not None:
                mapped["input_angle"] = input_angle

        if self.OUTPUT_POINT_MODE_KEY in parameters:
            mode = parameters.get(self.OUTPUT_POINT_MODE_KEY)
            if isinstance(mode, str) and mode:
                normalized_mode = mode.strip().lower()
                if mechanism_type == "cam_follower" and normalized_mode == "follower_end":
                    mapped[self.OUTPUT_POINT_MODE_KEY] = "follower_base"
                else:
                    mapped[self.OUTPUT_POINT_MODE_KEY] = normalized_mode

        # Pass through already-compatible keys.
        for key, value in parameters.items():
            if key in self.current_parameters and key not in mapped:
                numeric_value = _finite_float(value, math.nan)
                if not math.isfinite(numeric_value):
                    continue
                mapped[key] = numeric_value

        return mapped

    def update_from_design_tab(self, mechanism_id: str, parameters: dict) -> None:
        """Update Foundry view from Design Tab changes (bidirectional sync).

        Called when mechanism parameters are modified in Design Tab.
        Updates sliders and preview without emitting change signals back.

        Args:
            mechanism_id: The shared mechanism ID
            parameters: Updated parameters from Design Tab
        """
        # Only update if this is our synced mechanism
        if mechanism_id != self.synced_mechanism_id:
            return
        if not isinstance(parameters, dict):
            return

        # Suppress signal emission to prevent infinite loop
        self._suppress_sync_signal = True
        try:
            mechanism_type = self.current_mechanism.mechanism_type if self.current_mechanism else ""
            try:
                mapped_params = self._map_design_params_to_foundry(mechanism_type, parameters)
            except Exception:
                mapped_params = {}

            angle_value = mapped_params.get("input_angle")
            angle_number = _finite_float(angle_value, math.nan)
            if not math.isfinite(angle_number):
                if "input_angle" in parameters:
                    angle_number = _finite_float(parameters["input_angle"], math.nan)
                elif "crank_angle" in parameters:
                    angle_number = _finite_float(parameters["crank_angle"], math.nan)

            if math.isfinite(angle_number):
                self.current_angle = angle_number % 360.0
                with blocked_signals(self.angle_slider):
                    self.angle_slider.setValue(int(self.current_angle))
                self.angle_label.setText(f"{int(self.current_angle)}°")

            config = None
            if self.current_mechanism:
                config_type = self._to_controller_mechanism_type(
                    self.current_mechanism.mechanism_type
                )
                config = self.controller.get_configuration(config_type)

            # Update current parameters and slider UI.
            for key, value in mapped_params.items():
                if key == "input_angle":
                    continue

                if key == self.OUTPUT_POINT_MODE_KEY:
                    if isinstance(value, str) and value:
                        self.current_parameters[key] = value  # type: ignore[assignment]
                        if self.current_mechanism:
                            canonical_type = self._to_controller_mechanism_type(
                                self.current_mechanism.mechanism_type
                            )
                            self._refresh_motion_point_selector(canonical_type)
                    continue

                if key not in self.current_parameters:
                    continue

                value_number = _finite_float(value, math.nan)
                if not math.isfinite(value_number):
                    continue

                adjusted_value = self._snap_parameter_value_if_needed(key, value_number)
                self.current_parameters[key] = adjusted_value
                if key in self.parameter_sliders and config:
                    slider, label = self.parameter_sliders[key]
                    for spec in config.parameter_specs:
                        if spec.key == key:
                            with blocked_signals(slider):
                                slider.setValue(int(round(adjusted_value / spec.step)))
                            if spec.is_integer:
                                label.setText(f"{int(adjusted_value)}")
                            else:
                                label.setText(f"{adjusted_value:.1f}")
                            break

            # Re-render mechanism with updated parameters
            self._render_mechanism()

        finally:
            self._suppress_sync_signal = False

    def set_synced_mechanism(self, mechanism_id: str, mechanism_type: str) -> None:
        """Set the currently synced mechanism from Design Tab.

        Called when a mechanism is selected in Design Tab that originated from Foundry.

        Args:
            mechanism_id: The shared mechanism ID
            mechanism_type: The mechanism type (e.g., "four_bar", "cam_follower")
        """
        self.synced_mechanism_id = mechanism_id

        selector_type = canonical_mechanism_type(mechanism_type)

        current_selector_type = ""
        if self.current_mechanism:
            current_selector_type = canonical_mechanism_type(self.current_mechanism.mechanism_type)

        if current_selector_type != selector_type:
            self._load_mechanism(selector_type)

    def clear_synced_mechanism(self) -> None:
        """Clear the synced mechanism reference."""
        self.synced_mechanism_id = None
