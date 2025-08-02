# src/automataii/ui/views/image_processing/utils.py

"""
Utility functions for image processing view operations.
Contains vector math and geometric calculations.
"""

from PyQt6.QtCore import QLineF, QPointF


def normalize_vector(vector: QPointF) -> QPointF:
    """Normalizes a QPointF vector."""
    line = QLineF(QPointF(0, 0), vector)
    length = line.length()
    if length == 0:
        return QPointF(0, 0)
    return vector / length


def perpendicular_vector(vector: QPointF) -> QPointF:
    """Returns a vector perpendicular to the input vector (rotated 90 deg counter-clockwise)."""
    return QPointF(-vector.y(), vector.x())


def get_lines_connected_to_joint(joint_item, scene_items):
    """
    Returns a list of line items connected to the target joint.

    Args:
        joint_item: The joint item to find connections for
        scene_items: List of scene items to search for connections

    Returns:
        List of connected line items
    """
    connected_lines = []

    if not hasattr(joint_item, "joint_name"):
        return connected_lines

    # Search for line items that connect to this joint
    for item in scene_items:
        if hasattr(item, "joint1") and hasattr(item, "joint2"):
            # This is a skeleton line item
            if item.joint1 == joint_item or item.joint2 == joint_item:
                connected_lines.append(item)

    return connected_lines


def calculate_guide_direction(joint_item, connected_lines):
    """
    Calculate the guide direction for a joint based on its connected lines.

    Args:
        joint_item: The joint item to calculate direction for
        connected_lines: List of line items connected to the joint

    Returns:
        QPointF: The guide direction vector, or None if calculation fails
    """
    if not connected_lines:
        return None

    joint_pos = joint_item.pos()

    if len(connected_lines) == 1:
        # Terminal joint (connected to one bone)
        line = connected_lines[0]
        other_joint = line.joint1 if line.joint2 == joint_item else line.joint2
        if not other_joint:
            return None

        bone_vector = other_joint.pos() - joint_pos
        guide_direction = perpendicular_vector(bone_vector)

    else:
        # Intermediate joint (connected to multiple bones)
        # For simplicity, consider the first two connected lines
        line1 = connected_lines[0]
        other_joint1 = line1.joint1 if line1.joint2 == joint_item else line1.joint2
        if not other_joint1:
            return None

        line2 = connected_lines[1]
        other_joint2 = line2.joint1 if line2.joint2 == joint_item else line2.joint2
        if not other_joint2:
            return None

        vec1 = other_joint1.pos() - joint_pos
        vec2 = other_joint2.pos() - joint_pos

        norm_vec1 = normalize_vector(vec1)
        norm_vec2 = normalize_vector(vec2)

        if (norm_vec1 + norm_vec2).isNull():
            guide_direction = perpendicular_vector(norm_vec1)
        else:
            bisector_direction = normalize_vector(norm_vec1 + norm_vec2)
            guide_direction = perpendicular_vector(bisector_direction)

    return guide_direction
