# Z-Axis Layering (Z-Ordering) Documentation

This document outlines the Z-axis arrangement (layering order) for the 2D graphics items in the `automataii` application.
The Z-values determine which items appear on top of others in the scene. Higher values are rendered on top of lower values.

## Overview

The Z-indices are centrally defined in `src/automataii/config/z_indices.py`.

| Layer Group | Item Type | Z-Index | Description |
| :--- | :--- | :--- | :--- |
| **Debug** | Debug Visuals | 500+ | Bounding boxes, text overlays, IK solver visualizations. |
| **UI Overlays** | Tooltips | 200 | Temporary info displays. |
| **UI Overlays** | Hover Highlight | 106 | Visual feedback when hovering over items. |
| **Controls** | IK Control Points | 103 | Interactive points for Inverse Kinematics. |
| **Controls** | Mechanism Pivots | 102 | Pivot points for mechanisms. |
| **Skeleton** | Mechanism Joints | 46 | Enhanced skeleton joints for mechanism view. |
| **Skeleton** | Mechanism Bones | 45 | Enhanced skeleton bones for mechanism view. |
| **Preview** | Motion Path Preview | 45 | Temporary path being drawn by the user. |
| **UI Overlays** | Selection Highlight | 40 | Outline for selected items. |
| **Controls** | Anchor Points | 35 | Pivots and anchors. |
| **Motion** | Motion Path Lines | 20 | Visual lines representing motion paths. |
| **Parts** | Character Parts | 10 | Default layer for character body parts. |
| **Skeleton** | Standard Joints | 6 | Basic skeleton joints. |
| **Skeleton** | Standard Bones | 5 | Basic skeleton bones. |
| **Background** | Background Image | 0 | The base image or canvas background. |

## Detailed Configuration

### Background Layer
- **`Z_BACKGROUND_IMAGE` (0)**: The base reference image or background canvas.

### Character Parts
- **`Z_PART_DEFAULT` (10)**: The standard Z-value for character parts (e.g., head, torso, limbs).
- **`Z_PART_SELECTED_ADJUSTMENT` (+1)**: Added to a part's Z-value when it is selected to bring it slightly forward.

### Skeleton (Standard)
Used for basic visual guides and non-interactive skeleton displays.
- **`Z_SKELETON_BONES` (5)**: Bones connecting joints.
- **`Z_SKELETON_JOINTS` (6)**: Joint points.

### Skeleton (Mechanism Mode)
Used in the Mechanism Tab for better visibility over parts.
- **`Z_SKELETON_MECHANISM_BONES` (45)**
- **`Z_SKELETON_MECHANISM_JOINTS` (46)**

### Motion Paths
- **`Z_MOTION_PATH_LINE` (20)**: The finalized motion path lines.
- **`Z_MOTION_PATH_PREVIEW` (45)**: The temporary path currently being drawn by the user.

### Controls & Anchors
- **`Z_ANCHOR_POINT` (35)**: Anchor points on parts.
- **`Z_MECHANISM_PIVOT` (102)**: Pivot points for mechanism linkages.
- **`Z_IK_CONTROL_POINT` (103)**: Control handles for IK manipulation.

### UI Highlights & Overlays
- **`Z_SELECTION_HIGHLIGHT` (40)**: Selection outlines/boxes.
- **`Z_HOVER_HIGHLIGHT` (106)**: Highlight effect when hovering.
- **`Z_TOOLTIP` (100)** / **`Z_TOOLTIP_LIKE_OVERLAY` (200)**: Informational tooltips.

### Debug Layer
These items are always on top when debug mode is active.
- **`Z_DEBUG_BOUNDING_BOX` (500)**
- **`Z_DEBUG_TEXT_OVERLAY` (501)**
- **`Z_DEBUG_IK_SOLVER_VIS` (502)**

## Usage in Code

To use these constants, import them from the config module:

```python
from automataii.config.z_indices import Z_PART_DEFAULT, Z_SKELETON_JOINTS

item.setZValue(Z_PART_DEFAULT)
```
