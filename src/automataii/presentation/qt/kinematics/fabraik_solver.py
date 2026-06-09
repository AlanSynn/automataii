import logging
import math

from PyQt6.QtCore import QLineF, QPointF

# Module-level logger
logger = logging.getLogger(__name__)

# Maximum allowed bone length deviation from original extracted lengths
# 🔧 LENGTH TOLERANCE FIX: Allow 10% deviation for natural bone extension
# Updated from 5% to match the two-bone and single-bone IK systems
MAX_BONE_LENGTH_DEVIATION = 0.1  # 10% tolerance for natural bone extension


def get_world_rotation(item):
    """Get the world rotation angle of an item."""
    transform = item.sceneTransform()
    angle_rad = math.atan2(transform.m21(), transform.m11())
    return math.degrees(angle_rad)


def calculate_bend_hint(chain: list, bend_directions: dict[str, int]) -> dict[str, QPointF]:
    """Calculate bend hint positions for each joint based on preferred bend directions.

    This version uses a simpler, more stable method by creating a perpendicular
    offset from the middle joint, guided by the reliable bend_dir from IKManager.
    """
    bend_hints = {}

    for i in range(1, len(chain) - 1):  # Iterate over middle joints (e.g., elbow, knee)
        current_item = chain[i]
        part_name = current_item.part_info.name  # This is the part name (e.g., 'left_arm_upper')

        # Map the visual part name (e.g., 'left_arm_upper') to the logical joint name ('left_elbow')
        part_to_joint_mapping = {
            "left_arm_upper": "left_elbow",
            "right_arm_upper": "right_elbow",
            "left_leg_upper": "left_knee",
            "right_leg_upper": "right_knee",
        }

        joint_key = part_to_joint_mapping.get(part_name)
        if not joint_key or joint_key not in bend_directions:
            logger.debug(
                "No bend direction for joint '%s' (from part '%s'). Skipping hint.",
                joint_key,
                part_name,
            )
            continue

        # Use the stable bend direction provided by IKManager. Do NOT recalculate it.
        bend_dir = bend_directions[joint_key]

        # Get positions of the joints in the chain
        prev_item = chain[i - 1]

        prev_pos = prev_item.mapToScene(prev_item.anchor_offset)  # e.g., shoulder
        curr_pos = current_item.mapToScene(current_item.anchor_offset)  # e.g., elbow

        # --- Simplified and Robust Bend Hint Calculation ---
        # 1. Create a vector from the limb's root (shoulder) to its middle (elbow)
        vec_to_middle = curr_pos - prev_pos

        # 2. Calculate a vector perpendicular to this limb segment.
        #    The direction of rotation is controlled by `bend_dir` (+1 for CCW, -1 for CW).
        # 🔧 COORDINATE SYSTEM FIX: Adjust perpendicular vector for Qt's Y-down coordinate system
        perp_x = vec_to_middle.y() * bend_dir  # Remove negative sign for Qt Y-down
        perp_y = -vec_to_middle.x() * bend_dir  # Add negative sign for Qt Y-down
        perp_vec = QPointF(perp_x, perp_y)

        # 3. Scale the perpendicular vector to create a reasonable offset distance.
        perp_length = math.sqrt(perp_x**2 + perp_y**2)
        if perp_length > 0.1:
            # Using a fraction of the limb's length as the offset is a good heuristic.
            limb_length = QLineF(prev_pos, curr_pos).length()
            scale = 0.5 * limb_length / perp_length
            perp_vec *= scale

            # 4. The final hint is the elbow's position pushed outwards in the calculated direction.
            hint_position = curr_pos + perp_vec
            # CRITICAL FIX: Use joint_key (e.g., 'left_elbow') as the key, not part_name
            bend_hints[joint_key] = hint_position
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "Bend hint for '%s' set with direction %s. Hint pos: %s",
                    joint_key,
                    bend_dir,
                    hint_position,
                )

    return bend_hints


def solve_ik_fabrik_with_constraints(
    chain: list,
    target_pos: QPointF,
    original_bone_lengths: list[float] | None = None,
    bend_directions: dict[str, int] | None = None,
    iterations: int = 10,
    tolerance: float = 1.0,
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
    else:
        # Fallback: calculate from current positions (for compatibility)
        bone_lengths = []
        for i in range(len(chain) - 1):
            curr_pos = chain[i].mapToScene(chain[i].anchor_offset)
            next_pos = chain[i + 1].mapToScene(chain[i + 1].anchor_offset)
            length = QLineF(curr_pos, next_pos).length()
            bone_lengths.append(length)

    # Check if target is reachable
    total_length = sum(bone_lengths)
    base_pos = chain[0].mapToScene(chain[0].anchor_offset)
    target_distance = QLineF(base_pos, target_pos).length()

    # Apply length preservation constraint
    max_reach = total_length * (1.0 + MAX_BONE_LENGTH_DEVIATION)
    if target_distance > max_reach:
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
    for _iteration in range(iterations):
        # Forward pass: from end effector to base
        joint_positions[-1] = QPointF(target_pos)

        for i in range(len(chain) - 2, -1, -1):
            curr_pos = joint_positions[i]
            next_pos = joint_positions[i + 1]
            bone_length = bone_lengths[i]

            # Apply bend constraint if this is a middle joint with bend hint
            if i > 0 and i < len(chain) - 1:
                part_name = chain[i].part_info.name

                # Map part name to joint name for bend hint lookup
                part_to_joint_mapping = {
                    "left_arm_upper": "left_elbow",
                    "right_arm_upper": "right_elbow",
                    "left_leg_upper": "left_knee",
                    "right_leg_upper": "right_knee",
                }

                joint_name = part_to_joint_mapping.get(part_name, part_name)

                if joint_name in bend_hints:
                    hint_pos = bend_hints[joint_name]
                    # Blend between direct line and bend hint (increased for stronger anatomical effect)
                    blend_factor = 0.8

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
                        blended_pos = direct_pos * (1 - blend_factor) + bent_pos * blend_factor

                        # CRITICAL: Normalize blended position to preserve bone length
                        blend_dir = blended_pos - next_pos
                        blend_dist = QLineF(next_pos, blended_pos).length()
                        if blend_dist > 0.1:
                            joint_positions[i] = next_pos + (blend_dir / blend_dist) * bone_length
                        else:
                            joint_positions[i] = direct_pos
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
                part_name = chain[i].part_info.name

                # Map part name to joint name for bend hint lookup (backward pass)
                part_to_joint_mapping = {
                    "left_arm_upper": "left_elbow",
                    "right_arm_upper": "right_elbow",
                    "left_leg_upper": "left_knee",
                    "right_leg_upper": "right_knee",
                }

                joint_name = part_to_joint_mapping.get(part_name, part_name)

                if joint_name in bend_hints:
                    hint_pos = bend_hints[joint_name]
                    blend_factor = 0.8

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
                        # Blend positions
                        blended_pos = direct_pos * (1 - blend_factor) + bent_pos * blend_factor

                        # CRITICAL: Normalize blended position to preserve bone length
                        blend_dir = blended_pos - prev_pos
                        blend_dist = QLineF(prev_pos, blended_pos).length()
                        if blend_dist > 0.1:
                            joint_positions[i] = prev_pos + (blend_dir / blend_dist) * bone_length
                        else:
                            joint_positions[i] = direct_pos
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
            break

    # Apply positions and rotations to chain
    for i in range(len(chain)):
        item = chain[i]
        new_pos = joint_positions[i]

        # Skip locked joints
        if hasattr(item, "is_joint_locked") and item.is_joint_locked:
            continue

        # FABRIK solver already maintains bone length constraints,
        # so bypass CharacterPartItem's duplicate validation
        item.set_scene_position_from_anchor(new_pos, bypass_validation=True)

        # Calculate rotation to point to next joint
        if i < len(chain) - 1:
            next_pos = joint_positions[i + 1]
            angle_rad = math.atan2(next_pos.y() - new_pos.y(), next_pos.x() - new_pos.x())
            angle_deg = math.degrees(angle_rad)

            # Store initial angle if not set
            if not hasattr(item, "_initial_world_angle"):
                item._initial_world_angle = angle_deg

            # Apply relative rotation
            current_world_angle = get_world_rotation(item)
            angle_delta = angle_deg - current_world_angle
            item.setRotation(item.rotation() + angle_delta)


def _stretch_chain_to_target_with_preservation(
    chain: list, bone_lengths: list[float], base_pos: QPointF, target_pos: QPointF
):
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

    # Apply stretch with length preservation
    direction = effective_target - base_pos
    distance = QLineF(base_pos, effective_target).length()

    if distance < 0.1:
        return

    direction_normalized = direction / distance

    # Position joints along the line from base to effective target
    current_pos = base_pos
    for i in range(1, len(chain)):
        if hasattr(chain[i], "is_joint_locked") and chain[i].is_joint_locked:
            continue

        bone_length = bone_lengths[i - 1]
        current_pos = current_pos + direction_normalized * bone_length
        # FABRIK solver already maintains bone length constraints,
        # so bypass CharacterPartItem's duplicate validation
        chain[i].set_scene_position_from_anchor(current_pos, bypass_validation=True)

        # Update rotation
        if i > 0:
            prev_item = chain[i - 1]
            if not (hasattr(prev_item, "is_joint_locked") and prev_item.is_joint_locked):
                angle_rad = math.atan2(direction_normalized.y(), direction_normalized.x())
                angle_deg = math.degrees(angle_rad)
                current_world_angle = get_world_rotation(prev_item)
                angle_delta = angle_deg - current_world_angle
                prev_item.setRotation(prev_item.rotation() + angle_delta)


# Export the improved solver with clear naming
solve_ik_ccd = solve_ik_fabrik_with_constraints  # Backward compatibility alias
