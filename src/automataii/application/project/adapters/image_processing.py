"""
ImageProcessingTab Adapter.

Bridges ImageProcessingTab to ProjectStateManager.

Data Flow:
- Tab → StateManager: parts_generated, skeleton_updated
- StateManager → Tab: skeleton_changed (external updates)

Architecture: Application Layer (Hexagonal)
Pattern: Adapter
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..models import (
    BoneData,
    JointData,
    PartData,
    Point,
    SkeletonData,
    Transform,
)
from .base import TabAdapter

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ImageProcessingTabAdapter(TabAdapter):
    """
    Adapter for ImageProcessingTab.

    Transforms:
    - parts_generated (dict, str) → load_parts(dict[str, PartData])
    - skeleton_updated (dict) → load_skeleton(SkeletonData)

    Subscribes to:
    - skeleton_changed → on_skeleton_updated_externally
    """

    def __init__(
        self,
        state_manager,
        parent=None,
        *,
        prefer_main_window_pipeline: bool = False,
    ) -> None:
        super().__init__(state_manager, parent)
        self._prefer_main_window_pipeline = prefer_main_window_pipeline

    def _connect_tab_signals(self) -> None:
        """Connect to ImageProcessingTab's output signals."""
        if not self._tab:
            return

        self._tab.parts_generated.connect(self._on_parts_generated)
        self._tab.skeleton_updated.connect(self._on_skeleton_updated)
        logger.debug("ImageProcessingTabAdapter: Connected to tab signals")

    def _subscribe_to_state(self) -> None:
        """Subscribe to skeleton changes from state manager."""
        self._state_manager.skeleton_changed.connect(self._on_state_skeleton_changed)
        logger.debug("ImageProcessingTabAdapter: Subscribed to state changes")

    def _disconnect_tab_signals(self) -> None:
        """Disconnect from tab signals."""
        if not self._tab:
            return

        try:
            self._tab.parts_generated.disconnect(self._on_parts_generated)
            self._tab.skeleton_updated.disconnect(self._on_skeleton_updated)
        except TypeError:
            pass  # Already disconnected

    def _unsubscribe_from_state(self) -> None:
        """Unsubscribe from state manager."""
        try:
            self._state_manager.skeleton_changed.disconnect(self._on_state_skeleton_changed)
        except TypeError:
            pass

    # =========================================================================
    # TAB → STATE MANAGER
    # =========================================================================

    def _on_parts_generated(self, annotation_results: dict, output_dir: str) -> None:
        """
        Handle parts_generated signal from ImageProcessingTab.

        Args:
            annotation_results: Annotation results dict from image_to_annotations
            output_dir: Directory where parts_info.json was generated
        """
        if self._should_defer_parts_generated_to_main_window(annotation_results, output_dir):
            logger.info(
                "ImageProcessingTabAdapter: Received parts_generated for %s; deferred to MainWindow pipeline.",
                output_dir,
            )
            return

        logger.info(f"ImageProcessingTabAdapter: Parts generated in {output_dir}")

        try:
            # Load parts_info.json from output directory
            parts_info_path = Path(output_dir) / "parts_info.json"
            if not parts_info_path.exists():
                logger.warning(f"parts_info.json not found at {parts_info_path}")
                return

            with open(parts_info_path, encoding="utf-8") as f:
                parts_info = json.load(f)

            # Transform to domain models
            parts = self._transform_parts_info(parts_info, output_dir)

            if parts:
                self._state_manager.load_parts(parts)
                logger.info(f"Loaded {len(parts)} parts into state manager")

        except Exception as e:
            logger.exception(f"Error processing parts_generated: {e}")

    def _should_defer_parts_generated_to_main_window(
        self,
        annotation_results: dict,
        output_dir: str,
    ) -> bool:
        """Return True when MainWindow already owns the full parts load pipeline."""
        if not self._prefer_main_window_pipeline:
            return False
        if not isinstance(annotation_results, dict):
            return False
        # MainWindow legacy loader path requires char_cfg_path and parts_info.json.
        if not annotation_results.get("char_cfg_path"):
            return False
        return (Path(output_dir) / "parts_info.json").exists()

    def _on_skeleton_updated(self, skeleton_data: dict) -> None:
        """
        Handle skeleton_updated signal from ImageProcessingTab.

        Args:
            skeleton_data: Raw skeleton dict from char_cfg.yaml
        """
        if self._prefer_main_window_pipeline:
            logger.info(
                "ImageProcessingTabAdapter: Received skeleton_updated; deferred to MainWindow pipeline."
            )
            return
        logger.info("ImageProcessingTabAdapter: Skeleton updated from tab")

        try:
            skeleton = self._transform_skeleton_data(skeleton_data)
            if skeleton:
                self._state_manager.load_skeleton(skeleton)
                logger.info(f"Loaded skeleton with {len(skeleton.joints)} joints")

        except Exception as e:
            logger.exception(f"Error processing skeleton_updated: {e}")

    # =========================================================================
    # STATE MANAGER → TAB
    # =========================================================================

    def _on_state_skeleton_changed(self, skeleton: SkeletonData | None) -> None:
        """
        Handle skeleton changes from state manager.

        Forwards to tab's on_skeleton_updated_externally method.
        """
        if not self._tab:
            return
        if self._is_runtime_to_ssot_sync_in_progress():
            logger.debug(
                "ImageProcessingTabAdapter: Suppressing skeleton sync during runtime->SSOT mirror"
            )
            return

        # Convert back to dict format for tab compatibility
        skeleton_dict = skeleton.to_dict() if skeleton else None

        # Call tab's existing method
        if hasattr(self._tab, "on_skeleton_updated_externally"):
            self._tab.on_skeleton_updated_externally(skeleton_dict)

    # =========================================================================
    # DATA TRANSFORMATIONS
    # =========================================================================

    def _transform_parts_info(
        self,
        parts_info: dict[str, Any],
        output_dir: str,
    ) -> dict[str, PartData]:
        """
        Transform parts_info.json format to domain PartData.

        Args:
            parts_info: Raw parts_info dict with keys like 'parts', 'joint_map'
            output_dir: Base directory for relative paths

        Returns:
            Dict mapping part_name to PartData
        """
        parts: dict[str, PartData] = {}

        character_data = parts_info.get("character", {})
        if isinstance(character_data, dict) and isinstance(character_data.get("parts"), dict):
            raw_parts = character_data.get("parts", {})
        else:
            raw_parts = parts_info.get("parts", {})

        joint_map = parts_info.get("joint_map", {})

        for part_name, part_info in raw_parts.items():
            try:
                # Resolve image/mask paths from output dir when relative.
                image_path_raw = str(part_info.get("image_path", f"{part_name}.png"))
                image_path = image_path_raw
                if image_path and not Path(image_path).is_absolute():
                    image_path = str((Path(output_dir) / image_path).resolve())

                mask_path_raw = part_info.get("mask_path")
                mask_path = str(mask_path_raw) if mask_path_raw else ""
                if mask_path and not Path(mask_path).is_absolute():
                    mask_path = str((Path(output_dir) / mask_path).resolve())
                if not mask_path:
                    mask_path = image_path

                # Get anchor joint from explicit part data or joint_map fallback.
                anchor_joint = (
                    part_info.get("anchor_joint_id")
                    or part_info.get("anchor_joint")
                    or joint_map.get(part_name, "")
                    or "root"
                )

                # Get transform data
                roi = part_info.get("roi", [0, 0, 0, 0])
                roi_x = float(roi[0]) if len(roi) > 0 else 0.0
                roi_y = float(roi[1]) if len(roi) > 1 else 0.0
                roi_w = float(roi[2]) if len(roi) > 2 else 0.0
                roi_h = float(roi[3]) if len(roi) > 3 else 0.0
                transform = Transform(
                    x=roi_x,
                    y=roi_y,
                    rotation=0.0,
                    scale=1.0,
                )

                # Get z_index
                z_index = int(part_info.get("z_value", 0))

                parts[part_name] = PartData(
                    name=part_name,
                    texture_path=image_path,
                    mask_path=mask_path,
                    anchor_joint=anchor_joint,
                    transform=transform,
                    z_index=z_index,
                    roi=(roi_x, roi_y, roi_w, roi_h),
                    fill_color=str(part_info.get("fill_color", "rgba(128,128,128,0.5)")),
                    fixed=bool(part_info.get("fixed", False)),
                    opacity=float(part_info.get("opacity", 1.0)),
                    group=part_info.get("group"),
                    original_svg_path=part_info.get("original_svg_path"),
                    enhanced_svg_path=part_info.get("enhanced_svg_path"),
                    effective_bbox_offset_x=float(part_info.get("effective_bbox_offset_x", 0.0)),
                    effective_bbox_offset_y=float(part_info.get("effective_bbox_offset_y", 0.0)),
                    show_anchor=bool(part_info.get("show_anchor", False)),
                    local_pivot_offset=(
                        tuple(part_info["local_pivot_offset"])
                        if isinstance(part_info.get("local_pivot_offset"), list | tuple)
                        and len(part_info["local_pivot_offset"]) >= 2
                        else None
                    ),
                )

            except Exception as e:
                logger.warning(f"Error transforming part '{part_name}': {e}")
                continue

        return parts

    def _transform_skeleton_data(self, skeleton_data: dict) -> SkeletonData | None:
        """
        Transform char_cfg.yaml skeleton format to domain SkeletonData.

        Args:
            skeleton_data: Raw skeleton dict with 'skeleton' list

        Returns:
            SkeletonData or None if invalid
        """
        if not skeleton_data:
            return None

        raw_skeleton = skeleton_data.get("skeleton", [])
        if not raw_skeleton:
            return None

        joints: dict[str, JointData] = {}
        bones: list[BoneData] = []
        root_joint = ""

        # Build joint map from skeleton hierarchy
        for entry in raw_skeleton:
            joint_name = entry.get("name", "")
            loc = entry.get("loc", [0, 0])
            parent = entry.get("parent")

            if not joint_name:
                continue

            # Create joint
            joints[joint_name] = JointData(
                id=joint_name,
                position=Point(x=float(loc[0]), y=float(loc[1])),
                name=joint_name,
                parent=parent,
                is_locked=entry.get("is_locked", False),
                bend_direction=entry.get("bend_direction", 1.0),
            )

            # Track root (no parent)
            if parent is None:
                root_joint = joint_name

            # Create bone if has parent
            if parent:
                bones.append(BoneData(from_joint=parent, to_joint=joint_name))

        if not joints:
            return None

        return SkeletonData(
            joints=joints,
            bones=tuple(bones),
            root_joint=root_joint,
        )
