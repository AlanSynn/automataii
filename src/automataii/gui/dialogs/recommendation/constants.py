"""Constants and configuration for recommendation dialog."""

from PyQt6.QtGui import QColor

# Color palette
BITTERSWEET = QColor("#ff595e")
SUNGLOW = QColor("#ffca3a")
YELLOW_GREEN = QColor("#8ac926")
STEEL_BLUE = QColor("#1982c4")
ULTRA_VIOLET = QColor("#6a4c93")

# Default values
DEFAULT_NUM_SAMPLES_FOR_PATH = 100  # Default number of points to sample from QPainterPath

# Mechanism type constants for display and internal logic
MECHANISM_TYPE_USER_DISPLAY_3_BAR = "3-Bar Linkage"
MECHANISM_TYPE_USER_DISPLAY_4_BAR = "4-Bar Linkage"
MECHANISM_TYPE_USER_DISPLAY_CAM = "Cam Profile"
MECHANISM_TYPE_USER_DISPLAY_GEARS = "Gears (Simple Pair)"

# Type mapping from JSON to display names
MECHANISM_TYPE_MAPPING = {
    "4-bar Coupler": MECHANISM_TYPE_USER_DISPLAY_4_BAR,
    "3-bar Output": MECHANISM_TYPE_USER_DISPLAY_3_BAR,
    "Cam Profile": MECHANISM_TYPE_USER_DISPLAY_CAM,
    "Gear Train": MECHANISM_TYPE_USER_DISPLAY_GEARS,
    # Generic mappings
    "cam": "Cam & Follower",
    "linkage": MECHANISM_TYPE_USER_DISPLAY_4_BAR,
    "gears": MECHANISM_TYPE_USER_DISPLAY_GEARS,
}

# UI Configuration
PREVIEW_WIDGET_SIZE = (350, 300)
CONTAINER_MIN_WIDTH = 370
DIALOG_MIN_SIZE = (1200, 600)
BUTTON_SIZE = (80, 30)