"""
Mechanism Part Decomposer - Breaks down mechanisms into individual buildable parts.

This module takes complete mechanism assemblies (4-bar linkages, gear trains, cam mechanisms)
and decomposes them into individual parts that can be manufactured and assembled.

Each part includes:
- Geometric definition with mounting holes
- Material specifications
- Assembly instructions
- Dimensional annotations

Author: Alan Synn · alan@alansynn.com
"""

import numpy as np
import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import math


class PartType(Enum):
    """Types of mechanism parts that can be generated."""
    LINK = "link"
    PIN = "pin" 
    BEARING = "bearing"
    GEAR = "gear"
    CAM = "cam"
    FOLLOWER = "follower"
    HOUSING = "housing"
    GROUND_MOUNT = "ground_mount"


@dataclass
class MechanismPart:
    """Represents a single buildable part of a mechanism."""
    part_id: str
    part_type: PartType
    name: str
    description: str
    
    # Geometric properties
    geometry: Dict[str, Any]  # SVG path data, dimensions, etc.
    mounting_holes: List[Dict[str, float]]  # [{"x": 0, "y": 0, "diameter": 5}, ...]
    
    # Material properties
    material: str = "3mm Plywood"
    thickness: float = 3.0  # mm
    
    # Assembly information
    assembly_order: int = 0
    connects_to: List[str] = None  # Part IDs this connects to
    assembly_notes: str = ""
    
    # Dimensions for manufacturing
    bounding_box: Dict[str, float] = None  # {"width": 0, "height": 0}
    critical_dimensions: List[Dict[str, Any]] = None  # Dimensional annotations
    
    def __post_init__(self):
        if self.connects_to is None:
            self.connects_to = []
        if self.critical_dimensions is None:
            self.critical_dimensions = []


class MechanismPartDecomposer:
    """
    Decomposes mechanism assemblies into individual buildable parts.
    
    Supports:
    - 4-bar linkages → links, pins, ground mounts
    - Gear trains → gears, shafts, housing
    - Cam mechanisms → cam, follower, guide rails
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Standard part dimensions (in mm)
        self.standard_pin_diameter = 6.0
        self.standard_hole_diameter = 6.2  # 0.2mm clearance
        self.standard_thickness = 3.0
        self.min_material_thickness = 8.0  # Minimum material around holes
        
    def decompose_mechanism(self, mechanism_data: Dict[str, Any]) -> List[MechanismPart]:
        """
        Decompose a mechanism into individual parts.
        
        Args:
            mechanism_data: Complete mechanism data including type, parameters, simulation data
            
        Returns:
            List of MechanismPart objects ready for manufacturing
        """
        mech_type = mechanism_data.get("type", "").lower()
        
        if mech_type == "4bar":
            return self._decompose_4bar_linkage(mechanism_data)
        elif mech_type == "gear":
            return self._decompose_gear_train(mechanism_data)
        elif mech_type == "cam":
            return self._decompose_cam_mechanism(mechanism_data)
        else:
            self.logger.warning(f"Unsupported mechanism type for decomposition: {mech_type}")
            return []
    
    def _decompose_4bar_linkage(self, mechanism_data: Dict[str, Any]) -> List[MechanismPart]:
        """Decompose a 4-bar linkage into individual links and hardware."""
        params = mechanism_data.get("params", {})
        sim_data = mechanism_data.get("full_simulation_data", {})
        
        # Extract link lengths and positions
        l1 = params.get("l1", 100.0)  # Ground link
        l2 = params.get("l2", 80.0)   # Drive link
        l3 = params.get("l3", 120.0)  # Coupler
        l4 = params.get("l4", 90.0)   # Output link
        
        # Get joint positions for proper part geometry
        fourbar_data = sim_data.get("fourbar_data", {})
        if "joint_positions" in fourbar_data and len(fourbar_data["joint_positions"]) > 0:
            # Use first frame for reference geometry
            joints = fourbar_data["joint_positions"][0]
            p1 = np.array(joints.get("P1", [0, 0]))
            p2 = np.array(joints.get("P2", [l1, 0]))
            p3 = np.array(joints.get("P3", [l1 + l2, l3]))
            p4 = np.array(joints.get("P4", [0, l4]))
        else:
            # Default positions for rectangular configuration
            p1 = np.array([0, 0])
            p2 = np.array([l1, 0])
            p3 = np.array([l1 + l2 * 0.7, l2 * 0.7])  # Estimated
            p4 = np.array([0, l4])
        
        parts = []
        part_id_base = mechanism_data.get("mechanism_id", "4bar")
        
        # Ground Link (Link 1) - Usually a base plate
        ground_link = self._create_ground_link(
            f"{part_id_base}_ground",
            p1, p2, 
            link_length=l1
        )
        parts.append(ground_link)
        
        # Drive Link (Link 2) 
        drive_link = self._create_standard_link(
            f"{part_id_base}_drive",
            "Drive Link",
            p1, p3,
            link_length=l2,
            assembly_order=1,
            connects_to=[f"{part_id_base}_ground", f"{part_id_base}_coupler"]
        )
        parts.append(drive_link)
        
        # Coupler Link (Link 3)
        coupler_link = self._create_standard_link(
            f"{part_id_base}_coupler", 
            "Coupler Link",
            p3, p4,
            link_length=l3,
            assembly_order=2,
            connects_to=[f"{part_id_base}_drive", f"{part_id_base}_output"]
        )
        parts.append(coupler_link)
        
        # Output Link (Link 4)
        output_link = self._create_standard_link(
            f"{part_id_base}_output",
            "Output Link", 
            p4, p2,
            link_length=l4,
            assembly_order=3,
            connects_to=[f"{part_id_base}_coupler", f"{part_id_base}_ground"]
        )
        parts.append(output_link)
        
        # Hardware (pins, bushings)
        hardware_parts = self._create_4bar_hardware(part_id_base, [p1, p2, p3, p4])
        parts.extend(hardware_parts)
        
        return parts
    
    def _decompose_gear_train(self, mechanism_data: Dict[str, Any]) -> List[MechanismPart]:
        """Decompose a gear train into individual gears and housing."""
        params = mechanism_data.get("params", {})
        
        r1 = params.get("r1", 30.0)
        r2 = params.get("r2", 45.0)
        num_teeth_1 = params.get("num_teeth_1", 12)
        num_teeth_2 = params.get("num_teeth_2", 18)
        
        parts = []
        part_id_base = mechanism_data.get("mechanism_id", "gear")
        
        # Drive Gear
        drive_gear = MechanismPart(
            part_id=f"{part_id_base}_drive_gear",
            part_type=PartType.GEAR,
            name="Drive Gear",
            description=f"Drive gear with {num_teeth_1} teeth, {r1*2:.1f}mm diameter",
            geometry=self._generate_gear_geometry(r1, num_teeth_1),
            mounting_holes=[{"x": 0, "y": 0, "diameter": self.standard_hole_diameter}],
            material="3mm Plywood",
            thickness=self.standard_thickness,
            assembly_order=1,
            connects_to=[f"{part_id_base}_housing", f"{part_id_base}_driven_gear"],
            assembly_notes="Insert shaft through center hole, mesh with driven gear"
        )
        parts.append(drive_gear)
        
        # Driven Gear
        driven_gear = MechanismPart(
            part_id=f"{part_id_base}_driven_gear",
            part_type=PartType.GEAR,
            name="Driven Gear", 
            description=f"Driven gear with {num_teeth_2} teeth, {r2*2:.1f}mm diameter",
            geometry=self._generate_gear_geometry(r2, num_teeth_2),
            mounting_holes=[{"x": 0, "y": 0, "diameter": self.standard_hole_diameter}],
            material="3mm Plywood",
            thickness=self.standard_thickness,
            assembly_order=2,
            connects_to=[f"{part_id_base}_housing", f"{part_id_base}_drive_gear"],
            assembly_notes="Insert shaft through center hole, mesh with drive gear"
        )
        parts.append(driven_gear)
        
        # Housing/Base Plate
        housing = self._create_gear_housing(part_id_base, r1, r2)
        parts.append(housing)
        
        return parts
    
    def _decompose_cam_mechanism(self, mechanism_data: Dict[str, Any]) -> List[MechanismPart]:
        """Decompose a cam mechanism into cam, follower, and guides."""
        params = mechanism_data.get("params", {})
        
        base_radius = params.get("base_radius", 25.0)
        eccentricity = params.get("eccentricity", 10.0)
        
        parts = []
        part_id_base = mechanism_data.get("mechanism_id", "cam")
        
        # Cam Profile
        cam_part = MechanismPart(
            part_id=f"{part_id_base}_cam",
            part_type=PartType.CAM,
            name="Cam Profile",
            description=f"Egg-shaped cam profile, base radius {base_radius:.1f}mm, eccentricity {eccentricity:.1f}mm",
            geometry=self._generate_cam_geometry(base_radius, eccentricity),
            mounting_holes=[{"x": 0, "y": 0, "diameter": self.standard_hole_diameter}],
            material="3mm Plywood",
            thickness=self.standard_thickness,
            assembly_order=1,
            connects_to=[f"{part_id_base}_housing"],
            assembly_notes="Mount on rotating shaft, ensure smooth surface finish"
        )
        parts.append(cam_part)
        
        # Follower
        follower_part = MechanismPart(
            part_id=f"{part_id_base}_follower",
            part_type=PartType.FOLLOWER,
            name="Cam Follower",
            description="Rectangular follower with guide rails",
            geometry=self._generate_follower_geometry(),
            mounting_holes=[
                {"x": 0, "y": -15, "diameter": 4.0},  # Guide rail holes
                {"x": 0, "y": 15, "diameter": 4.0}
            ],
            material="3mm Plywood",
            thickness=self.standard_thickness,
            assembly_order=2,
            connects_to=[f"{part_id_base}_housing"],
            assembly_notes="Install in guide rails, maintain contact with cam"
        )
        parts.append(follower_part)
        
        # Housing with guide rails
        housing = self._create_cam_housing(part_id_base, base_radius, eccentricity)
        parts.append(housing)
        
        return parts
    
    def _create_standard_link(
        self, 
        part_id: str, 
        name: str,
        point1: np.ndarray, 
        point2: np.ndarray,
        link_length: float,
        assembly_order: int = 0,
        connects_to: List[str] = None
    ) -> MechanismPart:
        """Create a standard link with holes at both ends."""
        
        # Calculate link geometry
        length = link_length
        width = max(12.0, length * 0.15)  # Proportional width, min 12mm
        
        # Create mounting holes at both ends
        hole_offset = self.min_material_thickness
        mounting_holes = [
            {"x": -length/2 + hole_offset, "y": 0, "diameter": self.standard_hole_diameter},
            {"x": length/2 - hole_offset, "y": 0, "diameter": self.standard_hole_diameter}
        ]
        
        # Generate SVG geometry for the link
        geometry = self._generate_link_geometry(length, width, mounting_holes)
        
        return MechanismPart(
            part_id=part_id,
            part_type=PartType.LINK,
            name=name,
            description=f"Link, {length:.1f}mm long × {width:.1f}mm wide",
            geometry=geometry,
            mounting_holes=mounting_holes,
            material="3mm Plywood",
            thickness=self.standard_thickness,
            assembly_order=assembly_order,
            connects_to=connects_to or [],
            assembly_notes=f"Connect with {self.standard_pin_diameter}mm pins",
            bounding_box={"width": length, "height": width},
            critical_dimensions=[
                {"type": "length", "value": length, "tolerance": "±0.1mm"},
                {"type": "hole_spacing", "value": length - 2*hole_offset, "tolerance": "±0.05mm"}
            ]
        )
    
    def _create_ground_link(
        self, 
        part_id: str, 
        point1: np.ndarray, 
        point2: np.ndarray,
        link_length: float
    ) -> MechanismPart:
        """Create a ground link (base plate) with mounting provisions."""
        
        length = link_length
        width = max(20.0, length * 0.3)  # Wider base for stability
        
        # Ground links have additional mounting holes for table/frame attachment
        mounting_holes = [
            # Main joint holes
            {"x": -length/2 + self.min_material_thickness, "y": 0, "diameter": self.standard_hole_diameter},
            {"x": length/2 - self.min_material_thickness, "y": 0, "diameter": self.standard_hole_diameter},
            # Base mounting holes
            {"x": -length/3, "y": -width/3, "diameter": 4.0},
            {"x": length/3, "y": -width/3, "diameter": 4.0},
            {"x": -length/3, "y": width/3, "diameter": 4.0}, 
            {"x": length/3, "y": width/3, "diameter": 4.0}
        ]
        
        geometry = self._generate_ground_link_geometry(length, width, mounting_holes)
        
        return MechanismPart(
            part_id=part_id,
            part_type=PartType.GROUND_MOUNT,
            name="Ground Link (Base)",
            description=f"Base plate, {length:.1f}mm × {width:.1f}mm, with mounting holes",
            geometry=geometry,
            mounting_holes=mounting_holes,
            material="6mm Plywood",
            thickness=6.0,  # Thicker for ground link
            assembly_order=0,  # Install first
            connects_to=[],
            assembly_notes="Mount to table/frame using base holes. Install joint pins.",
            bounding_box={"width": length, "height": width}
        )
    
    def _create_4bar_hardware(self, part_id_base: str, joint_positions: List[np.ndarray]) -> List[MechanismPart]:
        """Create pins and bushings for 4-bar linkage joints."""
        hardware = []
        
        for i, pos in enumerate(joint_positions):
            # Pin for each joint
            pin = MechanismPart(
                part_id=f"{part_id_base}_pin_{i+1}",
                part_type=PartType.PIN,
                name=f"Joint Pin {i+1}",
                description=f"Steel pin, {self.standard_pin_diameter}mm diameter × 15mm long",
                geometry=self._generate_pin_geometry(self.standard_pin_diameter, 15.0),
                mounting_holes=[],
                material="Steel Rod",
                thickness=15.0,
                assembly_order=10 + i,
                assembly_notes="Insert through aligned holes, secure with clips if needed"
            )
            hardware.append(pin)
            
            # Optional: Bushings for smooth operation
            if i > 0:  # Skip ground joints for bushings
                bushing = MechanismPart(
                    part_id=f"{part_id_base}_bushing_{i+1}",
                    part_type=PartType.BEARING,
                    name=f"Bushing {i+1}",
                    description=f"Bronze bushing, {self.standard_pin_diameter}mm ID × {self.standard_hole_diameter + 0.5}mm OD",
                    geometry=self._generate_bushing_geometry(self.standard_pin_diameter, self.standard_hole_diameter + 0.5),
                    mounting_holes=[],
                    material="Bronze",
                    thickness=self.standard_thickness,
                    assembly_order=5 + i,
                    assembly_notes="Press fit into link holes before installing pins"
                )
                hardware.append(bushing)
        
        return hardware
    
    def _create_gear_housing(self, part_id_base: str, r1: float, r2: float) -> MechanismPart:
        """Create housing/base plate for gear train."""
        # Calculate housing dimensions
        gear_distance = r1 + r2 + 2.0  # Small clearance
        housing_width = gear_distance + max(r1, r2) + 40  # Extra space around
        housing_height = max(r1, r2) * 2 + 20
        
        # Shaft holes for gear centers
        mounting_holes = [
            {"x": -gear_distance/2, "y": 0, "diameter": self.standard_hole_diameter, "note": "Drive gear shaft"},
            {"x": gear_distance/2, "y": 0, "diameter": self.standard_hole_diameter, "note": "Driven gear shaft"},
            # Base mounting holes
            {"x": -housing_width/3, "y": -housing_height/3, "diameter": 4.0},
            {"x": housing_width/3, "y": -housing_height/3, "diameter": 4.0},
            {"x": -housing_width/3, "y": housing_height/3, "diameter": 4.0},
            {"x": housing_width/3, "y": housing_height/3, "diameter": 4.0}
        ]
        
        geometry = self._generate_housing_geometry(housing_width, housing_height, mounting_holes)
        
        return MechanismPart(
            part_id=f"{part_id_base}_housing",
            part_type=PartType.HOUSING,
            name="Gear Housing",
            description=f"Base plate for gear train, {housing_width:.1f}mm × {housing_height:.1f}mm",
            geometry=geometry,
            mounting_holes=mounting_holes,
            material="6mm Plywood",
            thickness=6.0,
            assembly_order=0,
            connects_to=[],
            assembly_notes="Mount to base first, then install gears with shafts",
            bounding_box={"width": housing_width, "height": housing_height}
        )
    
    def _create_cam_housing(self, part_id_base: str, base_radius: float, eccentricity: float) -> MechanismPart:
        """Create housing with guide rails for cam mechanism."""
        max_radius = base_radius + eccentricity + 2.0
        housing_width = max_radius * 2 + 40
        housing_height = max_radius * 2 + 60  # Extra height for follower travel
        
        # Cam shaft hole and guide rail slots
        mounting_holes = [
            {"x": 0, "y": -max_radius/2, "diameter": self.standard_hole_diameter, "note": "Cam shaft"},
            # Guide rail mounting holes for follower
            {"x": 15, "y": max_radius + 10, "diameter": 4.0, "note": "Guide rail top"},
            {"x": 15, "y": -max_radius - 10, "diameter": 4.0, "note": "Guide rail bottom"},
            {"x": -15, "y": max_radius + 10, "diameter": 4.0, "note": "Guide rail top"},
            {"x": -15, "y": -max_radius - 10, "diameter": 4.0, "note": "Guide rail bottom"}
        ]
        
        geometry = self._generate_cam_housing_geometry(housing_width, housing_height, mounting_holes, max_radius)
        
        return MechanismPart(
            part_id=f"{part_id_base}_housing",
            part_type=PartType.HOUSING,
            name="Cam Housing",
            description=f"Housing with guide rails, {housing_width:.1f}mm × {housing_height:.1f}mm",
            geometry=geometry,
            mounting_holes=mounting_holes,
            material="6mm Plywood",
            thickness=6.0,
            assembly_order=0,
            assembly_notes="Install cam shaft and follower guide rails",
            bounding_box={"width": housing_width, "height": housing_height}
        )
    
    # Geometry generation methods
    def _generate_link_geometry(self, length: float, width: float, holes: List[Dict]) -> Dict[str, Any]:
        """Generate SVG path data for a standard link."""
        # Rounded rectangle with holes
        corner_radius = min(width/4, 3.0)
        
        svg_path = f"""
        <g>
            <rect x="{-length/2}" y="{-width/2}" width="{length}" height="{width}" 
                  rx="{corner_radius}" ry="{corner_radius}" 
                  fill="none" stroke="black" stroke-width="0.5"/>
            {self._generate_holes_svg(holes)}
        </g>
        """
        
        return {
            "type": "svg_path",
            "data": svg_path,
            "dimensions": {"length": length, "width": width}
        }
    
    def _generate_ground_link_geometry(self, length: float, width: float, holes: List[Dict]) -> Dict[str, Any]:
        """Generate SVG for ground link (base plate)."""
        corner_radius = min(width/6, 4.0)
        
        svg_path = f"""
        <g>
            <rect x="{-length/2}" y="{-width/2}" width="{length}" height="{width}" 
                  rx="{corner_radius}" ry="{corner_radius}" 
                  fill="none" stroke="black" stroke-width="0.8"/>
            {self._generate_holes_svg(holes)}
            <text x="0" y="5" text-anchor="middle" font-size="8" fill="black">BASE</text>
        </g>
        """
        
        return {
            "type": "svg_path", 
            "data": svg_path,
            "dimensions": {"length": length, "width": width}
        }
    
    def _generate_gear_geometry(self, radius: float, num_teeth: int) -> Dict[str, Any]:
        """Generate SVG for gear profile with involute teeth."""
        # Simplified gear - actual involute profile would be more complex
        tooth_height = radius * 0.2
        outer_radius = radius + tooth_height
        
        # Generate approximate gear profile
        points = []
        for i in range(num_teeth * 2):  # Two points per tooth
            angle = (i / (num_teeth * 2)) * 2 * math.pi
            if i % 2 == 0:
                # Tooth tip
                r = outer_radius
            else:
                # Tooth root
                r = radius - tooth_height * 0.3
                
            x = r * math.cos(angle)
            y = r * math.sin(angle)
            points.append(f"{x:.2f},{y:.2f}")
        
        path_data = "M " + " L ".join(points) + " Z"
        
        svg_path = f"""
        <g>
            <path d="{path_data}" fill="none" stroke="black" stroke-width="0.5"/>
            <circle cx="0" cy="0" r="{self.standard_hole_diameter/2}" 
                   fill="none" stroke="black" stroke-width="0.3"/>
            <text x="0" y="-{radius/2}" text-anchor="middle" font-size="6" fill="black">{num_teeth}T</text>
        </g>
        """
        
        return {
            "type": "svg_path",
            "data": svg_path, 
            "dimensions": {"diameter": outer_radius * 2, "teeth": num_teeth}
        }
    
    def _generate_cam_geometry(self, base_radius: float, eccentricity: float) -> Dict[str, Any]:
        """Generate SVG for cam profile."""
        points = []
        num_points = 60
        
        for i in range(num_points):
            theta = (i / num_points) * 2 * math.pi
            # Cam profile equation
            lift = eccentricity * (1 + math.cos(theta + math.pi/2)) / 2
            r = base_radius + lift
            
            x = r * math.cos(theta)
            y = r * math.sin(theta)
            points.append(f"{x:.2f},{y:.2f}")
        
        path_data = "M " + " L ".join(points) + " Z"
        
        svg_path = f"""
        <g>
            <path d="{path_data}" fill="none" stroke="black" stroke-width="0.5"/>
            <circle cx="0" cy="0" r="{self.standard_hole_diameter/2}" 
                   fill="none" stroke="black" stroke-width="0.3"/>
            <text x="0" y="{base_radius/2}" text-anchor="middle" font-size="6" fill="black">CAM</text>
        </g>
        """
        
        return {
            "type": "svg_path",
            "data": svg_path,
            "dimensions": {"base_radius": base_radius, "max_radius": base_radius + eccentricity}
        }
    
    def _generate_follower_geometry(self) -> Dict[str, Any]:
        """Generate SVG for cam follower."""
        width = 20.0
        height = 40.0
        
        svg_path = f"""
        <g>
            <rect x="{-width/2}" y="{-height/2}" width="{width}" height="{height}" 
                  rx="2" ry="2" fill="none" stroke="black" stroke-width="0.5"/>
            <circle cx="0" cy="-15" r="2" fill="none" stroke="black" stroke-width="0.3"/>
            <circle cx="0" cy="15" r="2" fill="none" stroke="black" stroke-width="0.3"/>
            <text x="0" y="0" text-anchor="middle" font-size="6" fill="black">FOLLOWER</text>
        </g>
        """
        
        return {
            "type": "svg_path",
            "data": svg_path,
            "dimensions": {"width": width, "height": height}
        }
    
    def _generate_housing_geometry(self, width: float, height: float, holes: List[Dict]) -> Dict[str, Any]:
        """Generate SVG for mechanism housing."""
        corner_radius = 6.0
        
        svg_path = f"""
        <g>
            <rect x="{-width/2}" y="{-height/2}" width="{width}" height="{height}" 
                  rx="{corner_radius}" ry="{corner_radius}" 
                  fill="none" stroke="black" stroke-width="0.8"/>
            {self._generate_holes_svg(holes)}
            <text x="0" y="{height/2 - 10}" text-anchor="middle" font-size="8" fill="black">HOUSING</text>
        </g>
        """
        
        return {
            "type": "svg_path",
            "data": svg_path,
            "dimensions": {"width": width, "height": height}
        }
    
    def _generate_cam_housing_geometry(self, width: float, height: float, holes: List[Dict], cam_radius: float) -> Dict[str, Any]:
        """Generate SVG for cam housing with guide slots."""
        corner_radius = 6.0
        slot_width = 8.0
        slot_height = cam_radius * 1.5
        
        svg_path = f"""
        <g>
            <rect x="{-width/2}" y="{-height/2}" width="{width}" height="{height}" 
                  rx="{corner_radius}" ry="{corner_radius}" 
                  fill="none" stroke="black" stroke-width="0.8"/>
            <rect x="{-slot_width/2}" y="{-slot_height/2}" width="{slot_width}" height="{slot_height}" 
                  fill="none" stroke="black" stroke-width="0.5" stroke-dasharray="2,2"/>
            {self._generate_holes_svg(holes)}
            <text x="0" y="{height/2 - 10}" text-anchor="middle" font-size="8" fill="black">CAM HOUSING</text>
            <text x="{slot_width/2 + 5}" y="0" font-size="6" fill="black">GUIDE SLOT</text>
        </g>
        """
        
        return {
            "type": "svg_path",
            "data": svg_path,
            "dimensions": {"width": width, "height": height, "slot_height": slot_height}
        }
    
    def _generate_pin_geometry(self, diameter: float, length: float) -> Dict[str, Any]:
        """Generate SVG for pin (side view)."""
        svg_path = f"""
        <g>
            <rect x="{-length/2}" y="{-diameter/2}" width="{length}" height="{diameter}" 
                  fill="none" stroke="black" stroke-width="0.5"/>
            <text x="0" y="0" text-anchor="middle" font-size="4" fill="black">PIN</text>
        </g>
        """
        
        return {
            "type": "svg_path",
            "data": svg_path,
            "dimensions": {"diameter": diameter, "length": length}
        }
    
    def _generate_bushing_geometry(self, inner_diameter: float, outer_diameter: float) -> Dict[str, Any]:
        """Generate SVG for bushing."""
        svg_path = f"""
        <g>
            <circle cx="0" cy="0" r="{outer_diameter/2}" fill="none" stroke="black" stroke-width="0.5"/>
            <circle cx="0" cy="0" r="{inner_diameter/2}" fill="none" stroke="black" stroke-width="0.3"/>
            <text x="0" y="-{outer_diameter/4}" text-anchor="middle" font-size="4" fill="black">BUSHING</text>
        </g>
        """
        
        return {
            "type": "svg_path",
            "data": svg_path,
            "dimensions": {"inner_diameter": inner_diameter, "outer_diameter": outer_diameter}
        }
    
    def _generate_holes_svg(self, holes: List[Dict]) -> str:
        """Generate SVG for mounting holes."""
        svg_elements = []
        
        for hole in holes:
            x = hole["x"]
            y = hole["y"]
            diameter = hole["diameter"]
            radius = diameter / 2
            
            # Hole circle
            svg_elements.append(
                f'<circle cx="{x}" cy="{y}" r="{radius}" '
                f'fill="none" stroke="black" stroke-width="0.3"/>'
            )
            
            # Center cross for drilling reference
            cross_size = radius * 0.5
            svg_elements.append(
                f'<path d="M {x-cross_size},{y} L {x+cross_size},{y} '
                f'M {x},{y-cross_size} L {x},{y+cross_size}" '
                f'stroke="black" stroke-width="0.1"/>'
            )
        
        return "\n".join(svg_elements)


# Factory function for easy access
def decompose_mechanism_to_parts(mechanism_data: Dict[str, Any]) -> List[MechanismPart]:
    """
    Factory function to decompose a mechanism into buildable parts.
    
    Args:
        mechanism_data: Complete mechanism data
        
    Returns:
        List of MechanismPart objects
    """
    decomposer = MechanismPartDecomposer()
    return decomposer.decompose_mechanism(mechanism_data)


if __name__ == "__main__":
    """Test the decomposer with sample data."""
    
    # Test 4-bar linkage
    sample_4bar = {
        "type": "4bar",
        "mechanism_id": "test_4bar",
        "params": {
            "l1": 100.0,
            "l2": 80.0, 
            "l3": 120.0,
            "l4": 90.0
        },
        "full_simulation_data": {}
    }
    
    decomposer = MechanismPartDecomposer()
    parts = decomposer.decompose_mechanism(sample_4bar)
    
    print(f"Decomposed 4-bar into {len(parts)} parts:")
    for part in parts:
        print(f"  - {part.name}: {part.description}")
        print(f"    Material: {part.material}, Thickness: {part.thickness}mm")
        print(f"    Connects to: {', '.join(part.connects_to)}")
        print()