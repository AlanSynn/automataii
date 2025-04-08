import math
import logging
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPainterPath

def generate_cam_profile(follower_path: QPainterPath, cam_center: QPointF, num_steps: int = 100) -> QPainterPath:
    """Generates a cam profile based on a follower path and cam center.

    Args:
        follower_path: The QPainterPath the follower should trace (in scene coordinates).
        cam_center: The QPointF representing the cam's rotation center (in scene coordinates).
        num_steps: Number of points to sample along the path.

    Returns:
        A QPainterPath representing the cam profile (relative to cam_center),
        or an empty path if generation fails.
    """
    if not follower_path or follower_path.isEmpty() or not cam_center:
        logging.error("generate_cam_profile: Invalid input path or center.")
        return QPainterPath()

    cam_points = [] # List to store (angle_rad, radius) pairs
    min_radius = float('inf') # Track minimum radius to handle path passing through center

    # Sample points along the follower path
    for i in range(num_steps):
        percent = i / num_steps
        path_point = follower_path.pointAtPercent(percent)

        # Vector from cam center to path point
        delta_x = path_point.x() - cam_center.x()
        delta_y = path_point.y() - cam_center.y()

        # Calculate radius (distance) and angle
        radius = math.sqrt(delta_x * delta_x + delta_y * delta_y)
        # Angle of the vector from center to path point (atan2 handles quadrants)
        path_point_angle_rad = math.atan2(delta_y, delta_x)

        # Assume cam rotation angle corresponds directly to path percent
        # This is a simplification - real mapping might be more complex
        cam_angle_rad = percent * 2 * math.pi

        # Calculate the cam profile point for this cam angle.
        # When the cam is rotated by cam_angle_rad, the point on its profile
        # currently at path_point_angle_rad must have the calculated radius.
        # So, the point on the base cam profile (at angle 0)
        # corresponding to this follower position must be at:
        # Angle = path_point_angle_rad - cam_angle_rad
        # Radius = radius
        profile_angle_rad = path_point_angle_rad - cam_angle_rad

        if radius < 1e-6:
            logging.warning(f"Follower path is very close to cam center at step {i}. Using minimum radius substitute later.")
            radius = 0 # Mark as zero for now

        min_radius = min(min_radius, radius if radius > 1e-6 else float('inf'))

        # Store the BASE profile angle and the required radius at that angle
        cam_points.append((profile_angle_rad, radius))

    # --- Handle minimum radius --- #
    effective_min_radius = max(5.0, min_radius / 2.0) if min_radius != float('inf') else 5.0
    logging.info(f"Cam generation: Min follower radius={min_radius:.2f}, Effective min cam radius={effective_min_radius:.2f}")

    processed_cam_points = []
    for angle_rad, radius in cam_points:
        current_radius = radius if radius > 1e-6 else effective_min_radius
        processed_cam_points.append((angle_rad, current_radius))

    # Sort points by angle to construct the path correctly
    processed_cam_points.sort(key=lambda p: p[0])

    # Create the cam profile path (relative to cam center)
    cam_profile = QPainterPath()
    first_point = True
    for angle_rad, radius in processed_cam_points:
        # Convert polar coordinates (angle, radius) to Cartesian (x, y)
        x = radius * math.cos(angle_rad)
        y = radius * math.sin(angle_rad)
        point = QPointF(x, y) # Point relative to cam center

        if first_point:
            cam_profile.moveTo(point)
            first_point = False
        else:
            cam_profile.lineTo(point)

    cam_profile.closeSubpath() # Close the profile

    logging.info(f"Generated cam profile with {len(processed_cam_points)} points.")
    return cam_profile

# Example usage (for testing)
if __name__ == '__main__':
    # Create a simple circular follower path for testing
    test_path = QPainterPath()
    test_path.addEllipse(QPointF(100, 50), 30, 30) # Circle centered at (100, 50) with radius 30

    test_cam_center = QPointF(0, 0)

    # Generate cam profile
    generated_cam = generate_cam_profile(test_path, test_cam_center)

    if not generated_cam.isEmpty():
        print("Cam profile generated successfully.")
        # You would typically visualize this path
    else:
        print("Cam profile generation failed.")