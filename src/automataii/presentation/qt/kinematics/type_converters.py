"""
Type converters for bridging Qt types with domain types.

Provides utilities to convert between PyQt6 types (QPointF, QLineF)
and pure Python domain types (Point2D) for IK calculations.

Architecture Note:
    This module exists at the presentation layer boundary to bridge
    Qt-specific types with pure Python domain types. The IKSolverCore
    uses Point2D for all calculations, while IKManager uses QPointF
    for Qt integration.
"""

from __future__ import annotations

from PyQt6.QtCore import QPointF

from automataii.domain.kinematics.components.ik_solver_core import (
    IKSolution,
    Point2D,
)

# =============================================================================
# Basic Type Conversions
# =============================================================================


def qpoint_to_point2d(qpoint: QPointF) -> Point2D:
    """Convert QPointF to Point2D."""
    return Point2D(qpoint.x(), qpoint.y())


def point2d_to_qpoint(point: Point2D) -> QPointF:
    """Convert Point2D to QPointF."""
    return QPointF(point.x, point.y)


def qpoints_to_point2ds(qpoints: list[QPointF]) -> list[Point2D]:
    """Convert list of QPointF to list of Point2D."""
    return [qpoint_to_point2d(qp) for qp in qpoints]


def point2ds_to_qpoints(points: list[Point2D]) -> list[QPointF]:
    """Convert list of Point2D to list of QPointF."""
    return [point2d_to_qpoint(p) for p in points]


# =============================================================================
# IK Solution Conversions
# =============================================================================


def ik_solution_to_qpoints(
    solution: IKSolution,
) -> dict[str, QPointF]:
    """
    Convert IKSolution joint positions to QPointF dictionary.

    Args:
        solution: IKSolution from IKSolverCore

    Returns:
        Dictionary mapping joint names to QPointF positions
    """
    return {name: point2d_to_qpoint(pos) for name, pos in solution.joint_positions.items()}


def extract_two_bone_result(
    solution: IKSolution,
) -> tuple[QPointF, QPointF] | None:
    """
    Extract middle and end positions from two-bone IK solution.

    Args:
        solution: IKSolution from solve_two_bone

    Returns:
        Tuple of (middle_pos, end_pos) as QPointF, or None if failed
    """
    if not solution.success:
        return None

    middle = solution.joint_positions.get("middle")
    end = solution.joint_positions.get("end")

    if middle is None or end is None:
        return None

    return (point2d_to_qpoint(middle), point2d_to_qpoint(end))


# =============================================================================
# Skeleton Data Conversions
# =============================================================================


def skeleton_positions_to_point2ds(
    skeleton_data: dict[str, dict],
) -> dict[str, Point2D]:
    """
    Convert skeleton joint positions to Point2D format.

    Args:
        skeleton_data: Skeleton data with 'joints' containing position info

    Returns:
        Dictionary mapping joint names to Point2D positions
    """
    result: dict[str, Point2D] = {}
    joints = skeleton_data.get("joints", {})

    for joint_id, joint_info in joints.items():
        if isinstance(joint_info, dict):
            x = joint_info.get("x", 0.0)
            y = joint_info.get("y", 0.0)
            result[joint_id] = Point2D(float(x), float(y))

    return result
