"""
Mechanism Foundry View - Clean UI for interactive mechanism visualization
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, SupportsFloat, SupportsIndex, TypeVar, cast

from PyQt6.QtCore import QEvent, QObject, QPoint, QPointF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QBrush, QColor, QMouseEvent, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QComboBox,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPathItem,
    QGraphicsPolygonItem,
    QGraphicsRectItem,
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
    select_angle_bounds,
)
from automataii.application.mechanism_foundry.mechanism_types import (
    canonical_mechanism_type,
    normalize_mechanism_type_key,
)
from automataii.presentation.qt.animation import ViewportConfig, ViewportController
from automataii.presentation.qt.gear_rendering import (
    annulus_path,
    gear_attachment_hole_centers,
    gear_grid_attachment_hole_centers,
    gear_hole_radius,
    gear_outline_polygon,
    radial_tick_lines,
)
from automataii.presentation.qt.shared import blocked_signals, clear_layout
from automataii.presentation.qt.tabs.mechanism_foundry.gallery_view import GalleryView
from automataii.presentation.qt.tabs.mechanism_foundry.sensemaking_panel import (
    MechanismSensemakingPanel,
)
from automataii.shared.fabrication_assembly import (
    BOARD_COLUMNS,
    BOARD_ROWS,
    BoardCoord,
    board_coord_to_centered_mm,
)
from automataii.shared.physical_kit import (
    DEFAULT_GRID_CELL_CM,
    DEFAULT_PHYSICAL_KIT_PROFILE,
    CamPreset,
    PhysicalKitContext,
    PhysicalKitProfile,
    freeform_gear_radius_for_teeth,
    freeform_gear_teeth_for_radius,
    gear_center_distance,
    gear_pair_from_params,
    gear_radius_for_teeth,
    gear_teeth_for_radius,
    gear_teeth_from_params,
    grid_enabled_from_params,
    grid_step_mm,
    nearest_gear_teeth,
    nearest_pitch_choice,
    physical_context_from_params,
    physical_context_from_settings,
    physical_profile_from_params,
    snap_parameter_value,
    snap_physical_params,
)
from automataii.shared.physical_kit import (
    finite_float as physical_finite_float,
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
_GraphicsItemT = TypeVar("_GraphicsItemT", bound=QGraphicsItem)


def _require_graphics_item(item: _GraphicsItemT | None) -> _GraphicsItemT:
    """Narrow PyQt scene factory return types; Qt returns an item at runtime."""
    assert item is not None
    return item


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

    @staticmethod
    def _freeform_pair_from_params(
        parameters: dict[str, float],
        profile: PhysicalKitProfile,
    ) -> tuple[int, float, int, float]:
        teeth1 = gear_teeth_from_params(
            parameters,
            ("gear1_teeth",),
            ("gear1_radius", "r1"),
            16,
            enabled=False,
            profile=profile,
        )
        teeth2 = gear_teeth_from_params(
            parameters,
            ("gear2_teeth",),
            ("gear2_radius", "r2"),
            24,
            enabled=False,
            profile=profile,
        )
        return (
            teeth1,
            freeform_gear_radius_for_teeth(teeth1, profile=profile),
            teeth2,
            freeform_gear_radius_for_teeth(teeth2, profile=profile),
        )

    def compute_state(self, parameters: dict[str, float], input_angle: float) -> MechanismState:
        if not isinstance(parameters, dict):
            parameters = {}
        profile = physical_profile_from_params(parameters)
        grid_enabled = grid_enabled_from_params(parameters)
        raw_has_linkage = bool(parameters.get("gear_linkage_enabled")) or any(
            key in parameters for key in ("linkage_arm_length", "linkage_pin_radius")
        )
        if grid_enabled:
            parameters = snap_physical_params(
                "gear_linkage" if raw_has_linkage else "gear_train",
                parameters,
                parameters.get("grid_cell_cm", DEFAULT_GRID_CELL_CM),
                enabled=True,
                profile=profile,
            )
        if grid_enabled:
            teeth1, r1, teeth2, r2 = gear_pair_from_params(parameters, profile=profile)
        else:
            teeth1, r1, teeth2, r2 = self._freeform_pair_from_params(parameters, profile)
        clearance = parameters.get("gear_clearance", parameters.get("mesh_clearance"))
        clearance_mm = _finite_float(clearance, profile.default_gear_clearance_mm)
        center_distance = gear_center_distance(r1, r2, clearance_mm, profile=profile)
        grid_pitch = grid_step_mm(parameters.get("grid_cell_cm", DEFAULT_GRID_CELL_CM))

        g1 = (-center_distance / 2.0, 0.0)
        g2 = (center_distance / 2.0, 0.0)
        board_coords: dict[str, str] = {}
        if grid_enabled and grid_pitch > 0.0:
            distance_cells = center_distance / grid_pitch
            rounded_cells = int(round(distance_cells))
            anchor_label = "I6" if raw_has_linkage else "H6"
            anchor_coord = BoardCoord.from_label(anchor_label)
            driven_column = anchor_coord.column + rounded_cells
            if (
                math.isclose(distance_cells, rounded_cells, abs_tol=1e-6)
                and driven_column in BOARD_COLUMNS
            ):
                driven_label = f"{anchor_coord.row}{driven_column}"
                g1 = board_coord_to_centered_mm(anchor_label, grid_pitch)
                g2 = board_coord_to_centered_mm(driven_label, grid_pitch)
                board_coords = {
                    "gear1_center": anchor_label,
                    "gear2_center": driven_label,
                }

        theta1 = math.radians(_finite_float(input_angle, 0.0))
        # External gears counter-rotate.  Add a half-tooth phase on the driven
        # gear so the stylized tooth polygon visually interlocks instead of
        # tooth-on-tooth overlapping at the contact point.
        mesh_phase_offset = math.pi + (math.pi / max(teeth2, 1))
        theta2 = mesh_phase_offset - theta1 * (teeth1 / max(teeth2, 1))

        p1 = (g1[0] + r1 * math.cos(theta1), g1[1] + r1 * math.sin(theta1))
        p2 = (g2[0] + r2 * math.cos(theta2), g2[1] + r2 * math.sin(theta2))

        positions = {
            "gear1_center": g1,
            "gear2_center": g2,
            "gear1_indicator_end": p1,
            "gear2_indicator_end": p2,
        }
        metadata: dict[str, object] = {
            "gear1_teeth": teeth1,
            "gear2_teeth": teeth2,
            "r1": r1,
            "r2": r2,
            "theta1": theta1,
            "theta2": theta2,
            "mesh_phase_offset": mesh_phase_offset,
            "center_distance": center_distance,
            "board_space_distance": center_distance / grid_pitch,
            "gear_clearance": max(0.0, clearance_mm),
            "gear_mesh_ok": math.isclose(
                center_distance,
                r1 + r2 + max(0.0, clearance_mm),
                abs_tol=1e-6,
            ),
            "grid_system_enabled": grid_enabled,
            "grid_cell_cm": grid_pitch / 10.0,
            "fabrication_board_origin": "H8",
            "fabrication_board_coords": board_coords,
        }
        has_linkage = bool(parameters.get("gear_linkage_enabled")) or any(
            key in parameters for key in ("linkage_arm_length", "linkage_pin_radius")
        )
        if has_linkage:
            default_pin_radius = min(r2 * 0.72, grid_step_mm(parameters.get("grid_cell_cm", 2.0)))
            pin_radius = min(
                max(
                    1.0,
                    _positive_finite_float(
                        parameters.get("linkage_pin_radius"), default_pin_radius
                    ),
                ),
                max(1.0, r2 - (profile.hole_diameter_mm / 2.0)),
            )
            arm_length = _positive_finite_float(
                parameters.get("linkage_arm_length"),
                grid_step_mm(parameters.get("grid_cell_cm", 2.0)) * 2.0,
            )
            linkage_pin = (
                g2[0] + pin_radius * math.cos(theta2),
                g2[1] + pin_radius * math.sin(theta2),
            )
            linkage_end = (
                linkage_pin[0] + arm_length * math.cos(theta2),
                linkage_pin[1] + arm_length * math.sin(theta2),
            )
            positions["linkage_pin"] = linkage_pin
            positions["linkage_end"] = linkage_end
            metadata.update(
                {
                    "has_linkage": True,
                    "linkage_pin_radius": pin_radius,
                    "linkage_arm_length": arm_length,
                }
            )

        return MechanismState(
            positions=positions,
            safety_status=SafetyStatus(
                SafetyLevel.SAFE,
                (
                    f"Gear mesh nominal — {center_distance / grid_pitch:.1f} board-space centers"
                    if grid_enabled
                    else "Gear mesh nominal — custom freeform centers"
                ),
            ),
            metadata=metadata,
        )


class _PlanetaryGearPreviewMechanism:
    """Lightweight Foundry-only mechanism for planetary gear previews/export."""

    mechanism_type = "planetary_gear"

    def compute_state(self, parameters: dict[str, float], input_angle: float) -> MechanismState:
        if not isinstance(parameters, dict):
            parameters = {}
        profile = physical_profile_from_params(parameters)
        grid_enabled = grid_enabled_from_params(parameters)
        if grid_enabled:
            parameters = snap_physical_params(
                "planetary_gear",
                parameters,
                parameters.get("grid_cell_cm", DEFAULT_GRID_CELL_CM),
                enabled=True,
                profile=profile,
            )

        default_sun = profile.gear_presets[0].teeth if profile.gear_presets else 12
        default_planet = (
            profile.gear_presets[1].teeth if len(profile.gear_presets) > 1 else default_sun
        )
        if grid_enabled:
            sun_teeth = gear_teeth_from_params(
                parameters,
                ("sun_teeth",),
                ("r_sun", "sun_radius"),
                default_sun,
                enabled=True,
                profile=profile,
            )
            planet_teeth = gear_teeth_from_params(
                parameters,
                ("planet_teeth",),
                ("r_planet", "planet_radius"),
                default_planet,
                enabled=True,
                profile=profile,
            )
        else:
            sun_teeth = gear_teeth_from_params(
                parameters,
                ("sun_teeth",),
                ("r_sun", "sun_radius"),
                default_sun,
                enabled=False,
                profile=profile,
            )
            planet_teeth = gear_teeth_from_params(
                parameters,
                ("planet_teeth",),
                ("r_planet", "planet_radius"),
                default_planet,
                enabled=False,
                profile=profile,
            )

        if grid_enabled:
            r_sun = gear_radius_for_teeth(sun_teeth, profile=profile)
            r_planet = gear_radius_for_teeth(planet_teeth, profile=profile)
        else:
            r_sun = freeform_gear_radius_for_teeth(sun_teeth, profile=profile)
            r_planet = freeform_gear_radius_for_teeth(planet_teeth, profile=profile)
        planet_count = int(
            min(max(round(_finite_float(parameters.get("planet_count"), 1.0)), 1), 4)
        )
        clearance = _finite_float(
            parameters.get("gear_clearance", parameters.get("mesh_clearance")),
            profile.default_gear_clearance_mm,
        )
        orbit_radius = max(1.0, r_sun + r_planet + clearance * 0.5)
        ring_pitch_radius = orbit_radius + r_planet + clearance * 0.5
        ring_teeth = max(
            sun_teeth + planet_teeth * 2,
            int(round(ring_pitch_radius / max(profile.gear_radius_per_tooth_mm, 1e-6))),
        )

        theta = math.radians(_finite_float(input_angle, 0.0))
        carrier_angle = theta
        planet_spin = -theta * (r_sun / max(r_planet, 1e-6))
        arm_length = _positive_finite_float(
            parameters.get("carrier_arm_length", parameters.get("arm_length")),
            grid_step_mm(parameters.get("grid_cell_cm", DEFAULT_GRID_CELL_CM)),
        )

        positions: dict[str, tuple[float, float]] = {
            "sun_center": (0.0, 0.0),
            "carrier_center": (0.0, 0.0),
        }
        for idx in range(planet_count):
            angle = carrier_angle + (2.0 * math.pi * idx / planet_count)
            planet_center = (orbit_radius * math.cos(angle), orbit_radius * math.sin(angle))
            positions[f"planet_{idx + 1}_center"] = planet_center
            if idx == 0:
                tracking_point = (
                    planet_center[0] + arm_length * math.cos(angle + planet_spin),
                    planet_center[1] + arm_length * math.sin(angle + planet_spin),
                )
                positions["planet_center"] = planet_center
                positions["tracking_point"] = tracking_point

        metadata: dict[str, object] = {
            "sun_teeth": sun_teeth,
            "planet_teeth": planet_teeth,
            "ring_teeth": ring_teeth,
            "planet_count": planet_count,
            "r_sun": r_sun,
            "r_planet": r_planet,
            "orbit_radius": orbit_radius,
            "ring_pitch_radius": ring_pitch_radius,
            "ring_inner_radius": max(1.0, ring_pitch_radius - r_planet * 0.35),
            "ring_outer_radius": ring_pitch_radius + r_planet * 0.25,
            "theta_sun": theta,
            "theta_planet": planet_spin,
            "theta_carrier": carrier_angle,
            "carrier_arm_length": arm_length,
            "grid_system_enabled": grid_enabled,
            "grid_cell_cm": grid_step_mm(parameters.get("grid_cell_cm", DEFAULT_GRID_CELL_CM))
            / 10.0,
            "fabrication_board_origin": "H8",
            "fabrication_board_coords": {
                "sun_center": "H8",
                "ring_mounts": ("D8", "H4", "H12", "L8"),
                "carrier_reference": "H10",
            }
            if grid_enabled
            else {},
        }
        return MechanismState(
            positions=positions,
            safety_status=SafetyStatus(SafetyLevel.SAFE, "Planetary gear mesh nominal"),
            metadata=metadata,
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

        self._grid_system_enabled = True
        self._grid_cell_cm = DEFAULT_GRID_CELL_CM
        self._grid_pitch_choice = nearest_pitch_choice(DEFAULT_GRID_CELL_CM).key
        self._physical_profile: PhysicalKitProfile = DEFAULT_PHYSICAL_KIT_PROFILE
        self.controller = self._build_controller()
        self.current_mechanism: Mechanism | None = None
        self.current_parameters: dict[str, object] = {}
        self.current_angle: float = 30.0
        self._current_angle_bounds: tuple[float, float] = (0.0, 360.0)
        self._current_angle_bounds_partial = False
        self._current_angle_bounds_known = False
        self._current_angle_bounds_available = True
        self._angle_animation_direction = 1.0
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
        viewport = self.graphics_view.viewport()
        if viewport is not None:
            viewport.installEventFilter(self)
        self._viewport_controller = ViewportController(
            self.graphics_view,
            ViewportConfig(
                zoom_factor_base=1.05,
                min_zoom_level=-47,
                max_zoom_level=47,
                anchor_under_mouse=True,
            ),
            parent=self,
        )

        self.parameter_sliders: dict[str, tuple[QSlider, QLabel]] = {}
        self.mechanism_selector: QComboBox | None = None
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._on_animation_tick)
        self.is_playing = False
        self._user_paused_animation = False

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
        self.angle_range_selector: QComboBox | None = None

        self._build_ui()

    @staticmethod
    def _normalize_mechanism_type_key(mechanism_type: str) -> str:
        """Normalize type strings received from catalog, Design tab, or tests."""
        return str(normalize_mechanism_type_key(mechanism_type))

    @classmethod
    def _to_controller_mechanism_type(cls, mechanism_type: str) -> str:
        """Normalize mechanism type aliases to controller configuration keys."""
        return str(canonical_mechanism_type(mechanism_type))

    def _build_controller(self) -> MechanismFoundryController:
        return MechanismFoundryController(
            physical_profile=self._physical_profile,
            grid_cell_cm=self._grid_cell_cm,
        )

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.stacked_widget = QStackedWidget()

        self.gallery_view = GalleryView(
            self,
            controller=self.controller,
            physical_profile=self._physical_profile,
            grid_cell_cm=self._grid_cell_cm,
        )
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
        if not self._user_paused_animation:
            self._set_animation_playing(True)

    def _go_back_to_gallery(self) -> None:
        if self.is_playing:
            self._set_animation_playing(False)
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

        params["input_angle"] = _finite_float(self.current_angle, 0.0) % 360.0
        if (
            self._current_controller_mechanism_type() == "four_bar"
            and self._current_angle_bounds_known
            and self._current_angle_bounds_available
        ):
            minimum, maximum = self._current_angle_bounds
            if math.isfinite(minimum) and math.isfinite(maximum):
                params["valid_angle_min"] = minimum
                params["valid_angle_max"] = maximum
        context = physical_context_from_params(
            self._effective_physical_parameters(self.current_parameters),
            default_enabled=self._grid_system_enabled,
            default_grid_cell_cm=self._grid_cell_cm,
        )
        params.update(context.as_params())
        return params

    def _physical_context_overlay(self) -> dict[str, object]:
        return {
            "grid_system_enabled": self._grid_system_enabled,
            "grid_cell_cm": self._grid_cell_cm,
            "grid_pitch_choice": self._grid_pitch_choice,
            "physical_profile_key": self._physical_profile.key,
        }

    def _effective_physical_parameters(
        self,
        parameters: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Merge current Foundry physical context into params at compute/export boundaries."""
        effective = self._physical_context_overlay()
        if isinstance(parameters, dict):
            effective.update(parameters)
        return effective

    def _apply_physical_context_overrides(self, parameters: dict[str, object]) -> None:
        """Persist source context flags from Design sync without requiring visible sliders."""
        for key in (
            "grid_system_enabled",
            "grid_cell_cm",
            "grid_pitch_choice",
            "physical_profile_key",
        ):
            if key in parameters:
                self.current_parameters[key] = parameters[key]

    def _sync_physical_context_from_params(self, parameters: dict[str, object]) -> None:
        """Adopt physical-grid context received from Design before snapping/rendering."""
        if not any(
            key in parameters
            for key in (
                "grid_system_enabled",
                "grid_cell_cm",
                "grid_pitch_choice",
                "physical_profile_key",
            )
        ):
            return

        context = physical_context_from_params(
            self._effective_physical_parameters(parameters),
            default_enabled=self._grid_system_enabled,
            default_grid_cell_cm=self._grid_cell_cm,
        )
        profile_changed = context.profile != self._physical_profile
        cell_changed = abs(context.grid_cell_cm - self._grid_cell_cm) > 1e-9
        enabled_changed = context.enabled != self._grid_system_enabled
        pitch_changed = context.grid_pitch_choice != self._grid_pitch_choice

        self._grid_system_enabled = context.enabled
        self._grid_cell_cm = context.grid_cell_cm
        self._grid_pitch_choice = context.grid_pitch_choice
        self._physical_profile = context.profile
        self._apply_physical_context_overrides(context.as_params())
        if profile_changed or cell_changed:
            self._refresh_controller_for_physical_context()
        if profile_changed or cell_changed or enabled_changed or pitch_changed:
            self._draw_grid()
            self._state_cache_valid = False

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
                    self._effective_physical_parameters(self.current_parameters),
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

        snapshot: dict[str, object] = {
            "mechanism_type": str(self.current_mechanism.mechanism_type).strip(),
            "positions": positions,
        }
        fabrication_metadata: dict[str, object] = {}
        origin = state.metadata.get("fabrication_board_origin")
        if isinstance(origin, str) and origin:
            fabrication_metadata["board_origin"] = origin
        coords = state.metadata.get("fabrication_board_coords")
        if isinstance(coords, dict) and coords:
            fabrication_metadata["board_coords"] = dict(coords)
        if fabrication_metadata:
            snapshot["fabrication"] = fabrication_metadata
        return snapshot

    def _on_export_to_design(self) -> None:
        """Export current mechanism configuration to Mechanism Design tab."""
        if not self.current_mechanism:
            return

        # Export the controller selection so gear+linkage stays distinct from plain gear train.
        mechanism_type = self._current_controller_mechanism_type()
        if not mechanism_type and self.current_mechanism:
            mechanism_type = self._to_controller_mechanism_type(
                self.current_mechanism.mechanism_type
            )
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

        angle_range_row = QHBoxLayout()
        angle_range_row.addWidget(QLabel("Valid Range:"))
        self.angle_range_selector = QComboBox()
        self.angle_range_selector.currentIndexChanged.connect(self._on_angle_range_changed)
        self.angle_range_selector.setVisible(False)
        angle_range_row.addWidget(self.angle_range_selector)
        animation_layout.addLayout(angle_range_row)

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
        elif canonical_type in {"gear_train", "gear_linkage"}:
            self.current_mechanism = _GearTrainPreviewMechanism()
        elif canonical_type == "planetary_gear":
            self.current_mechanism = _PlanetaryGearPreviewMechanism()
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
                self._current_controller_mechanism_type(),
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
        if self.mechanism_selector is not None:
            selected = self.mechanism_selector.currentData()
            if isinstance(selected, str):
                selected_type = self._to_controller_mechanism_type(selected)
                if selected_type:
                    return selected_type
        if self.current_mechanism is not None:
            return self._to_controller_mechanism_type(self.current_mechanism.mechanism_type)
        return "unknown"

    def _refresh_angle_bounds(self) -> None:
        bounds = (0.0, 360.0)
        partial = False

        if self.current_mechanism and self._current_controller_mechanism_type() == "four_bar":
            point_name = self._selected_motion_state_key() or "B"
            try:
                path = self.path_cache.compute_and_cache(
                    self.current_mechanism,
                    self._effective_physical_parameters(self.current_parameters),
                    point_name,
                )
                bounds = select_angle_bounds(
                    path.valid_angle_ranges,
                    self.current_angle,
                    is_closed_cycle=path.is_closed_cycle,
                )
                if bounds is None:
                    self._apply_no_valid_angle_bounds()
                    return
                partial = not path.is_closed_cycle and bool(path.valid_angle_ranges)
                self._refresh_angle_range_selector(
                    path.valid_angle_ranges,
                    bounds,
                    partial=partial,
                )
            except Exception:
                self._apply_no_valid_angle_bounds()
                return
        else:
            self._refresh_angle_range_selector((), bounds, partial=False)

        self._apply_angle_bounds(bounds, partial)

    def _apply_angle_bounds(self, bounds: tuple[float, float], partial: bool) -> None:
        minimum, maximum = bounds
        if not math.isfinite(minimum) or not math.isfinite(maximum) or maximum < minimum:
            self._apply_no_valid_angle_bounds()
            return

        self._current_angle_bounds = (minimum, maximum)
        self._current_angle_bounds_partial = bool(partial)
        self._current_angle_bounds_known = True
        self._current_angle_bounds_available = True

        clamped_angle = self._angle_inside_bounds(self.current_angle, (minimum, maximum))
        if clamped_angle != self.current_angle:
            self.current_angle = clamped_angle
            self._state_cache_valid = False

        if not hasattr(self, "angle_slider"):
            return

        slider_min = int(math.floor(minimum))
        slider_max = int(math.ceil(maximum))
        with blocked_signals(self.angle_slider):
            self.angle_slider.setMinimum(slider_min)
            self.angle_slider.setMaximum(slider_max)
            self.angle_slider.setValue(int(round(self.current_angle)))
            self.angle_slider.setEnabled(True)
        if hasattr(self, "play_action"):
            self.play_action.setEnabled(True)
        self._update_angle_label()

    def _refresh_angle_range_selector(
        self,
        ranges: tuple[tuple[float, float], ...],
        selected_bounds: tuple[float, float],
        *,
        partial: bool,
    ) -> None:
        if self.angle_range_selector is None:
            return

        show_selector = bool(partial and len(ranges) > 1)
        with blocked_signals(self.angle_range_selector):
            self.angle_range_selector.clear()
            for index, bounds in enumerate(ranges, start=1):
                self.angle_range_selector.addItem(
                    f"{index}: {self._angle_range_text(bounds)}",
                    bounds,
                )
            selected_index = 0
            for index, bounds in enumerate(ranges):
                if self._same_angle_bounds(bounds, selected_bounds):
                    selected_index = index
                    break
            if ranges:
                self.angle_range_selector.setCurrentIndex(selected_index)
            self.angle_range_selector.setVisible(show_selector)

    @staticmethod
    def _same_angle_bounds(
        first: tuple[float, float],
        second: tuple[float, float],
    ) -> bool:
        return abs(first[0] - second[0]) < 1e-6 and abs(first[1] - second[1]) < 1e-6

    def _on_angle_range_changed(self, index: int) -> None:
        if self.angle_range_selector is None or index < 0:
            return
        data = self.angle_range_selector.itemData(index)
        if not isinstance(data, tuple) or len(data) != 2:
            return
        minimum = _finite_float(data[0], math.nan)
        maximum = _finite_float(data[1], math.nan)
        if not math.isfinite(minimum) or not math.isfinite(maximum):
            return
        self._apply_angle_bounds((minimum, maximum), partial=True)
        self._state_cache_valid = False
        self._render_mechanism()

    @staticmethod
    def _angle_inside_bounds(angle: float, bounds: tuple[float, float]) -> float:
        minimum, maximum = bounds
        candidates = (angle, angle - 360.0, angle + 360.0)
        for candidate in candidates:
            if minimum <= candidate <= maximum:
                return candidate
        return min(
            (minimum, maximum),
            key=lambda endpoint: min(abs(candidate - endpoint) for candidate in candidates),
        )

    @staticmethod
    def _angle_text(angle: float) -> str:
        normalized = angle % 360.0
        return f"{int(round(normalized))}°"

    def _angle_range_text(self, bounds: tuple[float, float]) -> str:
        return f"{self._angle_text(bounds[0])}–{self._angle_text(bounds[1])}"

    def _apply_no_valid_angle_bounds(self) -> None:
        self._current_angle_bounds = (self.current_angle, self.current_angle)
        self._current_angle_bounds_partial = False
        self._current_angle_bounds_known = True
        self._current_angle_bounds_available = False
        if hasattr(self, "animation_timer") and self.animation_timer.isActive():
            self._set_animation_playing(False)
        if hasattr(self, "angle_slider"):
            slider_value = int(round(self.current_angle))
            with blocked_signals(self.angle_slider):
                self.angle_slider.setMinimum(slider_value)
                self.angle_slider.setMaximum(slider_value)
                self.angle_slider.setValue(slider_value)
                self.angle_slider.setEnabled(False)
        if hasattr(self, "play_action"):
            self.play_action.setEnabled(False)
        if self.angle_range_selector is not None:
            with blocked_signals(self.angle_range_selector):
                self.angle_range_selector.clear()
                self.angle_range_selector.setVisible(False)
        if hasattr(self, "angle_label"):
            self.angle_label.setText("No valid input angle")

    def _update_angle_label(self) -> None:
        if not self._current_angle_bounds_available:
            self.angle_label.setText("No valid input angle")
            return
        angle_text = self._angle_text(self.current_angle)
        if self._current_angle_bounds_partial:
            angle_text += f" (valid {self._angle_range_text(self._current_angle_bounds)})"
        self.angle_label.setText(angle_text)

    def _selected_motion_point_label(self) -> str:
        if self.output_point_selector is not None and not self.output_point_selector.isHidden():
            text = self.output_point_selector.currentText().strip()
            if text:
                return text
        return "preview trace"

    def _selected_motion_point_key(self) -> str | None:
        if self.output_point_selector is None or self.output_point_selector.isHidden():
            return None
        value = self.output_point_selector.currentData()
        return value if isinstance(value, str) and value else None

    def _selected_motion_state_key(self) -> str | None:
        selected_value = self._selected_motion_point_key()
        if not selected_value:
            return None
        mechanism_type = self._current_controller_mechanism_type()
        for option in SensemakingService.motion_point_options_for(mechanism_type):
            if option.value == selected_value:
                return str(option.state_key)
        return selected_value

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

    def _parameter_row_label(self, spec: ParameterSpec) -> str:
        label_text = self._display_parameter_label(spec, spec.key)
        unit = str(spec.unit or "").strip().lower()
        if unit in {"mm", "millimeter", "millimeters"}:
            return f"{label_text} (in / board spaces):"
        if spec.unit:
            return f"{label_text} ({spec.unit}):"
        return f"{label_text}:"

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

            label = QLabel(self._parameter_row_label(spec))
            row_layout.addWidget(label)

            value_str = self._format_parameter_value(spec.key, spec.default_value)

            value_label = QLabel(value_str)
            value_label.setMinimumWidth(120)
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
        snapped_updates = self._snapped_parameter_updates_if_needed(param_key, value)
        adjusted_value = self._snap_parameter_value_if_needed(
            param_key,
            value,
            snapped_updates=snapped_updates,
        )
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
        if snapped_updates:
            for key, snapped_value in snapped_updates.items():
                if key != param_key and key not in self._parameter_specs_by_key:
                    self.current_parameters[key] = snapped_value
            self._apply_related_snapped_parameter_updates(snapped_updates, primary_key=param_key)
        self._state_cache_valid = False
        label.setText(self._format_parameter_value(param_key, adjusted_value))
        self._pending_param = (param_key, adjusted_value, label, is_integer)
        self._update_sensemaking_parameter_change(
            param_key,
            previous_value,
            adjusted_value,
            previous_positions,
        )
        self._render_mechanism(refresh_sensemaking=False)
        self._param_debounce_timer.start()

    @property
    def _grid_step_mm(self) -> float:
        return float(grid_step_mm(self._grid_cell_cm))

    @staticmethod
    def _is_length_spec(spec: ParameterSpec | None) -> bool:
        if spec is None:
            return False
        unit = (spec.unit or "").strip().lower()
        return unit in {"mm", "millimeter", "millimeters"}

    def _snapped_parameter_updates_if_needed(
        self,
        param_key: str,
        value: float,
    ) -> dict[str, object] | None:
        candidate = dict(self.current_parameters)
        candidate[param_key] = value
        context = physical_context_from_params(
            self._effective_physical_parameters(candidate),
            default_enabled=self._grid_system_enabled,
            default_grid_cell_cm=self._grid_cell_cm,
        )
        if not context.enabled:
            return None
        mechanism_type = self._current_controller_mechanism_type()
        if mechanism_type == "cam_follower":
            cam_updates = self._cam_preset_updates_for_primary_change(
                candidate,
                param_key,
                context,
            )
            if cam_updates is not None:
                return cam_updates
        return cast(
            dict[str, object],
            snap_physical_params(
                mechanism_type,
                candidate,
                context.grid_cell_cm,
                enabled=True,
                profile=context.profile,
            ),
        )

    def _cam_preset_updates_for_primary_change(
        self,
        candidate: dict[str, object],
        param_key: str,
        context: PhysicalKitContext,
    ) -> dict[str, object] | None:
        field_by_key = {
            "cam_radius": "base_radius",
            "base_radius": "base_radius",
            "cam_offset": "eccentricity",
            "eccentricity": "eccentricity",
            "cam_lobes": "cam_lobes",
            "profile_harmonic": "profile_harmonic",
        }
        field = field_by_key.get(param_key)
        if field is None:
            return None
        primary_value = snap_parameter_value(
            "cam_follower",
            param_key,
            candidate.get(param_key),
            context.grid_cell_cm,
            profile=context.profile,
        )

        def preset_distance(indexed_preset: tuple[int, CamPreset]) -> tuple[float, int]:
            index, preset = indexed_preset
            params = preset.params_mm(context.grid_cell_cm)
            return abs(_finite_float(params.get(field), primary_value) - primary_value), index

        _, preset = min(enumerate(context.profile.cam_presets), key=preset_distance)
        preset_params = preset.params_mm(context.grid_cell_cm)
        updates = dict(candidate)
        if "cam_radius" in self._parameter_specs_by_key or "cam_radius" in updates:
            updates["cam_radius"] = preset_params["base_radius"]
        updates["base_radius"] = preset_params["base_radius"]
        if "cam_offset" in self._parameter_specs_by_key or "cam_offset" in updates:
            updates["cam_offset"] = preset_params["eccentricity"]
        updates["eccentricity"] = preset_params["eccentricity"]
        updates["cam_lobes"] = int(preset_params["cam_lobes"])
        updates["profile_harmonic"] = preset_params["profile_harmonic"]
        updates["physical_cam_preset"] = preset.key
        for key in ("rise_deg", "high_dwell_deg", "return_deg"):
            updates[key] = preset_params[key]
        return updates

    def _apply_related_snapped_parameter_updates(
        self,
        snapped_updates: dict[str, object],
        *,
        primary_key: str,
    ) -> None:
        for key, spec in self._parameter_specs_by_key.items():
            if key == primary_key or key not in snapped_updates:
                continue
            snapped = _finite_float(snapped_updates[key], math.nan)
            if not math.isfinite(snapped):
                continue
            self.current_parameters[key] = snapped
            if key in self.parameter_sliders and spec.step > 0:
                slider, label = self.parameter_sliders[key]
                slider_value = int(round(snapped / spec.step))
                with blocked_signals(slider):
                    slider.setValue(slider_value)
                label.setText(self._format_parameter_value(key, snapped))

    def _snap_parameter_value_if_needed(
        self,
        param_key: str,
        value: float,
        *,
        snapped_updates: dict[str, object] | None = None,
    ) -> float:
        spec = self._parameter_specs_by_key.get(param_key)
        default = _finite_float(spec.default_value, 0.0) if spec else 0.0
        raw_value = _finite_float(value, default)
        context = physical_context_from_params(
            self._effective_physical_parameters(self.current_parameters),
            default_enabled=self._grid_system_enabled,
            default_grid_cell_cm=self._grid_cell_cm,
        )
        if not context.enabled:
            return raw_value

        mechanism_type = self._current_controller_mechanism_type()
        if snapped_updates and param_key in snapped_updates:
            snapped = _finite_float(snapped_updates[param_key], raw_value)
        else:
            snapped = snap_parameter_value(
                mechanism_type,
                param_key,
                raw_value,
                context.grid_cell_cm,
                profile=context.profile,
            )
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
        """Apply current physical-kit snapping policy to current parameters."""
        context = physical_context_from_params(
            self._effective_physical_parameters(self.current_parameters),
            default_enabled=self._grid_system_enabled,
            default_grid_cell_cm=self._grid_cell_cm,
        )
        if not context.enabled:
            return

        mechanism_type = self._current_controller_mechanism_type()
        snapped_params = snap_physical_params(
            mechanism_type,
            self.current_parameters,
            context.grid_cell_cm,
            enabled=True,
            profile=context.profile,
        )
        changed = False
        for key, spec in self._parameter_specs_by_key.items():
            current = self.current_parameters.get(key)
            if current is None:
                continue

            current_value = _finite_float(current, math.nan)
            if not math.isfinite(current_value):
                continue

            snapped_raw = snapped_params.get(key, current_value)
            snapped = _finite_float(snapped_raw, current_value)
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

    def set_physical_context(self, context: PhysicalKitContext) -> None:
        """Apply the app-owned physical context to Foundry render/snapping caches."""
        previous_profile = self._physical_profile
        previous_grid_cell_cm = self._grid_cell_cm
        changed = (
            context.enabled != self._grid_system_enabled
            or abs(context.grid_cell_cm - self._grid_cell_cm) > 1e-9
            or context.grid_pitch_choice != self._grid_pitch_choice
            or context.profile != self._physical_profile
        )
        if not changed:
            self._apply_physical_context_overrides(context.as_params())
            if self.gallery_view is not None:
                self.gallery_view.set_physical_context(context)
            return

        self._grid_system_enabled = context.enabled
        self._grid_cell_cm = context.grid_cell_cm
        self._grid_pitch_choice = context.grid_pitch_choice
        self._physical_profile = context.profile
        self._apply_physical_context_overrides(context.as_params())
        if self.gallery_view is not None:
            self.gallery_view.set_physical_context(context)
        if (
            previous_profile != self._physical_profile
            or abs(previous_grid_cell_cm - self._grid_cell_cm) > 1e-9
        ):
            self._refresh_controller_for_physical_context()
        self._draw_grid()
        self._apply_grid_snap_to_current_parameters()
        self._state_cache_valid = False
        self._render_mechanism()

    def set_grid_system(self, enabled: bool, cell_cm: float) -> None:
        """Compatibility wrapper; app-level PhysicalKitContext is preferred."""
        self.set_physical_context(
            physical_context_from_settings(
                enabled,
                physical_finite_float(cell_cm, DEFAULT_GRID_CELL_CM),
                profile=self._physical_profile,
            )
        )

    def set_physical_profile(self, profile: PhysicalKitProfile) -> None:
        """Compatibility wrapper; app-level PhysicalKitContext is preferred."""
        self.set_physical_context(
            physical_context_from_settings(
                self._grid_system_enabled,
                self._grid_cell_cm,
                self._grid_pitch_choice,
                profile=profile,
            )
        )

    def _refresh_controller_for_physical_context(self) -> None:
        """Rebuild controller-backed defaults after physical grid/profile changes."""
        current_type = self._current_controller_mechanism_type()
        self.controller = self._build_controller()
        if self.gallery_view is not None:
            self.gallery_view.set_controller(self.controller)

        if current_type == "unknown":
            return

        config = self.controller.get_configuration(current_type)
        if config is None:
            return

        if self.parameter_sliders:
            self._rebuild_parameter_sliders(tuple(config.parameter_specs))
        else:
            self._parameter_specs_by_key = {
                spec.key: spec for spec in tuple(config.parameter_specs)
            }
        if self.info_panel is not None:
            self._update_info_panel(current_type, config)

    def _apply_pending_parameter(self) -> None:
        """Apply debounced parameter change."""
        self._render_mechanism()

        if self.current_mechanism:
            config_type = self._current_controller_mechanism_type()
            config = self.controller.get_configuration(config_type)
            if config:
                self._update_info_panel(config_type, config)
            self._refresh_sensemaking_context(config_type)

            # Emit sync signal if we have a synced mechanism (bidirectional sync)
            if self.synced_mechanism_id and not self._suppress_sync_signal:
                params = self._build_sync_payload_parameters()
                self.mechanism_parameters_changed.emit(
                    self.synced_mechanism_id,
                    self._current_controller_mechanism_type(),
                    params,
                )

    def _on_angle_changed(self, value: int) -> None:
        self.current_angle = float(value)
        self._update_angle_label()
        self._state_cache_valid = False
        self._render_mechanism()

        # Emit sync signal for angle change (bidirectional sync)
        if self.synced_mechanism_id and self.current_mechanism and not self._suppress_sync_signal:
            params = self._build_sync_payload_parameters()
            self.mechanism_parameters_changed.emit(
                self.synced_mechanism_id,
                self._current_controller_mechanism_type(),
                params,
            )

    def _toggle_play(self) -> None:
        self._set_animation_playing(not self.is_playing, user_initiated=True)

    def _set_animation_playing(self, playing: bool, *, user_initiated: bool = False) -> None:
        if playing == self.is_playing:
            if user_initiated:
                self._user_paused_animation = not playing
            return
        if not playing:
            self.animation_timer.stop()
            self.play_action.setText("▶ Play")
            self.play_action.setChecked(False)
            self.is_playing = False
            if user_initiated:
                self._user_paused_animation = True
        else:
            self.animation_timer.start(33)
            self.play_action.setText("⏸ Pause")
            self.play_action.setChecked(True)
            self.is_playing = True
            if user_initiated:
                self._user_paused_animation = False

    def _reset_animation(self) -> None:
        self._refresh_angle_bounds()
        minimum, maximum = self._current_angle_bounds
        self.current_angle = min(max(30.0, minimum), maximum)
        self._angle_animation_direction = 1.0
        with blocked_signals(self.angle_slider):
            self.angle_slider.setValue(int(round(self.current_angle)))
        self._update_angle_label()
        if self.is_playing:
            self._set_animation_playing(False)

    def _on_animation_tick(self) -> None:
        if not self._current_angle_bounds_available:
            self._set_animation_playing(False)
            self._render_mechanism()
            return

        minimum, maximum = self._current_angle_bounds
        if self._current_angle_bounds_partial:
            next_angle = self.current_angle + 4.0 * self._angle_animation_direction
            if next_angle > maximum:
                overshoot = next_angle - maximum
                self.current_angle = max(minimum, maximum - overshoot)
                self._angle_animation_direction = -1.0
            elif next_angle < minimum:
                overshoot = minimum - next_angle
                self.current_angle = min(maximum, minimum + overshoot)
                self._angle_animation_direction = 1.0
            else:
                self.current_angle = next_angle
        else:
            self.current_angle = (self.current_angle + 4.0) % 360.0
        with blocked_signals(self.angle_slider):
            self.angle_slider.setValue(int(round(self.current_angle)))
        self._update_angle_label()
        self._render_mechanism()

    def _render_mechanism(self, *, refresh_sensemaking: bool = True) -> None:
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
            self._refresh_angle_bounds()
            state = self.current_mechanism.compute_state(
                self._effective_physical_parameters(self.current_parameters),
                self.current_angle,
            )
            self._last_rendered_state = state
            self._last_rendered_mechanism = self.current_mechanism
            self._state_cache_valid = True
            self._draw_mechanism_state(state)
            self._update_safety_display(state)
            if refresh_sensemaking:
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
        elif mechanism_type == "cam_follower":
            self._draw_cam_mechanism_optimized(state)
        elif mechanism_type in {"gear_train", "gear_linkage"}:
            self._draw_gear_mechanism_optimized(state)
        elif mechanism_type == "planetary_gear":
            self._draw_planetary_gear_mechanism_optimized(state)
        elif mechanism_type == "slider_crank":
            self._draw_slider_crank_mechanism_optimized(state)
        self._show_default_paths(state)

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
        cp_x = _finite_float(coupler_x, 0.0)
        cp_y = _finite_float(coupler_y, 0.0)

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
                item = _require_graphics_item(
                    self.scene.addPolygon(
                        triangle,
                        QPen(QColor("#5dade2"), 2),
                        QBrush(QColor(124, 252, 176, 150)),
                    )
                )
                item.setZValue(8.0)
                item.setData(0, "mechanism_item")
                cache[triangle_key] = item
            else:
                cast(QGraphicsPolygonItem, cache[triangle_key]).setPolygon(triangle)
                cache[triangle_key].setVisible(True)
        elif triangle_key in cache:
            cache[triangle_key].setVisible(False)

        if marker_key not in cache:
            marker = _require_graphics_item(
                self.scene.addEllipse(
                    p_c.x() - 5.0,
                    p_c.y() - 5.0,
                    10.0,
                    10.0,
                    QPen(QColor("#1e8449"), 2),
                    QBrush(QColor("#27ae60")),
                )
            )
            marker.setZValue(11.0)
            marker.setData(0, "mechanism_item")
            cache[marker_key] = marker
        else:
            marker = cast(QGraphicsEllipseItem, cache[marker_key])
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
                    cam_poly_item = _require_graphics_item(
                        self.scene.addPolygon(polygon, cam_pen, QBrush(QColor(70, 130, 180, 100)))
                    )
                    cam_poly_item.setData(0, "mechanism_item")
                    cache["cam_poly"] = cam_poly_item
                else:
                    cast(QGraphicsPolygonItem, cache["cam_poly"]).setPolygon(polygon)

        # 2. Cam Center
        if "cam_center" not in cache:
            cam_center_item = _require_graphics_item(
                self.scene.addEllipse(
                    0,
                    0,
                    16,
                    16,
                    QPen(QColor(255, 0, 0), 2),
                    QBrush(QColor(255, 100, 100)),
                )
            )
            cam_center_item.setData(0, "mechanism_item")
            cache["cam_center"] = cam_center_item
        cast(QGraphicsEllipseItem, cache["cam_center"]).setRect(
            cam_center[0] - 8, cam_center[1] - 8, 16, 16
        )

        # 3. Contact Point
        if "contact_pt" not in cache:
            contact_item = _require_graphics_item(
                self.scene.addEllipse(
                    0,
                    0,
                    10,
                    10,
                    QPen(QColor(220, 20, 60), 3),
                    QBrush(QColor(220, 20, 60)),
                )
            )
            contact_item.setData(0, "mechanism_item")
            cache["contact_pt"] = contact_item
        cast(QGraphicsEllipseItem, cache["contact_pt"]).setRect(
            contact_point[0] - 5, contact_point[1] - 5, 10, 10
        )

        # 4. Follower Line (Rod)
        if "follower_rod" not in cache:
            follower_rod_item = _require_graphics_item(
                self.scene.addLine(0, 0, 0, 0, QPen(QColor(80, 80, 80), 6))
            )
            follower_rod_item.setData(0, "mechanism_item")
            cache["follower_rod"] = follower_rod_item
        cast(QGraphicsLineItem, cache["follower_rod"]).setLine(
            float(follower_base[0]),
            float(follower_base[1]),
            float(follower_end[0]),
            float(follower_end[1]),
        )

        # 5. Follower Head
        follower_width, follower_height = 30, 15
        if "follower_head" not in cache:
            follower_head_item = _require_graphics_item(
                self.scene.addRect(
                    0,
                    0,
                    follower_width,
                    follower_height,
                    QPen(QColor(50, 50, 50), 2),
                    QBrush(QColor(120, 120, 120)),
                )
            )
            follower_head_item.setData(0, "mechanism_item")
            cache["follower_head"] = follower_head_item
        cast(QGraphicsRectItem, cache["follower_head"]).setRect(
            follower_end[0] - follower_width / 2,
            follower_end[1] - follower_height / 2,
            follower_width,
            follower_height,
        )

        # 6. Guide Line
        if "guide_line" not in cache:
            guide_pen = QPen(QColor(150, 150, 150), 2, Qt.PenStyle.DashLine)
            guide_item = _require_graphics_item(self.scene.addLine(0, 0, 0, 0, guide_pen))
            guide_item.setData(0, "mechanism_item")
            cache["guide_line"] = guide_item
        cast(QGraphicsLineItem, cache["guide_line"]).setLine(
            float(follower_base[0]),
            float(follower_base[1] - 50),
            float(follower_base[0]),
            float(cam_center[1] + 150),
        )

        # 7. Base Rect
        base_width, base_height = 60, 30
        if "base_rect" not in cache:
            base_item = _require_graphics_item(
                self.scene.addRect(
                    0,
                    0,
                    base_width,
                    base_height,
                    QPen(QColor(80, 80, 80), 3),
                    QBrush(QColor(100, 100, 100)),
                )
            )
            base_item.setData(0, "mechanism_item")
            cache["base_rect"] = base_item
        cast(QGraphicsRectItem, cache["base_rect"]).setRect(
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
        teeth1 = int(_finite_float(metadata.get("gear1_teeth"), 16.0))
        teeth2 = int(_finite_float(metadata.get("gear2_teeth"), 18.0))
        theta1 = _finite_float(metadata.get("theta1"), 0.0)
        theta2 = _finite_float(metadata.get("theta2"), 0.0)
        grid_enabled = bool(metadata.get("grid_system_enabled", self._grid_system_enabled))
        grid_cell_cm = _finite_float(metadata.get("grid_cell_cm"), self._grid_cell_cm)
        profile = self._physical_profile

        def set_gear_body(
            key: str,
            center: tuple[float, float],
            radius: float,
            teeth: int,
            angle: float,
            stroke: QColor,
            fill: QColor,
        ) -> None:
            polygon = gear_outline_polygon(QPointF(center[0], center[1]), radius, teeth, angle)
            cached = cache.get(key)
            if not isinstance(cached, QGraphicsPolygonItem):
                if cached is not None and cached.scene() == self.scene:
                    self.scene.removeItem(cached)
                cached = cast(
                    QGraphicsPolygonItem,
                    self.scene.addPolygon(polygon, QPen(stroke, 2.5), QBrush(fill)),
                )
                cached.setData(0, "mechanism_item")
                cached.setZValue(12)
                cache[key] = cached
            else:
                cached.setPolygon(polygon)
                cached.setPen(QPen(stroke, 2.5))
                cached.setBrush(QBrush(fill))
            cached.setVisible(True)

        def set_holes(
            prefix: str, center: tuple[float, float], radius: float, angle: float
        ) -> None:
            hole_r = gear_hole_radius(radius)
            hole_pen = QPen(QColor("#5c4033"), 1.4)
            hole_brush = QBrush(QColor(255, 255, 255, 225))
            centers = (
                gear_grid_attachment_hole_centers(
                    QPointF(center[0], center[1]),
                    radius,
                    angle,
                    grid_cell_cm=grid_cell_cm,
                    profile=profile,
                )
                if grid_enabled
                else gear_attachment_hole_centers(
                    QPointF(center[0], center[1]), radius, angle, count=4
                )
            )
            active_keys: set[str] = set()
            for index, hole_center in enumerate(centers):
                key = f"{prefix}_attachment_hole_{index}"
                active_keys.add(key)
                item = cache.get(key)
                if not isinstance(item, QGraphicsEllipseItem):
                    if item is not None and item.scene() == self.scene:
                        self.scene.removeItem(item)
                    item = cast(
                        QGraphicsEllipseItem,
                        self.scene.addEllipse(0, 0, 1, 1, hole_pen, hole_brush),
                    )
                    item.setData(0, "mechanism_item")
                    item.setZValue(16)
                    cache[key] = item
                item.setRect(
                    hole_center.x() - hole_r, hole_center.y() - hole_r, hole_r * 2, hole_r * 2
                )
                item.setVisible(True)
            for key in tuple(cache):
                if key.startswith(f"{prefix}_attachment_hole_") and key not in active_keys:
                    old_item = cache.pop(key, None)
                    if old_item is not None and old_item.scene() == self.scene:
                        self.scene.removeItem(old_item)

        set_gear_body(
            "gear1_body",
            (float(g1[0]), float(g1[1])),
            r1,
            teeth1,
            theta1,
            QColor("#9a6a00"),
            QColor("#d8b45d"),
        )
        set_gear_body(
            "gear2_body",
            (float(g2[0]), float(g2[1])),
            r2,
            teeth2,
            theta2,
            QColor("#8a3f2d"),
            QColor("#c47b5c"),
        )
        set_holes("gear1", (float(g1[0]), float(g1[1])), r1, theta1)
        set_holes("gear2", (float(g2[0]), float(g2[1])), r2, theta2)

        if "gear1_indicator" not in cache:
            item = cast(
                QGraphicsLineItem,
                self.scene.addLine(0, 0, 0, 0, QPen(QColor("#ffffff"), 2)),
            )
            item.setData(0, "mechanism_item")
            cache["gear1_indicator"] = item
        cast(QGraphicsLineItem, cache["gear1_indicator"]).setLine(g1[0], g1[1], p1[0], p1[1])

        if "gear2_indicator" not in cache:
            item = cast(
                QGraphicsLineItem,
                self.scene.addLine(0, 0, 0, 0, QPen(QColor("#ffffff"), 2)),
            )
            item.setData(0, "mechanism_item")
            cache["gear2_indicator"] = item
        cast(QGraphicsLineItem, cache["gear2_indicator"]).setLine(g2[0], g2[1], p2[0], p2[1])

        if "gear_mesh_line" not in cache:
            mesh_pen = QPen(QColor(120, 120, 120), 1, Qt.PenStyle.DashLine)
            item = cast(QGraphicsLineItem, self.scene.addLine(0, 0, 0, 0, mesh_pen))
            item.setData(0, "mechanism_item")
            cache["gear_mesh_line"] = item
        cast(QGraphicsLineItem, cache["gear_mesh_line"]).setLine(g1[0], g1[1], g2[0], g2[1])

        has_linkage = bool(metadata.get("has_linkage"))
        linkage_pin = positions.get("linkage_pin")
        linkage_end = positions.get("linkage_end")
        if has_linkage and linkage_pin and linkage_end:
            if "gear_linkage_arm" not in cache:
                arm_pen = QPen(QColor("#c9ad10"), 7, Qt.PenStyle.SolidLine)
                arm_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                item = cast(QGraphicsLineItem, self.scene.addLine(0, 0, 0, 0, arm_pen))
                item.setData(0, "mechanism_item")
                item.setZValue(20)
                cache["gear_linkage_arm"] = item
            cast(QGraphicsLineItem, cache["gear_linkage_arm"]).setLine(
                linkage_pin[0],
                linkage_pin[1],
                linkage_end[0],
                linkage_end[1],
            )

            for key, point, color in (
                ("gear_linkage_pin", linkage_pin, QColor("#9b7a17")),
                ("gear_linkage_end", linkage_end, QColor("#d6b64c")),
            ):
                marker = cache.get(key)
                if not isinstance(marker, QGraphicsEllipseItem):
                    if marker is not None and marker.scene() == self.scene:
                        self.scene.removeItem(marker)
                    marker = cast(
                        QGraphicsEllipseItem,
                        self.scene.addEllipse(
                            0, 0, 1, 1, QPen(QColor("#5c4033"), 2), QBrush(color)
                        ),
                    )
                    marker.setData(0, "mechanism_item")
                    marker.setZValue(21)
                    cache[key] = marker
                marker.setRect(point[0] - 5.0, point[1] - 5.0, 10.0, 10.0)
        else:
            for key in ("gear_linkage_arm", "gear_linkage_pin", "gear_linkage_end"):
                old_item = cache.pop(key, None)
                if old_item is not None and old_item.scene() == self.scene:
                    self.scene.removeItem(old_item)

    def _draw_planetary_gear_mechanism_optimized(self, state: MechanismState) -> None:
        """Draw a realistic planetary gear preview with sun, planets, ring, and carrier."""
        positions = state.positions
        metadata = state.metadata or {}
        cache = self.visual_items_cache

        sun_center = positions.get("sun_center", (0.0, 0.0))
        r_sun = _finite_float(metadata.get("r_sun"), 24.0)
        r_planet = _finite_float(metadata.get("r_planet"), 18.0)
        sun_teeth = int(_finite_float(metadata.get("sun_teeth"), 14.0))
        planet_teeth = int(_finite_float(metadata.get("planet_teeth"), 12.0))
        ring_teeth = int(_finite_float(metadata.get("ring_teeth"), 40.0))
        planet_count = int(min(max(_finite_float(metadata.get("planet_count"), 1.0), 1.0), 4.0))
        theta_sun = _finite_float(metadata.get("theta_sun"), 0.0)
        theta_planet = _finite_float(metadata.get("theta_planet"), 0.0)
        ring_inner = _finite_float(metadata.get("ring_inner_radius"), r_sun + r_planet * 1.6)
        ring_outer = _finite_float(metadata.get("ring_outer_radius"), ring_inner + r_planet * 0.35)
        center_point = QPointF(float(sun_center[0]), float(sun_center[1]))
        grid_enabled = bool(metadata.get("grid_system_enabled", self._grid_system_enabled))
        grid_cell_cm = _finite_float(metadata.get("grid_cell_cm"), self._grid_cell_cm)
        active_dynamic_keys: set[str] = set()

        ring_key = "planetary_ring"
        ring_path = annulus_path(center_point, ring_outer, ring_inner)
        ring_item = cache.get(ring_key)
        if not isinstance(ring_item, QGraphicsPathItem):
            if ring_item is not None and ring_item.scene() == self.scene:
                self.scene.removeItem(ring_item)
            ring_item = cast(
                QGraphicsPathItem,
                self.scene.addPath(
                    ring_path,
                    QPen(QColor("#5d6d7e"), 3),
                    QBrush(QColor(180, 185, 190, 110)),
                ),
            )
            ring_item.setData(0, "mechanism_item")
            ring_item.setZValue(5)
            cache[ring_key] = ring_item
        else:
            ring_item.setPath(ring_path)
        ring_item.setVisible(True)

        for idx, (start, end) in enumerate(
            radial_tick_lines(
                center_point, ring_inner - 2.0, ring_inner + 4.0, ring_teeth, -theta_sun
            )
        ):
            key = f"planetary_ring_tooth_{idx}"
            active_dynamic_keys.add(key)
            item = cache.get(key)
            if not isinstance(item, QGraphicsLineItem):
                if item is not None and item.scene() == self.scene:
                    self.scene.removeItem(item)
                item = cast(
                    QGraphicsLineItem,
                    self.scene.addLine(0, 0, 0, 0, QPen(QColor("#5d6d7e"), 1)),
                )
                item.setData(0, "mechanism_item")
                item.setZValue(6)
                cache[key] = item
            item.setLine(start.x(), start.y(), end.x(), end.y())
            item.setVisible(idx < min(ring_teeth, 64))

        sun_polygon = gear_outline_polygon(center_point, r_sun, sun_teeth, theta_sun)
        sun_key = "planetary_sun_body"
        sun_item = cache.get(sun_key)
        if not isinstance(sun_item, QGraphicsPolygonItem):
            if sun_item is not None and sun_item.scene() == self.scene:
                self.scene.removeItem(sun_item)
            sun_item = cast(
                QGraphicsPolygonItem,
                self.scene.addPolygon(
                    sun_polygon,
                    QPen(QColor("#936b1f"), 2.5),
                    QBrush(QColor("#d7b65d")),
                ),
            )
            sun_item.setData(0, "mechanism_item")
            sun_item.setZValue(10)
            cache[sun_key] = sun_item
        else:
            sun_item.setPolygon(sun_polygon)
        sun_item.setVisible(True)

        carrier_pen = QPen(QColor("#7f8c8d"), 3, Qt.PenStyle.SolidLine)
        carrier_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        for idx in range(planet_count):
            planet_center = positions.get(f"planet_{idx + 1}_center")
            if planet_center is None:
                continue
            planet_point = QPointF(float(planet_center[0]), float(planet_center[1]))
            carrier_key = f"planetary_carrier_{idx + 1}"
            active_dynamic_keys.add(carrier_key)
            carrier = cache.get(carrier_key)
            if not isinstance(carrier, QGraphicsLineItem):
                if carrier is not None and carrier.scene() == self.scene:
                    self.scene.removeItem(carrier)
                carrier = cast(QGraphicsLineItem, self.scene.addLine(0, 0, 0, 0, carrier_pen))
                carrier.setData(0, "mechanism_item")
                carrier.setZValue(8)
                cache[carrier_key] = carrier
            carrier.setLine(center_point.x(), center_point.y(), planet_point.x(), planet_point.y())
            carrier.setVisible(True)

            planet_key = f"planetary_planet_{idx + 1}_body"
            active_dynamic_keys.add(planet_key)
            polygon = gear_outline_polygon(
                planet_point,
                r_planet,
                planet_teeth,
                theta_planet + (idx * 0.33),
            )
            planet_item = cache.get(planet_key)
            if not isinstance(planet_item, QGraphicsPolygonItem):
                if planet_item is not None and planet_item.scene() == self.scene:
                    self.scene.removeItem(planet_item)
                planet_item = cast(
                    QGraphicsPolygonItem,
                    self.scene.addPolygon(
                        polygon,
                        QPen(QColor("#9c4f22"), 2.2),
                        QBrush(QColor("#d38a4b")),
                    ),
                )
                planet_item.setData(0, "mechanism_item")
                planet_item.setZValue(12)
                cache[planet_key] = planet_item
            else:
                planet_item.setPolygon(polygon)
            planet_item.setVisible(True)

            hole_radius = gear_hole_radius(r_planet)
            hole_centers = (
                gear_grid_attachment_hole_centers(
                    planet_point,
                    r_planet,
                    theta_planet,
                    grid_cell_cm=grid_cell_cm,
                    profile=self._physical_profile,
                )
                if grid_enabled
                else gear_attachment_hole_centers(planet_point, r_planet, theta_planet, count=4)
            )
            for hole_idx, hole_center in enumerate(hole_centers):
                hole_key = f"planetary_planet_{idx + 1}_hole_{hole_idx}"
                active_dynamic_keys.add(hole_key)
                hole = cache.get(hole_key)
                if not isinstance(hole, QGraphicsEllipseItem):
                    if hole is not None and hole.scene() == self.scene:
                        self.scene.removeItem(hole)
                    hole = cast(
                        QGraphicsEllipseItem,
                        self.scene.addEllipse(
                            0,
                            0,
                            1,
                            1,
                            QPen(QColor("#5c4033"), 1.2),
                            QBrush(QColor(255, 255, 255, 225)),
                        ),
                    )
                    hole.setData(0, "mechanism_item")
                    hole.setZValue(14)
                    cache[hole_key] = hole
                hole.setRect(
                    hole_center.x() - hole_radius,
                    hole_center.y() - hole_radius,
                    hole_radius * 2,
                    hole_radius * 2,
                )
                hole.setVisible(True)

        for key, radius, brush_color in (
            ("planetary_sun_axle", 5.5, QColor("#34495e")),
            ("planetary_carrier_hub", 9.0, QColor(255, 255, 255, 210)),
        ):
            active_dynamic_keys.add(key)
            item = cache.get(key)
            if not isinstance(item, QGraphicsEllipseItem):
                if item is not None and item.scene() == self.scene:
                    self.scene.removeItem(item)
                item = cast(
                    QGraphicsEllipseItem,
                    self.scene.addEllipse(
                        0,
                        0,
                        1,
                        1,
                        QPen(QColor("#2c3e50"), 2),
                        QBrush(brush_color),
                    ),
                )
                item.setData(0, "mechanism_item")
                item.setZValue(18)
                cache[key] = item
            item.setRect(
                center_point.x() - radius,
                center_point.y() - radius,
                radius * 2,
                radius * 2,
            )
            item.setVisible(True)

        tracking_point = positions.get("tracking_point")
        planet_center = positions.get("planet_center")
        if tracking_point and planet_center:
            arm_key = "planetary_output_arm"
            arm = cache.get(arm_key)
            if not isinstance(arm, QGraphicsLineItem):
                if arm is not None and arm.scene() == self.scene:
                    self.scene.removeItem(arm)
                arm_pen = QPen(QColor("#c9ad10"), 6)
                arm_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                arm = cast(QGraphicsLineItem, self.scene.addLine(0, 0, 0, 0, arm_pen))
                arm.setData(0, "mechanism_item")
                arm.setZValue(20)
                cache[arm_key] = arm
            arm.setLine(planet_center[0], planet_center[1], tracking_point[0], tracking_point[1])
            arm.setVisible(True)

            end_key = "planetary_output_pin"
            end = cache.get(end_key)
            if not isinstance(end, QGraphicsEllipseItem):
                if end is not None and end.scene() == self.scene:
                    self.scene.removeItem(end)
                end = cast(
                    QGraphicsEllipseItem,
                    self.scene.addEllipse(
                        0,
                        0,
                        1,
                        1,
                        QPen(QColor("#5c4033"), 2),
                        QBrush(QColor("#d6b64c")),
                    ),
                )
                end.setData(0, "mechanism_item")
                end.setZValue(21)
                cache[end_key] = end
            end.setRect(tracking_point[0] - 5.0, tracking_point[1] - 5.0, 10.0, 10.0)
            end.setVisible(True)
        else:
            for key in ("planetary_output_arm", "planetary_output_pin"):
                item = cache.pop(key, None)
                if item is not None and item.scene() == self.scene:
                    self.scene.removeItem(item)

        stale_prefixes = (
            "planetary_ring_tooth_",
            "planetary_carrier_",
            "planetary_planet_",
        )
        for key in list(cache):
            if key.startswith(stale_prefixes) and key not in active_dynamic_keys:
                item = cache.pop(key)
                if item.scene() == self.scene:
                    self.scene.removeItem(item)

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
            slider_guide = _require_graphics_item(self.scene.addLine(-260, 0, 260, 0, guide_pen))
            slider_guide.setData(0, "mechanism_item")
            cache["slider_guide"] = slider_guide

        if "crank_link" not in cache:
            crank_link = _require_graphics_item(
                self.scene.addLine(0, 0, 0, 0, QPen(QColor("#1f77b4"), 4))
            )
            crank_link.setData(0, "mechanism_item")
            cache["crank_link"] = crank_link
        cast(QGraphicsLineItem, cache["crank_link"]).setLine(
            ground[0], ground[1], crank_end[0], crank_end[1]
        )

        if "rod_link" not in cache:
            rod_link = _require_graphics_item(
                self.scene.addLine(0, 0, 0, 0, QPen(QColor("#ff7f0e"), 4))
            )
            rod_link.setData(0, "mechanism_item")
            cache["rod_link"] = rod_link
        cast(QGraphicsLineItem, cache["rod_link"]).setLine(
            crank_end[0], crank_end[1], slider_pin[0], slider_pin[1]
        )

        if "ground_pivot" not in cache:
            ground_pivot = _require_graphics_item(
                self.scene.addEllipse(
                    0, 0, 1, 1, QPen(QColor(40, 40, 40), 2), QBrush(QColor(110, 110, 110))
                )
            )
            ground_pivot.setData(0, "mechanism_item")
            cache["ground_pivot"] = ground_pivot
        cast(QGraphicsEllipseItem, cache["ground_pivot"]).setRect(
            ground[0] - 7, ground[1] - 7, 14, 14
        )

        if "crank_pin" not in cache:
            crank_pin = _require_graphics_item(
                self.scene.addEllipse(
                    0, 0, 1, 1, QPen(QColor(40, 40, 40), 2), QBrush(QColor(220, 120, 80))
                )
            )
            crank_pin.setData(0, "mechanism_item")
            cache["crank_pin"] = crank_pin
        cast(QGraphicsEllipseItem, cache["crank_pin"]).setRect(
            crank_end[0] - 6, crank_end[1] - 6, 12, 12
        )

        if "slider_block" not in cache:
            slider_block = _require_graphics_item(
                self.scene.addRect(
                    0, 0, 1, 1, QPen(QColor(40, 40, 40), 2), QBrush(QColor(180, 180, 180))
                )
            )
            slider_block.setData(0, "mechanism_item")
            cache["slider_block"] = slider_block
        cast(QGraphicsRectItem, cache["slider_block"]).setRect(
            slider_center[0] - 18, slider_center[1] - 12, 36, 24
        )

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
                line = _require_graphics_item(self.scene.addLine(x, y, nx, ny, cam_pen))
                line.setData(0, "mechanism_item")

        cam_center_item = _require_graphics_item(
            self.scene.addEllipse(
                cam_center[0] - 8,
                cam_center[1] - 8,
                16,
                16,
                QPen(QColor(255, 0, 0), 2),
                QBrush(QColor(255, 100, 100)),
            )
        )
        cam_center_item.setData(0, "mechanism_item")

        contact_pen = QPen(QColor(220, 20, 60), 3)
        contact_item = _require_graphics_item(
            self.scene.addEllipse(
                contact_point[0] - 5,
                contact_point[1] - 5,
                10,
                10,
                contact_pen,
                QBrush(QColor(220, 20, 60)),
            )
        )
        contact_item.setData(0, "mechanism_item")

        follower_pen = QPen(QColor(80, 80, 80), 6)
        follower_line = _require_graphics_item(
            self.scene.addLine(
                follower_base[0],
                follower_base[1],
                follower_end[0],
                follower_end[1],
                follower_pen,
            )
        )
        follower_line.setData(0, "mechanism_item")

        follower_width = 30
        follower_height = 15
        follower_rect = _require_graphics_item(
            self.scene.addRect(
                follower_end[0] - follower_width / 2,
                follower_end[1] - follower_height / 2,
                follower_width,
                follower_height,
                QPen(QColor(50, 50, 50), 2),
                QBrush(QColor(120, 120, 120)),
            )
        )
        follower_rect.setData(0, "mechanism_item")

        guide_pen = QPen(QColor(150, 150, 150), 2, Qt.PenStyle.DashLine)
        guide_line = _require_graphics_item(
            self.scene.addLine(
                follower_base[0],
                follower_base[1] - 50,
                follower_base[0],
                cam_center[1] + 150,
                guide_pen,
            )
        )
        guide_line.setData(0, "mechanism_item")

        base_width = 60
        base_height = 30
        base_rect = _require_graphics_item(
            self.scene.addRect(
                follower_base[0] - base_width / 2,
                follower_base[1] - base_height / 2,
                base_width,
                base_height,
                QPen(QColor(80, 80, 80), 3),
                QBrush(QColor(100, 100, 100)),
            )
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

        message = safety.message
        if not self._current_angle_bounds_available:
            message = f"{message} | No valid input angle range"
        elif self._current_angle_bounds_partial:
            message = f"{message} | Valid input angle: {self._angle_range_text(self._current_angle_bounds)}"

        safety_html = f"<span style='color:{color}'>{prefix} {message}</span>"
        if safety_html == self._last_safety_html:
            return
        self._last_safety_html = safety_html
        self.safety_label.setText(safety_html)
        if self.info_panel is not None:
            self.info_panel.set_safety_status(f"{prefix} {message}", level.name.lower())

    def _draw_grid(self) -> None:
        for item in self._grid_items:
            if item.scene() == self.scene:
                self.scene.removeItem(item)
        self._grid_items.clear()

        if not self._grid_system_enabled:
            return

        cell_grid = max(1.0, float(self._grid_step_mm))
        major_interval = max(1, int(round(100.0 / cell_grid)))
        minor_color = QColor(190, 190, 190, 75)
        major_color = QColor(145, 145, 145, 120)
        axis_color = QColor(100, 100, 100, 200)
        board_color = QColor(37, 99, 235, 150)

        rect = self.scene.sceneRect()
        minor_pen = QPen(minor_color, 1, Qt.PenStyle.SolidLine)
        major_pen = QPen(major_color, 1, Qt.PenStyle.SolidLine)

        start_x = math.floor(rect.left() / cell_grid)
        end_x = math.ceil(rect.right() / cell_grid)
        for index_x in range(start_x, end_x + 1):
            x = index_x * cell_grid
            pen = major_pen if index_x % major_interval == 0 else minor_pen
            line = _require_graphics_item(self.scene.addLine(x, rect.top(), x, rect.bottom(), pen))
            line.setZValue(-99)
            line.setData(0, "fabrication_grid_line")
            self._grid_items.append(line)

        start_y = math.floor(rect.top() / cell_grid)
        end_y = math.ceil(rect.bottom() / cell_grid)
        for index_y in range(start_y, end_y + 1):
            y = index_y * cell_grid
            pen = major_pen if index_y % major_interval == 0 else minor_pen
            line = _require_graphics_item(self.scene.addLine(rect.left(), y, rect.right(), y, pen))
            line.setZValue(-99)
            line.setData(0, "fabrication_grid_line")
            self._grid_items.append(line)

        axis_pen = QPen(axis_color, 2, Qt.PenStyle.SolidLine)
        x_axis = _require_graphics_item(
            self.scene.addLine(rect.left(), 0, rect.right(), 0, axis_pen)
        )
        y_axis = _require_graphics_item(
            self.scene.addLine(0, rect.top(), 0, rect.bottom(), axis_pen)
        )
        x_axis.setZValue(-98)
        y_axis.setZValue(-98)
        x_axis.setData(0, "fabrication_axis")
        y_axis.setData(0, "fabrication_axis")
        self._grid_items.extend([x_axis, y_axis])

        board_size = (len(BOARD_COLUMNS) - 1) * cell_grid
        half_board = board_size / 2.0
        board_pen = QPen(board_color, 1.4, Qt.PenStyle.DashLine)
        board_fill = QBrush(QColor(37, 99, 235, 12))
        board = _require_graphics_item(
            self.scene.addRect(
                -half_board,
                -half_board,
                board_size,
                board_size,
                board_pen,
                board_fill,
            )
        )
        board.setZValue(-97.5)
        board.setData(0, "fabrication_board_boundary")
        board.setData(1, "15x15")
        self._grid_items.append(board)

        hole_radius = max(1.2, min(2.4, cell_grid * 0.08))
        board_hole_pen = QPen(QColor(30, 64, 175, 130), 0.6)
        board_hole_brush = QBrush(QColor(30, 64, 175, 60))
        for row in BOARD_ROWS:
            for column in BOARD_COLUMNS:
                label = f"{row}{column}"
                x_mm, y_mm = board_coord_to_centered_mm(label, cell_grid)
                hole = _require_graphics_item(
                    self.scene.addEllipse(
                        x_mm - hole_radius,
                        y_mm - hole_radius,
                        hole_radius * 2.0,
                        hole_radius * 2.0,
                        board_hole_pen,
                        board_hole_brush,
                    )
                )
                hole.setZValue(-97.0)
                hole.setData(0, "fabrication_board_hole")
                hole.setData(1, label)
                self._grid_items.append(hole)

        label_color = QColor(30, 64, 175, 180)
        for column in BOARD_COLUMNS:
            x_mm, _y_mm = board_coord_to_centered_mm(f"H{column}", cell_grid)
            label_item = _require_graphics_item(self.scene.addText(str(column)))
            label_item.setDefaultTextColor(label_color)
            label_item.setScale(0.42)
            label_item.setPos(x_mm - 3.0, -half_board - 16.0)
            label_item.setZValue(-96.5)
            label_item.setData(0, "fabrication_board_label")
            label_item.setData(1, str(column))
            self._grid_items.append(label_item)
        for row in BOARD_ROWS:
            _x_mm, y_mm = board_coord_to_centered_mm(f"{row}8", cell_grid)
            label_item = _require_graphics_item(self.scene.addText(row))
            label_item.setDefaultTextColor(label_color)
            label_item.setScale(0.42)
            label_item.setPos(-half_board - 17.0, y_mm - 6.0)
            label_item.setZValue(-96.5)
            label_item.setData(0, "fabrication_board_label")
            label_item.setData(1, row)
            self._grid_items.append(label_item)

        origin = _require_graphics_item(
            self.scene.addEllipse(-3, -3, 6, 6, axis_pen, QBrush(axis_color))
        )
        origin.setZValue(-97)
        origin.setData(0, "fabrication_board_origin")
        origin.setData(1, "H8")
        self._grid_items.append(origin)

    def _show_default_paths(self, state: MechanismState) -> None:
        """Show default paths for all tracked points."""
        if not self.current_mechanism or not self.path_preview_overlay.enabled:
            return

        mechanism_type = self._current_controller_mechanism_type()
        default_points_by_type = {
            "four_bar": ("B", "A"),
            "fourbar": ("B", "A"),
            "cam_follower": ("contact_point", "follower_base"),
            "gear_train": ("gear2_indicator_end", "gear1_indicator_end"),
            "gear_linkage": ("linkage_end", "linkage_pin", "gear2_indicator_end"),
            "planetary_gear": ("tracking_point", "planet_center"),
            "slider_crank": ("slider_pin", "crank_end"),
        }

        default_points: list[str] = []
        selected_point = self._selected_motion_state_key()
        if isinstance(selected_point, str) and selected_point in state.positions:
            default_points.append(selected_point)
        for point_name in default_points_by_type.get(mechanism_type, ()):
            if point_name not in default_points:
                default_points.append(point_name)

        visible_points = {point for point in default_points if point in state.positions}
        for point_name in self.path_preview_overlay.active_point_names():
            if point_name not in visible_points:
                self.path_preview_overlay.hide_path(point_name)
        for point_name in default_points:
            if point_name in state.positions:
                self.path_preview_overlay.show_path(
                    self.current_mechanism,
                    self._effective_physical_parameters(self.current_parameters),
                    point_name,
                )
                self.path_preview_overlay.update_progress_marker(
                    point_name,
                    state.positions[point_name],
                )

    def zoom_in(self) -> None:
        """Zoom in on the mechanism canvas."""
        self._viewport_controller.zoom_in()

    def zoom_out(self) -> None:
        """Zoom out from the mechanism canvas."""
        self._viewport_controller.zoom_out()

    def zoom_to_fit(self) -> None:
        """Fit the mechanism canvas content in view."""
        self._viewport_controller.zoom_to_fit()

    def reset_view(self) -> None:
        """Reset the mechanism canvas view."""
        self._viewport_controller.reset_view()

    def eventFilter(self, a0: QObject | None, a1: QEvent | None) -> bool:
        if a1 and a1.type() == QEvent.Type.MouseMove:
            if self.current_mechanism and self.path_preview_overlay.enabled:
                if isinstance(a1, QMouseEvent):
                    point_name = self._get_hovered_point_name(a1.pos())
                    if point_name:
                        self.path_preview_overlay.show_path(
                            self.current_mechanism,
                            self._effective_physical_parameters(self.current_parameters),
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
                    self._effective_physical_parameters(self.current_parameters),
                    self.current_angle,
                )
            except Exception:
                return None
            self._last_rendered_state = state
            self._last_rendered_mechanism = self.current_mechanism
            self._state_cache_valid = True

        mechanism_type = self._current_controller_mechanism_type()
        test_points_by_type = {
            "four_bar": ("A", "B"),
            "fourbar": ("A", "B"),
            "cam_follower": ("follower_base", "contact_point"),
            "gear_train": ("gear2_indicator_end", "gear1_indicator_end"),
            "gear_linkage": ("linkage_end", "linkage_pin", "gear2_indicator_end"),
            "planetary_gear": ("tracking_point", "planet_center"),
            "slider_crank": ("slider_pin", "crank_end"),
        }
        test_points = test_points_by_type.get(mechanism_type)
        if not test_points:
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

        elif mechanism_type in {"gear_train", "gear_linkage"}:
            grid_enabled = grid_enabled_from_params(parameters, self._grid_system_enabled)
            source_profile = physical_profile_from_params(
                self._effective_physical_parameters(parameters)
            )

            # Prefer live radii from Design editing over stale tooth-count params
            # only while physical-kit snapping is active. With the grid disabled,
            # preserve explicit freeform teeth so Design <-> Foundry sync does
            # not silently collapse custom gears back to presets.
            gear1_radius = _pick_float("gear1_radius", "r1")
            if grid_enabled and gear1_radius is not None and gear1_radius > 0.0:
                mapped["gear1_teeth"] = float(
                    gear_teeth_for_radius(gear1_radius, profile=source_profile)
                )
            else:
                gear1_teeth = _pick_float("gear1_teeth")
                if gear1_teeth is not None:
                    mapped["gear1_teeth"] = (
                        float(nearest_gear_teeth(gear1_teeth, profile=source_profile))
                        if grid_enabled
                        else float(max(1, int(round(gear1_teeth))))
                    )
                elif gear1_radius is not None and gear1_radius > 0.0:
                    mapped["gear1_teeth"] = float(
                        freeform_gear_teeth_for_radius(
                            gear1_radius,
                            profile=source_profile,
                        )
                    )

            gear2_radius = _pick_float("gear2_radius", "r2")
            if grid_enabled and gear2_radius is not None and gear2_radius > 0.0:
                mapped["gear2_teeth"] = float(
                    gear_teeth_for_radius(gear2_radius, profile=source_profile)
                )
            else:
                gear2_teeth = _pick_float("gear2_teeth")
                if gear2_teeth is not None:
                    mapped["gear2_teeth"] = (
                        float(nearest_gear_teeth(gear2_teeth, profile=source_profile))
                        if grid_enabled
                        else float(max(1, int(round(gear2_teeth))))
                    )
                elif gear2_radius is not None and gear2_radius > 0.0:
                    mapped["gear2_teeth"] = float(
                        freeform_gear_teeth_for_radius(
                            gear2_radius,
                            24,
                            profile=source_profile,
                        )
                    )

            input_torque = _pick_float("input_torque")
            if input_torque is not None:
                mapped["input_torque"] = input_torque
            input_angle = _pick_float("input_angle")
            if input_angle is not None:
                mapped["input_angle"] = input_angle
            if mechanism_type == "gear_linkage":
                mapped["gear_linkage_enabled"] = 1.0
                linkage_pin_radius = _pick_float("linkage_pin_radius")
                if linkage_pin_radius is not None:
                    mapped["linkage_pin_radius"] = linkage_pin_radius
                linkage_arm_length = _pick_float("linkage_arm_length")
                if linkage_arm_length is not None:
                    mapped["linkage_arm_length"] = linkage_arm_length

        elif mechanism_type == "planetary_gear":
            grid_enabled = grid_enabled_from_params(parameters, self._grid_system_enabled)
            source_profile = physical_profile_from_params(
                self._effective_physical_parameters(parameters)
            )
            for foundry_key, radius_keys, default_teeth in (
                ("sun_teeth", ("r_sun", "sun_radius"), 12),
                ("planet_teeth", ("r_planet", "planet_radius"), 14),
            ):
                radius = _pick_float(*radius_keys)
                if grid_enabled and radius is not None and radius > 0.0:
                    mapped[foundry_key] = float(
                        gear_teeth_for_radius(radius, profile=source_profile)
                    )
                    continue
                teeth = _pick_float(foundry_key)
                if teeth is not None:
                    mapped[foundry_key] = (
                        float(nearest_gear_teeth(teeth, profile=source_profile))
                        if grid_enabled
                        else float(max(1, int(round(teeth))))
                    )
                elif radius is not None and radius > 0.0:
                    mapped[foundry_key] = float(
                        freeform_gear_teeth_for_radius(
                            radius,
                            default_teeth,
                            profile=source_profile,
                        )
                    )
            planet_count = _pick_float("planet_count", "num_planets")
            if planet_count is not None:
                mapped["planet_count"] = float(min(max(round(planet_count), 1), 4))
            arm_length = _pick_float("carrier_arm_length", "arm_length")
            if arm_length is not None:
                mapped["carrier_arm_length"] = arm_length
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
            mechanism_type = self._current_controller_mechanism_type()
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
                self._update_angle_label()

            self._sync_physical_context_from_params(parameters)

            config = None
            if self.current_mechanism:
                config_type = self._current_controller_mechanism_type()
                config = self.controller.get_configuration(config_type)

            # Update current parameters and slider UI.
            for key, value in mapped_params.items():
                if key == "input_angle":
                    continue

                if key == self.OUTPUT_POINT_MODE_KEY:
                    if isinstance(value, str) and value:
                        self.current_parameters[key] = value  # type: ignore[assignment]
                        if self.current_mechanism:
                            self._refresh_motion_point_selector(
                                self._current_controller_mechanism_type()
                            )
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

        current_selector_type = self._current_controller_mechanism_type()

        if current_selector_type != selector_type:
            self._load_mechanism(selector_type)

    def clear_synced_mechanism(self) -> None:
        """Clear the synced mechanism reference."""
        self.synced_mechanism_id = None
