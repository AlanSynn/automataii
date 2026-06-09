"""
Manual Segmentation Handler - Manual segmentation workflow and part generation.

Extracted from ImageProcessingTab. Handles manual segmentation editor,
result application, and part generation from segmentation masks.

Design Pattern: Handler (processes segmentation workflow)
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QMessageBox

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget

    from automataii.presentation.qt.models import PartInfo


class ManualSegmentationHandler(QObject):
    """
    Handles manual segmentation workflow for image processing.

    Responsibilities:
    - Open manual segmentation editor
    - Apply segmentation results
    - Generate parts from manual segmentation masks
    - Extract part info from segmentation masks

    Signals:
        segmentation_completed: Emitted when segmentation is complete (parts_info dict)
        segmentation_cancelled: Emitted when user cancels segmentation
    """

    segmentation_completed = pyqtSignal(dict)
    segmentation_cancelled = pyqtSignal()

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        """
        Initialize manual segmentation handler.

        Args:
            parent: Parent widget for dialogs
        """
        super().__init__(parent)
        self._parent_widget = parent

        # State
        self._input_image_path: str | None = None
        self._character_dir: str | None = None
        self._current_annotation_results: dict | None = None

        # Callbacks
        self._get_main_window: Callable[[], Any] = lambda: None
        self._update_button_states: Callable[[], None] = lambda: None

    def configure(
        self,
        input_image_path: str | None,
        character_dir: str | None,
        current_annotation_results: dict | None,
    ) -> None:
        """Configure with current processing state."""
        self._input_image_path = input_image_path
        self._character_dir = character_dir
        self._current_annotation_results = current_annotation_results

    def configure_callbacks(
        self,
        get_main_window: Callable[[], Any],
        update_button_states: Callable[[], None],
    ) -> None:
        """Configure callback functions."""
        self._get_main_window = get_main_window
        self._update_button_states = update_button_states

    def open_manual_segmentation_editor(self) -> None:
        """
        Open manual segmentation editor for interactive boundary definition.

        Requires an image to be loaded first.
        """
        if not self._input_image_path:
            QMessageBox.warning(
                self._parent_widget,
                "No Image",
                "Please load an image first before using manual segmentation.",
            )
            return

        try:
            from automataii.presentation.qt.interactive_segmentation_editor import (
                InteractiveSegmentationEditor,
            )

            editor = InteractiveSegmentationEditor(
                image_path=self._input_image_path,
                char_dir=self._character_dir,
                parent=self._parent_widget,
            )

            # Connect result signal
            editor.segmentation_complete.connect(self._apply_manual_segmentation_results)

            editor.show()

            main_window = self._get_main_window()
            if main_window:
                main_window.statusBar().showMessage(
                    "Manual segmentation editor opened. Click to define body part boundaries."
                )

        except ImportError as e:
            QMessageBox.critical(
                self._parent_widget,
                "Import Error",
                f"Could not load segmentation editor: {e}",
            )
        except Exception as e:
            QMessageBox.critical(
                self._parent_widget,
                "Error",
                f"Could not open segmentation editor: {e}",
            )

    def _apply_manual_segmentation_results(self, results: dict) -> None:
        """
        Apply results from manual segmentation editor.

        Args:
            results: Segmentation results containing masks and boundaries
        """
        if not results:
            logging.info("ManualSegmentationHandler: No results from segmentation editor")
            self.segmentation_cancelled.emit()
            return

        try:
            logging.info(f"ManualSegmentationHandler: Applying results: {list(results.keys())}")

            # Generate parts from the segmentation results
            parts_info = self._generate_parts_from_manual_segmentation(results)

            if parts_info:
                self.segmentation_completed.emit(parts_info)
                self._update_button_states()

                main_window = self._get_main_window()
                if main_window:
                    main_window.statusBar().showMessage(
                        f"Manual segmentation applied: {len(parts_info)} parts defined"
                    )
            else:
                QMessageBox.warning(
                    self._parent_widget,
                    "No Parts",
                    "No parts were generated from the segmentation.",
                )

        except Exception as e:
            logging.error(f"ManualSegmentationHandler: Error applying results: {e}")
            QMessageBox.critical(
                self._parent_widget,
                "Apply Error",
                f"Could not apply segmentation results: {e}",
            )

    def _generate_parts_from_manual_segmentation(
        self, segmentation_results: dict
    ) -> dict[str, PartInfo]:
        """
        Generate part info from manual segmentation masks.

        Args:
            segmentation_results: Dict with part names as keys, mask data as values

        Returns:
            Dict mapping part names to PartInfo objects

        Time Complexity: O(p * m) where p = parts, m = mask pixels
        """

        parts_info: dict[str, PartInfo] = {}

        for part_name, part_data in segmentation_results.items():
            if not isinstance(part_data, dict):
                continue

            try:
                part_info = self._extract_part_info_from_mask(part_name, part_data)
                if part_info:
                    parts_info[part_name] = part_info
            except Exception as e:
                logging.warning(f"ManualSegmentationHandler: Failed to extract {part_name}: {e}")

        return parts_info

    def _extract_part_info_from_mask(self, part_name: str, mask_data: dict) -> PartInfo | None:
        """
        Extract PartInfo from segmentation mask data.

        Args:
            part_name: Name of the body part
            mask_data: Mask data including boundary points and centroid

        Returns:
            PartInfo object or None if extraction fails
        """
        from automataii.presentation.qt.models import PartInfo

        try:
            # Extract boundary and centroid from mask data
            boundary = mask_data.get("boundary", [])
            centroid = mask_data.get("centroid", (0, 0))
            bounding_box = mask_data.get("bounding_box", (0, 0, 100, 100))

            if not boundary:
                return None

            # Calculate anchor point (typically centroid)
            anchor_x, anchor_y = centroid

            # Create PartInfo
            part_info = PartInfo(
                name=part_name,
                texture_path=mask_data.get("texture_path", ""),
                mask_path=mask_data.get("mask_path", ""),
                bounding_box=bounding_box,
                anchor=(anchor_x, anchor_y),
                anchor_joint_id=mask_data.get("anchor_joint_id"),
            )

            return part_info

        except Exception as e:
            logging.error(f"ManualSegmentationHandler: Error extracting {part_name}: {e}")
            return None
