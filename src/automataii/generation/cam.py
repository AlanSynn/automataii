import math
import logging
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPainterPath

def generate_cam_profile(follower_path: QPainterPath, cam_center: QPointF, num_steps: int = 100) -> QPainterPath:
    """Generates a cam profile based on a follower path and cam center.

    Args:
        follower_path: The QPainterPath representing the desired motion of the follower
                       (in scene coordinates).
        cam_center: The desired rotation center of the cam (in scene coordinates).
        num_steps: The number of steps to sample along the follower path.

    Returns:
        A QPainterPath representing the cam profile (coordinates relative to cam_center).
        Returns an empty path if generation fails.
    """
    if follower_path.isEmpty():
        logging.warning("Cannot generate cam profile: Follower path is empty.")
        return QPainterPath()
    if num_steps < 4:
        logging.warning("Cannot generate cam profile: num_steps must be at least 4.")
        return QPainterPath()

    cam_profile = QPainterPath()
    cam_points = []

    logging.info(f"Generating cam profile with {num_steps} steps from center {cam_center}")

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
        angle_rad = math.atan2(delta_y, delta_x) # Angle in radians

        if radius < 1e-6:
            # Avoid issues if path goes directly through cam center
            # Option 1: Skip this point (might create discontinuity)
            # Option 2: Use a minimum radius (creates a small circle at center)
             logging.warning(f"Follower path is very close to cam center at step {i}. Using minimum radius substitute.")
             # We will handle minimum radius later
             radius = 0 # Mark as zero for now
             # Keep the angle as is

        min_radius = min(min_radius, radius if radius > 1e-6 else float('inf'))

        # Store angle and radius
        # We need angle to sort points later to construct the path correctly
        cam_points.append((angle_rad, radius))

    # --- Handle minimum radius ---
    # If the path went through the center, ensure the cam has a minimum size
    # Choose a small default radius if needed (e.g., 5 units)
    effective_min_radius = max(5.0, min_radius / 4.0) if min_radius != float('inf') else 5.0

    processed_cam_points = []
    for angle_rad, radius in cam_points:
        # Ensure a minimum radius, especially if path went through center
        current_radius = radius if radius > 1e-6 else effective_min_radius
        processed_cam_points.append((angle_rad, current_radius))

    # Sort points by angle to construct the path correctly
    processed_cam_points.sort(key=lambda p: p[0])

    # Convert polar coordinates (angle, radius) to Cartesian (x, y) relative to cam center
    cartesian_points = []
    for angle_rad, radius in processed_cam_points:
        x = radius * math.cos(angle_rad)
        y = radius * math.sin(angle_rad)
        cartesian_points.append(QPointF(x, y))

    # Build the QPainterPath
    if cartesian_points:
        cam_profile.moveTo(cartesian_points[0])
        for point in cartesian_points[1:]:
            cam_profile.lineTo(point)
        cam_profile.closeSubpath() # Close the loop

    logging.info(f"Generated cam profile path with {len(cartesian_points)} points.")
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