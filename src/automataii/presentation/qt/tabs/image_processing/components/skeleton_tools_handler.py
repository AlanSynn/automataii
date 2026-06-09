"""
Skeleton Tools Handler - Skeleton manipulation operations.

Extracted from ImageProcessingTab. Handles skeleton extension and
joint locking operations.

Design Pattern: Handler (skeleton manipulation workflow)
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QMessageBox

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget


class SkeletonToolsHandler(QObject):
    """
    Handles skeleton manipulation tools for image processing.

    Responsibilities:
    - Extend skeleton bone lengths
    - Lock/unlock individual joints
    - Update view after skeleton modifications

    Signals:
        skeleton_modified: Emitted when skeleton is modified (skeleton_data dict)
    """

    skeleton_modified = pyqtSignal(dict)

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        """
        Initialize skeleton tools handler.

        Args:
            parent: Parent widget for dialogs
        """
        super().__init__(parent)
        self._parent_widget = parent
        self._logger = logging.getLogger(__name__)

        # Callbacks
        self._get_skeleton_manager: Callable[[], Any] = lambda: None
        self._get_skeleton_data: Callable[[], dict | None] = lambda: None
        self._update_view: Callable[[dict], None] = lambda d: None
        self._get_status_bar: Callable[[], Any] = lambda: None

    def configure_callbacks(
        self,
        get_skeleton_manager: Callable[[], Any],
        get_skeleton_data: Callable[[], dict | None],
        update_view: Callable[[dict], None],
        get_status_bar: Callable[[], Any],
    ) -> None:
        """Configure callback functions."""
        self._get_skeleton_manager = get_skeleton_manager
        self._get_skeleton_data = get_skeleton_data
        self._update_view = update_view
        self._get_status_bar = get_status_bar

    def extend_skeleton(self, factor: float = 1.1) -> bool:
        """
        Extend skeleton bone lengths by a factor.

        Args:
            factor: Extension factor (1.1 = 10% increase)

        Returns:
            True if extension was successful
        """
        skeleton_manager = self._get_skeleton_manager()
        if not skeleton_manager:
            QMessageBox.warning(
                self._parent_widget,
                "Extend Skeleton",
                "No skeleton manager available.",
            )
            return False

        if not skeleton_manager.standardized_model:
            QMessageBox.warning(
                self._parent_widget,
                "Extend Skeleton",
                "No skeleton loaded. Please process an image or load a skeleton first.",
            )
            return False

        # Confirm action with user
        percent = int((factor - 1.0) * 100)
        reply = QMessageBox.question(
            self._parent_widget,
            "Extend Skeleton",
            f"This will increase all skeleton bone lengths by {percent}%. "
            "This action cannot be undone. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return False

        if skeleton_manager.extend_skeleton_lengths(factor):
            # Update view with modified skeleton
            updated_skeleton = skeleton_manager.standardized_model.model_dump()
            self._update_view(updated_skeleton)
            self.skeleton_modified.emit(updated_skeleton)

            QMessageBox.information(
                self._parent_widget,
                "Extend Skeleton",
                f"Skeleton lengths extended by {percent}% successfully.",
            )

            status_bar = self._get_status_bar()
            if status_bar:
                status_bar.showMessage(f"Skeleton extended by {percent}%", 3000)

            return True
        else:
            QMessageBox.critical(
                self._parent_widget,
                "Extend Skeleton",
                "Failed to extend skeleton lengths.",
            )
            return False

    def show_lock_joints_dialog(self) -> bool:
        """
        Show dialog for locking/unlocking specific joints.

        Returns:
            True if changes were applied
        """
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import (
            QDialog,
            QDialogButtonBox,
            QLabel,
            QListWidget,
            QListWidgetItem,
            QVBoxLayout,
        )

        skeleton_manager = self._get_skeleton_manager()
        if not skeleton_manager:
            QMessageBox.warning(
                self._parent_widget,
                "Lock/Unlock Joints",
                "No skeleton manager available.",
            )
            return False

        if not skeleton_manager.standardized_model:
            QMessageBox.warning(
                self._parent_widget,
                "Lock/Unlock Joints",
                "No skeleton loaded. Please process an image or load a skeleton first.",
            )
            return False

        dialog = QDialog(self._parent_widget)
        dialog.setWindowTitle("Lock/Unlock Joints")
        dialog.setModal(True)
        dialog.resize(300, 400)

        layout = QVBoxLayout(dialog)

        label = QLabel("Check joints to lock them during IK solving:")
        layout.addWidget(label)

        list_widget = QListWidget()

        skeleton_model = skeleton_manager.standardized_model
        for joint_id, joint in skeleton_model.joints.items():
            item = QListWidgetItem(f"{joint.name} ({joint_id})")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if joint.is_locked else Qt.CheckState.Unchecked
            )
            item.setData(Qt.ItemDataRole.UserRole, joint_id)
            list_widget.addItem(item)

        layout.addWidget(list_widget)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(button_box)

        changes_applied = False

        def accept_changes() -> None:
            nonlocal changes_applied
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                joint_id = item.data(Qt.ItemDataRole.UserRole)
                is_locked = item.checkState() == Qt.CheckState.Checked
                skeleton_manager.lock_joint(joint_id, is_locked)

            # Update view with modified skeleton
            updated_skeleton = skeleton_manager.standardized_model.model_dump()
            self._update_view(updated_skeleton)
            self.skeleton_modified.emit(updated_skeleton)

            changes_applied = True
            dialog.accept()

        button_box.accepted.connect(accept_changes)
        button_box.rejected.connect(dialog.reject)

        dialog.exec()
        return changes_applied
