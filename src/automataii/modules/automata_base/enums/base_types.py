"""
Base type enumerations for automata base system.

This module defines the core enumeration types used throughout the automata
base system, including base types, mounting methods, materials, and assembly
techniques.
"""

from enum import Enum, auto
from typing import List, Tuple


class BaseType(Enum):
    """Types of automata bases available."""
    
    FLAT_RECTANGULAR = "flat_rectangular"
    FLAT_CIRCULAR = "flat_circular"
    BOX_ENCLOSED = "box_enclosed"
    BOX_OPEN = "box_open"
    PEDESTAL = "pedestal"
    WALL_MOUNTED = "wall_mounted"
    MODULAR = "modular"
    CUSTOM = "custom"
    
    @classmethod
    def get_display_name(cls, base_type: "BaseType") -> str:
        """Get human-readable display name for base type."""
        display_names = {
            cls.FLAT_RECTANGULAR: "Flat Rectangular Base",
            cls.FLAT_CIRCULAR: "Flat Circular Base",
            cls.BOX_ENCLOSED: "Enclosed Box Base",
            cls.BOX_OPEN: "Open Box Base",
            cls.PEDESTAL: "Pedestal Base",
            cls.WALL_MOUNTED: "Wall-Mounted Base",
            cls.MODULAR: "Modular Base System",
            cls.CUSTOM: "Custom Base",
        }
        return display_names.get(base_type, base_type.value)


class MountingType(Enum):
    """Mounting methods for automata bases."""
    
    SURFACE = "surface"  # Flat surface mounting
    WALL = "wall"  # Wall mounting with brackets
    CEILING = "ceiling"  # Ceiling suspension
    PEDESTAL = "pedestal"  # Pedestal/column mounting
    CLAMP = "clamp"  # Clamp-on mounting
    MAGNETIC = "magnetic"  # Magnetic mounting
    ADHESIVE = "adhesive"  # Adhesive mounting
    FREESTANDING = "freestanding"  # No mounting required
    
    @classmethod
    def get_compatible_bases(cls, mounting_type: "MountingType") -> List[BaseType]:
        """Get list of base types compatible with this mounting type."""
        compatibility = {
            cls.SURFACE: [BaseType.FLAT_RECTANGULAR, BaseType.FLAT_CIRCULAR, 
                         BaseType.BOX_ENCLOSED, BaseType.BOX_OPEN, BaseType.MODULAR],
            cls.WALL: [BaseType.WALL_MOUNTED, BaseType.BOX_ENCLOSED, 
                      BaseType.BOX_OPEN, BaseType.MODULAR],
            cls.CEILING: [BaseType.BOX_ENCLOSED, BaseType.MODULAR],
            cls.PEDESTAL: [BaseType.PEDESTAL],
            cls.CLAMP: [BaseType.FLAT_RECTANGULAR, BaseType.MODULAR],
            cls.MAGNETIC: [BaseType.FLAT_RECTANGULAR, BaseType.FLAT_CIRCULAR],
            cls.ADHESIVE: [BaseType.FLAT_RECTANGULAR, BaseType.FLAT_CIRCULAR],
            cls.FREESTANDING: [BaseType.BOX_ENCLOSED, BaseType.BOX_OPEN, 
                              BaseType.PEDESTAL, BaseType.MODULAR],
        }
        return compatibility.get(mounting_type, [])


class MaterialType(Enum):
    """Materials used for automata bases."""
    
    WOOD = "wood"
    MDF = "mdf"
    PLYWOOD = "plywood"
    ACRYLIC = "acrylic"
    ALUMINUM = "aluminum"
    STEEL = "steel"
    PLASTIC_3D_PRINTED = "plastic_3d_printed"
    RESIN_3D_PRINTED = "resin_3d_printed"
    CARDBOARD = "cardboard"
    COMPOSITE = "composite"
    
    @classmethod
    def get_properties(cls, material: "MaterialType") -> dict:
        """Get material properties."""
        properties = {
            cls.WOOD: {
                "density": 700, 
                "strength": "medium", 
                "cost": "Medium", 
                "workability": "Easy", 
                "finish": "natural",
                "category": "Organic",
                "durability": "Medium",
                "weight": "Medium"
            },
            cls.MDF: {
                "density": 750, 
                "strength": "medium", 
                "cost": "Low", 
                "workability": "Easy", 
                "finish": "painted",
                "category": "Organic",
                "durability": "Low",
                "weight": "Medium"
            },
            cls.PLYWOOD: {
                "density": 680, 
                "strength": "high", 
                "cost": "Medium", 
                "workability": "Medium", 
                "finish": "natural/painted",
                "category": "Organic",
                "durability": "Medium",
                "weight": "Light"
            },
            cls.ACRYLIC: {
                "density": 1190, 
                "strength": "medium", 
                "cost": "High", 
                "workability": "Medium", 
                "finish": "transparent/colored",
                "category": "Plastic",
                "durability": "High",
                "weight": "Light"
            },
            cls.ALUMINUM: {
                "density": 2700, 
                "strength": "high", 
                "cost": "Medium", 
                "workability": "Moderate", 
                "finish": "metallic",
                "category": "Metal",
                "durability": "High",
                "weight": "Light"
            },
            cls.STEEL: {
                "density": 7850, 
                "strength": "very_high", 
                "cost": "High", 
                "workability": "Hard", 
                "finish": "metallic",
                "category": "Metal",
                "durability": "Very High",
                "weight": "Heavy"
            },
            cls.PLASTIC_3D_PRINTED: {
                "density": 1200, 
                "strength": "medium", 
                "cost": "Medium", 
                "workability": "N/A", 
                "finish": "matte",
                "category": "Plastic",
                "durability": "Medium",
                "weight": "Light"
            },
            cls.RESIN_3D_PRINTED: {
                "density": 1300, 
                "strength": "medium", 
                "cost": "High", 
                "workability": "N/A", 
                "finish": "smooth",
                "category": "Plastic",
                "durability": "High",
                "weight": "Light"
            },
            cls.CARDBOARD: {
                "density": 200, 
                "strength": "low", 
                "cost": "Very Low", 
                "workability": "Very Easy", 
                "finish": "paper",
                "category": "Organic",
                "durability": "Very Low",
                "weight": "Very Light"
            },
            cls.COMPOSITE: {
                "density": 1500, 
                "strength": "high", 
                "cost": "High", 
                "workability": "Medium", 
                "finish": "various",
                "category": "Composite",
                "durability": "High",
                "weight": "Medium"
            },
        }
        return properties.get(material, {})


class AssemblyMethod(Enum):
    """Assembly methods for constructing bases."""
    
    SCREWS = "screws"
    GLUE = "glue"
    SNAP_FIT = "snap_fit"
    INTERLOCKING = "interlocking"
    WELDING = "welding"
    MAGNETIC = "magnetic"
    PRESS_FIT = "press_fit"
    BOLTS = "bolts"
    RIVETS = "rivets"
    
    @classmethod
    def get_requirements(cls, method: "AssemblyMethod") -> dict:
        """Get assembly method requirements."""
        requirements = {
            cls.SCREWS: {"tools": ["screwdriver", "drill"], "skill": "low", 
                        "reversible": True, "time": "medium"},
            cls.GLUE: {"tools": ["adhesive"], "skill": "low", 
                      "reversible": False, "time": "long"},
            cls.SNAP_FIT: {"tools": [], "skill": "low", 
                          "reversible": True, "time": "short"},
            cls.INTERLOCKING: {"tools": [], "skill": "medium", 
                              "reversible": True, "time": "short"},
            cls.WELDING: {"tools": ["welder"], "skill": "high", 
                         "reversible": False, "time": "medium"},
            cls.MAGNETIC: {"tools": ["magnets"], "skill": "low", 
                          "reversible": True, "time": "short"},
            cls.PRESS_FIT: {"tools": ["hammer"], "skill": "low", 
                           "reversible": False, "time": "short"},
            cls.BOLTS: {"tools": ["wrench", "drill"], "skill": "low", 
                       "reversible": True, "time": "medium"},
            cls.RIVETS: {"tools": ["rivet_gun"], "skill": "medium", 
                        "reversible": False, "time": "medium"},
        }
        return requirements.get(method, {})


class ConnectionType(Enum):
    """Types of connections for modular systems."""
    
    SLOT_AND_TAB = "slot_and_tab"
    DOVETAIL = "dovetail"
    MAGNETIC = "magnetic"
    THREADED = "threaded"
    BAYONET = "bayonet"
    RAIL = "rail"
    PIN = "pin"
    CLIP = "clip"
    
    @classmethod
    def get_strength_rating(cls, connection: "ConnectionType") -> int:
        """Get strength rating (1-5) for connection type."""
        ratings = {
            cls.SLOT_AND_TAB: 3,
            cls.DOVETAIL: 4,
            cls.MAGNETIC: 2,
            cls.THREADED: 5,
            cls.BAYONET: 4,
            cls.RAIL: 3,
            cls.PIN: 3,
            cls.CLIP: 2,
        }
        return ratings.get(connection, 0)