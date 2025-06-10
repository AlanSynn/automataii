"""Part list widget component."""

import logging
from typing import Dict, Optional, List, Any

from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QAbstractItemView
from PyQt6.QtCore import pyqtSignal, Qt


class PartListWidget(QListWidget):
    """Reusable part list widget.

    This component displays a list of parts and handles selection.
    """

    # Signals
    part_selected = pyqtSignal(str)  # part_name
    part_deselected = pyqtSignal()

    # Display name mapping for common parts
    DISPLAY_NAMES = {
        "head": "Head",
        "left_arm_lower": "Left Arm",
        "right_arm_lower": "Right Arm",
        "left_leg_lower": "Left Leg",
        "right_leg_lower": "Right Leg",
        "torso": "Torso",
        "left_hand": "Left Hand",
        "right_hand": "Right Hand",
        "left_foot": "Left Foot",
        "right_foot": "Right Foot"
    }

    def __init__(self, parent=None):
        super().__init__(parent)

        self._parts_info: Dict[str, Any] = {}
        self._display_order = [
            "head",
            "torso",
            "left_arm_lower",
            "right_arm_lower",
            "left_hand",
            "right_hand",
            "left_leg_lower",
            "right_leg_lower",
            "left_foot",
            "right_foot"
        ]

        self._init_ui()
        self._connect_signals()

    def _init_ui(self) -> None:
        """Initialize UI settings."""
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setToolTip("Select a part to edit")

        # Apply styling
        self.setStyleSheet("""
            QListWidget {
                border: 1px solid #d0d7de;
                border-radius: 4px;
                background-color: white;
                outline: none;
            }
            QListWidget::item {
                padding: 4px;
                border-bottom: 1px solid #f0f0f0;
            }
            QListWidget::item:selected {
                background-color: #fd7e14;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #f6f8fa;
            }
        """)

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self.currentItemChanged.connect(self._on_selection_changed)

    def load_parts(self, parts_info: Dict[str, Any]) -> None:
        """Load parts into the list.

        Args:
            parts_info: Dictionary mapping part names to part information
        """
        self.clear()
        self._parts_info = parts_info.copy()

        if not parts_info:
            logging.info("PartListWidget: No parts to load")
            return

        # Add parts in preferred order
        added_parts = set()

        # First add ordered parts
        for part_name in self._display_order:
            if part_name in parts_info:
                self._add_part_item(part_name, parts_info[part_name])
                added_parts.add(part_name)

        # Then add any remaining parts
        for part_name, part_info in parts_info.items():
            if part_name not in added_parts:
                self._add_part_item(part_name, part_info)

        logging.info(f"PartListWidget: Loaded {self.count()} parts")

    def _add_part_item(self, part_name: str, part_info: Any) -> None:
        """Add a part item to the list.

        Args:
            part_name: System name of the part
            part_info: Part information
        """
        # Get display name
        display_name = self.DISPLAY_NAMES.get(part_name, part_name.replace('_', ' ').title())

        # Add motion path indicator if available
        if hasattr(part_info, 'has_motion_path') and part_info.has_motion_path:
            display_name += " ✓"

        # Create item
        item = QListWidgetItem(display_name)
        item.setData(Qt.ItemDataRole.UserRole, part_name)

        # Add tooltip with more info if available
        tooltip_parts = [f"Part: {part_name}"]
        if hasattr(part_info, 'z_value'):
            tooltip_parts.append(f"Z-Order: {part_info.z_value}")
        if hasattr(part_info, 'fixed'):
            tooltip_parts.append(f"Fixed: {'Yes' if part_info.fixed else 'No'}")

        item.setToolTip('\n'.join(tooltip_parts))

        self.addItem(item)

    def select_part(self, part_name: str) -> bool:
        """Select a part by name.

        Args:
            part_name: Name of the part to select

        Returns:
            True if part was found and selected
        """
        for i in range(self.count()):
            item = self.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == part_name:
                self.setCurrentItem(item)
                return True

        return False

    def get_selected_part(self) -> Optional[str]:
        """Get the currently selected part name.

        Returns:
            Part name or None if no selection
        """
        current_item = self.currentItem()
        if current_item:
            return current_item.data(Qt.ItemDataRole.UserRole)
        return None

    def update_part_status(self, part_name: str, has_path: bool) -> None:
        """Update the status indicator for a part.

        Args:
            part_name: Name of the part
            has_path: Whether the part has a motion path
        """
        for i in range(self.count()):
            item = self.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == part_name:
                display_name = self.DISPLAY_NAMES.get(part_name, part_name.replace('_', ' ').title())
                if has_path:
                    display_name += " ✓"
                item.setText(display_name)
                break

    def clear_selection(self) -> None:
        """Clear the current selection."""
        self.clearSelection()
        self.setCurrentItem(None)

    def _on_selection_changed(self, current: Optional[QListWidgetItem], previous: Optional[QListWidgetItem]) -> None:
        """Handle selection change.

        Args:
            current: Current item
            previous: Previous item
        """
        if current:
            part_name = current.data(Qt.ItemDataRole.UserRole)
            if part_name:
                self.part_selected.emit(part_name)
                logging.debug(f"PartListWidget: Selected part '{part_name}'")
        else:
            self.part_deselected.emit()
            logging.debug("PartListWidget: Part deselected")

    def set_parts_enabled(self, enabled: bool) -> None:
        """Enable or disable the part list.

        Args:
            enabled: Whether to enable the list
        """
        self.setEnabled(enabled)

    def filter_parts(self, filter_text: str) -> None:
        """Filter displayed parts by text.

        Args:
            filter_text: Text to filter by
        """
        filter_lower = filter_text.lower()

        for i in range(self.count()):
            item = self.item(i)
            if item:
                part_name = item.data(Qt.ItemDataRole.UserRole)
                display_text = item.text().lower()

                # Show if filter matches part name or display text
                should_show = (
                    filter_lower in part_name.lower() or
                    filter_lower in display_text
                )

                item.setHidden(not should_show)