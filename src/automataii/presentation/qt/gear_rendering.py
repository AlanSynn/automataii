"""Qt gear drawing helpers shared by Foundry, Design, and recommendation previews."""

from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QPainterPath, QPolygonF


def _finite_float(value: object, default: float) -> float:
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _safe_teeth(teeth: object, default: int = 14) -> int:
    rounded = int(round(_finite_float(teeth, float(default))))
    return min(max(rounded, 6), 80)


def gear_tooth_depth(radius: object) -> float:
    """Return a visible tooth depth for a pitch-radius in scene units."""
    safe_radius = max(1.0, abs(_finite_float(radius, 1.0)))
    return max(1.6, min(safe_radius * 0.18, 5.0))


def gear_root_radius(radius: object) -> float:
    """Return the root radius used by app-level tooth previews."""
    safe_radius = max(1.0, abs(_finite_float(radius, 1.0)))
    return max(1.0, safe_radius - gear_tooth_depth(safe_radius) * 0.75)


def gear_outer_radius(radius: object) -> float:
    """Return the outer radius used by app-level tooth previews."""
    safe_radius = max(1.0, abs(_finite_float(radius, 1.0)))
    return safe_radius + gear_tooth_depth(safe_radius)


def gear_outline_polygon(
    center: QPointF,
    pitch_radius: object,
    teeth: object,
    rotation_rad: float = 0.0,
) -> QPolygonF:
    """Build a simple tooth polygon around a pitch circle.

    The app deliberately uses a stylized involute-like outline rather than a true
    manufacturing tooth profile; fabrication SVGs remain the print source of
    truth. Keeping this helper shared prevents Foundry, Design, and dialogs from
    drifting back to plain circles.
    """
    tooth_count = _safe_teeth(teeth)
    root = gear_root_radius(pitch_radius)
    outer = gear_outer_radius(pitch_radius)
    points: list[QPointF] = []
    for tooth_idx in range(tooth_count):
        base = rotation_rad + (2.0 * math.pi * tooth_idx / tooth_count)
        for fraction, radius in ((0.08, root), (0.28, outer), (0.56, outer), (0.82, root)):
            theta = base + (2.0 * math.pi * fraction / tooth_count)
            points.append(
                QPointF(
                    center.x() + radius * math.cos(theta), center.y() + radius * math.sin(theta)
                )
            )
    return QPolygonF(points)


def gear_attachment_hole_centers(
    center: QPointF,
    pitch_radius: object,
    rotation_rad: float = 0.0,
    *,
    count: int = 4,
) -> tuple[QPointF, ...]:
    safe_radius = max(1.0, abs(_finite_float(pitch_radius, 1.0)))
    hole_count = min(max(count, 3), 8)
    ring_radius = min(max(safe_radius * 0.52, safe_radius - 9.0), max(2.0, safe_radius - 5.0))
    return tuple(
        QPointF(
            center.x() + ring_radius * math.cos(rotation_rad + 2.0 * math.pi * idx / hole_count),
            center.y() + ring_radius * math.sin(rotation_rad + 2.0 * math.pi * idx / hole_count),
        )
        for idx in range(hole_count)
    )


def gear_hole_radius(pitch_radius: object) -> float:
    safe_radius = max(1.0, abs(_finite_float(pitch_radius, 1.0)))
    return max(2.0, min(4.5, safe_radius * 0.11))


def annulus_path(center: QPointF, outer_radius: object, inner_radius: object) -> QPainterPath:
    outer = max(1.0, abs(_finite_float(outer_radius, 1.0)))
    inner = max(0.5, min(abs(_finite_float(inner_radius, outer * 0.8)), outer - 0.5))
    path = QPainterPath()
    path.setFillRule(Qt.FillRule.OddEvenFill)
    path.addEllipse(center, outer, outer)
    path.addEllipse(center, inner, inner)
    return path


def radial_tick_lines(
    center: QPointF,
    radius_inner: object,
    radius_outer: object,
    count: object,
    rotation_rad: float = 0.0,
) -> tuple[tuple[QPointF, QPointF], ...]:
    inner = max(0.5, abs(_finite_float(radius_inner, 1.0)))
    outer = max(inner + 0.5, abs(_finite_float(radius_outer, inner + 1.0)))
    tick_count = _safe_teeth(count, default=24)
    lines: list[tuple[QPointF, QPointF]] = []
    for idx in range(tick_count):
        theta = rotation_rad + (2.0 * math.pi * idx / tick_count)
        lines.append(
            (
                QPointF(center.x() + inner * math.cos(theta), center.y() + inner * math.sin(theta)),
                QPointF(center.x() + outer * math.cos(theta), center.y() + outer * math.sin(theta)),
            )
        )
    return tuple(lines)


def contrasting_hole_brush(fill: QColor) -> QColor:
    return QColor(255, 255, 255, 220) if fill.lightness() < 210 else QColor(40, 40, 40, 160)
