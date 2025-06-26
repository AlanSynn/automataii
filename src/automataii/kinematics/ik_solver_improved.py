import logging
import math

from PyQt6.QtCore import QLineF, QPointF

# ===== SKELETON LENGTH PRESERVATION SETTINGS =====
# Maximum allowed bone length deviation from original extracted lengths
# 0.0 = No stretching allowed (rigid preservation)
# 0.1 = 10% stretching allowed
# 0.2 = 20% stretching allowed
MAX_BONE_LENGTH_DEVIATION = 0.1  # 10% margin by default


def get_world_rotation(item):
    """Get the world rotation angle of an item."""
    transform = item.sceneTransform()
    angle_rad = math.atan2(transform.m21(), transform.m11())
    return math.degrees(angle_rad)


def calculate_bend_hint(chain: list, bend_directions: dict[str, int]) -> dict[str, QPointF]:
    """Calculate bend hint positions for each joint based on preferred bend directions.
    
    Args:
        chain: List of CharacterPartItem objects in the kinematic chain
        bend_directions: Dictionary mapping joint names to bend directions (+1 or -1)
        
    Returns:
        Dictionary mapping joint names to bend hint positions in scene coordinates
    """
    bend_hints = {}

    for i in range(1, len(chain) - 1):  # Only middle joints need bend hints
        current_item = chain[i]
        joint_name = current_item.part_info.name

        # Check if this joint has a preferred bend direction
        bend_dir = None
        for key in bend_directions:
            if key in joint_name or joint_name in key:
                bend_dir = bend_directions[key]
                break

        if bend_dir is None:
            continue

        # Get positions of prev, current, and next joints
        prev_item = chain[i - 1]
        next_item = chain[i + 1]

        prev_pos = prev_item.mapToScene(prev_item.anchor_offset)
        curr_pos = current_item.mapToScene(current_item.anchor_offset)
        next_pos = next_item.mapToScene(next_item.anchor_offset)

        # Calculate the vector from prev to next
        vec_prev_next = next_pos - prev_pos

        # Calculate perpendicular vector (rotated 90 degrees)
        # For bend_dir = 1 (CCW), rotate left (-90 deg)
        # For bend_dir = -1 (CW), rotate right (+90 deg)
        perp_x = -vec_prev_next.y() * bend_dir
        perp_y = vec_prev_next.x() * bend_dir

        # Normalize and scale the perpendicular vector
        perp_vec = QPointF(perp_x, perp_y)
        perp_length = math.sqrt(perp_x**2 + perp_y**2)
        if perp_length > 0.1:
            # Scale to about 20% of the limb length
            scale = 0.2 * QLineF(prev_pos, curr_pos).length() / perp_length
            perp_vec *= scale

            # Place bend hint offset from current position
            bend_hints[joint_name] = curr_pos + perp_vec

            logging.debug(f"Bend hint for {joint_name}: {bend_hints[joint_name]} (dir: {bend_dir})")

    return bend_hints


def solve_ik_fabrik_with_constraints(
    chain: list,
    target_pos: QPointF,
    original_bone_lengths: list[float] | None = None,
    bend_directions: dict[str, int] | None = None,
    iterations: int = 10,
    tolerance: float = 1.0
):
    """FABRIK solver with bend direction constraints for natural limb bending.
    
    Args:
        chain: List of CharacterPartItem objects forming the kinematic chain
        target_pos: Target position in scene coordinates
        original_bone_lengths: Optional list of original bone lengths to preserve
        bend_directions: Dictionary mapping joint names to preferred bend directions
        iterations: Maximum number of iterations
        tolerance: Position error tolerance
    """
    if not chain or len(chain) < 2:
        logging.warning("IK solver requires at least 2 items in chain.")
        return

    # Use provided original bone lengths or calculate from current positions
    if original_bone_lengths and len(original_bone_lengths) == len(chain) - 1:
        bone_lengths = original_bone_lengths.copy()
        logging.debug(f"IK: Using preserved bone lengths: {bone_lengths}")
    else:
        # Fallback: calculate from current positions (for compatibility)
        bone_lengths = []
        for i in range(len(chain) - 1):
            curr_pos = chain[i].mapToScene(chain[i].anchor_offset)
            next_pos = chain[i + 1].mapToScene(chain[i + 1].anchor_offset)
            length = QLineF(curr_pos, next_pos).length()
            bone_lengths.append(length)
        logging.debug(f"IK: Calculated bone lengths from current positions: {bone_lengths}")

    # Check if target is reachable
    total_length = sum(bone_lengths)
    base_pos = chain[0].mapToScene(chain[0].anchor_offset)
    target_distance = QLineF(base_pos, target_pos).length()

    # Apply length preservation constraint
    max_reach = total_length * (1.0 + MAX_BONE_LENGTH_DEVIATION)
    if target_distance > max_reach:
        logging.debug(f"Target unreachable with length preservation. Distance: {target_distance:.2f}, Max reach: {max_reach:.2f}")
        # Stretch towards target but respect length limits
        _stretch_chain_to_target_with_preservation(chain, bone_lengths, base_pos, target_pos)
        return

    # Calculate bend hints if bend directions provided
    bend_hints = {}
    if bend_directions:
        bend_hints = calculate_bend_hint(chain, bend_directions)

    # Get initial joint positions
    joint_positions = []
    for item in chain:
        pos = item.mapToScene(item.anchor_offset)
        joint_positions.append(QPointF(pos))

    # FABRIK iterations
    for iteration in range(iterations):
        # Forward pass: from end effector to base
        joint_positions[-1] = QPointF(target_pos)

        for i in range(len(chain) - 2, -1, -1):
            curr_pos = joint_positions[i]
            next_pos = joint_positions[i + 1]
            bone_length = bone_lengths[i]

            # Apply bend constraint if this is a middle joint with bend hint
            if i > 0 and i < len(chain) - 1:
                joint_name = chain[i].part_info.name
                if joint_name in bend_hints:
                    hint_pos = bend_hints[joint_name]
                    # Blend between direct line and bend hint
                    blend_factor = 0.3  # How much to follow the bend hint

                    # Direct position
                    direction = curr_pos - next_pos
                    distance = QLineF(curr_pos, next_pos).length()
                    if distance < 0.1:
                        direction = QPointF(bone_length, 0)
                        distance = bone_length
                    direct_pos = next_pos + (direction / distance) * bone_length

                    # Bent position (towards hint)
                    hint_dir = hint_pos - next_pos
                    hint_dist = QLineF(hint_pos, next_pos).length()
                    if hint_dist > 0.1:
                        bent_pos = next_pos + (hint_dir / hint_dist) * bone_length
                        # Blend positions
                        joint_positions[i] = direct_pos * (1 - blend_factor) + bent_pos * blend_factor
                    else:
                        joint_positions[i] = direct_pos
                else:
                    # No bend hint, use direct calculation
                    direction = curr_pos - next_pos
                    distance = QLineF(curr_pos, next_pos).length()
                    if distance < 0.1:
                        direction = QPointF(bone_length, 0)
                        distance = bone_length
                    joint_positions[i] = next_pos + (direction / distance) * bone_length
            else:
                # End joints don't need bend constraints
                direction = curr_pos - next_pos
                distance = QLineF(curr_pos, next_pos).length()
                if distance < 0.1:
                    direction = QPointF(bone_length, 0)
                    distance = bone_length
                joint_positions[i] = next_pos + (direction / distance) * bone_length

        # Backward pass: from base to end effector
        joint_positions[0] = QPointF(base_pos)  # Fix base

        for i in range(1, len(chain)):
            prev_pos = joint_positions[i - 1]
            curr_pos = joint_positions[i]
            bone_length = bone_lengths[i - 1]

            # Apply bend constraint for middle joints
            if i > 0 and i < len(chain) - 1:
                joint_name = chain[i].part_info.name
                if joint_name in bend_hints:
                    hint_pos = bend_hints[joint_name]
                    blend_factor = 0.3

                    # Direct position
                    direction = curr_pos - prev_pos
                    distance = QLineF(prev_pos, curr_pos).length()
                    if distance < 0.1:
                        direction = QPointF(bone_length, 0)
                        distance = bone_length
                    direct_pos = prev_pos + (direction / distance) * bone_length

                    # Bent position
                    hint_dir = hint_pos - prev_pos
                    hint_dist = QLineF(hint_pos, prev_pos).length()
                    if hint_dist > 0.1:
                        bent_pos = prev_pos + (hint_dir / hint_dist) * bone_length
                        joint_positions[i] = direct_pos * (1 - blend_factor) + bent_pos * blend_factor
                    else:
                        joint_positions[i] = direct_pos
                else:
                    direction = curr_pos - prev_pos
                    distance = QLineF(prev_pos, curr_pos).length()
                    if distance < 0.1:
                        direction = QPointF(bone_length, 0)
                        distance = bone_length
                    joint_positions[i] = prev_pos + (direction / distance) * bone_length
            else:
                direction = curr_pos - prev_pos
                distance = QLineF(prev_pos, curr_pos).length()
                if distance < 0.1:
                    direction = QPointF(bone_length, 0)
                    distance = bone_length
                joint_positions[i] = prev_pos + (direction / distance) * bone_length

        # Check convergence
        end_pos = joint_positions[-1]
        error = QLineF(end_pos, target_pos).length()
        if error < tolerance:
            logging.debug(f"FABRIK converged in {iteration + 1} iterations, error: {error:.2f}")
            break

    # Apply positions and rotations to chain
    for i in range(len(chain)):
        item = chain[i]
        new_pos = joint_positions[i]

        # Skip locked joints
        if hasattr(item, 'is_joint_locked') and item.is_joint_locked:
            continue

        item.set_scene_position_from_anchor(new_pos)

        # Calculate rotation to point to next joint
        if i < len(chain) - 1:
            next_pos = joint_positions[i + 1]
            angle_rad = math.atan2(
                next_pos.y() - new_pos.y(),
                next_pos.x() - new_pos.x()
            )
            angle_deg = math.degrees(angle_rad)

            # Store initial angle if not set
            if not hasattr(item, '_initial_world_angle'):
                item._initial_world_angle = angle_deg

            # Apply relative rotation
            current_world_angle = get_world_rotation(item)
            angle_delta = angle_deg - current_world_angle
            item.setRotation(item.rotation() + angle_delta)


def _stretch_chain_to_target(chain: list, bone_lengths: list[float], base_pos: QPointF, target_pos: QPointF):
    """Stretch the chain towards an unreachable target."""
    direction = target_pos - base_pos
    distance = QLineF(base_pos, target_pos).length()

    if distance < 0.1:
        return

    direction_normalized = direction / distance

    # Position joints along the line from base to target
    current_pos = base_pos
    for i in range(1, len(chain)):
        if hasattr(chain[i], 'is_joint_locked') and chain[i].is_joint_locked:
            continue

        bone_length = bone_lengths[i - 1]
        current_pos = current_pos + direction_normalized * bone_length
        chain[i].set_scene_position_from_anchor(current_pos)

        # Update rotation
        if i > 0:
            prev_item = chain[i - 1]
            if not (hasattr(prev_item, 'is_joint_locked') and prev_item.is_joint_locked):
                angle_rad = math.atan2(direction_normalized.y(), direction_normalized.x())
                angle_deg = math.degrees(angle_rad)
                current_world_angle = get_world_rotation(prev_item)
                angle_delta = angle_deg - current_world_angle
                prev_item.setRotation(prev_item.rotation() + angle_delta)


def _stretch_chain_to_target_with_preservation(chain: list, bone_lengths: list[float], base_pos: QPointF, target_pos: QPointF):
    """Stretch the chain towards target while preserving bone length constraints."""
    direction = target_pos - base_pos
    distance = QLineF(base_pos, target_pos).length()

    if distance < 0.1:
        return

    # Calculate maximum allowed total length
    max_total_length = sum(bone_lengths) * (1.0 + MAX_BONE_LENGTH_DEVIATION)
    
    # If target is still unreachable, stretch to maximum allowed distance
    if distance > max_total_length:
        direction_normalized = direction / distance
        # Stretch to maximum allowed distance, not to target
        stretch_distance = max_total_length
        effective_target = base_pos + direction_normalized * stretch_distance
    else:
        effective_target = target_pos

    # Use regular stretch with effective target
    _stretch_chain_to_target(chain, bone_lengths, base_pos, effective_target)


# Export the improved solver
solve_ik_ccd = solve_ik_fabrik_with_constraints  # Replace CCD with improved FABRIK
_solve_ik_fabrik = solve_ik_fabrik_with_constraints
