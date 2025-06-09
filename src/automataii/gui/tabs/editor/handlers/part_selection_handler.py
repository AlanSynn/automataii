"""Handler for part selection operations."""

import logging
from typing import Optional, Callable

from PyQt6.QtCore import QObject, pyqtSignal

from automataii.gui.tabs.editor.state import EditorState, PartState
from automataii.events import event_bus, PartSelectedEvent


class PartSelectionHandler(QObject):
    """Handles part selection logic."""

    # Signals
    part_selected = pyqtSignal(str)  # part_name
    part_deselected = pyqtSignal()
    selection_changed = pyqtSignal()

    def __init__(self, state: EditorState):
        super().__init__()
        self._state = state
        self._selection_callbacks: list[Callable[[Optional[str]], None]] = []

        logging.debug("PartSelectionHandler initialized")

    def select_part(self, part_name: Optional[str]) -> bool:
        """Select a part by name.

        Args:
            part_name: Name of part to select, or None to deselect

        Returns:
            True if selection changed
        """
        previous_selection = self._state.selected_part_name

        # Check if part exists
        if part_name and part_name not in self._state.parts:
            logging.warning(f"PartSelectionHandler: Part '{part_name}' not found")
            return False

        # No change
        if previous_selection == part_name:
            return False

        # Update state
        self._state.select_part(part_name)

        # Emit signals
        if part_name:
            self.part_selected.emit(part_name)
            logging.info(f"PartSelectionHandler: Selected part '{part_name}'")
        else:
            self.part_deselected.emit()
            logging.info("PartSelectionHandler: Part deselected")

        self.selection_changed.emit()

        # Publish event
        event = PartSelectedEvent(
            part_name=part_name,
            previous_part=previous_selection,
            source="part_selection_handler"
        )
        event_bus.publish(event)

        # Call callbacks
        self._notify_callbacks(part_name)

        return True

    def get_selected_part(self) -> Optional[str]:
        """Get currently selected part name."""
        return self._state.selected_part_name

    def get_selected_part_state(self) -> Optional[PartState]:
        """Get state of selected part."""
        return self._state.get_selected_part()

    def is_part_selected(self, part_name: str) -> bool:
        """Check if a specific part is selected."""
        return self._state.selected_part_name == part_name

    def clear_selection(self) -> None:
        """Clear current selection."""
        self.select_part(None)

    def add_selection_callback(self, callback: Callable[[Optional[str]], None]) -> None:
        """Add callback for selection changes.

        Args:
            callback: Function to call with selected part name
        """
        if callback not in self._selection_callbacks:
            self._selection_callbacks.append(callback)

    def remove_selection_callback(self, callback: Callable[[Optional[str]], None]) -> None:
        """Remove selection callback."""
        if callback in self._selection_callbacks:
            self._selection_callbacks.remove(callback)

    def _notify_callbacks(self, part_name: Optional[str]) -> None:
        """Notify all callbacks of selection change."""
        for callback in self._selection_callbacks:
            try:
                callback(part_name)
            except Exception as e:
                logging.error(f"PartSelectionHandler: Callback error - {e}")