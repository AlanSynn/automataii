"""
Rendering module for four-bar mechanism visualization
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from PyQt6.QtCore import QLineF, QPointF, Qt
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
        """
        Render mechanism state to scene.

        Note: This legacy method recreates items every frame.
        Use update_scene() for high-performance animation.
        """
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

    def update_scene(
        self,
        state: MechanismState,
        scene: QGraphicsScene,
        config: RenderConfig,
        cache: dict[str, QGraphicsItem],
    ) -> None:
        """
        Update existing scene items or create them if missing.

        Args:
            state: Current mechanism state
            scene: The graphics scene
            config: Render configuration
            cache: Dictionary mapping item keys to QGraphicsItems
        """
        positions = state.positions
        O1 = QPointF(*positions["O1"])
        O4 = QPointF(*positions["O4"])
        A = QPointF(*positions["A"])
        B = QPointF(*positions["B"])

        stress_data = state.metadata.get("stress", {})

        # Helper to track used keys for cleanup
        used_keys = set()

        # Update Links
        self._update_link(
            scene,
            O1,
            A,
            stress_data.get("input", 0.0),
            config.show_labels,
            "Input",
            cache,
            used_keys,
        )
        self._update_link(
            scene,
            A,
            B,
            stress_data.get("coupler", 0.0),
            config.show_labels,
            "Coupler",
            cache,
            used_keys,
        )
        self._update_link(
            scene,
            B,
            O4,
            stress_data.get("output", 0.0),
            config.show_labels,
            "Output",
            cache,
            used_keys,
        )

        # Update Joints
        self._update_fixed_joint(scene, O1, "O1", config.show_labels, cache, used_keys)
        self._update_fixed_joint(scene, O4, "O4", config.show_labels, cache, used_keys)
        self._update_moving_joint(scene, A, "A", config.show_labels, cache, used_keys)
        self._update_moving_joint(scene, B, "B", config.show_labels, cache, used_keys)

        # Update Forces (Forces are dynamic, simpler to recreate or pool)
        # For now, we'll recreate forces but manage them via a special group key prefix
        if config.show_forces and state.forces:
            self._update_forces(scene, state.forces, cache, used_keys)

        # Cleanup unused items
        # (Optional: implement if topology changes frequently, but for 4-bar it's static)

    def _update_link(
        self,
        scene: QGraphicsScene,
        start: QPointF,
        end: QPointF,
        stress: float,
        show_labels: bool,
        label: str,
        cache: dict[str, QGraphicsItem],
        used_keys: set[str],
    ) -> None:
        # Calculate color
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

        # 1. Polygon Body
        poly_key = f"{label}_poly"
        used_keys.add(poly_key)

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

        if poly_key not in cache:
            brush = QBrush(color.lighter(150))
            pen = QPen(color, 1)
            item = scene.addPolygon(polygon, pen, brush)
            item.setOpacity(0.7)
            item.setData(0, "mechanism_item")  # Marker
            cache[poly_key] = item
        else:
            item = cache[poly_key]
            item.setPolygon(polygon)
            item.setBrush(QBrush(color.lighter(150)))
            item.setPen(QPen(color, 1))

        # 2. Main Line
        line_key = f"{label}_line"
        used_keys.add(line_key)
        if line_key not in cache:
            pen = QPen(color.darker(120), 3)
            item = scene.addLine(start.x(), start.y(), end.x(), end.y(), pen)
            item.setData(0, "mechanism_item")
            cache[line_key] = item
        else:
            item = cache[line_key]
            item.setLine(QLineF(start, end))
            item.setPen(QPen(color.darker(120), 3))

        # 3. Label
        if show_labels and label:
            text_key = f"{label}_text"
            used_keys.add(text_key)
            mid_x = (start.x() + end.x()) / 2
            mid_y = (start.y() + end.y()) / 2

            if text_key not in cache:
                item = scene.addText(label, QFont("Arial", 8))
                item.setDefaultTextColor(QColor(60, 60, 60))
                item.setData(0, "mechanism_item")
                cache[text_key] = item
            else:
                item = cache[text_key]

            item.setPos(mid_x + 5, mid_y - 15)
            item.setVisible(True)
        else:
            # Hide text if disabled
            text_key = f"{label}_text"
            if text_key in cache:
                cache[text_key].setVisible(False)

    def _update_fixed_joint(
        self,
        scene: QGraphicsScene,
        position: QPointF,
        joint_id: str,
        show_labels: bool,
        cache: dict[str, QGraphicsItem],
        used_keys: set[str],
    ) -> None:
        # Base key
        base_key = f"fixed_{joint_id}"

        size = 16
        color = QColor(105, 105, 105)

        # Ground lines (3 lines)
        for i in range(3):
            line_key = f"{base_key}_gnd_{i}"
            used_keys.add(line_key)
            x_offset = -15 + i * 7

            p1 = QPointF(position.x() + x_offset, position.y())
            p2 = QPointF(position.x() + x_offset - 8, position.y() + 8)

            if line_key not in cache:
                item = scene.addLine(p1.x(), p1.y(), p2.x(), p2.y(), QPen(color, 1))
                item.setData(0, "mechanism_item")
                cache[line_key] = item
            else:
                item = cache[line_key]
                item.setLine(QLineF(p1, p2))

        # Main Joint Circle
        circle_key = f"{base_key}_circle"
        used_keys.add(circle_key)
        if circle_key not in cache:
            item = scene.addEllipse(0, 0, size, size, QPen(color.darker(120), 2), QBrush(color))
            item.setZValue(10)
            item.setData(0, "mechanism_item")
            cache[circle_key] = item

        cache[circle_key].setRect(position.x() - size / 2, position.y() - size / 2, size, size)

        # Inner Circle
        inner_key = f"{base_key}_inner"
        used_keys.add(inner_key)
        inner_size = size * 0.4
        if inner_key not in cache:
            item = scene.addEllipse(
                0,
                0,
                inner_size,
                inner_size,
                QPen(Qt.PenStyle.NoPen),
                QBrush(QColor(255, 255, 255, 150)),
            )
            item.setZValue(11)
            item.setData(0, "mechanism_item")
            cache[inner_key] = item

        cache[inner_key].setRect(
            position.x() - inner_size / 2, position.y() - inner_size / 2, inner_size, inner_size
        )

        # Label
        text_key = f"{base_key}_text"
        if show_labels:
            used_keys.add(text_key)
            if text_key not in cache:
                item = scene.addText(joint_id, QFont("Arial", 8))
                item.setDefaultTextColor(QColor(60, 60, 60))
                item.setData(0, "mechanism_item")
                cache[text_key] = item

            cache[text_key].setPos(position.x() + size / 2 + 5, position.y() - 10)
            cache[text_key].setVisible(True)
        elif text_key in cache:
            cache[text_key].setVisible(False)

    def _update_moving_joint(
        self,
        scene: QGraphicsScene,
        position: QPointF,
        joint_id: str,
        show_labels: bool,
        cache: dict[str, QGraphicsItem],
        used_keys: set[str],
    ) -> None:
        base_key = f"moving_{joint_id}"
        size = 12
        color = QColor(220, 20, 60)

        # Main Circle
        circle_key = f"{base_key}_circle"
        used_keys.add(circle_key)
        if circle_key not in cache:
            item = scene.addEllipse(0, 0, size, size, QPen(color.darker(120), 2), QBrush(color))
            item.setZValue(10)
            item.setData(0, "mechanism_item")
            cache[circle_key] = item

        cache[circle_key].setRect(position.x() - size / 2, position.y() - size / 2, size, size)

        # Inner Circle
        inner_key = f"{base_key}_inner"
        used_keys.add(inner_key)
        inner_size = size * 0.4
        if inner_key not in cache:
            item = scene.addEllipse(
                0,
                0,
                inner_size,
                inner_size,
                QPen(Qt.PenStyle.NoPen),
                QBrush(QColor(255, 255, 255, 150)),
            )
            item.setZValue(11)
            item.setData(0, "mechanism_item")
            cache[inner_key] = item

        cache[inner_key].setRect(
            position.x() - inner_size / 2, position.y() - inner_size / 2, inner_size, inner_size
        )

        # Label
        text_key = f"{base_key}_text"
        if show_labels:
            used_keys.add(text_key)
            if text_key not in cache:
                item = scene.addText(joint_id, QFont("Arial", 8))
                item.setDefaultTextColor(QColor(60, 60, 60))
                item.setData(0, "mechanism_item")
                cache[text_key] = item

            cache[text_key].setPos(position.x() + size / 2 + 5, position.y() - 10)
            cache[text_key].setVisible(True)
        elif text_key in cache:
            cache[text_key].setVisible(False)

    def _update_forces(
        self,
        scene: QGraphicsScene,
        forces: dict[str, ForceVector],
        cache: dict[str, QGraphicsItem],
        used_keys: set[str],
    ) -> None:
        # Prune old force items that are no longer in the current force list
        # This is a bit simplistic but works given forces change rapidly
        for force_id, force_vec in forces.items():
            base_key = f"force_{force_id}"
            line_key = f"{base_key}_arrow"
            head_key = f"{base_key}_head"
            used_keys.add(line_key)
            used_keys.add(head_key)

            pos = force_vec.position
            mag = force_vec.magnitude
            angle_rad = math.radians(force_vec.angle)
            scale = 2.0

            end_x = pos.x() + mag * scale * math.cos(angle_rad)
            end_y = pos.y() + mag * scale * math.sin(angle_rad)
            end_pt = QPointF(end_x, end_y)

            color = force_vec.color or QColor(255, 0, 0, 200)
            pen = QPen(color, 2)

            # Arrow Line
            if line_key not in cache:
                item = scene.addLine(pos.x(), pos.y(), end_x, end_y, pen)
                item.setData(0, "mechanism_item")
                cache[line_key] = item
            else:
                item = cache[line_key]
                item.setLine(QLineF(pos, end_pt))
                item.setPen(pen)

            # Arrow Head
            arrow_size = 8
            arrow_angle1 = angle_rad + math.pi * 0.85
            arrow_angle2 = angle_rad - math.pi * 0.85

            p1 = QPointF(
                end_x + arrow_size * math.cos(arrow_angle1),
                end_y + arrow_size * math.sin(arrow_angle1),
            )
            p2 = QPointF(
                end_x + arrow_size * math.cos(arrow_angle2),
                end_y + arrow_size * math.sin(arrow_angle2),
            )

            head_poly = QPolygonF([end_pt, p1, p2])

            if head_key not in cache:
                item = scene.addPolygon(head_poly, pen, QBrush(color))
                item.setData(0, "mechanism_item")
                cache[head_key] = item
            else:
                item = cache[head_key]
                item.setPolygon(head_poly)
                item.setPen(pen)
                item.setBrush(QBrush(color))

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
