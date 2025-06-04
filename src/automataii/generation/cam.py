from typing import List, Tuple, Optional, Dict, Any
import math
import logging
import numpy as np
from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import QPainterPath, QPolygonF

from .base_mechanism import BaseMechanism

class Cam(BaseMechanism):
    """
    Generates cam mechanism data.
    """
    def __init__(self, name: str = "Cam Mechanism"):
        super().__init__(name, mechanism_type="Cam")

    def generate(
        self,
        cam_center_scene: QPointF,
        follower_path_points: List[QPointF], # Should be QPointF from resampled path
        follower_radius: float = 5.0,
        num_samples: int = 360,
        return_dict: bool = False, # Added flag
        base_radius_override: Optional[float] = None # For default/preview cams
    ) -> Any: # Returns QPainterPath or Dict
        """
        Generates a cam profile based on a list of follower center points.
        The cam is assumed to rotate clockwise, follower moves accordingly.
        The generated cam profile is the locus of the follower center when the
        cam is stationary and the follower path rotates counter-clockwise around the cam center.

        Args:
            cam_center_scene: The fixed center of the cam in scene coordinates.
            follower_path_points: A list of QPointF representing the desired path of the follower's center.
            follower_radius: The radius of the (roller) follower.
            num_samples: Number of points to define the cam profile.
                             (Effectively, how many points from follower_path_points to map)
            return_dict: If True, returns a dictionary with cam data instead of just QPainterPath.
            base_radius_override: If provided, uses this as the cam's base radius,
                                  ignoring follower_path_points for profile shape (e.g. for a simple eccentric preview).


        Returns:
            If return_dict is False: QPainterPath for the cam profile (raw, centered at origin).
                                     The caller should position it at cam_center_scene.
            If return_dict is True: A dictionary containing cam data including the QPainterPath.
        """
        if not follower_path_points and not base_radius_override:
            # print("Warning: No follower path points and no base_radius_override provided for cam generation.")
            return QPainterPath() if not return_dict else {}

        cam_profile_path = QPainterPath()
        cam_profile_points_world = [] # Store points for potential dictionary return

        min_dist_to_center = float('inf')
        max_dist_to_center = 0.0

        if base_radius_override is not None:
            # Generate a simple eccentric cam for preview or default
            # For simplicity, let's make it a circle offset from cam_center
            # This part is more for placeholder/preview generation
            eccentricity = base_radius_override * 0.4 # Example eccentricity
            actual_cam_radius = base_radius_override - eccentricity

            # Cam profile is a circle of actual_cam_radius, whose center is offset by eccentricity
            # For the QPainterPath returned (if not dict), it should be relative to cam_center_scene (0,0) effectively
            # So, the path is drawn at (eccentricity, 0) rotated if angle, then addEllipse...
            # This needs to be thought through more carefully if this function is the sole source of this shape.
            # For now, let's assume the preview data for cam includes specific base_radius, eccentric_radius, angle.
            # This function, if base_radius_override is used, will create a simple circular cam for that base radius.
            cam_profile_path.addEllipse(QRectF(-base_radius_override, -base_radius_override,
                                               base_radius_override*2, base_radius_override*2))
            min_dist_to_center = base_radius_override
            max_dist_to_center = base_radius_override
            # Add points for dict if needed
            for i in range(num_samples):
                angle = 2 * math.pi * i / num_samples
                pt = QPointF(base_radius_override * math.cos(angle), base_radius_override * math.sin(angle))
                cam_profile_points_world.append(pt + cam_center_scene)

        elif follower_path_points:
            # Actual cam generation from follower path
            num_path_points = len(follower_path_points)
            if num_path_points < 2:
                # print("Warning: Not enough points in follower path for cam generation.")
                return QPainterPath() if not return_dict else {}

            # Generate cam profile points by inverse kinematics
            # For each angle of cam rotation, find corresponding follower path point
            # Then transform this point to cam's coordinate system

            for i in range(num_samples):
                # Angle of cam rotation (clockwise, so follower path effectively rotates CCW)
                theta_rad = (2 * math.pi * i) / num_samples

                # Determine corresponding point on follower path
                # This maps cam angle to a point on the follower path. Simple linear mapping for now.
                path_idx = int((i / num_samples) * num_path_points) % num_path_points
                path_element_or_point = follower_path_points[path_idx]

                if isinstance(path_element_or_point, QPointF):
                    follower_center_world = path_element_or_point
                else: # Assuming it's a QPainterPath.Element or similar with x, y methods
                    try:
                        # QPainterPath.Element has .x and .y attributes
                        follower_center_world = QPointF(path_element_or_point.x, path_element_or_point.y)
                    except AttributeError:
                        logging.error(f"Cannot convert path element {path_element_or_point} (type: {type(path_element_or_point)}) to QPointF in cam generation.")
                        # Skip this problematic point to avoid crashing; cam profile might be incomplete/incorrect.
                        continue

                # Vector from cam center to follower center in world coords
                vec_cf_world = follower_center_world - cam_center_scene
                dist_cf = math.sqrt(vec_cf_world.x()**2 + vec_cf_world.y()**2)
                min_dist_to_center = min(min_dist_to_center, dist_cf)
                max_dist_to_center = max(max_dist_to_center, dist_cf)

                # Rotate this vector by -theta_rad to bring it into cam's frame
                # (equivalent to follower path rotating by +theta_rad around cam)
                # This point is on the pitch curve of the cam (center of follower relative to cam)
                pitch_curve_point_cam_frame = QPointF(
                    vec_cf_world.x() * math.cos(-theta_rad) - vec_cf_world.y() * math.sin(-theta_rad),
                    vec_cf_world.x() * math.sin(-theta_rad) + vec_cf_world.y() * math.cos(-theta_rad)
                )

                # The cam surface point is offset from pitch_curve_point_cam_frame by follower_radius
                # along the normal to the pitch curve.
                # For a simple approximation (especially with dense samples or smooth path),
                # we can use the pitch curve itself if follower_radius is small or for initial version.
                # A more accurate way is to find the normal or use an offset curve.
                # For now, using the pitch curve points and assuming follower_radius is handled by interpretation
                # or by a visual offset if this path is for the follower center.
                # If this path is for the CAM SURFACE, we need to offset by follower_radius.
                # Let's assume this function generates the PITCH CURVE first, then offsets for cam surface.

                cam_profile_points_world.append(pitch_curve_point_cam_frame + cam_center_scene) # Store world points of pitch curve

                if i == 0:
                    cam_profile_path.moveTo(pitch_curve_point_cam_frame) # Path relative to (0,0) for cam
                else:
                    cam_profile_path.lineTo(pitch_curve_point_cam_frame)

            if cam_profile_points_world:
                cam_profile_path.closeSubpath()
            else: # Should not happen if follower_path_points is valid
                return QPainterPath() if not return_dict else {}

        # Cam profile path generated is relative to (0,0) assuming cam center IS (0,0).
        # The caller needs to position it at cam_center_scene.

        if return_dict:
            # Base radius can be approximated as min_dist_to_center - follower_radius
            # However, for previews, a simpler base_radius might come from input.
            # This calculated base_radius is the smallest distance from cam center to PITCH CURVE.
            effective_base_radius = min_dist_to_center
            # Peak radius is max_dist_to_center
            effective_peak_radius = max_dist_to_center

            # If follower_radius is considered, the actual cam body would be smaller/larger.
            # Assuming cam_profile_path is the PITCH curve for now.
            # For visualization similar to matplotlib example, we need more params:
            # e.g. an effective "eccentricity" or main shape parameters for the preview.
            # The current generated path can be complex.

            # For preview purposes, estimate some simple parameters if not overridden
            preview_base_radius = base_radius_override if base_radius_override is not None else (effective_base_radius or 40)
            preview_eccentric_radius = (effective_peak_radius - effective_base_radius) / 2 if effective_peak_radius > effective_base_radius else preview_base_radius * 0.4
            if preview_eccentric_radius <=0 : preview_eccentric_radius = preview_base_radius * 0.4 # Ensure positive

            return {
                "type": "Cam & Follower",
                "cam_center_scene": [cam_center_scene.x(), cam_center_scene.y()],
                "profile_path_qt": cam_profile_path, # This is the PITCH CURVE relative to (0,0)
                "profile_points_world": [[p.x(), p.y()] for p in cam_profile_points_world], # Pitch curve points in world coords
                "follower_radius": follower_radius,
                "base_radius": preview_base_radius, # Effective base radius for preview
                "eccentric_radius": preview_eccentric_radius, # Effective eccentricity for preview
                "angle_offset_rad": math.pi / 4, # Placeholder for preview angle
                "min_dist_pitch_curve_to_center": min_dist_to_center if min_dist_to_center != float('inf') else 0,
                "max_dist_pitch_curve_to_center": max_dist_to_center,
                "description": "Generated from follower path" if follower_path_points else "Default eccentric cam"
            }
        else:
            return cam_profile_path


def _generate_offset_curve(points: List[QPointF], offset: float) -> QPainterPath:
    """ Generates an offset curve (simplified). Not fully robust. """
    offset_path = QPainterPath()
    if len(points) < 2: return offset_path

    for i in range(len(points)):
        p1 = points[i]
        p2 = points[(i + 1) % len(points)] # Next point, wraps around for closed curve

        # Calculate normal (simplified)
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        length = math.sqrt(dx*dx + dy*dy)
        if length == 0: continue

        # Normal vector (pointing outwards for CCW path)
        norm_x = -dy / length
        norm_y = dx / length

        offset_p1 = QPointF(p1.x() + norm_x * offset, p1.y() + norm_y * offset)
        # offset_p2 = QPointF(p2.x() + norm_x * offset, p2.y() + norm_y * offset)
        # This simplified normal is for the segment, not vertex, better to average normals at vertices

        if i == 0:
            offset_path.moveTo(offset_p1)
        else:
            offset_path.lineTo(offset_p1) # This creates a polyline of offset points.
                                         # For smooth curves, Bezier segments based on normals needed.
    offset_path.closeSubpath()
    return offset_path


if __name__ == '__main__':
    # Example Usage
    cam_generator = Cam()
    print(f"Cam Generator Description: {cam_generator.get_description()}")

    center = QPointF(100, 100)
    path = []
    for i in range(100):
        angle = 2 * math.pi * i / 100
        radius = 50 + 20 * math.sin(5 * angle) # A wobbly circle path for follower
        path.append(QPointF(center.x() + radius * math.cos(angle),
                          center.y() + radius * math.sin(angle)))

    # Test returning QPainterPath
    cam_path_only = cam_generator.generate(
        cam_center_scene=center,
        follower_path_points=path,
        follower_radius=5
    )
    if cam_path_only and not cam_path_only.isEmpty():
        print(f"Generated QPainterPath for cam. BoundingRect (relative to 0,0): {cam_path_only.boundingRect()}")
    else:
        print("Failed to generate QPainterPath for cam.")

    # Test returning dict
    cam_data = cam_generator.generate(
        cam_center_scene=center,
        follower_path_points=path,
        follower_radius=5,
        return_dict=True
    )
    if cam_data:
        print("\nGenerated Cam Data Dictionary:")
        for key, value in cam_data.items():
            if key == "profile_path_qt":
                print(f"  {key}: QPainterPath (boundingRect: {value.boundingRect()})")
            elif key == "profile_points_world":
                print(f"  {key}: List of {len(value)} points (first: {value[0] if value else 'N/A'})")
            else:
                print(f"  {key}: {value}")
        # Example: visualize the path (requires QApplication if showing widgets)
        # from PyQt6.QtWidgets import QApplication, QGraphicsView, QGraphicsScene, QGraphicsPathItem
        # from PyQt6.QtGui import QColor
        # app = QApplication([])
        # scene = QGraphicsScene()
        # view = QGraphicsView(scene)
        # cam_item = QGraphicsPathItem(cam_data["profile_path_qt"])
        # cam_item.setPos(cam_data["cam_center_scene"][0], cam_data["cam_center_scene"][1]) # Position it
        # cam_item.setBrush(QColor("lightblue"))
        # scene.addItem(cam_item)
        # view.show()
        # app.exec()
    else:
        print("\nFailed to generate cam data dictionary.")

    # Test with base_radius_override (for default/preview cam)
    default_cam_data = cam_generator.generate(
        cam_center_scene=QPointF(50,50),
        follower_path_points=[], # No follower path
        follower_radius=0,
        return_dict=True,
        base_radius_override=30
    )
    if default_cam_data:
        print("\nGenerated Default Cam Data (using base_radius_override):")
        for key, value in default_cam_data.items():
            if key == "profile_path_qt":
                print(f"  {key}: QPainterPath (boundingRect: {value.boundingRect()})")
            else:
                print(f"  {key}: {value}")
    else:
        print("\nFailed to generate default cam data.")
