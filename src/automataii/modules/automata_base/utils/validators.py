"""Validation utilities for automata base configurations."""

from typing import List, Dict, Any, Tuple

from automataii.modules.automata_base.models.base_config import BaseConfiguration
from automataii.modules.automata_base.enums.base_types import BaseType, MountingType


class ConfigValidator:
    """Validator for base configurations."""
    
    @staticmethod
    def validate(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate a configuration dictionary.
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Check required fields
        required = ['base_type', 'dimensions']
        for field in required:
            if field not in config:
                errors.append(f"Missing required field: {field}")
        
        # Check dimensions
        if 'dimensions' in config:
            dims = config['dimensions']
            if isinstance(dims, dict):
                if 'width' in dims and dims['width'] <= 0:
                    errors.append("Width must be positive")
                if 'height' in dims and dims['height'] <= 0:
                    errors.append("Height must be positive")
        
        return len(errors) == 0, errors


def validate_base_configuration(config: BaseConfiguration) -> List[str]:
    """
    Validate a base configuration and return list of issues.
    
    Args:
        config: BaseConfiguration to validate
        
    Returns:
        List of validation error messages (empty if valid)
    """
    issues = []
    
    # Validate dimensions
    if config.dimensions.width <= 0 or config.dimensions.height <= 0:
        issues.append("Base dimensions must be positive")
    
    if hasattr(config.dimensions, 'depth') and config.dimensions.depth <= 0:
        issues.append("Base depth must be positive")
    
    # Validate material thickness for certain types
    if config.base_type in [BaseType.FLAT_RECTANGULAR, BaseType.FLAT_CIRCULAR]:
        if not config.material_thickness or config.material_thickness <= 0:
            issues.append(f"Material thickness required for {config.base_type.value}")
    
    # Validate mounting compatibility
    compatible_bases = MountingType.get_compatible_bases(config.mounting_type)
    if config.base_type not in compatible_bases:
        issues.append(
            f"{config.base_type.value} is not compatible with "
            f"{config.mounting_type.value} mounting"
        )
    
    # Validate weight and load capacity
    if config.weight and config.weight < 0:
        issues.append("Weight cannot be negative")
    
    if config.max_load and config.max_load < 0:
        issues.append("Max load cannot be negative")
    
    if config.weight and config.max_load:
        if config.max_load < config.weight:
            issues.append("Max load should be greater than base weight")
    
    # Validate mounting points
    for i, mp in enumerate(config.mounting_points):
        if mp.hole_diameter <= 0:
            issues.append(f"Mounting point {i}: hole diameter must be positive")
        
        if mp.hole_depth is not None and mp.hole_depth <= 0:
            issues.append(f"Mounting point {i}: hole depth must be positive")
        
        if mp.countersink and not mp.countersink_diameter:
            issues.append(f"Mounting point {i}: countersink diameter required")
        
        if mp.countersink_diameter and mp.countersink_diameter <= mp.hole_diameter:
            issues.append(
                f"Mounting point {i}: countersink diameter must be "
                f"larger than hole diameter"
            )
    
    # Validate assembly info if present
    if config.assembly_info:
        assembly_issues = config.assembly_info.validate_assembly()
        issues.extend(assembly_issues)
    
    return issues


def validate_dimensions_for_base_type(
    base_type: BaseType,
    dimensions: Dict[str, float]
) -> List[str]:
    """
    Validate dimensions are appropriate for base type.
    
    Args:
        base_type: Type of base
        dimensions: Dictionary of dimensions
        
    Returns:
        List of validation errors
    """
    issues = []
    
    # Get expected dimensions for base type
    if base_type in [BaseType.FLAT_RECTANGULAR, BaseType.FLAT_CIRCULAR]:
        required = ["width", "height"]
        optional = ["thickness"]
    elif base_type in [BaseType.BOX_ENCLOSED, BaseType.BOX_OPEN, 
                       BaseType.PEDESTAL, BaseType.WALL_MOUNTED]:
        required = ["width", "height", "depth"]
        optional = ["thickness"]
    else:
        required = ["width", "height"]
        optional = ["depth", "thickness"]
    
    # Check required dimensions
    for dim in required:
        if dim not in dimensions:
            issues.append(f"Missing required dimension: {dim}")
        elif dimensions[dim] <= 0:
            issues.append(f"Dimension {dim} must be positive")
    
    # Check optional dimensions if present
    for dim in optional:
        if dim in dimensions and dimensions[dim] <= 0:
            issues.append(f"Dimension {dim} must be positive")
    
    # Base-specific validations
    if base_type == BaseType.PEDESTAL:
        if "height" in dimensions and "width" in dimensions:
            if dimensions["height"] < dimensions["width"]:
                issues.append("Pedestal height should typically exceed width")
    
    if base_type == BaseType.FLAT_CIRCULAR:
        if "width" in dimensions and "height" in dimensions:
            if dimensions["width"] != dimensions["height"]:
                issues.append("Circular base should have equal width and height")
    
    return issues