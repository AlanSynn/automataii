"""
Rendering module for four-bar mechanism visualization
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPen, QPolygonF
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsScene

from automataii.domain.mechanisms.core.state import MechanismState, RenderConfig

if TYPE_CHECKING:
    from automataii.domain.mechanisms.core.state import ForceVector


class LinkageRenderer:
    def render(
        self,
        state: MechanismState,
        scene: QGraphicsScene,
        config: RenderConfig,
    ) -> list[QGraphicsItem]:
        items: list[QGraphicsItem] = []

        positions = state.positions
        O1 = QPointF(*positions["O1"])
        O4 = QPointF(*positions["O4"])
        A = QPointF(*positions["A"])
        B = QPointF(*positions["B"])

        stress_data = state.metadata.get("stress", {})

        items.extend(
            self._draw_link(
                scene, O1, A, stress_data.get("input", 0.0), config.show_labels, "Input"
            )
        )
        items.extend(
            self._draw_link(
                scene, A, B, stress_data.get("coupler", 0.0), config.show_labels, "Coupler"
            )
        )
        items.extend(
            self._draw_link(
                scene, B, O4, stress_data.get("output", 0.0), config.show_labels, "Output"
            )
        )

        items.extend(self._draw_fixed_joint(scene, O1, "O1", config.show_labels))
        items.extend(self._draw_fixed_joint(scene, O4, "O4", config.show_labels))
        items.extend(self._draw_moving_joint(scene, A, "A", config.show_labels))
        items.extend(self._draw_moving_joint(scene, B, "B", config.show_labels))

        if config.show_forces and state.forces:
            items.extend(self._render_forces(scene, state.forces))

        return items

    def _draw_link(
        self,
        scene: QGraphicsScene,
        start: QPointF,
        end: QPointF,
        stress: float,
        show_labels: bool,
        label: str = "",
    ) -> list[QGraphicsItem]:
        items: list[QGraphicsItem] = []
        base_color = QColor(70, 130, 180)

        if stress != 0:
            intensity = min(abs(stress), 1.0)
            if stress > 0:
                color = QColor(
                    int(255 * intensity + base_color.red() * (1 - intensity)),
                    int(base_color.green() * (1 - intensity)),
                    int(base_color.blue() * (1 - intensity)),
                )
            else:
                color = QColor(
                    int(base_color.red() * (1 - intensity)),
                    int(base_color.green() * (1 - intensity)),
                    int(255 * intensity + base_color.blue() * (1 - intensity)),
                )
        else:
            color = base_color

        angle = math.atan2(end.y() - start.y(), end.x() - start.x())
        width = 8
        perp_x = -math.sin(angle) * width / 2
        perp_y = math.cos(angle) * width / 2

        polygon = QPolygonF(
            [
                QPointF(start.x() + perp_x, start.y() + perp_y),
                QPointF(start.x() - perp_x, start.y() - perp_y),
                QPointF(end.x() - perp_x, end.y() - perp_y),
                QPointF(end.x() + perp_x, end.y() + perp_y),
            ]
        )

        brush = QBrush(color.lighter(150))
        pen = QPen(color, 1)
        poly_item = scene.addPolygon(polygon, pen, brush)
        poly_item.setOpacity(0.7)
        items.append(poly_item)

        main_pen = QPen(color.darker(120), 3)
        line = scene.addLine(start.x(), start.y(), end.x(), end.y(), main_pen)
        items.append(line)

        if show_labels and label:
            mid_x = (start.x() + end.x()) / 2
            mid_y = (start.y() + end.y()) / 2
            text = scene.addText(label, QFont("Arial", 8))
            text.setPos(mid_x + 5, mid_y - 15)
            text.setDefaultTextColor(QColor(60, 60, 60))
            items.append(text)

        return items

    def _draw_fixed_joint(
        self, scene: QGraphicsScene, position: QPointF, joint_id: str, show_labels: bool
    ) -> list[QGraphicsItem]:
        items: list[QGraphicsItem] = []
        size = 16
        color = QColor(105, 105, 105)

        for i in range(3):
            x_offset = -15 + i * 7
            line = scene.addLine(
                position.x() + x_offset,
                position.y(),
                position.x() + x_offset - 8,
                position.y() + 8,
                QPen(color, 1),
            )
            items.append(line)

        joint = scene.addEllipse(
            position.x() - size / 2,
            position.y() - size / 2,
            size,
            size,
            QPen(color.darker(120), 2),
            QBrush(color),
        )
        joint.setZValue(10)
        items.append(joint)

        inner_size = size * 0.4
        inner = scene.addEllipse(
            position.x() - inner_size / 2,
            position.y() - inner_size / 2,
            inner_size,
            inner_size,
            QPen(Qt.PenStyle.NoPen),
            QBrush(QColor(255, 255, 255, 150)),
        )
        inner.setZValue(11)
        items.append(inner)

        if show_labels:
            text = scene.addText(joint_id, QFont("Arial", 8))
            text.setPos(position.x() + size / 2 + 5, position.y() - 10)
            text.setDefaultTextColor(QColor(60, 60, 60))
            items.append(text)

        return items

    def _draw_moving_joint(
        self, scene: QGraphicsScene, position: QPointF, joint_id: str, show_labels: bool
    ) -> list[QGraphicsItem]:
        items: list[QGraphicsItem] = []
        size = 12
        color = QColor(220, 20, 60)

        joint = scene.addEllipse(
            position.x() - size / 2,
            position.y() - size / 2,
            size,
            size,
            QPen(color.darker(120), 2),
            QBrush(color),
        )
        joint.setZValue(10)
        items.append(joint)

        inner_size = size * 0.4
        inner = scene.addEllipse(
            position.x() - inner_size / 2,
            position.y() - inner_size / 2,
            inner_size,
            inner_size,
            QPen(Qt.PenStyle.NoPen),
            QBrush(QColor(255, 255, 255, 150)),
        )
        inner.setZValue(11)
        items.append(inner)

        if show_labels:
            text = scene.addText(joint_id, QFont("Arial", 8))
            text.setPos(position.x() + size / 2 + 5, position.y() - 10)
            text.setDefaultTextColor(QColor(60, 60, 60))
            items.append(text)

        return items

    def _render_forces(
        self, scene: QGraphicsScene, forces: dict[str, ForceVector]
    ) -> list[QGraphicsItem]:
        items: list[QGraphicsItem] = []

        for _force_id, force_vec in forces.items():
            pos = force_vec.position
            mag = force_vec.magnitude
            angle_rad = math.radians(force_vec.angle)

            scale = 2.0
            end_x = pos.x() + mag * scale * math.cos(angle_rad)
            end_y = pos.y() + mag * scale * math.sin(angle_rad)

            color = force_vec.color or QColor(255, 0, 0, 200)
            pen = QPen(color, 2)
            arrow_line = scene.addLine(pos.x(), pos.y(), end_x, end_y, pen)
            items.append(arrow_line)

            arrow_size = 8
            arrow_angle1 = angle_rad + math.pi * 0.85
            arrow_angle2 = angle_rad - math.pi * 0.85

            arrow_p1 = QPointF(
                end_x + arrow_size * math.cos(arrow_angle1),
                end_y + arrow_size * math.sin(arrow_angle1),
            )
            arrow_p2 = QPointF(
                end_x + arrow_size * math.cos(arrow_angle2),
                end_y + arrow_size * math.sin(arrow_angle2),
            )

            arrow_head = QPolygonF([QPointF(end_x, end_y), arrow_p1, arrow_p2])
            arrow_item = scene.addPolygon(arrow_head, pen, QBrush(color))
            items.append(arrow_item)

        return items
