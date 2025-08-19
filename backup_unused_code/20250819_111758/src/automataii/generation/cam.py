import logging
import math
from typing import Any

from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPainterPath

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
        follower_path_points: list[QPointF],  # Should be QPointF from resampled path
        follower_radius: float = 5.0,
        num_samples: int = 360,
        return_dict: bool = False,  # Added flag
        base_radius_override: float | None = None,  # For default/preview cams
    ) -> Any:  # Returns QPainterPath or Dict
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
        cam_profile_points_world = []  # Store points for potential dictionary return

        min_dist_to_center = float("inf")
        max_dist_to_center = 0.0

        if base_radius_override is not None:
            # Generate a proper egg-shaped cam for preview/default with correct physics
            # The cam should have high points that push the follower UP and low points that let it fall DOWN
            base_radius = base_radius_override
            lift_amount = base_radius * 0.4  # 40% lift variation

            # Create proper cam profile: higher radius at bottom pushes follower up
            # Using a sinusoidal lift profile for smooth motion
            for i in range(num_samples):
                theta = 2 * math.pi * i / num_samples

                # Lift profile: maximum lift when cam's high point is at bottom (theta=3π/2)
                # This creates the physics where cam pushes follower UP when convex part is below
                lift = lift_amount * (1 + math.cos(theta + math.pi/2)) / 2  # Shifted cosine for proper phase
                cam_radius = base_radius + lift

                # Generate cam profile point
                pt = QPointF(
                    cam_radius * math.cos(theta),
                    cam_radius * math.sin(theta),
                )

                if i == 0:
                    cam_profile_path.moveTo(pt)
                else:
                    cam_profile_path.lineTo(pt)

                cam_profile_points_world.append(pt + cam_center_scene)

                min_dist_to_center = min(min_dist_to_center, cam_radius)
                max_dist_to_center = max(max_dist_to_center, cam_radius)

            cam_profile_path.closeSubpath()

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
                else:  # Assuming it's a QPainterPath.Element or similar with x, y methods
                    try:
                        # QPainterPath.Element has .x and .y attributes
                        follower_center_world = QPointF(
                            path_element_or_point.x, path_element_or_point.y
                        )
                    except AttributeError:
                        logging.error(
                            f"Cannot convert path element {path_element_or_point} (type: {type(path_element_or_point)}) to QPointF in cam generation."
                        )
                        # Skip this problematic point to avoid crashing; cam profile might be incomplete/incorrect.
                        continue

                # Vector from cam center to follower center in world coords
                vec_cf_world = follower_center_world - cam_center_scene
                dist_cf = math.sqrt(vec_cf_world.x() ** 2 + vec_cf_world.y() ** 2)
                min_dist_to_center = min(min_dist_to_center, dist_cf)
                max_dist_to_center = max(max_dist_to_center, dist_cf)

                # Rotate this vector by -theta_rad to bring it into cam's frame
                # (equivalent to follower path rotating by +theta_rad around cam)
                # This point is on the pitch curve of the cam (center of follower relative to cam)
                pitch_curve_point_cam_frame = QPointF(
                    vec_cf_world.x() * math.cos(-theta_rad)
                    - vec_cf_world.y() * math.sin(-theta_rad),
                    vec_cf_world.x() * math.sin(-theta_rad)
                    + vec_cf_world.y() * math.cos(-theta_rad),
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

                cam_profile_points_world.append(
                    pitch_curve_point_cam_frame + cam_center_scene
                )  # Store world points of pitch curve

                if i == 0:
                    cam_profile_path.moveTo(
                        pitch_curve_point_cam_frame
                    )  # Path relative to (0,0) for cam
                else:
                    cam_profile_path.lineTo(pitch_curve_point_cam_frame)

            if cam_profile_points_world:
                cam_profile_path.closeSubpath()
            else:  # Should not happen if follower_path_points is valid
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
            preview_base_radius = (
                base_radius_override
                if base_radius_override is not None
                else (effective_base_radius or 40)
            )
            preview_eccentric_radius = (
                (effective_peak_radius - effective_base_radius) / 2
                if effective_peak_radius > effective_base_radius
                else preview_base_radius * 0.4
            )
            if preview_eccentric_radius <= 0:
                preview_eccentric_radius = preview_base_radius * 0.4  # Ensure positive

            return {
                "type": "Cam & Follower",
                "cam_center_scene": [cam_center_scene.x(), cam_center_scene.y()],
                "profile_path_qt": cam_profile_path,  # This is the CAM PROFILE relative to (0,0)
                "profile_points_world": [
                    [p.x(), p.y()] for p in cam_profile_points_world
                ],  # Cam profile points in world coords
                "follower_radius": follower_radius,
                "base_radius": preview_base_radius,  # Effective base radius for preview
                "eccentricity": preview_eccentric_radius,  # Effective eccentricity for preview
                "lift_amount": preview_eccentric_radius,  # Added lift amount for physics
                "angle_offset_rad": 0,  # Start with no offset for proper orientation
                "min_radius": (
                    min_dist_to_center if min_dist_to_center != float("inf") else preview_base_radius
                ),
                "max_radius": max_dist_to_center if max_dist_to_center > 0 else preview_base_radius + preview_eccentric_radius,
                "description": (
                    "Generated cam with proper lift profile"
                    if base_radius_override is not None
                    else "Generated from follower path"
                ),
            }
        else:
            return cam_profile_path


def _generate_offset_curve(points: list[QPointF], offset: float) -> QPainterPath:
    """Generates an offset curve (simplified). Not fully robust."""
    offset_path = QPainterPath()
    if len(points) < 2:
        return offset_path

    for i in range(len(points)):
        p1 = points[i]
        p2 = points[(i + 1) % len(points)]  # Next point, wraps around for closed curve

        # Calculate normal (simplified)
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        length = math.sqrt(dx * dx + dy * dy)
        if length == 0:
            continue

        # Normal vector (pointing outwards for CCW path)
        norm_x = -dy / length
        norm_y = dx / length

        offset_p1 = QPointF(p1.x() + norm_x * offset, p1.y() + norm_y * offset)
        # offset_p2 = QPointF(p2.x() + norm_x * offset, p2.y() + norm_y * offset)
        # This simplified normal is for the segment, not vertex, better to average normals at vertices

        if i == 0:
            offset_path.moveTo(offset_p1)
        else:
            offset_path.lineTo(offset_p1)  # This creates a polyline of offset points.
            # For smooth curves, Bezier segments based on normals needed.
    offset_path.closeSubpath()
    return offset_path


if __name__ == "__main__":
    # Example Usage
    cam_generator = Cam()
    print(f"Cam Generator Description: {cam_generator.get_description()}")

    center = QPointF(100, 100)
    path = []
    for i in range(100):
        angle = 2 * math.pi * i / 100
        radius = 50 + 20 * math.sin(5 * angle)  # A wobbly circle path for follower
        path.append(
            QPointF(
                center.x() + radius * math.cos(angle),
                center.y() + radius * math.sin(angle),
            )
        )

    # Test returning QPainterPath
    cam_path_only = cam_generator.generate(
        cam_center_scene=center, follower_path_points=path, follower_radius=5
    )
    if cam_path_only and not cam_path_only.isEmpty():
        print(
            f"Generated QPainterPath for cam. BoundingRect (relative to 0,0): {cam_path_only.boundingRect()}"
        )
    else:
        print("Failed to generate QPainterPath for cam.")

    # Test returning dict
    cam_data = cam_generator.generate(
        cam_center_scene=center,
        follower_path_points=path,
        follower_radius=5,
        return_dict=True,
    )
    if cam_data:
        print("\nGenerated Cam Data Dictionary:")
        for key, value in cam_data.items():
            if key == "profile_path_qt":
                print(f"  {key}: QPainterPath (boundingRect: {value.boundingRect()})")
            elif key == "profile_points_world":
                print(
                    f"  {key}: List of {len(value)} points (first: {value[0] if value else 'N/A'})"
                )
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
        cam_center_scene=QPointF(50, 50),
        follower_path_points=[],  # No follower path
        follower_radius=0,
        return_dict=True,
        base_radius_override=30,
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


class CamGenerator:
    """Generator for cam mechanism SVG blueprints."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def generate_svg(self, cam_data: dict[str, Any]) -> str:
        """
        Generate SVG representation of cam mechanism for blueprints.
        
        Args:
            cam_data: Dictionary containing cam mechanism data
            
        Returns:
            str: SVG content for the cam mechanism
        """
        try:
            # Extract cam parameters with defaults
            center = cam_data.get('center', [0, 0])
            base_radius = cam_data.get('base_radius', 20.0)
            max_radius = cam_data.get('max_radius', 30.0)
            profile_points = cam_data.get('profile_points', [])
            name = cam_data.get('name', 'Cam')

            # If no profile points, create a simple circular cam
            if not profile_points:
                profile_points = self._generate_circular_profile(center, base_radius, 36)

            # Generate cam profile path
            profile_path = self._generate_cam_profile_path(profile_points)

            # Calculate additional cam parameters
            lift = max_radius - base_radius
            bore_radius = base_radius * 0.15
            follower_diameter = 8.0  # Standard follower size

            # Create comprehensive technical drawing
            svg_content = f'''
            <g class="cam-mechanism">
                <!-- Title and part information -->
                <text x="{center[0]}" y="{center[1] - max_radius - 50}" 
                      font-family="Arial" font-size="12" font-weight="bold" text-anchor="middle">{name}</text>
                <text x="{center[0]}" y="{center[1] - max_radius - 35}" 
                      font-family="Arial" font-size="8" text-anchor="middle">Part No: CAM-{lift:.0f}MM-LIFT</text>
                <text x="{center[0]}" y="{center[1] - max_radius - 20}" 
                      font-family="Arial" font-size="8" text-anchor="middle">Cam Profile with {lift:.1f}mm Lift</text>
                
                <!-- Base circle (reference for machining) -->
                <circle cx="{center[0]}" cy="{center[1]}" r="{base_radius}" 
                        fill="none" stroke="blue" stroke-width="0.5" stroke-dasharray="3,3"/>
                
                <!-- Cam profile (cutting outline) -->
                <path d="{profile_path}" fill="none" stroke="red" stroke-width="2"/>
                
                <!-- Center bore -->
                <circle cx="{center[0]}" cy="{center[1]}" r="{bore_radius}" 
                        fill="none" stroke="black" stroke-width="1.5"/>
                
                <!-- Keyway -->
                <rect x="{center[0] - bore_radius * 0.3}" y="{center[1] - bore_radius}" 
                      width="{bore_radius * 0.6}" height="{bore_radius * 2}" 
                      fill="none" stroke="black" stroke-width="1"/>
                
                <!-- Timing marks every 90 degrees -->
                <g class="timing-marks">
                    <circle cx="{center[0]}" cy="{center[1] - base_radius}" r="1" fill="green"/>
                    <text x="{center[0] + 5}" y="{center[1] - base_radius + 3}" 
                          font-family="Arial" font-size="6">0°</text>
                    
                    <circle cx="{center[0] + base_radius}" cy="{center[1]}" r="1" fill="green"/>
                    <text x="{center[0] + base_radius + 5}" y="{center[1] + 3}" 
                          font-family="Arial" font-size="6">90°</text>
                    
                    <circle cx="{center[0]}" cy="{center[1] + base_radius}" r="1" fill="green"/>
                    <text x="{center[0] + 5}" y="{center[1] + base_radius + 8}" 
                          font-family="Arial" font-size="6">180°</text>
                    
                    <circle cx="{center[0] - base_radius}" cy="{center[1]}" r="1" fill="green"/>
                    <text x="{center[0] - base_radius - 15}" y="{center[1] + 3}" 
                          font-family="Arial" font-size="6">270°</text>
                </g>
                
                <!-- Follower assembly detail -->
                <g class="follower-assembly" transform="translate({center[0] + max_radius + 40}, {center[1]})">
                    <!-- Follower housing -->
                    <rect x="-8" y="-15" width="16" height="30" 
                          fill="none" stroke="black" stroke-width="1.5"/>
                    <!-- Follower rod -->
                    <circle r="{follower_diameter/2}" fill="none" stroke="black" stroke-width="1"/>
                    <!-- Spring -->
                    <path d="M -6,8 Q -3,12 0,8 Q 3,4 6,8" 
                          stroke="black" stroke-width="0.5" fill="none"/>
                    <!-- Mounting holes -->
                    <circle cx="-5" cy="-10" r="1" fill="none" stroke="black" stroke-width="0.5"/>
                    <circle cx="5" cy="-10" r="1" fill="none" stroke="black" stroke-width="0.5"/>
                    <circle cx="-5" cy="10" r="1" fill="none" stroke="black" stroke-width="0.5"/>
                    <circle cx="5" cy="10" r="1" fill="none" stroke="black" stroke-width="0.5"/>
                    
                    <!-- Labels -->
                    <text x="0" y="-25" font-family="Arial" font-size="8" text-anchor="middle" font-weight="bold">
                        FOLLOWER ASSEMBLY
                    </text>
                    <text x="0" y="25" font-family="Arial" font-size="7" text-anchor="middle">
                        Ø{follower_diameter:.1f}mm Roller
                    </text>
                </g>
                
                <!-- Manufacturing specifications -->
                <g class="manufacturing-specs">
                    <text x="{center[0] - max_radius - 40}" y="{center[1] - 40}" 
                          font-family="Arial" font-size="8" font-weight="bold">Manufacturing Notes:</text>
                    <text x="{center[0] - max_radius - 40}" y="{center[1] - 25}" 
                          font-family="Arial" font-size="7">• Material: 6mm Plywood/Acrylic</text>
                    <text x="{center[0] - max_radius - 40}" y="{center[1] - 15}" 
                          font-family="Arial" font-size="7">• Cut RED profile outline</text>
                    <text x="{center[0] - max_radius - 40}" y="{center[1] - 5}" 
                          font-family="Arial" font-size="7">• Drill center bore Ø{bore_radius * 2:.1f}mm</text>
                    <text x="{center[0] - max_radius - 40}" y="{center[1] + 5}" 
                          font-family="Arial" font-size="7">• Cut keyway slot</text>
                    <text x="{center[0] - max_radius - 40}" y="{center[1] + 15}" 
                          font-family="Arial" font-size="7">• Sand profile smooth</text>
                    <text x="{center[0] - max_radius - 40}" y="{center[1] + 25}" 
                          font-family="Arial" font-size="7">• Tolerance: ±0.05mm</text>
                    
                    <text x="{center[0] - max_radius - 40}" y="{center[1] + 45}" 
                          font-family="Arial" font-size="8" font-weight="bold">Performance Data:</text>
                    <text x="{center[0] - max_radius - 40}" y="{center[1] + 60}" 
                          font-family="Arial" font-size="7">• Max Lift: {lift:.1f}mm</text>
                    <text x="{center[0] - max_radius - 40}" y="{center[1] + 70}" 
                          font-family="Arial" font-size="7">• Base Circle: Ø{base_radius * 2:.1f}mm</text>
                    <text x="{center[0] - max_radius - 40}" y="{center[1] + 80}" 
                          font-family="Arial" font-size="7">• Rotation: Clockwise</text>
                </g>
                
                <!-- Dimension lines -->
                <g class="dimensions">
                    <!-- Overall diameter -->
                    <line x1="{center[0] - max_radius - 15}" y1="{center[1]}" 
                          x2="{center[0] + max_radius + 15}" y2="{center[1]}" 
                          stroke="#666" stroke-width="0.5"/>
                    <line x1="{center[0] - max_radius - 15}" y1="{center[1] - 5}" 
                          x2="{center[0] - max_radius - 15}" y2="{center[1] + 5}" 
                          stroke="#666" stroke-width="0.5"/>
                    <line x1="{center[0] + max_radius + 15}" y1="{center[1] - 5}" 
                          x2="{center[0] + max_radius + 15}" y2="{center[1] + 5}" 
                          stroke="#666" stroke-width="0.5"/>
                    
                    <text x="{center[0]}" y="{center[1] + max_radius + 35}" 
                          font-family="Arial" font-size="9" text-anchor="middle" font-weight="bold">
                          Ø{max_radius * 2:.1f}mm MAX DIA
                    </text>
                    
                    <!-- Base circle dimension -->
                    <text x="{center[0]}" y="{center[1] + max_radius + 50}" 
                          font-family="Arial" font-size="8" text-anchor="middle">
                          Ø{base_radius * 2:.1f}mm BASE CIRCLE
                    </text>
                    
                    <!-- Bore dimension -->
                    <line x1="{center[0] - bore_radius}" y1="{center[1] - max_radius - 5}" 
                          x2="{center[0] + bore_radius}" y2="{center[1] - max_radius - 5}" 
                          stroke="#666" stroke-width="0.5"/>
                    <text x="{center[0]}" y="{center[1] - max_radius - 10}" 
                          font-family="Arial" font-size="8" text-anchor="middle">
                          Ø{bore_radius * 2:.1f}mm BORE
                    </text>
                </g>
            </g>
            '''

            return svg_content.strip()

        except Exception as e:
            self.logger.error(f"Failed to generate cam SVG: {e}")
            return '<text x="0" y="0" font-family="Arial" font-size="10">Error: Failed to generate cam</text>'

    def _generate_circular_profile(self, center: list[float], radius: float, num_points: int) -> list[list[float]]:
        """Generate points for a circular cam profile."""
        points = []
        for i in range(num_points):
            angle = 2 * math.pi * i / num_points
            x = center[0] + radius * math.cos(angle)
            y = center[1] + radius * math.sin(angle)
            points.append([x, y])
        return points

    def _generate_cam_profile_path(self, profile_points: list[list[float]]) -> str:
        """Generate SVG path for cam profile."""
        if not profile_points:
            return ""

        path_data = f"M {profile_points[0][0]:.2f} {profile_points[0][1]:.2f} "

        for point in profile_points[1:]:
            path_data += f"L {point[0]:.2f} {point[1]:.2f} "

        path_data += "Z"  # Close the path
        return path_data
