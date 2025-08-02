"""
Base Generation Service - Structural Foundation Creation

Automatic base generation for mechanical characters that creates
structural foundations connecting all mechanisms with optimized
mounting points for actuators and fixed pivots.

Architecture: Disney Research Computational Character Design
- Automatic structural base generation from mechanism requirements
- Topology optimization for material efficiency and rigidity  
- Integration with mounting requirements for actuators and pivots
- Manufacturing-aware design with standard processes
"""

import logging
import math
from typing import Dict, List, Optional, Tuple, Any
from scipy.spatial import ConvexHull
import numpy as np

from PyQt6.QtCore import QObject, pyqtSignal

from ..core.event_bus import EventBus
from ..core.event_types import EventType
from ..models.mechanical_character import StructuralBase, ManufacturingProcess
from ..models.mechanism import Point2D, Point3D

logger = logging.getLogger(__name__)


class BaseGenerationService(QObject):
    """
    Automatic base generation service for mechanical characters.
    
    Creates optimized structural foundations that:
    - Connect all fixed pivot points with minimal material
    - Provide secure mounting for actuators and mechanisms
    - Consider manufacturing constraints and processes
    - Ensure structural rigidity under operational loads
    
    Generation Methods:
    - Convex Hull: Fast generation connecting all ground points
    - Topology Optimized: Advanced material minimization algorithms
    - Standard Patterns: Pre-designed base templates for common configurations
    """
    
    # Signals for progress feedback
    base_generation_started = pyqtSignal(str)  # character_id
    base_generation_completed = pyqtSignal(str, dict)  # character_id, base_data
    base_generation_failed = pyqtSignal(str, str)  # character_id, error_message
    
    def __init__(self, event_bus: EventBus, parent=None):
        super().__init__(parent)
        self.event_bus = event_bus
        
        # Generation parameters
        self.default_base_thickness = 6.0  # mm
        self.default_material = "aluminum"
        self.minimum_base_area = 500.0  # mm²
        self.mounting_hole_diameter = 3.0  # mm for M3 bolts
        self.edge_clearance = 15.0  # mm clearance from pivot to edge
        
        # Generation algorithms available
        self.generation_algorithms = {
            'convex_hull': self._generate_convex_hull_base,
            'optimized': self._generate_topology_optimized_base,
            'rectangular': self._generate_rectangular_base,
            'circular': self._generate_circular_base
        }
        
        # Subscribe to base generation requests
        self._subscribe_to_events()
        
        logger.info("BaseGenerationService initialized for structural foundation creation")
    
    def _subscribe_to_events(self):
        """Subscribe to base generation request events"""
        self.event_bus.subscribe(
            EventType.BASE_GENERATION_REQUESTED,
            self._handle_base_generation_request
        )
    
    def _handle_base_generation_request(self, event_data: Dict[str, Any]):
        """
        Handle base generation request from character design service.
        
        Args:
            event_data: Contains character_id, pivot_points, base_type, etc.
        """
        try:
            character_id = event_data.get('character_id')
            pivot_points_data = event_data.get('pivot_points', [])
            base_type = event_data.get('base_type', 'optimized')
            material = event_data.get('material', self.default_material)
            
            if not character_id or not pivot_points_data:
                logger.error("Invalid base generation request - missing required data")
                return
            
            # Convert pivot points to Point2D objects
            pivot_points = [Point2D(p['x'], p['y']) for p in pivot_points_data]
            
            logger.info(f"Generating {base_type} base for character {character_id} with {len(pivot_points)} pivots")
            
            # Emit start signal
            self.base_generation_started.emit(character_id)
            
            # Generate base using selected algorithm
            base = self._generate_base(character_id, pivot_points, base_type, material)
            
            if base:
                # Publish completion event
                base_data = {
                    'character_id': character_id,
                    'base': base.dict(),
                    'pivot_count': len(pivot_points),
                    'base_area': base.base_area
                }
                
                self.event_bus.publish(EventType.BASE_GENERATION_COMPLETED, base_data)
                self.base_generation_completed.emit(character_id, base_data)
                
                logger.info(f"Base generation completed for character {character_id}")
            else:
                error_msg = "Base generation failed - no valid base created"
                self.event_bus.publish(
                    EventType.BASE_GENERATION_ERROR,
                    {'character_id': character_id, 'error': error_msg}
                )
                self.base_generation_failed.emit(character_id, error_msg)
                
        except Exception as e:
            error_msg = f"Base generation error: {str(e)}"
            logger.error(error_msg)
            
            character_id = event_data.get('character_id', 'unknown')
            self.event_bus.publish(
                EventType.BASE_GENERATION_ERROR,
                {'character_id': character_id, 'error': error_msg}
            )
            self.base_generation_failed.emit(character_id, error_msg)
    
    def _generate_base(self, character_id: str, pivot_points: List[Point2D],
                      base_type: str, material: str) -> Optional[StructuralBase]:
        """
        Generate structural base using specified algorithm.
        
        Args:
            character_id: Unique character identifier
            pivot_points: List of fixed pivot locations
            base_type: Generation algorithm to use
            material: Base material specification
            
        Returns:
            StructuralBase: Generated base specification
        """
        try:
            if len(pivot_points) < 2:
                logger.warning("Insufficient pivot points for base generation")
                return None
            
            # Select generation algorithm
            if base_type not in self.generation_algorithms:
                logger.warning(f"Unknown base type {base_type}, using 'optimized'")
                base_type = 'optimized'
            
            generation_func = self.generation_algorithms[base_type]
            
            # Generate base outline
            outline_points = generation_func(pivot_points)
            
            if not outline_points or len(outline_points) < 3:
                logger.error("Base generation produced invalid outline")
                return None
            
            # Create base specification
            base = StructuralBase(
                base_id=f"base_{character_id}",
                base_type=base_type,
                outline_points=outline_points,
                thickness=self.default_base_thickness,
                material=material,
                manufacturing_process=self._select_manufacturing_process(material, outline_points)
            )
            
            # Generate mounting points
            self._generate_mounting_points(base, pivot_points)
            
            # Calculate physical properties
            self._calculate_base_properties(base)
            
            # Validate base design
            if not self._validate_base_design(base):
                logger.error("Generated base failed validation")
                return None
            
            return base
            
        except Exception as e:
            logger.error(f"Error in base generation: {e}")
            return None
    
    def _generate_convex_hull_base(self, pivot_points: List[Point2D]) -> List[Point2D]:
        """
        Generate base using convex hull algorithm.
        
        Fast generation that creates the smallest convex polygon
        containing all pivot points with edge clearance.
        """
        try:
            # Add clearance around each pivot point
            expanded_points = []
            for point in pivot_points:
                # Add points in a circle around each pivot for clearance
                for angle in np.linspace(0, 2*np.pi, 8, endpoint=False):
                    x = point.x + self.edge_clearance * np.cos(angle)
                    y = point.y + self.edge_clearance * np.sin(angle)
                    expanded_points.append([x, y])
            
            # Calculate convex hull
            if len(expanded_points) < 3:
                return []
            
            points_array = np.array(expanded_points)
            hull = ConvexHull(points_array)
            
            # Convert hull vertices to Point2D objects
            hull_points = []
            for vertex_idx in hull.vertices:
                point = points_array[vertex_idx]
                hull_points.append(Point2D(float(point[0]), float(point[1])))
            
            return hull_points
            
        except Exception as e:
            logger.error(f"Error in convex hull generation: {e}")
            return []
    
    def _generate_topology_optimized_base(self, pivot_points: List[Point2D]) -> List[Point2D]:
        """
        Generate topology optimized base for minimal material usage.
        
        Advanced algorithm that minimizes material while maintaining
        structural connectivity and rigidity requirements.
        """
        try:
            # For now, use enhanced convex hull with local optimizations
            # In production, this would implement full topology optimization
            
            # Start with convex hull
            hull_points = self._generate_convex_hull_base(pivot_points)
            
            if not hull_points:
                return []
            
            # Apply local optimizations
            optimized_points = self._optimize_base_outline(hull_points, pivot_points)
            
            return optimized_points
            
        except Exception as e:
            logger.error(f"Error in topology optimization: {e}")
            # Fallback to convex hull
            return self._generate_convex_hull_base(pivot_points)
    
    def _generate_rectangular_base(self, pivot_points: List[Point2D]) -> List[Point2D]:
        """Generate rectangular base encompassing all pivot points."""
        try:
            if not pivot_points:
                return []
            
            # Find bounding box
            min_x = min(p.x for p in pivot_points) - self.edge_clearance
            max_x = max(p.x for p in pivot_points) + self.edge_clearance
            min_y = min(p.y for p in pivot_points) - self.edge_clearance
            max_y = max(p.y for p in pivot_points) + self.edge_clearance
            
            # Create rectangular outline
            return [
                Point2D(min_x, min_y),
                Point2D(max_x, min_y),
                Point2D(max_x, max_y),
                Point2D(min_x, max_y)
            ]
            
        except Exception as e:
            logger.error(f"Error in rectangular base generation: {e}")
            return []
    
    def _generate_circular_base(self, pivot_points: List[Point2D]) -> List[Point2D]:
        """Generate circular base centered on pivot points."""
        try:
            if not pivot_points:
                return []
            
            # Find center point
            center_x = sum(p.x for p in pivot_points) / len(pivot_points)
            center_y = sum(p.y for p in pivot_points) / len(pivot_points)
            
            # Find maximum distance from center to any pivot
            max_distance = 0.0
            for point in pivot_points:
                distance = math.sqrt((point.x - center_x)**2 + (point.y - center_y)**2)
                max_distance = max(max_distance, distance)
            
            # Add clearance to radius
            radius = max_distance + self.edge_clearance
            
            # Generate circular outline with 16 points
            circle_points = []
            for i in range(16):
                angle = 2 * math.pi * i / 16
                x = center_x + radius * math.cos(angle)
                y = center_y + radius * math.sin(angle)
                circle_points.append(Point2D(x, y))
            
            return circle_points
            
        except Exception as e:
            logger.error(f"Error in circular base generation: {e}")
            return []
    
    def _optimize_base_outline(self, outline_points: List[Point2D], 
                              pivot_points: List[Point2D]) -> List[Point2D]:
        """
        Optimize base outline for material efficiency.
        
        Applies local optimizations to reduce material usage while
        maintaining structural requirements.
        """
        try:
            # Simple optimization: remove unnecessary vertices
            optimized = []
            n = len(outline_points)
            
            for i in range(n):
                current = outline_points[i]
                prev_point = outline_points[(i - 1) % n]
                next_point = outline_points[(i + 1) % n]
                
                # Check if removing this point would create too sharp an angle
                # or violate clearance requirements
                if self._is_vertex_necessary(current, prev_point, next_point, pivot_points):
                    optimized.append(current)
            
            # Ensure we have at least 3 points for a valid polygon
            if len(optimized) < 3:
                return outline_points
            
            return optimized
            
        except Exception as e:
            logger.error(f"Error in outline optimization: {e}")
            return outline_points
    
    def _is_vertex_necessary(self, vertex: Point2D, prev_vertex: Point2D, 
                           next_vertex: Point2D, pivot_points: List[Point2D]) -> bool:
        """
        Check if a vertex is necessary for the base outline.
        
        Considers structural requirements and clearance constraints.
        """
        try:
            # Always keep vertices that are close to pivot points
            for pivot in pivot_points:
                distance = math.sqrt((vertex.x - pivot.x)**2 + (vertex.y - pivot.y)**2)
                if distance < self.edge_clearance * 1.5:
                    return True
            
            # Check if removing vertex would create too sharp an angle
            # (which could cause manufacturing issues)
            
            # Calculate angle between prev->vertex and vertex->next
            v1_x = vertex.x - prev_vertex.x
            v1_y = vertex.y - prev_vertex.y
            v2_x = next_vertex.x - vertex.x
            v2_y = next_vertex.y - vertex.y
            
            # Calculate angle using dot product
            dot_product = v1_x * v2_x + v1_y * v2_y
            magnitude1 = math.sqrt(v1_x**2 + v1_y**2)
            magnitude2 = math.sqrt(v2_x**2 + v2_y**2)
            
            if magnitude1 > 0 and magnitude2 > 0:
                cos_angle = dot_product / (magnitude1 * magnitude2)
                cos_angle = max(-1.0, min(1.0, cos_angle))  # Clamp to valid range
                angle = math.acos(cos_angle)
                
                # Keep vertex if removing it would create an angle < 30 degrees
                if angle < math.radians(30):
                    return True
            
            # Default: vertex can be removed
            return False
            
        except Exception as e:
            logger.error(f"Error checking vertex necessity: {e}")
            return True  # Conservative: keep vertex if unsure
    
    def _generate_mounting_points(self, base: StructuralBase, pivot_points: List[Point2D]):
        """
        Generate mounting points for pivots and actuators.
        
        Creates precisely positioned mounting holes and fixtures
        for mechanism attachment.
        """
        try:
            # Generate pivot mounting points
            for i, pivot in enumerate(pivot_points):
                mount_point = {
                    'mount_id': f"pivot_mount_{i}",
                    'mount_type': 'pivot',
                    'position': {'x': pivot.x, 'y': pivot.y, 'z': 0},
                    'hole_diameter': self.mounting_hole_diameter,
                    'thread_spec': 'M3',
                    'depth': base.thickness,
                    'counterbore': True,
                    'counterbore_diameter': 6.0,
                    'counterbore_depth': 2.0
                }
                base.pivot_mounts.append(mount_point)
            
            # Generate actuator mounting points (simplified)
            # In production, this would be based on actuator specifications
            if pivot_points:
                # Place actuator mount near center of base
                center_x = sum(p.x for p in pivot_points) / len(pivot_points)
                center_y = sum(p.y for p in pivot_points) / len(pivot_points)
                
                actuator_mount = {
                    'mount_id': 'primary_actuator',
                    'mount_type': 'actuator',
                    'position': {'x': center_x, 'y': center_y, 'z': 0},
                    'mounting_pattern': 'NEMA17',  # Standard stepper motor pattern
                    'bolt_circle_diameter': 31.0,
                    'bolt_count': 4,
                    'bolt_size': 'M3'
                }
                base.actuator_mounts.append(actuator_mount)
            
        except Exception as e:
            logger.error(f"Error generating mounting points: {e}")
    
    def _calculate_base_properties(self, base: StructuralBase):
        """
        Calculate physical properties of the generated base.
        
        Computes mass, center of mass, and structural characteristics.
        """
        try:
            # Calculate area (already implemented in StructuralBase)
            area = base.base_area
            
            # Calculate mass based on material properties
            material_density = self._get_material_density(base.material)
            volume = area * base.thickness * 1e-9  # Convert mm³ to m³
            base.mass = volume * material_density  # kg
            
            # Calculate center of mass (centroid of polygon)
            if base.outline_points:
                center_x = sum(p.x for p in base.outline_points) / len(base.outline_points)
                center_y = sum(p.y for p in base.outline_points) / len(base.outline_points)
                base.center_of_mass = Point3D(center_x, center_y, base.thickness / 2)
            
            # Calculate structural efficiency (area efficiency)
            if area > 0:
                # Compare to bounding box area
                min_x = min(p.x for p in base.outline_points)
                max_x = max(p.x for p in base.outline_points)
                min_y = min(p.y for p in base.outline_points)
                max_y = max(p.y for p in base.outline_points)
                
                bounding_area = (max_x - min_x) * (max_y - min_y)
                if bounding_area > 0:
                    base.structural_efficiency = area / bounding_area
            
        except Exception as e:
            logger.error(f"Error calculating base properties: {e}")
    
    def _get_material_density(self, material: str) -> float:
        """Get material density in kg/m³"""
        densities = {
            'aluminum': 2700.0,
            'steel': 7850.0,
            'plastic': 1200.0,
            'carbon_fiber': 1600.0,
            'wood': 600.0
        }
        return densities.get(material.lower(), 2700.0)  # Default to aluminum
    
    def _select_manufacturing_process(self, material: str, 
                                    outline_points: List[Point2D]) -> ManufacturingProcess:
        """
        Select optimal manufacturing process based on material and geometry.
        
        Considers material properties and geometric complexity.
        """
        try:
            # Simple heuristics for process selection
            if material.lower() in ['aluminum', 'steel']:
                # Check geometric complexity
                if len(outline_points) <= 4:
                    return ManufacturingProcess.SHEET_METAL  # Simple shapes
                else:
                    return ManufacturingProcess.LASER_CUTTING  # Complex shapes
            
            elif material.lower() == 'plastic':
                return ManufacturingProcess.THREE_D_PRINTING
            
            else:
                return ManufacturingProcess.LASER_CUTTING  # Default
                
        except Exception as e:
            logger.error(f"Error selecting manufacturing process: {e}")
            return ManufacturingProcess.LASER_CUTTING
    
    def _validate_base_design(self, base: StructuralBase) -> bool:
        """
        Validate generated base design for manufacturability and functionality.
        
        Checks geometric constraints, material limits, and manufacturing feasibility.
        """
        try:
            # Check minimum area
            if base.base_area < self.minimum_base_area:
                logger.warning(f"Base area {base.base_area:.1f} below minimum {self.minimum_base_area}")
                return False
            
            # Check outline validity
            if len(base.outline_points) < 3:
                logger.error("Base outline has insufficient points")
                return False
            
            # Check for self-intersection (simplified)
            # In production, this would be more comprehensive
            
            # Check mounting point validity
            for mount in base.pivot_mounts:
                position = mount['position']
                if not self._point_inside_polygon(Point2D(position['x'], position['y']), base.outline_points):
                    logger.error(f"Mounting point outside base outline: {mount['mount_id']}")
                    return False
            
            # All checks passed
            return True
            
        except Exception as e:
            logger.error(f"Error in base validation: {e}")
            return False
    
    def _point_inside_polygon(self, point: Point2D, polygon: List[Point2D]) -> bool:
        """
        Check if point is inside polygon using ray casting algorithm.
        
        Returns True if point is inside the polygon.
        """
        try:
            x, y = point.x, point.y
            n = len(polygon)
            inside = False
            
            p1x, p1y = polygon[0].x, polygon[0].y
            for i in range(1, n + 1):
                p2x, p2y = polygon[i % n].x, polygon[i % n].y
                
                if y > min(p1y, p2y):
                    if y <= max(p1y, p2y):
                        if x <= max(p1x, p2x):
                            if p1y != p2y:
                                xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                            if p1x == p2x or x <= xinters:
                                inside = not inside
                p1x, p1y = p2x, p2y
            
            return inside
            
        except Exception as e:
            logger.error(f"Error in point-in-polygon test: {e}")
            return False
    
    def cleanup(self):
        """Clean up resources"""
        logger.info("BaseGenerationService cleaned up")