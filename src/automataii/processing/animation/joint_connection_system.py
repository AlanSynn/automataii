"""
Experimental Joint Connection System for Smooth Part Transitions

This module implements various methods for creating smooth connections between
animated parts at their joint points, including mesh deformation, overlap blending,
and elastic joint simulation.
"""

import numpy as np
import cv2
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import logging
from scipy.interpolate import griddata
from scipy.spatial import Delaunay

from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import QImage, QPixmap, QPainter, QColor, QBrush, QPen, QRadialGradient

logger = logging.getLogger(__name__)


class ConnectionType(Enum):
    """Types of joint connections available."""
    RIGID = "rigid"  # Simple overlap, no deformation
    MESH_DEFORM = "mesh_deform"  # Mesh-based deformation
    ELASTIC = "elastic"  # Spring-like elastic connection
    BLEND = "blend"  # Alpha blending at connection points


@dataclass
class JointConnection:
    """Represents a connection between two parts at a joint."""
    part1_name: str
    part2_name: str
    joint_id: str
    joint_position: Tuple[float, float]  # World coordinates
    connection_type: ConnectionType = ConnectionType.MESH_DEFORM
    stiffness: float = 0.7  # 0.0 (very flexible) to 1.0 (very stiff)
    blend_radius: float = 20.0  # Radius for blending effects
    
    # Computed properties
    part1_connection_point: Optional[Tuple[float, float]] = None  # Local to part1
    part2_connection_point: Optional[Tuple[float, float]] = None  # Local to part2
    deformation_region1: Optional[np.ndarray] = None  # Mask for part1 deform region
    deformation_region2: Optional[np.ndarray] = None  # Mask for part2 deform region


class JointConnectionAnalyzer:
    """Analyzes skeleton and part relationships to identify joint connections."""
    
    def __init__(self):
        self.connections: List[JointConnection] = []
        
    def analyze_skeleton(self, skeleton_data: Dict[str, Any], parts_info: Dict[str, Any]) -> List[JointConnection]:
        """
        Analyze skeleton structure to find connections between parts.
        
        Args:
            skeleton_data: Skeleton joint information
            parts_info: Information about character parts
            
        Returns:
            List of identified joint connections
        """
        connections = []
        
        # Get joint hierarchy
        joints = skeleton_data.get('joints', {})
        hierarchy = skeleton_data.get('hierarchy', {})
        
        # For each part, find connected parts through shared joints
        for part_name, part_info in parts_info.items():
            anchor_joint_id = part_info.get('anchor_joint_id')
            if not anchor_joint_id:
                continue
                
            # Find child joints that might connect to other parts
            child_joint_ids = hierarchy.get(anchor_joint_id, [])
            
            for child_joint_id in child_joint_ids:
                # Find parts anchored to child joints
                for other_part_name, other_part_info in parts_info.items():
                    if other_part_name == part_name:
                        continue
                        
                    if other_part_info.get('anchor_joint_id') == child_joint_id:
                        # Found a connection
                        joint = joints.get(child_joint_id, {})
                        joint_pos = joint.get('position', (0, 0))
                        
                        connection = JointConnection(
                            part1_name=part_name,
                            part2_name=other_part_name,
                            joint_id=child_joint_id,
                            joint_position=joint_pos,
                            connection_type=self._determine_connection_type(part_name, other_part_name)
                        )
                        connections.append(connection)
                        
                        logger.debug(f"Found connection: {part_name} -> {other_part_name} at joint {child_joint_id}")
        
        self.connections = connections
        return connections
    
    def _determine_connection_type(self, part1: str, part2: str) -> ConnectionType:
        """Determine the best connection type based on part names."""
        # Rigid connections for certain part combinations
        rigid_pairs = [
            ('torso', 'head'),
            ('hand', 'forearm'),
            ('foot', 'shin')
        ]
        
        for p1, p2 in rigid_pairs:
            if (part1 == p1 and part2 == p2) or (part1 == p2 and part2 == p1):
                return ConnectionType.RIGID
        
        # Elastic for limb connections
        if any(limb in part1.lower() for limb in ['arm', 'leg', 'forearm', 'shin']):
            return ConnectionType.ELASTIC
            
        # Default to mesh deformation
        return ConnectionType.MESH_DEFORM


class MeshDeformer:
    """Handles mesh-based deformation for smooth joint connections."""
    
    def __init__(self):
        self.mesh_resolution = 20  # Grid resolution for mesh
        
    def create_deformation_mesh(self, image_shape: Tuple[int, int], 
                               connection_point: Tuple[float, float],
                               radius: float) -> Tuple[np.ndarray, np.ndarray]:
        """
        Create a deformation mesh around a connection point.
        
        Returns:
            Grid points and triangulation for mesh deformation
        """
        h, w = image_shape[:2]
        cx, cy = connection_point
        
        # Create grid points around connection
        x = np.linspace(max(0, cx - radius), min(w, cx + radius), self.mesh_resolution)
        y = np.linspace(max(0, cy - radius), min(h, cy + radius), self.mesh_resolution)
        xx, yy = np.meshgrid(x, y)
        
        # Flatten grid points
        points = np.column_stack([xx.ravel(), yy.ravel()])
        
        # Create Delaunay triangulation
        tri = Delaunay(points)
        
        return points, tri
    
    def deform_mesh(self, points: np.ndarray, connection_point: Tuple[float, float],
                   displacement: Tuple[float, float], stiffness: float) -> np.ndarray:
        """
        Deform mesh points based on connection displacement.
        
        Args:
            points: Original mesh points
            connection_point: Center of deformation
            displacement: How much the connection point moved
            stiffness: How much surrounding points should follow (0-1)
            
        Returns:
            Deformed mesh points
        """
        deformed_points = points.copy()
        cx, cy = connection_point
        dx, dy = displacement
        
        for i, (px, py) in enumerate(points):
            # Calculate distance from connection point
            dist = np.sqrt((px - cx)**2 + (py - cy)**2)
            
            # Weight based on distance (Gaussian falloff)
            weight = np.exp(-dist**2 / (2 * (20 / stiffness)**2))
            
            # Apply weighted displacement
            deformed_points[i, 0] += dx * weight
            deformed_points[i, 1] += dy * weight
            
        return deformed_points
    
    def apply_mesh_deformation(self, image: np.ndarray, original_points: np.ndarray,
                             deformed_points: np.ndarray, triangulation: Delaunay) -> np.ndarray:
        """Apply mesh deformation to an image."""
        h, w = image.shape[:2]
        output = np.zeros_like(image)
        
        # For each triangle in the mesh
        for simplex in triangulation.simplices:
            # Get triangle vertices
            src_tri = original_points[simplex].astype(np.float32)
            dst_tri = deformed_points[simplex].astype(np.float32)
            
            # Get bounding box of destination triangle
            x_min = int(max(0, np.min(dst_tri[:, 0])))
            x_max = int(min(w, np.max(dst_tri[:, 0])))
            y_min = int(max(0, np.min(dst_tri[:, 1])))
            y_max = int(min(h, np.max(dst_tri[:, 1])))
            
            # Create mask for this triangle
            mask = np.zeros((h, w), dtype=np.uint8)
            cv2.fillConvexPoly(mask, dst_tri.astype(np.int32), 255)
            
            # Compute affine transform
            if x_max > x_min and y_max > y_min:
                try:
                    M = cv2.getAffineTransform(dst_tri, src_tri)
                    
                    # Apply transform to get source coordinates
                    for y in range(y_min, y_max):
                        for x in range(x_min, x_max):
                            if mask[y, x] > 0:
                                src_x = M[0, 0] * x + M[0, 1] * y + M[0, 2]
                                src_y = M[1, 0] * x + M[1, 1] * y + M[1, 2]
                                
                                if 0 <= src_x < w and 0 <= src_y < h:
                                    # Bilinear interpolation
                                    output[y, x] = self._bilinear_interpolate(image, src_x, src_y)
                except cv2.error:
                    continue
                    
        return output
    
    def _bilinear_interpolate(self, image: np.ndarray, x: float, y: float) -> np.ndarray:
        """Bilinear interpolation for smooth sampling."""
        h, w = image.shape[:2]
        x0, y0 = int(x), int(y)
        x1, y1 = min(x0 + 1, w - 1), min(y0 + 1, h - 1)
        
        dx, dy = x - x0, y - y0
        
        # Get pixel values
        p00 = image[y0, x0]
        p01 = image[y0, x1]
        p10 = image[y1, x0]
        p11 = image[y1, x1]
        
        # Interpolate
        p0 = (1 - dx) * p00 + dx * p01
        p1 = (1 - dx) * p10 + dx * p11
        
        return (1 - dy) * p0 + dy * p1


class JointBlender:
    """Handles visual blending at joint connection points."""
    
    def create_blend_mask(self, image_shape: Tuple[int, int],
                         center: Tuple[float, float],
                         radius: float) -> np.ndarray:
        """Create a radial gradient mask for blending."""
        h, w = image_shape[:2]
        mask = np.zeros((h, w), dtype=np.float32)
        
        y, x = np.ogrid[:h, :w]
        dist = np.sqrt((x - center[0])**2 + (y - center[1])**2)
        
        # Smooth gradient from 1 at center to 0 at radius
        mask = np.clip(1 - dist / radius, 0, 1)
        mask = mask ** 2  # Quadratic falloff for smoother blend
        
        return mask
    
    def blend_parts_at_joint(self, part1_image: np.ndarray, part2_image: np.ndarray,
                           joint_pos_part1: Tuple[float, float],
                           joint_pos_part2: Tuple[float, float],
                           blend_radius: float) -> Tuple[np.ndarray, np.ndarray]:
        """
        Blend two parts at their joint connection points.
        
        Returns:
            Modified part1 and part2 images with smooth blending
        """
        # Create blend masks
        mask1 = self.create_blend_mask(part1_image.shape, joint_pos_part1, blend_radius)
        mask2 = self.create_blend_mask(part2_image.shape, joint_pos_part2, blend_radius)
        
        # Apply feathering to edges
        mask1 = cv2.GaussianBlur(mask1, (5, 5), 0)
        mask2 = cv2.GaussianBlur(mask2, (5, 5), 0)
        
        # Modify alpha channels for smooth blending
        if part1_image.shape[2] == 4:
            part1_image[:, :, 3] = (part1_image[:, :, 3] * (1 - mask1 * 0.3)).astype(np.uint8)
        if part2_image.shape[2] == 4:
            part2_image[:, :, 3] = (part2_image[:, :, 3] * (1 - mask2 * 0.3)).astype(np.uint8)
            
        return part1_image, part2_image


class ElasticJointSimulator:
    """Simulates elastic/spring-like behavior at joints."""
    
    def __init__(self):
        self.spring_constant = 0.1
        self.damping = 0.8
        
    def calculate_elastic_deformation(self, rest_position: Tuple[float, float],
                                    current_position: Tuple[float, float],
                                    velocity: Tuple[float, float] = (0, 0)) -> Tuple[float, float]:
        """
        Calculate elastic deformation based on spring physics.
        
        Returns:
            New position after elastic deformation
        """
        # Spring force (Hooke's law)
        dx = rest_position[0] - current_position[0]
        dy = rest_position[1] - current_position[1]
        
        fx = self.spring_constant * dx
        fy = self.spring_constant * dy
        
        # Damping force
        fx -= self.damping * velocity[0]
        fy -= self.damping * velocity[1]
        
        # Update velocity (simplified, assuming unit mass)
        new_vx = velocity[0] + fx
        new_vy = velocity[1] + fy
        
        # Update position
        new_x = current_position[0] + new_vx
        new_y = current_position[1] + new_vy
        
        return (new_x, new_y)


class JointConnectionRenderer:
    """Main renderer that combines all joint connection techniques."""
    
    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self.analyzer = JointConnectionAnalyzer()
        self.mesh_deformer = MeshDeformer()
        self.blender = JointBlender()
        self.elastic_sim = ElasticJointSimulator()
        self.connections: List[JointConnection] = []
        
    def set_enabled(self, enabled: bool):
        """Enable or disable the joint connection system."""
        self.enabled = enabled
        logger.info(f"Joint connection system {'enabled' if enabled else 'disabled'}")
        
    def analyze_and_setup(self, skeleton_data: Dict[str, Any], parts_info: Dict[str, Any]):
        """Analyze skeleton and set up joint connections."""
        if not self.enabled:
            return
            
        self.connections = self.analyzer.analyze_skeleton(skeleton_data, parts_info)
        logger.info(f"Analyzed {len(self.connections)} joint connections")
        
    def render_connected_parts(self, parts_data: Dict[str, Dict[str, Any]]) -> Dict[str, np.ndarray]:
        """
        Render parts with smooth joint connections.
        
        Args:
            parts_data: Dictionary of part names to their data (image, position, rotation, etc.)
            
        Returns:
            Dictionary of part names to modified images
        """
        if not self.enabled or not self.connections:
            # Return original images if system is disabled
            return {name: data['image'] for name, data in parts_data.items()}
            
        rendered_parts = {}
        
        # Process each connection
        for connection in self.connections:
            part1_data = parts_data.get(connection.part1_name)
            part2_data = parts_data.get(connection.part2_name)
            
            if not part1_data or not part2_data:
                continue
                
            # Get or initialize rendered images
            part1_image = rendered_parts.get(connection.part1_name, part1_data['image'].copy())
            part2_image = rendered_parts.get(connection.part2_name, part2_data['image'].copy())
            
            # Apply connection based on type
            if connection.connection_type == ConnectionType.MESH_DEFORM:
                part1_image, part2_image = self._apply_mesh_deformation(
                    part1_image, part2_image, part1_data, part2_data, connection
                )
            elif connection.connection_type == ConnectionType.BLEND:
                part1_image, part2_image = self._apply_blending(
                    part1_image, part2_image, part1_data, part2_data, connection
                )
            elif connection.connection_type == ConnectionType.ELASTIC:
                part1_image, part2_image = self._apply_elastic_connection(
                    part1_image, part2_image, part1_data, part2_data, connection
                )
            elif connection.connection_type == ConnectionType.RIGID:
                # Rigid connections don't need special processing
                pass
                
            rendered_parts[connection.part1_name] = part1_image
            rendered_parts[connection.part2_name] = part2_image
            
        # Add any unprocessed parts
        for name, data in parts_data.items():
            if name not in rendered_parts:
                rendered_parts[name] = data['image']
                
        return rendered_parts
    
    def _apply_mesh_deformation(self, part1_image: np.ndarray, part2_image: np.ndarray,
                               part1_data: Dict, part2_data: Dict,
                               connection: JointConnection) -> Tuple[np.ndarray, np.ndarray]:
        """Apply mesh deformation to create smooth connection."""
        # Calculate connection points in each part's local space
        joint_world_pos = connection.joint_position
        
        # Transform to local coordinates
        part1_local_joint = self._world_to_local(joint_world_pos, part1_data)
        part2_local_joint = self._world_to_local(joint_world_pos, part2_data)
        
        # Create deformation meshes
        points1, tri1 = self.mesh_deformer.create_deformation_mesh(
            part1_image.shape, part1_local_joint, connection.blend_radius
        )
        points2, tri2 = self.mesh_deformer.create_deformation_mesh(
            part2_image.shape, part2_local_joint, connection.blend_radius
        )
        
        # Calculate displacement (simplified - in real use would be based on animation)
        displacement = (0, 0)  # This would come from actual animation data
        
        # Deform meshes
        deformed_points1 = self.mesh_deformer.deform_mesh(
            points1, part1_local_joint, displacement, connection.stiffness
        )
        deformed_points2 = self.mesh_deformer.deform_mesh(
            points2, part2_local_joint, displacement, connection.stiffness
        )
        
        # Apply deformation
        part1_deformed = self.mesh_deformer.apply_mesh_deformation(
            part1_image, points1, deformed_points1, tri1
        )
        part2_deformed = self.mesh_deformer.apply_mesh_deformation(
            part2_image, points2, deformed_points2, tri2
        )
        
        return part1_deformed, part2_deformed
    
    def _apply_blending(self, part1_image: np.ndarray, part2_image: np.ndarray,
                       part1_data: Dict, part2_data: Dict,
                       connection: JointConnection) -> Tuple[np.ndarray, np.ndarray]:
        """Apply alpha blending at connection points."""
        # Transform joint position to local coordinates
        part1_local_joint = self._world_to_local(connection.joint_position, part1_data)
        part2_local_joint = self._world_to_local(connection.joint_position, part2_data)
        
        # Apply blending
        return self.blender.blend_parts_at_joint(
            part1_image, part2_image,
            part1_local_joint, part2_local_joint,
            connection.blend_radius
        )
    
    def _apply_elastic_connection(self, part1_image: np.ndarray, part2_image: np.ndarray,
                                 part1_data: Dict, part2_data: Dict,
                                 connection: JointConnection) -> Tuple[np.ndarray, np.ndarray]:
        """Apply elastic deformation at connection."""
        # This would integrate with the animation system to create spring-like motion
        # For now, just apply subtle blending
        return self._apply_blending(part1_image, part2_image, part1_data, part2_data, connection)
    
    def _world_to_local(self, world_pos: Tuple[float, float], part_data: Dict) -> Tuple[float, float]:
        """Convert world coordinates to part's local coordinates."""
        # Simple translation for now - would include rotation in full implementation
        part_pos = part_data.get('position', (0, 0))
        return (world_pos[0] - part_pos[0], world_pos[1] - part_pos[1])
    
    def create_debug_visualization(self, image_size: Tuple[int, int],
                                 parts_data: Dict[str, Dict[str, Any]]) -> np.ndarray:
        """Create a debug visualization showing all connections."""
        debug_image = np.zeros((image_size[1], image_size[0], 4), dtype=np.uint8)
        
        for connection in self.connections:
            # Draw connection line
            cv2.line(debug_image,
                    tuple(map(int, connection.joint_position)),
                    tuple(map(int, connection.joint_position)),
                    (255, 0, 0, 255), 3)
            
            # Draw connection info
            text = f"{connection.part1_name}-{connection.part2_name}"
            cv2.putText(debug_image, text,
                       tuple(map(int, connection.joint_position)),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255, 255), 1)
                       
        return debug_image


# Integration helper for Qt
class QtJointConnectionHelper:
    """Helper class for integrating with Qt/PyQt rendering."""
    
    @staticmethod
    def numpy_to_qpixmap(image: np.ndarray) -> QPixmap:
        """Convert numpy array to QPixmap."""
        height, width, channel = image.shape
        bytes_per_line = channel * width
        
        if channel == 4:
            format = QImage.Format.Format_RGBA8888
        elif channel == 3:
            format = QImage.Format.Format_RGB888
        else:
            raise ValueError(f"Unsupported channel count: {channel}")
            
        qimage = QImage(image.data, width, height, bytes_per_line, format)
        return QPixmap.fromImage(qimage)
    
    @staticmethod
    def apply_joint_connections_to_scene(renderer: JointConnectionRenderer,
                                       part_items: Dict[str, Any],
                                       skeleton_data: Dict[str, Any]) -> None:
        """Apply joint connections to Qt graphics scene items."""
        if not renderer.enabled:
            return
            
        # Gather part data
        parts_data = {}
        for name, item in part_items.items():
            pixmap = item.pixmap()
            if pixmap and not pixmap.isNull():
                # Convert QPixmap to numpy array
                image = pixmap.toImage()
                width, height = image.width(), image.height()
                
                # Convert to numpy array
                ptr = image.bits()
                ptr.setsize(height * width * 4)
                arr = np.frombuffer(ptr, np.uint8).reshape((height, width, 4))
                
                parts_data[name] = {
                    'image': arr.copy(),
                    'position': (item.pos().x(), item.pos().y()),
                    'rotation': item.rotation(),
                    'scale': item.scale()
                }
        
        # Render with connections
        rendered_parts = renderer.render_connected_parts(parts_data)
        
        # Update part items with rendered images
        for name, image in rendered_parts.items():
            if name in part_items:
                pixmap = QtJointConnectionHelper.numpy_to_qpixmap(image)
                part_items[name].setPixmap(pixmap)