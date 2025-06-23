import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional  # Added Any for data dict

from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QColor, QPainterPath

if TYPE_CHECKING:
    from .models_pydantic import (
        PartInfoModel as PydanticPartInfoModel,
    )  # For type hinting

# svgpathtools is no longer needed for basic PartInfo if rendering is via QPixmap
# try:
#     from svgpathtools import svg2paths, Path as SvgPathToolPath, Line, Arc, CubicBezier, QuadraticBezier # Aliased Path
#     HAS_SVGPATH = True
# except ImportError:
#     logging.warning("svgpathtools not found. SVG parsing will be unavailable. pip install svgpathtools")
#     HAS_SVGPATH = False
#     # Define dummy classes if the library is missing
#     class SvgPathToolPath: pass
#     class Line: pass
#     class Arc: pass
#     class CubicBezier: pass
#     class QuadraticBezier: pass

# --- Constants ---
SKELETON_JOINTS = [
    "head",
    "neck",
    "right_shoulder",
    "right_elbow",
    "right_wrist",
    "left_shoulder",
    "left_elbow",
    "left_wrist",
    "right_hip",
    "right_knee",
    "right_ankle",
    "left_hip",
    "left_knee",
    "left_ankle",
]

JOINT_CONNECTIONS = [
    ("head", "neck"),
    ("neck", "right_shoulder"),
    ("right_shoulder", "right_elbow"),
    ("right_elbow", "right_wrist"),
    ("neck", "left_shoulder"),
    ("left_shoulder", "left_elbow"),
    ("left_elbow", "left_wrist"),
    ("neck", "right_hip"),
    ("right_hip", "right_knee"),
    ("right_knee", "right_ankle"),
    ("neck", "left_hip"),
    ("left_hip", "left_knee"),
    ("left_knee", "left_ankle"),
]

JOINT_COLORS = {
    "head": QColor(255, 0, 0),
    "neck": QColor(255, 100, 0),
    "right_shoulder": QColor(255, 200, 0),
    "right_elbow": QColor(200, 255, 0),
    "right_wrist": QColor(100, 255, 0),
    "left_shoulder": QColor(0, 255, 0),
    "left_elbow": QColor(0, 255, 100),
    "left_wrist": QColor(0, 255, 200),
    "right_hip": QColor(0, 200, 255),
    "right_knee": QColor(0, 100, 255),
    "right_ankle": QColor(0, 0, 255),
    "left_hip": QColor(100, 0, 255),
    "left_knee": QColor(200, 0, 255),
    "left_ankle": QColor(255, 0, 200),
}


class PartInfo:
    """
    Runtime representation of a character part, including Qt-specific objects
    like QPainterPath and parsed SVG data.
    It is initialized from a validated PartInfoModel.
    """

    def __init__(
        self, model: "PydanticPartInfoModel", resolved_image_path: str | None = None
    ):
        from .models_pydantic import (
            QPointFModel,
        )  # Late import for type hint resolution

        self.name: str = model.name
        self.roi: list[float] | None = model.roi
        # Store resolved absolute paths if provided, otherwise use what's in the model (which might be relative)
        self.image_path: str | None = (
            resolved_image_path if resolved_image_path is not None else model.image_path
        )
        self.fill_color: str = model.fill_color
        self.z_value: float = model.z_value
        self.fixed: bool = model.fixed
        self.opacity: float = model.opacity
        self.group: str | None = model.group
        self.original_svg_path: str | None = model.original_svg_path
        self.enhanced_svg_path: str | None = model.enhanced_svg_path
        self.effective_bbox_offset_x: float = model.effective_bbox_offset_x
        self.effective_bbox_offset_y: float = model.effective_bbox_offset_y
        self.show_anchor: bool = model.show_anchor
        self.local_pivot_offset: list[float] | None = model.local_pivot_offset
        self.anchor_joint_id: str | None = model.anchor_joint_id

        self.motion_path_data: QPainterPath | None = None
        if model.motion_path_data and model.motion_path_data.path_points:
            path = QPainterPath()
            first_point = True
            for p_model in model.motion_path_data.path_points:
                if isinstance(p_model, QPointFModel):  # Ensure it's QPointFModel
                    point = p_model.to_qpointf()
                    if first_point:
                        path.moveTo(point)
                        first_point = False
                    else:
                        path.lineTo(point)
                elif (
                    isinstance(p_model, (tuple, list)) and len(p_model) == 2
                ):  # Handle raw tuple/list
                    try:
                        point = QPointF(float(p_model[0]), float(p_model[1]))
                        if first_point:
                            path.moveTo(point)
                            first_point = False
                        else:
                            path.lineTo(point)
                    except (ValueError, TypeError):
                        logging.warning(
                            f"Skipping invalid point data in motion_path_data for {self.name}: {p_model}"
                        )
            self.motion_path_data = path

        self.qpainter_path: QPainterPath = QPainterPath()
        self.x: float = self.roi[0] if self.roi and len(self.roi) == 4 else 0.0
        self.y: float = self.roi[1] if self.roi and len(self.roi) == 4 else 0.0

    @classmethod
    def from_pydantic(
        cls, model: "PydanticPartInfoModel", project_dir: Optional["Path"] = None
    ) -> "PartInfo":
        """Creates a PartInfo instance from a validated PartInfoModel, resolving paths if project_dir is given."""
        from pathlib import Path  # Ensure Path is available

        resolved_img_path = model.image_path
        if (
            project_dir
            and model.image_path
            and not Path(model.image_path).is_absolute()
        ):
            resolved_img_path = str(project_dir / model.image_path)
            # logging.debug(f"Resolved image path for {model.name}: {resolved_img_path}")

        # Pass resolved paths to constructor
        return cls(model, resolved_image_path=resolved_img_path)

    def to_pydantic_model(self) -> "PydanticPartInfoModel":
        from .models_pydantic import (
            MotionPathDataModel,
            PydanticPartInfoModel,
            QPointFModel,
        )  # Late import

        motion_path_pydantic = None
        if self.motion_path_data and not self.motion_path_data.isEmpty():
            points_for_pydantic: list[QPointFModel] = []  # Type hint for clarity
            for i in range(self.motion_path_data.elementCount()):
                element = self.motion_path_data.elementAt(i)
                # For simplicity, only capture LineTo and MoveTo points.
                # Curve control points would require a more complex MotionPathDataModel structure.
                if element.isMoveTo() or element.isLineTo():
                    points_for_pydantic.append(
                        QPointFModel(x=element.x, y=element.y)
                    )
            if points_for_pydantic:
                motion_path_pydantic = MotionPathDataModel(
                    path_points=points_for_pydantic
                )

        return PydanticPartInfoModel(
            name=self.name,
            roi=self.roi,
            z_value=self.z_value,
            image_path=self.image_path,
            fill_color=self.fill_color,
            fixed=self.fixed,
            opacity=self.opacity,
            group=self.group,
            original_svg_path=self.original_svg_path,
            enhanced_svg_path=self.enhanced_svg_path,
            effective_bbox_offset_x=self.effective_bbox_offset_x,
            effective_bbox_offset_y=self.effective_bbox_offset_y,
            motion_path_data=motion_path_pydantic,
            show_anchor=self.show_anchor,
            local_pivot_offset=self.local_pivot_offset,
            anchor_joint_id=self.anchor_joint_id,
        )


class Joint:
    """Joint connecting two parts"""

    # Assuming parent_item and child_item are CharacterPartItem instances,
    # which would internally hold a PartInfo instance.
    def __init__(
        self,
        parent_item_name: str,
        child_item_name: str,
        parent_pos: QPointF,
        child_pos: QPointF,
        name: str = "",
    ):
        self.parent_item_name: str = parent_item_name
        self.child_item_name: str = child_item_name
        self.parent_pos: QPointF = (
            parent_pos  # Joint position in parent local coordinates
        )
        self.child_pos: QPointF = child_pos  # Joint position in child local coordinates
        self.name: str = name or f"Joint_{parent_item_name}_{child_item_name}"
        self.angle: float = 0.0  # Current joint angle (relative to parent, in degrees)

    # get_global_pos would require access to the actual QGraphicsItem instances,
    # which PartInfo itself doesn't hold. This method might be better placed
    # in a class that manages runtime CharacterPartItem instances if needed generally.
    # For now, commenting out as it depends on live scene items.
    # def get_global_pos(self, parent_item_qgraphicsitem): # Requires actual QGraphicsItem
    #     """Get joint's global position (based on parent item)"""
    #     if parent_item_qgraphicsitem:
    #         if parent_item_qgraphicsitem.scene():
    #              return parent_item_qgraphicsitem.mapToScene(self.parent_pos)
    #         else:
    #              logging.warning(f"Joint {self.name} parent item not yet in scene.")
    #              return parent_item_qgraphicsitem.pos() + self.parent_pos
    #     return QPointF(0, 0)
