from __future__ import annotations

import math
from typing import TYPE_CHECKING, Protocol

from PyQt6.QtCore import QPointF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QHideEvent, QMouseEvent, QPen, QShowEvent
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from automataii.presentation.qt.gear_rendering import (
    annulus_path,
    gear_attachment_hole_centers,
    gear_hole_radius,
    gear_outline_polygon,
    radial_tick_lines,
)

if TYPE_CHECKING:
    from automataii.domain.mechanisms.core.protocols import Mechanism
    from automataii.domain.mechanisms.core.state import MechanismState


class _PreviewRenderer(Protocol):
    def render(self, state: object, scene: QGraphicsScene, config: object) -> object: ...


def _safe_label_text(value: object, default: str = "", max_chars: int = 240) -> str:
    if value is None:
        text = default
    else:
        text = str(value).strip() or default
    if max_chars > 1 and len(text) > max_chars:
        return f"{text[: max_chars - 1]}…"
    return text


class GalleryThumbnail(QFrame):
    clicked = pyqtSignal(str)

    def __init__(
        self,
        mechanism_type: str,
        display_name: str,
        description: str,
        parent: QWidget | None = None,
        motion_summary: str = "",
    ):
        super().__init__(parent)
        self.mechanism_type = _safe_label_text(mechanism_type, max_chars=80)
        self.display_name = _safe_label_text(
            display_name,
            default="Untitled mechanism",
            max_chars=80,
        )
        self.description = _safe_label_text(
            description,
            default="Preview description unavailable.",
            max_chars=320,
        )
        self.motion_summary = _safe_label_text(motion_summary, max_chars=160)
        self.current_angle = 0.0
        self.mechanism: Mechanism | None = None
        self.renderer: _PreviewRenderer | None = None
        self.params: dict[str, float] = {}

        self._setup_ui()
        self._setup_animation()

    def _setup_ui(self) -> None:
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setStyleSheet(
            """
            GalleryThumbnail {
                background-color: white;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                padding: 12px;
            }
            GalleryThumbnail:hover {
                border-color: #3498db;
                background-color: #f8f9fa;
            }
            """
        )
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(300)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(14, 14, 14, 12)

        title_label = QLabel(self.display_name)
        title_label.setTextFormat(Qt.TextFormat.PlainText)
        title_label.setStyleSheet(
            """
            font-size: 16px;
            font-weight: 600;
            color: #2c3e50;
            """
        )
        layout.addWidget(title_label)

        motion_label = QLabel()
        motion_label.setTextFormat(Qt.TextFormat.PlainText)
        if self.motion_summary:
            motion_label.setText(f"Motions: {self.motion_summary}")
        else:
            motion_label.setText("Motions: Preview available")
        motion_label.setWordWrap(True)
        motion_label.setStyleSheet(
            """
            color: #4f46e5;
            font-size: 11px;
            font-weight: 600;
            background-color: #eef2ff;
            border: 1px solid #c7d2fe;
            border-radius: 10px;
            padding: 4px 8px;
            """
        )
        layout.addWidget(motion_label)

        desc_label = QLabel(self.description)
        desc_label.setTextFormat(Qt.TextFormat.PlainText)
        desc_label.setWordWrap(True)
        desc_label.setMaximumHeight(72)
        desc_label.setStyleSheet(
            """
            font-size: 12px;
            color: #7f8c8d;
            line-height: 1.4;
            """
        )
        layout.addWidget(desc_label)

        self.scene = QGraphicsScene()
        self.scene.setSceneRect(-150, -100, 300, 200)
        self.scene.setBackgroundBrush(QBrush(QColor(250, 250, 250)))

        self.graphics_view = QGraphicsView(self.scene)
        self.graphics_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.graphics_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.graphics_view.setMinimumHeight(130)
        self.graphics_view.setMaximumHeight(165)
        self.graphics_view.setStyleSheet("border: 1px solid #ddd; border-radius: 4px;")
        layout.addWidget(self.graphics_view)

        click_hint = QLabel("Click to explore →")
        click_hint.setTextFormat(Qt.TextFormat.PlainText)
        click_hint.setStyleSheet(
            """
            font-size: 11px;
            color: #3498db;
            font-weight: 500;
            """
        )
        layout.addWidget(click_hint)

    def _setup_animation(self) -> None:
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self._animate)
        self._load_mechanism()
        self._render_preview()
        if self.mechanism and self.isVisible():
            self.animation_timer.start(50)

    def _load_mechanism(self) -> None:
        if self.mechanism_type == "four_bar":
            from automataii.domain.mechanisms.linkages.fourbar.compute import FourBarMechanism
            from automataii.presentation.qt.mechanisms.renderers import LinkageRenderer

            self.mechanism = FourBarMechanism()
            self.renderer = LinkageRenderer()
            self.params = {"link1": 100.0, "link2": 80.0, "link3": 120.0, "link4": 100.0}
        elif self.mechanism_type == "cam_follower":
            from automataii.domain.mechanisms.cam.compute import CamFollowerMechanism

            self.mechanism = CamFollowerMechanism()
            self.renderer = None
            self.params = {
                "cam_radius": 50.0,
                "follower_offset": 0.0,
                "base_circle_radius": 40.0,
            }
        elif self.mechanism_type == "slider_crank":
            self.mechanism = None
            self.renderer = None
            self.params = {}
        elif self.mechanism_type == "gear_train":
            self.mechanism = None
            self.renderer = None
            self.params = {}
        elif self.mechanism_type in {"gear_linkage", "planetary_gear"}:
            self.mechanism = None
            self.renderer = None
            self.params = {}
        else:
            self.mechanism = None
            self.renderer = None
            self.params = {}

    def _animate(self) -> None:
        self.current_angle = (self.current_angle + 3.0) % 360.0
        self._render_preview()

    def _render_preview(self) -> None:
        self.scene.clear()

        if self.mechanism_type in {"gear_train", "gear_linkage"}:
            self._draw_gear_preview(with_linkage=self.mechanism_type == "gear_linkage")
            return
        if self.mechanism_type == "planetary_gear":
            self._draw_planetary_preview()
            return

        if not self.mechanism:
            self._draw_placeholder()
            return

        try:
            from automataii.domain.mechanisms.core.state import RenderConfig

            state = self.mechanism.compute_state(self.params, self.current_angle)

            if self.mechanism_type == "four_bar" and self.renderer:
                config = RenderConfig(show_forces=False, show_labels=False, show_safety_zones=False)
                self.renderer.render(state, self.scene, config)
            elif self.mechanism_type == "cam_follower":
                self._draw_cam_preview(state)
            else:
                self._draw_placeholder()

        except Exception:
            self._draw_placeholder()

    def _draw_cam_preview(self, state: MechanismState) -> None:
        positions = state.positions
        cam_center = positions.get("cam_center", (0, 0))
        contact_point = positions.get("contact_point", (0, 0))
        follower_base = positions.get("follower_base", (0, 0))
        follower_end = positions.get("follower_end", (0, 0))

        cam_profile = state.metadata.get("cam_profile", [])
        if cam_profile:
            cam_pen = QPen(QColor(70, 130, 180), 2)
            for i, (x, y) in enumerate(cam_profile):
                next_idx = (i + 1) % len(cam_profile)
                nx, ny = cam_profile[next_idx]
                self.scene.addLine(x, y, nx, ny, cam_pen)

        self.scene.addEllipse(
            cam_center[0] - 5,
            cam_center[1] - 5,
            10,
            10,
            QPen(QColor(255, 0, 0), 2),
            QBrush(QColor(255, 100, 100)),
        )

        self.scene.addEllipse(
            contact_point[0] - 3,
            contact_point[1] - 3,
            6,
            6,
            QPen(QColor(220, 20, 60), 2),
            QBrush(QColor(220, 20, 60)),
        )

        follower_pen = QPen(QColor(80, 80, 80), 4)
        self.scene.addLine(
            follower_base[0], follower_base[1], follower_end[0], follower_end[1], follower_pen
        )

        self.scene.addRect(
            follower_end[0] - 15,
            follower_end[1] - 8,
            30,
            16,
            QPen(QColor(50, 50, 50), 2),
            QBrush(QColor(120, 120, 120)),
        )

    def _draw_gear_shape(
        self,
        center: QPointF,
        radius: float,
        teeth: int,
        angle: float,
        stroke: QColor,
        fill: QColor,
    ) -> None:
        gear = self.scene.addPolygon(
            gear_outline_polygon(center, radius, teeth, angle),
            QPen(stroke, 2),
            QBrush(fill),
        )
        assert gear is not None
        gear.setZValue(5)
        hole_r = gear_hole_radius(radius)
        for hole_center in gear_attachment_hole_centers(center, radius, angle, count=4):
            self.scene.addEllipse(
                hole_center.x() - hole_r,
                hole_center.y() - hole_r,
                hole_r * 2,
                hole_r * 2,
                QPen(QColor("#5c4033"), 1),
                QBrush(QColor(255, 255, 255, 225)),
            )
        self.scene.addEllipse(
            center.x() - 5,
            center.y() - 5,
            10,
            10,
            QPen(QColor("#5c4033"), 1.5),
            QBrush(QColor("#8c6d1f")),
        )

    def _draw_gear_preview(self, *, with_linkage: bool) -> None:
        angle = self.current_angle * 0.03
        c1 = QPointF(-48, 0)
        c2 = QPointF(25, 0)
        r1 = 28.0
        r2 = 34.0
        self._draw_gear_shape(c1, r1, 12, angle, QColor("#9a6a00"), QColor("#d8b45d"))
        self._draw_gear_shape(c2, r2, 16, -angle * (r1 / r2), QColor("#8a3f2d"), QColor("#c47b5c"))
        self.scene.addLine(
            c1.x(),
            c1.y(),
            c2.x(),
            c2.y(),
            QPen(QColor(120, 120, 120), 1, Qt.PenStyle.DashLine),
        )
        if not with_linkage:
            return
        pin_angle = -angle * (r1 / r2)
        pin_radius = r2 * 0.55
        pin = QPointF(
            c2.x() + pin_radius * math.cos(pin_angle), c2.y() + pin_radius * math.sin(pin_angle)
        )
        end = QPointF(pin.x() + 64.0 * math.cos(pin_angle), pin.y() + 64.0 * math.sin(pin_angle))
        arm_pen = QPen(QColor("#c9ad10"), 7)
        arm_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        self.scene.addLine(pin.x(), pin.y(), end.x(), end.y(), arm_pen)
        for point in (pin, end):
            self.scene.addEllipse(
                point.x() - 5,
                point.y() - 5,
                10,
                10,
                QPen(QColor("#5c4033"), 1.5),
                QBrush(QColor("#d6b64c")),
            )

    def _draw_planetary_preview(self) -> None:
        angle = self.current_angle * 0.025
        center = QPointF(0, 0)
        ring_inner = 66.0
        ring_outer = 78.0
        self.scene.addPath(
            annulus_path(center, ring_outer, ring_inner),
            QPen(QColor("#5d6d7e"), 2),
            QBrush(QColor(180, 185, 190, 90)),
        )
        for start, end in radial_tick_lines(center, ring_inner - 2, ring_inner + 4, 36):
            self.scene.addLine(start.x(), start.y(), end.x(), end.y(), QPen(QColor("#5d6d7e"), 1))
        self._draw_gear_shape(center, 24.0, 12, angle, QColor("#936b1f"), QColor("#d7b65d"))
        orbit = 42.0
        for idx in range(3):
            planet_angle = angle + idx * (2.0 * math.pi / 3.0)
            planet = QPointF(orbit * math.cos(planet_angle), orbit * math.sin(planet_angle))
            carrier_pen = QPen(QColor("#7f8c8d"), 2.5)
            carrier_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            self.scene.addLine(center.x(), center.y(), planet.x(), planet.y(), carrier_pen)
            self._draw_gear_shape(
                planet,
                18.0,
                12,
                -angle * 1.7,
                QColor("#9c4f22"),
                QColor("#d38a4b"),
            )

    def _draw_placeholder(self) -> None:
        text = self.scene.addText("Preview Coming Soon")
        if text:
            text.setFont(QFont("Arial", 12))
            text.setDefaultTextColor(QColor(150, 150, 150))
            text.setPos(-80, -10)

    def mousePressEvent(self, a0: QMouseEvent | None) -> None:
        self.clicked.emit(self.mechanism_type)
        super().mousePressEvent(a0)

    def showEvent(self, event: QShowEvent | None) -> None:
        """Start animation when widget becomes visible."""
        super().showEvent(event)
        if self.mechanism and not self.animation_timer.isActive():
            self.animation_timer.start(50)

    def hideEvent(self, event: QHideEvent | None) -> None:
        """Stop animation when widget is hidden to save CPU."""
        super().hideEvent(event)
        self.animation_timer.stop()
