"""
Vulture whitelist for intentionally unused code.

This file documents code that appears unused to static analysis but is
intentional:
1. Protocol/Interface method parameters (required for signature)
2. Public API functions (used by external consumers)
3. Configuration constants (imported by name)
4. Plugin extension points (registered at runtime)

Usage:
    uv run vulture src/automataii vulture_whitelist.py --min-confidence 60
"""

# === PROTOCOL/INTERFACE PARAMETERS ===
# These parameters must exist in method signatures even if not used in stubs

# view_protocol.py - Protocol method parameters
interval_ms  # Protocol parameter for animation timer

# signal_connector.py - Protocol method stub parameters
transforms  # Stub parameter for IK visual updates
pose  # Stub parameter for skeleton pose updates
theme_name  # Stub parameter for theme application


# === CONFIGURATION CONSTANTS ===
# Z-index configuration values imported by name from config/z_indices.py

Z_BACKGROUND_IMAGE
Z_PART_SELECTED_ADJUSTMENT
Z_ANCHOR_POINT
Z_IK_CONTROL_POINT
Z_HOVER_HIGHLIGHT
Z_TOOLTIP_LIKE_OVERLAY
Z_PART_ITEM_SELECTED_HIGHLIGHT
Z_DEBUG_BOUNDING_BOX
Z_DEBUG_TEXT_OVERLAY
Z_DEBUG_IK_SOLVER_VIS
Z_TOOLTIP


# === PUBLIC API FUNCTIONS ===
# Functions that are part of the public API for external use

list_mechanism_types  # registry.py - Public API for mechanism listing
register_renderer  # factory.py - Plugin extension point
validate_part_info  # schemas.py - Public validation API
validate_skeleton_data  # schemas.py - Public validation API
validate_project_metadata  # schemas.py - Public validation API


# === ENUM VALUES ===
# Enum variants that may be used dynamically or in comparisons

CAM  # MechanismType enum value
PARAMETRIC  # MechanismType enum value


# === DATACLASS FIELDS ===
# Fields used in serialization/deserialization even if not accessed directly

preview_size  # MechanismEntry dataclass field, used in JSON
bounding_box_path  # Image annotation field, used in JSON export


# === EXTENSION POINTS ===
# Code designed for future extension or plugin architecture

create_default_registry  # Factory function for registry initialization
try_result  # Utility function for Result pattern
collect_results  # Utility function for batch Result handling
