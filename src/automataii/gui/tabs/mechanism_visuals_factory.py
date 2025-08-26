# MechanismVisualsFactory
# - Lines: ~400
# - Public API: create_4bar_linkage_visuals, create_5bar_linkage_visuals, create_6bar_linkage_visuals, create_cam_visuals, create_gear_visuals, create_planetary_gear_visuals
# - Deps In (Afferent): 1 [MechanismDesignTab]
# - Deps Out (Efferent): 3 [PyQt6, numpy, automataii.config.z_indices]
# - Coupling: Low (single dependency: scene object)
# - Cohesion: Feature (visual creation for mechanisms)
# - Owner: Alan Synn, Reviewers: TBD
# - Last Updated: 2025-01-26

"""
Factory class for creating visual representations of mechanisms.

This class encapsulates all mechanism visual creation logic, providing a clean
separation between the main tab logic and visual rendering concerns.
"""

import math
from typing import Any

import numpy as np
from PyQt6.QtCore import QLineF, QPointF, Qt
from PyQt6.QtGui import QBrush, QColor, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPathItem,
    QGraphicsPolygonItem,
    QGraphicsRectItem,
    QGraphicsScene,
)

from automataii.config.z_indices import (
    Z_MECHANISM_PIVOT,
    Z_SELECTION_MARKER,
)


class MechanismVisualsFactory:
    """Factory for creating visual representations of mechanisms."""
    
    def __init__(self, scene: QGraphicsScene):
        """Initialize the factory with a graphics scene.
        
        Args:
            scene: The QGraphicsScene where visual items will be added
        """
        self.scene = scene
    
    def create_4bar_linkage_visuals(self, mechanism_data: dict, transform_function=None) -> list[QGraphicsItem]:
        """Create visual representation of 4-bar linkage with triangular coupler (like dataset generator)."""
        to_scene_coords = transform_function or self._get_scene_transform_function(mechanism_data)
        params = mechanism_data.get("params", {})

        if not to_scene_coords or not params:
            return []

        l1 = params.get("l1")
        l2 = params.get("l2")
        l3 = params.get("l3")
        l4 = params.get("l4")

        if not all([l1 is not None, l2 is not None, l3 is not None, l4 is not None]):
            return []

        # Use initial positions from simulation data if available
        full_sim_data = mechanism_data.get("full_simulation_data", {})
        if "joint_positions" in full_sim_data:
            joint_positions = full_sim_data["joint_positions"]
            if "p1_positions" in joint_positions and len(joint_positions["p1_positions"]) > 0:
                # Use first frame from simulation
                p1 = np.array(joint_positions["p1_positions"][0])
                p2 = np.array(joint_positions["p2_positions"][0])
                p3 = np.array(joint_positions["p3_positions"][0])
                p4 = np.array(joint_positions["p4_positions"][0])

                # Calculate initial coupler point position (same as dataset)
                coupler_point_x = params.get("coupler_point_x", 0.0)
                coupler_point_y = params.get("coupler_point_y", 0.0)

                coupler_vec = p4 - p3
                coupler_length = np.linalg.norm(coupler_vec)
                if coupler_length > 0:
                    coupler_unit = coupler_vec / coupler_length
                    coupler_normal = np.array([-coupler_unit[1], coupler_unit[0]])
                    p_coupler = p3 + coupler_point_x * coupler_unit + coupler_point_y * coupler_normal
                else:
                    p_coupler = p3
            else:
                return []
        else:
            # Fallback - use default ground pivot positions based on l1
            p1 = np.array([0, 0])
            p2 = np.array([l1, 0])
            p3 = p1 + np.array([l2 * math.cos(0), l2 * math.sin(0)])
            d = np.linalg.norm(p2 - p3)
            if not (abs(l3 - l4) <= d <= l3 + l4):
                return []

            a = (l3**2 - l4**2 + d**2) / (2 * d)
            h = math.sqrt(max(0, l3**2 - a**2))
            p3_p2_unit = (p2 - p3) / d
            midpoint = p3 + a * p3_p2_unit
            p4 = midpoint + h * np.array([-p3_p2_unit[1], p3_p2_unit[0]])

            coupler_point_x = params.get("coupler_point_x", l3/2)
            coupler_point_y = params.get("coupler_point_y", 0.0)

            coupler_vec = p4 - p3
            coupler_length = np.linalg.norm(coupler_vec)
            if coupler_length > 0:
                coupler_unit = coupler_vec / coupler_length
                coupler_normal = np.array([-coupler_unit[1], coupler_unit[0]])
                p_coupler = p3 + coupler_point_x * coupler_unit + coupler_point_y * coupler_normal
            else:
                p_coupler = p3

        # Transform all points to scene coordinates
        p1_t = to_scene_coords(p1)
        p2_t = to_scene_coords(p2)
        p3_t = to_scene_coords(p3)
        p4_t = to_scene_coords(p4)
        p_coupler_t = to_scene_coords(p_coupler)

        visual_items = []

        # Draw basic links (driver and follower)
        driver_link = QGraphicsLineItem(QLineF(p1_t, p3_t))
        driver_pen = QPen(QColor("#e74c3c"), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        driver_link.setPen(driver_pen)
        driver_link.setZValue(15)  # Above parts (Z_PART_DEFAULT = 10)
        self.scene.addItem(driver_link)
        visual_items.append(driver_link)

        follower_link = QGraphicsLineItem(QLineF(p2_t, p4_t))
        follower_pen = QPen(QColor("#f39c12"), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        follower_link.setPen(follower_pen)
        follower_link.setZValue(15)  # Above parts
        self.scene.addItem(follower_link)
        visual_items.append(follower_link)

        # Check if coupler forms a triangle or is collinear (same as dataset generator)
        area = abs(p3[0]*(p4[1]-p_coupler[1]) + p4[0]*(p_coupler[1]-p3[1]) + p_coupler[0]*(p3[1]-p4[1])) / 2

        if area < 1e-3:  # Collinear - show as line
            coupler_line = QGraphicsLineItem(QLineF(p3_t, p4_t))
            coupler_pen = QPen(QColor("#2ecc71"), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            coupler_line.setPen(coupler_pen)
            coupler_line.setZValue(16)  # Above other links
            self.scene.addItem(coupler_line)
            visual_items.append(coupler_line)
        else:  # Non-collinear - show as triangle
            # Create triangular coupler plate (p3, p4, coupler_point)
            triangle_points = [p3_t, p4_t, p_coupler_t]
            triangle_polygon = QPolygonF(triangle_points)

            coupler_triangle = QGraphicsPolygonItem(triangle_polygon)
            triangle_pen = QPen(QColor("#2ecc71"), 2, Qt.PenStyle.SolidLine)
            triangle_brush = QBrush(QColor("#2ecc71").lighter(160))
            triangle_brush.setStyle(Qt.BrushStyle.SolidPattern)
            coupler_triangle.setPen(triangle_pen)
            coupler_triangle.setBrush(triangle_brush)
            coupler_triangle.setZValue(16)  # Above other links
            coupler_triangle.setOpacity(0.8)
            self.scene.addItem(coupler_triangle)
            visual_items.append(coupler_triangle)

        # Add ground link (p1 to p2) with colorful style like dataset generator
        ground_link = QGraphicsLineItem(QLineF(p1_t, p2_t))
        ground_pen = QPen(QColor("#9b59b6"), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)  # Purple
        ground_link.setPen(ground_pen)
        ground_link.setZValue(14)  # Base mechanism level, above parts
        self.scene.addItem(ground_link)
        visual_items.append(ground_link)

        # Add pivot points with colorful style (like dataset generator)
        pivot_colors = [QColor("#f39c12"), QColor("#f39c12"), QColor("#e74c3c"), QColor("#3498db")]  # Orange, Orange, Red, Blue
        pivot_positions = [p1_t, p2_t, p3_t, p4_t]
        pivot_names = ["Ground Pivot 1", "Ground Pivot 2", "Moving Joint 1", "Moving Joint 2"]

        for pos, color, name in zip(pivot_positions, pivot_colors, pivot_names, strict=False):
            # Outer circle
            outer_pivot = self.scene.addEllipse(
                pos.x() - 8, pos.y() - 8, 16, 16,
                QPen(color.darker(150), 2),
                QBrush(color)
            )
            outer_pivot.setZValue(Z_MECHANISM_PIVOT)
            outer_pivot.setToolTip(name)  # Add tooltip for identification
            visual_items.append(outer_pivot)

            # Inner highlight
            inner_pivot = self.scene.addEllipse(
                pos.x() - 4, pos.y() - 4, 8, 8,
                QPen(Qt.PenStyle.NoPen),
                QBrush(color.lighter(150))
            )
            inner_pivot.setZValue(Z_MECHANISM_PIVOT + 1)
            visual_items.append(inner_pivot)

        # Add coupler point marker (red dot)
        coupler_marker = self.scene.addEllipse(
            p_coupler_t.x() - 4, p_coupler_t.y() - 4, 8, 8,
            QPen(QColor("#ff0000"), 2),
            QBrush(QColor("#ff0000"))
        )
        coupler_marker.setZValue(Z_SELECTION_MARKER)
        coupler_marker.setToolTip("Coupler Point (follows path)")
        visual_items.append(coupler_marker)

        return visual_items

    def create_5bar_linkage_visuals(self, mechanism_data: dict, transform_function=None) -> list[QGraphicsItem]:
        """Create visual representation for 5-bar linkage mechanism."""
        visual_items = []

        try:
            params = mechanism_data.get("params", {})
            to_scene_coords = transform_function or self._get_scene_transform_function(mechanism_data)

            if not to_scene_coords:
                return visual_items

            # Get ground pivots
            p1 = np.array(params.get("ground_pivot_1", [0, 0]))
            p2 = np.array(params.get("ground_pivot_2", [100, 0]))

            # Get initial joint positions from simulation data or calculate
            full_sim_data = mechanism_data.get("full_simulation_data", {})
            joint_positions = full_sim_data.get("joint_positions", {})

            if joint_positions and "p3_positions" in joint_positions:
                # Use first frame positions
                p3 = np.array(joint_positions["p3_positions"][0])
                p4 = np.array(joint_positions["p4_positions"][0])
                p5 = np.array(joint_positions["p5_positions"][0])
            else:
                # Calculate initial positions
                L2 = params.get("L2", 40)
                L3 = params.get("L3", 50)
                L4 = params.get("L4", 45)
                L5 = params.get("L5", 55)

                p3 = p1 + np.array([L2, 0])
                p4 = p3 + np.array([L3 * 0.7, L3 * 0.7])
                p5 = p2 + np.array([-L5 * 0.5, L5 * 0.866])

            # Transform to scene coordinates
            p1_scene = to_scene_coords(p1)
            p2_scene = to_scene_coords(p2)
            p3_scene = to_scene_coords(p3)
            p4_scene = to_scene_coords(p4)
            p5_scene = to_scene_coords(p5)

            # Create links
            pen = QPen(QColor(100, 100, 200), 3)

            # Input link (p1 to p3)
            input_link = QGraphicsLineItem(QLineF(p1_scene, p3_scene))
            input_link.setPen(pen)
            self.scene.addItem(input_link)
            visual_items.append(input_link)

            # Coupler 1 (p3 to p4)
            coupler1 = QGraphicsLineItem(QLineF(p3_scene, p4_scene))
            coupler1.setPen(pen)
            self.scene.addItem(coupler1)
            visual_items.append(coupler1)

            # Coupler 2 (p4 to p5)
            coupler2 = QGraphicsLineItem(QLineF(p4_scene, p5_scene))
            coupler2.setPen(pen)
            self.scene.addItem(coupler2)
            visual_items.append(coupler2)

            # Output link (p5 to p2)
            output_link = QGraphicsLineItem(QLineF(p5_scene, p2_scene))
            output_link.setPen(pen)
            self.scene.addItem(output_link)
            visual_items.append(output_link)

            # Ground link
            ground_pen = QPen(QColor(50, 50, 50), 4)
            ground_link = QGraphicsLineItem(QLineF(p1_scene, p2_scene))
            ground_link.setPen(ground_pen)
            self.scene.addItem(ground_link)
            visual_items.append(ground_link)

            # Add pivot markers
            pivot_brush = QBrush(QColor(150, 150, 255))
            ground_pivot_brush = QBrush(QColor(80, 80, 80))

            # Ground pivots
            for pos in [p1_scene, p2_scene]:
                pivot = QGraphicsEllipseItem(pos.x() - 8, pos.y() - 8, 16, 16)
                pivot.setBrush(ground_pivot_brush)
                pivot.setPen(QPen(Qt.GlobalColor.black, 2))
                self.scene.addItem(pivot)
                visual_items.append(pivot)

            # Moving joints
            for pos in [p3_scene, p4_scene, p5_scene]:
                pivot = QGraphicsEllipseItem(pos.x() - 6, pos.y() - 6, 12, 12)
                pivot.setBrush(pivot_brush)
                pivot.setPen(QPen(Qt.GlobalColor.black, 1))
                self.scene.addItem(pivot)
                visual_items.append(pivot)

        except Exception:
            pass

        return visual_items

    def create_6bar_linkage_visuals(self, mechanism_data: dict, transform_function=None) -> list[QGraphicsItem]:
        """Create visual representation for 6-bar linkage mechanism (Stephenson Type I)."""
        visual_items = []

        try:
            params = mechanism_data.get("params", {})
            to_scene_coords = transform_function or self._get_scene_transform_function(mechanism_data)

            if not to_scene_coords:
                return visual_items

            # Get ground pivots
            p1 = np.array(params.get("ground_pivot_1", [0, 0]))
            p2 = np.array(params.get("ground_pivot_2", [100, 0]))
            p6 = np.array(params.get("ground_pivot_3", [50, -30]))

            # Get initial joint positions from simulation data or calculate
            full_sim_data = mechanism_data.get("full_simulation_data", {})
            joint_positions = full_sim_data.get("joint_positions", {})

            if joint_positions and "p3_positions" in joint_positions:
                # Use first frame positions
                p3 = np.array(joint_positions["p3_positions"][0])
                p4 = np.array(joint_positions["p4_positions"][0])
                p5 = np.array(joint_positions["p5_positions"][0])
            else:
                # Calculate initial positions
                L2 = params.get("L2", 40)
                L3 = params.get("L3", 60)
                L4 = params.get("L4", 50)
                L5 = params.get("L5", 45)

                p3 = p1 + np.array([L2, 0])
                p4 = p2 + np.array([-L4 * 0.5, L4 * 0.866])
                p5 = p6 + np.array([L5 * 0.7, L5 * 0.7])

            # Transform to scene coordinates
            p1_scene = to_scene_coords(p1)
            p2_scene = to_scene_coords(p2)
            p3_scene = to_scene_coords(p3)
            p4_scene = to_scene_coords(p4)
            p5_scene = to_scene_coords(p5)
            p6_scene = to_scene_coords(p6)

            # Create links
            pen = QPen(QColor(150, 100, 200), 3)

            # Input link (p1 to p3)
            input_link = QGraphicsLineItem(QLineF(p1_scene, p3_scene))
            input_link.setPen(pen)
            self.scene.addItem(input_link)
            visual_items.append(input_link)

            # Coupler (p3 to p4)
            coupler = QGraphicsLineItem(QLineF(p3_scene, p4_scene))
            coupler.setPen(pen)
            self.scene.addItem(coupler)
            visual_items.append(coupler)

            # Rocker (p4 to p2)
            rocker = QGraphicsLineItem(QLineF(p4_scene, p2_scene))
            rocker.setPen(pen)
            self.scene.addItem(rocker)
            visual_items.append(rocker)

            # Ternary link (p4 to p5)
            ternary = QGraphicsLineItem(QLineF(p4_scene, p5_scene))
            ternary.setPen(QPen(QColor(200, 150, 100), 3))
            self.scene.addItem(ternary)
            visual_items.append(ternary)

            # Output link (p5 to p6)
            output_link = QGraphicsLineItem(QLineF(p5_scene, p6_scene))
            output_link.setPen(pen)
            self.scene.addItem(output_link)
            visual_items.append(output_link)

            # Ground links
            ground_pen = QPen(QColor(50, 50, 50), 4)

            ground1 = QGraphicsLineItem(QLineF(p1_scene, p2_scene))
            ground1.setPen(ground_pen)
            self.scene.addItem(ground1)
            visual_items.append(ground1)

            ground2 = QGraphicsLineItem(QLineF(p2_scene, p6_scene))
            ground2.setPen(QPen(QColor(50, 50, 50), 2, Qt.PenStyle.DashLine))
            self.scene.addItem(ground2)
            visual_items.append(ground2)

            # Add pivot markers
            pivot_brush = QBrush(QColor(150, 150, 255))
            ground_pivot_brush = QBrush(QColor(80, 80, 80))

            # Ground pivots
            for pos in [p1_scene, p2_scene, p6_scene]:
                pivot = QGraphicsEllipseItem(pos.x() - 8, pos.y() - 8, 16, 16)
                pivot.setBrush(ground_pivot_brush)
                pivot.setPen(QPen(Qt.GlobalColor.black, 2))
                self.scene.addItem(pivot)
                visual_items.append(pivot)

            # Moving joints
            for pos in [p3_scene, p4_scene, p5_scene]:
                pivot = QGraphicsEllipseItem(pos.x() - 6, pos.y() - 6, 12, 12)
                pivot.setBrush(pivot_brush)
                pivot.setPen(QPen(Qt.GlobalColor.black, 1))
                self.scene.addItem(pivot)
                visual_items.append(pivot)

        except Exception:
            pass

        return visual_items

    def create_cam_visuals(self, mechanism_data: dict, transform_function=None, character_position=None) -> list[QGraphicsItem]:
        """Create visual representation of cam and follower mechanism with egg-shaped cam."""
        to_scene_coords = transform_function or self._get_scene_transform_function(mechanism_data)
        params = mechanism_data.get("params", {})

        if not params:
            return []

        # Adjusted parameters for more realistic CAM size
        # CAM should be smaller, rod should be longer for realistic appearance
        base_radius = params.get("base_radius", 25.0)
        eccentricity = params.get("eccentricity", 10.0)
        follower_rod_length = params.get("follower_rod_length", 40.0)

        # Scale CAM appropriately for character interaction
        # Use stored scaling factors if available, otherwise use defaults
        cam_scale_factor = mechanism_data.get('cam_scale_factor', 1.0)  # Normal CAM size
        rod_length_multiplier = mechanism_data.get('rod_length_multiplier', 1.0)  # Direct rod length control

        # Apply scaling
        scaled_base_radius = base_radius * cam_scale_factor
        scaled_eccentricity = eccentricity * cam_scale_factor
        scaled_rod_length = follower_rod_length * rod_length_multiplier

        # Create egg-shaped cam profile
        def create_egg_shape_profile(base_radius, eccentricity):
            """Create an egg-shaped cam profile using parametric equations"""
            points = []
            num_points = 100

            for i in range(num_points):
                theta = (i / num_points) * 2 * np.pi

                # Create egg shape: one end more pointed than the other
                # The egg is wider at bottom (theta = π/2) and narrower at top (theta = 3π/2)
                # This creates proper egg shape with follower riding on the surface
                lift = eccentricity * (1 + np.cos(theta)) / 2  # Maximum at theta=0 (right side)
                r = base_radius + lift

                # Convert to Cartesian coordinates
                x = r * np.cos(theta)
                y = r * np.sin(theta)

                points.append([x, y])

            return points

        # Get CAM position - use stored position if available, otherwise calculate
        if 'cam_position' in mechanism_data:
            cam_position = mechanism_data['cam_position']
        else:
            cam_position = character_position or [300, 400]  # Default fallback
            mechanism_data['cam_position'] = cam_position

        # CAM is positioned at bottom with follower above (gravity physics)
        # Position cam at origin for proper coordinate transformation
        cam_center_orig = np.array([0, 0])  # CAM center at origin

        # Place follower ABOVE cam center
        # Follower should be at foot level, so calculate based on that
        follower_y_orig = cam_center_orig[1] - (scaled_base_radius + scaled_rod_length)
        follower_pos_orig = np.array([cam_center_orig[0], follower_y_orig])

        # Create egg-shaped cam profile with scaled dimensions
        egg_profile = create_egg_shape_profile(scaled_base_radius, scaled_eccentricity)

        # Use existing transform function if available, otherwise create new one
        if 'cam_transform_function' in mechanism_data:
            cam_to_scene_coords = mechanism_data['cam_transform_function']
        else:
            # Create custom transformation for CAM positioning
            # CAM should be positioned directly at character feet position
            def cam_to_scene_coords(p):
                """Transform CAM coordinates to scene, placing CAM at character feet."""
                if len(p) != 2:
                    return QPointF(cam_position[0], cam_position[1])

                # Transform point relative to character position
                # Y coordinate: cam_position[1] is already at feet + offset
                # CAM should be centered at this position
                return QPointF(
                    float(p[0] + cam_position[0]),
                    float(p[1] + cam_position[1])
                )
            mechanism_data['cam_transform_function'] = cam_to_scene_coords

        # Store scaling factors for consistency in animation and parametric editing
        mechanism_data['cam_scale_factor'] = cam_scale_factor
        mechanism_data['rod_length_multiplier'] = rod_length_multiplier

        # Transform key points to scene coordinates
        cam_center_scene = cam_to_scene_coords(cam_center_orig)
        follower_scene = cam_to_scene_coords(follower_pos_orig)

        # Transform egg profile points to scene coordinates
        cam_polygon_points = []
        for point in egg_profile:
            # Position relative to cam center
            point_offset = np.array(point) + cam_center_orig
            scene_point = cam_to_scene_coords(point_offset)
            cam_polygon_points.append(scene_point)

        # Create QPolygonF from points
        cam_polygon = QPolygonF(cam_polygon_points)

        visual_items = []

        # Create egg-shaped cam body with enhanced visibility
        cam_color = QColor("#2196f3")  # Modern blue
        cam_body = QGraphicsPolygonItem(cam_polygon)
        cam_body.setPen(QPen(cam_color.darker(120), 3))  # Thinner border for smaller cam
        cam_body.setBrush(QBrush(cam_color.lighter(130)))
        cam_body.setZValue(15)  # Above parts
        cam_body.setOpacity(1.0)  # Full opacity for visibility
        cam_body.setToolTip("Cam - Egg-shaped rotating profile")
        self.scene.addItem(cam_body)
        visual_items.append(cam_body)

        # Create follower with appropriate size
        follower_color = QColor("#ff9800")  # Orange
        follower_width, follower_height = 20, 15  # Larger for visibility
        follower_body = QGraphicsRectItem(
            follower_scene.x() - follower_width/2,
            follower_scene.y() - follower_height/2,
            follower_width,
            follower_height
        )
        follower_body.setPen(QPen(follower_color.darker(120), 2))
        follower_body.setBrush(QBrush(follower_color))
        follower_body.setZValue(16)  # Above cam
        follower_body.setToolTip("Follower - Moves up/down as cam rotates")
        self.scene.addItem(follower_body)
        visual_items.append(follower_body)

        # Create cam center marker (rotation point)
        cam_center_color = QColor("#f44336")  # Red for rotation center
        cam_center_marker = QGraphicsEllipseItem(
            cam_center_scene.x() - 5, cam_center_scene.y() - 5, 10, 10
        )
        cam_center_marker.setPen(QPen(cam_center_color.darker(150), 2))
        cam_center_marker.setBrush(QBrush(cam_center_color))
        cam_center_marker.setZValue(20)  # Top level
        cam_center_marker.setToolTip("Cam Center - Rotation axis")
        self.scene.addItem(cam_center_marker)
        visual_items.append(cam_center_marker)

        # Create follower rod line to show connection
        rod_pen = QPen(QColor("#9e9e9e"), 3, Qt.PenStyle.DashLine)  # Gray dashed line, thicker
        follower_rod = QGraphicsLineItem(
            cam_center_scene.x(), cam_center_scene.y(),
            follower_scene.x(), follower_scene.y()
        )
        follower_rod.setPen(rod_pen)
        follower_rod.setZValue(14)  # Below cam but above parts
        follower_rod.setToolTip("Connecting Rod")
        self.scene.addItem(follower_rod)
        visual_items.append(follower_rod)

        # Return visual items
        return visual_items

    def create_gear_visuals(self, mechanism_data: dict, transform_function=None) -> list[QGraphicsItem]:
        """Create visual representation of gear train mechanism."""
        to_scene_coords = transform_function or self._get_scene_transform_function(mechanism_data)
        params = mechanism_data.get("params", {})

        if not to_scene_coords or not params:
            return []

        r1 = params.get("r1", 30)
        r2 = params.get("r2", 50)

        # Gear centers in original coordinates - match dataset generator
        distance = r1 + r2  # Gears touching
        gear1_center_orig = np.array([0, 0])
        gear2_center_orig = np.array([distance, 0])

        # Transform to scene coordinates
        gear1_center_scene = to_scene_coords(gear1_center_orig)
        gear2_center_scene = to_scene_coords(gear2_center_orig)

        visual_items = []

        # Create gear 1 (driver) with proper screen coordinates
        gear1_color = QColor("#3498db")  # Blue

        # Calculate screen radius for gear1
        gear1_edge_orig = gear1_center_orig + np.array([r1, 0])
        gear1_edge_scene = to_scene_coords(gear1_edge_orig)
        r1_screen = QLineF(gear1_center_scene, gear1_edge_scene).length()

        gear1_body = self.scene.addEllipse(
            gear1_center_scene.x() - r1_screen, gear1_center_scene.y() - r1_screen,
            r1_screen * 2, r1_screen * 2,
            QPen(gear1_color, 4),
            QBrush(gear1_color.lighter(170))
        )
        gear1_body.setZValue(15)  # Above parts
        visual_items.append(gear1_body)

        # Create gear 2 (driven) with proper screen coordinates
        gear2_color = QColor("#2ecc71")  # Green

        # Calculate screen radius for gear2
        gear2_edge_orig = gear2_center_orig + np.array([r2, 0])
        gear2_edge_scene = to_scene_coords(gear2_edge_orig)
        r2_screen = QLineF(gear2_center_scene, gear2_edge_scene).length()

        gear2_body = self.scene.addEllipse(
            gear2_center_scene.x() - r2_screen, gear2_center_scene.y() - r2_screen,
            r2_screen * 2, r2_screen * 2,
            QPen(gear2_color, 4),
            QBrush(gear2_color.lighter(170))
        )
        gear2_body.setZValue(15)  # Above parts
        visual_items.append(gear2_body)

        # Create rotation indicators (lines that will rotate)
        indicator_color = QColor("#ffffff")  # White lines

        # Gear 1 indicator (initially horizontal) - use screen-space radius
        gear1_indicator = self.scene.addLine(
            gear1_center_scene.x(), gear1_center_scene.y(),
            gear1_center_scene.x() + r1_screen, gear1_center_scene.y(),
            QPen(indicator_color, 3)
        )
        gear1_indicator.setZValue(15)
        visual_items.append(gear1_indicator)

        # Gear 2 indicator (initially horizontal) - use screen-space radius
        gear2_indicator = self.scene.addLine(
            gear2_center_scene.x(), gear2_center_scene.y(),
            gear2_center_scene.x() + r2_screen, gear2_center_scene.y(),
            QPen(indicator_color, 3)
        )
        gear2_indicator.setZValue(15)
        visual_items.append(gear2_indicator)

        # Create center pivots
        pivot_color = QColor("#f39c12")  # Orange

        # Gear 1 center
        gear1_pivot = self.scene.addEllipse(
            gear1_center_scene.x() - 8, gear1_center_scene.y() - 8, 16, 16,
            QPen(pivot_color.darker(150), 3),
            QBrush(pivot_color)
        )
        gear1_pivot.setZValue(20)
        visual_items.append(gear1_pivot)

        # Gear 2 center
        gear2_pivot = self.scene.addEllipse(
            gear2_center_scene.x() - 8, gear2_center_scene.y() - 8, 16, 16,
            QPen(pivot_color.darker(150), 3),
            QBrush(pivot_color)
        )
        gear2_pivot.setZValue(20)
        visual_items.append(gear2_pivot)

        return visual_items

    def create_planetary_gear_visuals(self, mechanism_data: dict, transform_function=None) -> list[QGraphicsItem]:
        """Create visual representation of planetary gear mechanism."""
        to_scene_coords = transform_function or self._get_scene_transform_function(mechanism_data)
        params = mechanism_data.get("params", {})

        if not to_scene_coords or not params:
            return []

        r_sun = params.get("r_sun", 20)
        r_planet = params.get("r_planet", 30)
        arm_length = params.get("arm_length", 15)

        visual_items = []

        # Try to get initial positions from simulation data
        full_sim_data = mechanism_data.get("full_simulation_data", {})
        gear_positions = full_sim_data.get("gear_positions", {})

        if gear_positions and "sun_centers" in gear_positions and len(gear_positions["sun_centers"]) > 0:
            # Use simulation data for accurate positioning
            frame_idx = 0
            sun_center_orig = np.array(gear_positions["sun_centers"][frame_idx])
            planet_center_orig = np.array(gear_positions["planet_centers"][frame_idx])
            tracking_point_orig = np.array(gear_positions["tracking_points"][frame_idx])
        else:
            # Fallback to calculated initial positions
            sun_center_orig = np.array([0, 0])
            planet_center_orig = sun_center_orig + (r_sun + r_planet) * np.array([1, 0])  # Initial position
            tracking_point_orig = planet_center_orig + arm_length * np.array([1, 0])  # Initial tracking point

        # Transform to scene coordinates
        sun_center_scene = to_scene_coords(sun_center_orig)
        planet_center_scene = to_scene_coords(planet_center_orig)
        tracking_point_scene = to_scene_coords(tracking_point_orig)

        # Calculate screen radii for proper scaling
        sun_edge_orig = sun_center_orig + np.array([r_sun, 0])
        planet_edge_orig = planet_center_orig + np.array([r_planet, 0])

        sun_edge_scene = to_scene_coords(sun_edge_orig)
        planet_edge_scene = to_scene_coords(planet_edge_orig)

        r_sun_screen = QLineF(sun_center_scene, sun_edge_scene).length()
        r_planet_screen = QLineF(planet_center_scene, planet_edge_scene).length()

        # Create sun gear (stationary)
        sun_color = QColor("#7f8c8d")  # Gray
        sun_gear = self.scene.addEllipse(
            sun_center_scene.x() - r_sun_screen, sun_center_scene.y() - r_sun_screen,
            r_sun_screen * 2, r_sun_screen * 2,
            QPen(sun_color, 4),
            QBrush(sun_color.lighter(150))
        )
        sun_gear.setZValue(14)  # Base level, above parts
        visual_items.append(sun_gear)

        # Create planet gear (orbiting)
        planet_color = QColor("#e67e22")  # Orange
        planet_gear = self.scene.addEllipse(
            planet_center_scene.x() - r_planet_screen, planet_center_scene.y() - r_planet_screen,
            r_planet_screen * 2, r_planet_screen * 2,
            QPen(planet_color, 4),
            QBrush(planet_color.lighter(150))
        )
        planet_gear.setZValue(15)  # Above base level
        visual_items.append(planet_gear)

        # Create arm connecting planet center to tracking point
        arm_color = QColor("#f39c12")  # Golden
        arm_line = self.scene.addLine(
            QLineF(planet_center_scene, tracking_point_scene),
            QPen(arm_color, 3)
        )
        arm_line.setZValue(15)
        visual_items.append(arm_line)

        # Create tracking point marker
        tracking_color = QColor("#e74c3c")  # Red
        tracking_marker = self.scene.addEllipse(
            tracking_point_scene.x() - 8, tracking_point_scene.y() - 8, 16, 16,
            QPen(tracking_color, 2),
            QBrush(tracking_color)
        )
        tracking_marker.setZValue(20)
        visual_items.append(tracking_marker)

        # Create center markers for pivots
        center_color = QColor("#3498db")  # Blue

        # Sun center marker
        sun_center_marker = self.scene.addEllipse(
            sun_center_scene.x() - 6, sun_center_scene.y() - 6, 12, 12,
            QPen(center_color.darker(150), 2),
            QBrush(center_color)
        )
        sun_center_marker.setZValue(25)
        visual_items.append(sun_center_marker)

        # Planet center marker
        planet_center_marker = self.scene.addEllipse(
            planet_center_scene.x() - 4, planet_center_scene.y() - 4, 8, 8,
            QPen(center_color.darker(150), 1),
            QBrush(center_color.lighter(130))
        )
        planet_center_marker.setZValue(25)
        visual_items.append(planet_center_marker)

        return visual_items

    def _get_scene_transform_function(self, layer_data: dict):
        """
        Creates proper coordinate transformation using recommendation system's transform_params.
        
        Note: This is a temporary method that duplicates logic from the main class.
        TODO: This should be refactored to be injected as a dependency rather than duplicated.
        """
        # TODO: This method should be injected as a dependency rather than duplicated
        # For now, returning None to indicate this needs to be handled by the caller
        return None