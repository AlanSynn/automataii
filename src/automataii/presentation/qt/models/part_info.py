"""
PartInfo - Qt-specific runtime representation of a character part.

This class contains Qt types (QPainterPath) and is used for runtime
representation in the UI layer.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPainterPath

if TYPE_CHECKING:
    from automataii.domain.project.models import PartInfoModel


class PartInfo:
    """
    Runtime representation of a character part, including Qt-specific objects
    like QPainterPath and parsed SVG data.

    It is initialized from a validated PartInfoModel (pure Pydantic model).
    """

    def __init__(
        self,
        model: PartInfoModel,
        resolved_image_path: str | None = None,
    ) -> None:

        self.name: str = model.name
        self.roi: list[float] | None = model.roi
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

        # Convert motion path data to QPainterPath
        self.motion_path_data: QPainterPath | None = None
        if model.motion_path_data and model.motion_path_data.path_points:
            path = QPainterPath()
            first_point = True
            for p_model in model.motion_path_data.path_points:
                if hasattr(p_model, "x") and hasattr(p_model, "y"):
                    point = QPointF(float(p_model.x), float(p_model.y))
                    if first_point:
                        path.moveTo(point)
                        first_point = False
                    else:
                        path.lineTo(point)
                elif isinstance(p_model, tuple | list) and len(p_model) == 2:
                    try:
                        point = QPointF(float(p_model[0]), float(p_model[1]))
                        if first_point:
                            path.moveTo(point)
                            first_point = False
                        else:
                            path.lineTo(point)
                    except (ValueError, TypeError):
                        logging.warning(
                            f"Skipping invalid point in motion_path_data for {self.name}: {p_model}"
                        )
            self.motion_path_data = path

        self.qpainter_path: QPainterPath = QPainterPath()
        self.x: float = self.roi[0] if self.roi and len(self.roi) == 4 else 0.0
        self.y: float = self.roi[1] if self.roi and len(self.roi) == 4 else 0.0

    @classmethod
    def from_pydantic(
        cls,
        model: PartInfoModel,
        project_dir: Path | None = None,
    ) -> PartInfo:
        """Creates a PartInfo instance from a validated PartInfoModel."""
        resolved_img_path = model.image_path
        if model.image_path and not Path(model.image_path).is_absolute():
            image_path = Path(model.image_path)

            # 1) Prefer already-valid relative paths (e.g., repo-relative example assets).
            if image_path.exists():
                resolved_img_path = str(image_path.resolve())
            # 2) Then try project-local resolution (normal saved-project behavior).
            elif project_dir:
                project_candidate = project_dir / image_path
                if project_candidate.exists():
                    resolved_img_path = str(project_candidate.resolve())
                else:
                    # 3) Final fallback: keep project-relative path for downstream handling.
                    resolved_img_path = str(project_candidate)

        return cls(model, resolved_image_path=resolved_img_path)
