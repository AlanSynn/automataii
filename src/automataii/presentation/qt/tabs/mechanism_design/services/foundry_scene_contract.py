"""Scene-space contract helpers for Mechanism Foundry imports.

Foundry exports are already in Design-tab scene coordinates.  Keep that
contract explicit so scalar Foundry updates do not accidentally reuse stale
drag/edit coordinates from an earlier frame.
"""

from __future__ import annotations

import math
from typing import Any

FOURBAR_SCENE_PARAM_KEYS = (
    "anchor1_x",
    "anchor1_y",
    "anchor2_x",
    "anchor2_y",
    "crank_x",
    "crank_y",
    "rocker_x",
    "rocker_y",
    "coupler_x",
    "coupler_y",
)

FOURBAR_ANCHOR_GROUND_MIDPOINT = "ground_midpoint"
FOURBAR_ANCHOR_COUPLER_POINT = "coupler_point"
_FOURBAR_ANCHOR_KEYS = {
    FOURBAR_ANCHOR_GROUND_MIDPOINT,
    FOURBAR_ANCHOR_COUPLER_POINT,
}


def _finite_float(value: object, default: float) -> float:
    if isinstance(value, bool):
        return default
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _positive_float(value: object, default: float) -> float:
    result = _finite_float(value, default)
    return result if result > 0.0 else default


def _stable_float(value: float) -> float:
    return float(round(float(value), 12))


def _finite_point(value: object) -> tuple[float, float] | None:
    if not isinstance(value, list | tuple) or len(value) < 2:
        return None
    x = _finite_float(value[0], math.nan)
    y = _finite_float(value[1], math.nan)
    if not math.isfinite(x) or not math.isfinite(y):
        return None
    return x, y


def _solve_circle_intersection(
    p1: tuple[float, float],
    r1: float,
    p2: tuple[float, float],
    r2: float,
) -> tuple[float, float] | None:
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    distance = math.hypot(dx, dy)
    if distance <= 1e-9 or distance > r1 + r2 or distance < abs(r1 - r2):
        return None

    a = (r1 * r1 - r2 * r2 + distance * distance) / (2.0 * distance)
    h_sq = r1 * r1 - a * a
    if h_sq < -1e-9:
        return None
    h = math.sqrt(max(0.0, h_sq))

    xm = p1[0] + a * dx / distance
    ym = p1[1] + a * dy / distance
    rx = -dy * h / distance
    ry = dx * h / distance
    return xm + rx, ym + ry


def scene_anchor_for_layer(
    layer_data: dict[str, Any],
    *,
    fallback: tuple[float, float] = (400.0, 300.0),
) -> tuple[float, float]:
    """Return the stable scene anchor used to rebuild Foundry geometry."""
    explicit_anchor = _finite_point(layer_data.get("scene_anchor"))
    if explicit_anchor is not None:
        return explicit_anchor

    key_points = layer_data.get("key_points")
    if isinstance(key_points, dict):
        p1 = _finite_point(key_points.get("ground_pivot_1"))
        p2 = _finite_point(key_points.get("ground_pivot_2"))
        if p1 is not None and p2 is not None:
            return (p1[0] + p2[0]) * 0.5, (p1[1] + p2[1]) * 0.5

    cam_position = _finite_point(layer_data.get("cam_position"))
    if cam_position is not None:
        return cam_position

    return fallback


def mark_scene_space(
    layer_data: dict[str, Any],
    anchor: tuple[float, float],
    *,
    anchor_key: str | None = None,
) -> None:
    """Mark a layer as scene-space and store its stable rebuild anchor."""
    layer_data["coordinate_space"] = "scene"
    layer_data["scene_anchor"] = [float(anchor[0]), float(anchor[1])]
    if anchor_key in _FOURBAR_ANCHOR_KEYS:
        layer_data["scene_anchor_key"] = anchor_key


def fourbar_scene_anchor_key(layer_data: dict[str, Any]) -> str:
    """Return how a four-bar Foundry scene anchor should be interpreted."""
    anchor_key = str(layer_data.get("scene_anchor_key", "")).strip()
    if anchor_key in _FOURBAR_ANCHOR_KEYS:
        return anchor_key
    return FOURBAR_ANCHOR_GROUND_MIDPOINT


def sync_fourbar_scene_params_from_key_points(
    layer_data: dict[str, Any],
    params: dict[str, Any],
) -> None:
    """Synchronize scene-space 4-bar param aliases from finite key points."""
    key_points = layer_data.setdefault("key_points", {})
    p1 = _finite_point(key_points.get("ground_pivot_1"))
    p2 = _finite_point(key_points.get("ground_pivot_2"))
    crank = _finite_point(key_points.get("crank_end"))
    rocker = _finite_point(key_points.get("rocker_end"))
    coupler = _finite_point(key_points.get("coupler_point"))
    if p1 is None or p2 is None or crank is None or rocker is None:
        return

    ground_midpoint = ((p1[0] + p2[0]) * 0.5, (p1[1] + p2[1]) * 0.5)
    anchor_key = fourbar_scene_anchor_key(layer_data)
    if anchor_key == FOURBAR_ANCHOR_COUPLER_POINT:
        anchor = scene_anchor_for_layer(layer_data, fallback=coupler or ground_midpoint)
    else:
        anchor = ground_midpoint
    mark_scene_space(layer_data, anchor, anchor_key=anchor_key)

    params["ground_pivot_1"] = [float(p1[0]), float(p1[1])]
    params["ground_pivot_2"] = [float(p2[0]), float(p2[1])]
    params["anchor1_x"] = float(p1[0])
    params["anchor1_y"] = float(p1[1])
    params["anchor2_x"] = float(p2[0])
    params["anchor2_y"] = float(p2[1])
    params["crank_x"] = float(crank[0])
    params["crank_y"] = float(crank[1])
    params["rocker_x"] = float(rocker[0])
    params["rocker_y"] = float(rocker[1])
    l1 = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
    l2 = math.hypot(crank[0] - p1[0], crank[1] - p1[1])
    l3 = math.hypot(rocker[0] - crank[0], rocker[1] - crank[1])
    l4 = math.hypot(rocker[0] - p2[0], rocker[1] - p2[1])
    params["l1"] = params["L1"] = _stable_float(l1)
    params["l2"] = params["L2"] = _stable_float(l2)
    params["l3"] = params["L3"] = _stable_float(l3)
    params["l4"] = params["L4"] = _stable_float(l4)
    crank_angle = math.degrees(math.atan2(crank[1] - p1[1], crank[0] - p1[0]))
    params["input_angle"] = _stable_float(crank_angle)
    params["crank_angle"] = _stable_float(crank_angle)
    if coupler is not None:
        params["coupler_x"] = float(coupler[0])
        params["coupler_y"] = float(coupler[1])


def rebuild_fourbar_scene_geometry_from_params(
    layer_data: dict[str, Any],
    params: dict[str, Any],
    *,
    scene_anchor: tuple[float, float] | None = None,
) -> None:
    """Rebuild Foundry 4-bar scene key points from scalar mechanism params.

    This is the Foundry scalar-update source of truth.  It intentionally
    recomputes scene coordinates from link lengths and input angle rather than
    preserving earlier `crank_x/y` or `rocker_x/y` drag coordinates.
    """
    anchor_key = fourbar_scene_anchor_key(layer_data)
    anchor = scene_anchor or scene_anchor_for_layer(layer_data)
    mark_scene_space(layer_data, anchor, anchor_key=anchor_key)

    l1 = _positive_float(params.get("l1", params.get("L1", 150.0)), 150.0)
    l2 = _positive_float(params.get("l2", params.get("L2", 40.0)), 40.0)
    l3 = _positive_float(params.get("l3", params.get("L3", 120.0)), 120.0)
    l4 = _positive_float(params.get("l4", params.get("L4", 130.0)), 130.0)
    input_angle = _finite_float(
        params.get("input_angle", params.get("crank_angle", 30.0)),
        30.0,
    )
    theta = math.radians(input_angle)

    p1 = (anchor[0] - l1 * 0.5, anchor[1])
    p2 = (anchor[0] + l1 * 0.5, anchor[1])
    crank = (p1[0] + l2 * math.cos(theta), p1[1] + l2 * math.sin(theta))
    rocker = _solve_circle_intersection(crank, l3, p2, l4)
    if rocker is None:
        rocker = (p2[0], p2[1] - l4)

    coupler_x = _finite_float(params.get("coupler_point_x", params.get("p_x", l3 * 0.5)), l3 * 0.5)
    coupler_y = _finite_float(params.get("coupler_point_y", params.get("p_y", 0.0)), 0.0)
    coupler_vec = (rocker[0] - crank[0], rocker[1] - crank[1])
    coupler_len = math.hypot(coupler_vec[0], coupler_vec[1])
    if coupler_len > 1e-9:
        coupler_unit = (coupler_vec[0] / coupler_len, coupler_vec[1] / coupler_len)
        coupler_normal = (-coupler_unit[1], coupler_unit[0])
        coupler = (
            crank[0] + coupler_x * coupler_unit[0] + coupler_y * coupler_normal[0],
            crank[1] + coupler_x * coupler_unit[1] + coupler_y * coupler_normal[1],
        )
    else:
        coupler = crank

    if anchor_key == FOURBAR_ANCHOR_COUPLER_POINT:
        shift_x = anchor[0] - coupler[0]
        shift_y = anchor[1] - coupler[1]
        p1 = (p1[0] + shift_x, p1[1] + shift_y)
        p2 = (p2[0] + shift_x, p2[1] + shift_y)
        crank = (crank[0] + shift_x, crank[1] + shift_y)
        rocker = (rocker[0] + shift_x, rocker[1] + shift_y)
        coupler = (anchor[0], anchor[1])

    layer_data["key_points"] = {
        "ground_pivot_1": [float(p1[0]), float(p1[1])],
        "ground_pivot_2": [float(p2[0]), float(p2[1])],
        "crank_end": [float(crank[0]), float(crank[1])],
        "rocker_end": [float(rocker[0]), float(rocker[1])],
        "coupler_point": [float(coupler[0]), float(coupler[1])],
    }

    params["l1"] = params["L1"] = float(l1)
    params["l2"] = params["L2"] = float(l2)
    params["l3"] = params["L3"] = float(l3)
    params["l4"] = params["L4"] = float(l4)
    params["input_angle"] = float(input_angle)
    params["crank_angle"] = float(input_angle)
    params["coupler_point_x"] = float(coupler_x)
    params["coupler_point_y"] = float(coupler_y)
    params["p_x"] = float(coupler_x)
    params["p_y"] = float(coupler_y)
    sync_fourbar_scene_params_from_key_points(layer_data, params)
