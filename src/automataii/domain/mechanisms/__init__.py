"""Domain layer for mechanism design.

Pure Python domain services and types with no UI dependencies.
"""

from .generation_service import MechanismGenerationProtocol, MechanismGenerationService
from .geometry_math_service import GeometryMathProtocol, GeometryMathService
from .path_repository import PathRepository, PathRepositoryProtocol
from .types import BoundingBox, MechanismResult, MechanismSpec, PathID, Point2D, StoredPath

__all__ = [
    # Types
    "BoundingBox",
    "MechanismResult",
    "MechanismSpec",
    "PathID",
    "Point2D",
    "StoredPath",
    # Geometry
    "GeometryMathProtocol",
    "GeometryMathService",
    # Path Storage
    "PathRepository",
    "PathRepositoryProtocol",
    # Generation
    "MechanismGenerationProtocol",
    "MechanismGenerationService",
]
