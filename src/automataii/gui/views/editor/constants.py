"""Constants used across the editor view components."""

from PyQt6.QtCore import Qt

# Path drawing constants
TARGET_PATH_POINTS = 12

# Default display settings
DEFAULT_DISPLAY_UNIT = "cm"
DEFAULT_DPI = 96

# Grid drawing settings
DEFAULT_PIXEL_GRID_SIZE = 20
GRID_LIGHT_COLOR = (230, 230, 230)
GRID_DARK_COLOR = (200, 200, 200)
GRID_LIGHT_WIDTH = 1
GRID_DARK_WIDTH = 1.5
GRID_MAJOR_INTERVAL_PIXEL = 5
GRID_MAJOR_INTERVAL_UNIT = 1

# Zoom settings
ZOOM_FACTOR_BASE = 1.05  # 5% per step
MIN_ZOOM_LEVEL = -47  # ~0.1x scale
MAX_ZOOM_LEVEL = 47   # ~10x scale
ABSOLUTE_MIN_SCALE = 0.1
ABSOLUTE_MAX_SCALE = 10.0

# Pan settings
PAN_SENSITIVITY = 0.0001
PAN_MULTIPLIER = 20

# Editor modes
class EditorMode:
    SELECT = "select"
    DEFINE_JOINT = "define_joint"
    DEFINE_MOTION_PATH = "define_motion_path"
    SELECT_END_EFFECTOR = "select_end_effector"
    SELECT_CAM_CENTER = "select_cam_center"
    SIMULATION = "simulation"
    SELECT_PIVOT_A = "select_pivot_a"
    SELECT_PIVOT_D = "select_pivot_d"
    SELECT_DRIVER_CENTER = "select_driver_center"
    SELECT_DRIVEN_CENTER = "select_driven_center"

# Cursor mappings
MODE_CURSORS = {
    EditorMode.SELECT: Qt.CursorShape.ArrowCursor,
    EditorMode.DEFINE_JOINT: Qt.CursorShape.CrossCursor,
    EditorMode.DEFINE_MOTION_PATH: Qt.CursorShape.CrossCursor,
    EditorMode.SELECT_END_EFFECTOR: Qt.CursorShape.CrossCursor,
    EditorMode.SELECT_CAM_CENTER: Qt.CursorShape.CrossCursor,
    EditorMode.SIMULATION: Qt.CursorShape.ForbiddenCursor,
    EditorMode.SELECT_PIVOT_A: Qt.CursorShape.CrossCursor,
    EditorMode.SELECT_PIVOT_D: Qt.CursorShape.CrossCursor,
    EditorMode.SELECT_DRIVER_CENTER: Qt.CursorShape.CrossCursor,
    EditorMode.SELECT_DRIVEN_CENTER: Qt.CursorShape.CrossCursor,
}