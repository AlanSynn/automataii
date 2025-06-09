"""Defines Z-order constants for graphics items to ensure consistent layering."""

# Base Image/Background
Z_BACKGROUND_IMAGE = 0

# Character Parts
Z_PART_DEFAULT = 10
Z_PART_SELECTED_ADJUSTMENT = (
    1  # Added to base when selected, if needed visually on top of others
)

# Skeletons (visual guides, non-interactive typically)
Z_SKELETON_BONES = 5
Z_SKELETON_JOINTS = 6

# Motion Paths
Z_MOTION_PATH_LINE = 20

# Anchors / Pivots / Control Points
Z_ANCHOR_POINT = 35
Z_MECHANISM_PIVOT = 102
Z_IK_CONTROL_POINT = 103

# UI Overlays / Highlights
Z_SELECTION_HIGHLIGHT = 40  # Used by CharacterPartItem for its selection outline
Z_HOVER_HIGHLIGHT = 106
Z_TOOLTIP_LIKE_OVERLAY = 200  # For temporary info displays
Z_PART_ITEM_SELECTED_HIGHLIGHT = 40

# Debug Visuals (should be on top of everything if active)
Z_DEBUG_BOUNDING_BOX = 500
Z_DEBUG_TEXT_OVERLAY = 501
Z_DEBUG_IK_SOLVER_VIS = 502

# Z-index for the temporary path being drawn by the user in EditorView
Z_MOTION_PATH_PREVIEW = 45  # Higher than selection highlight and finalized paths
Z_SKELETON_OVERLAY = (
    40  # For SkeletonGraphicsItem, above parts, below motion path preview
)
Z_SELECTION_MARKER = 50  # For mechanism point markers like pivot A, D etc.
Z_TOOLTIP = 100  # Tooltips should be on top

Z_SELECTION_RECT = 1000