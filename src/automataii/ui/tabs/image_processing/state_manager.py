# src/automataii/ui/tabs/image_processing/state_manager.py

from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal

from automataii.domain.animation.image_to_annotations import AnnotationResults


class ImageProcessingStateManager(QObject):
    """
    Manages all state for the Image Processing tab.
    Emits signals when state changes to update UI and scene.
    """

    # Signals
    state_changed = pyqtSignal()
    image_path_changed = pyqtSignal(str)  # Specific signal for image loading
    skeleton_data_changed = pyqtSignal(dict)  # Specific signal for skeleton updates
    processing_state_changed = pyqtSignal(bool)  # For progress indicators

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        # File/Path State
        self.input_image_path: str | None = None
        self.character_dir: str | None = None
        self.current_temp_char_dir: str | None = None
        self.current_parts_info_path: str | None = None

        # Processing State
        self.current_annotation_results: AnnotationResults | None = None
        self.skeleton_data: dict | None = None

        # UI State
        self.is_editing_skeleton: bool = False
        self.processing_in_progress: bool = False
        self.active_camera_dialogs: list = []

        # Button states
        self.buttons_enabled: dict[str, bool] = {
            "process": False,
            "edit_skeleton": False,
            "save_skeleton": False,
            "generate_parts": False,
            "extend_skeleton": False,
            "lock_joints": False,
        }

    def set_input_image_path(self, path: str | None) -> None:
        """Set the input image path and emit appropriate signals."""
        if self.input_image_path != path:
            self.input_image_path = path
            self.image_path_changed.emit(path if path else "")
            self.update_button_states()
            self.state_changed.emit()

    def set_skeleton_data(self, skeleton_data: dict | None) -> None:
        """Set skeleton data and emit appropriate signals."""
        self.skeleton_data = skeleton_data
        if skeleton_data:
            self.skeleton_data_changed.emit(skeleton_data)
        self.update_button_states()
        self.state_changed.emit()

    def set_annotation_results(self, results: AnnotationResults | None) -> None:
        """Set annotation results from image processing."""
        self.current_annotation_results = results
        self.state_changed.emit()

    def set_character_dir(self, path: str | None) -> None:
        """Set the character directory path."""
        self.character_dir = path
        self.state_changed.emit()

    def set_temp_char_dir(self, path: str | None) -> None:
        """Set the temporary character directory path."""
        self.current_temp_char_dir = path
        self.state_changed.emit()

    def set_parts_info_path(self, path: str | None) -> None:
        """Set the parts info JSON path."""
        self.current_parts_info_path = path
        self.state_changed.emit()

    def set_editing_skeleton(self, editing: bool) -> None:
        """Set skeleton editing mode."""
        if self.is_editing_skeleton != editing:
            self.is_editing_skeleton = editing
            self.state_changed.emit()

    def set_processing_in_progress(self, processing: bool) -> None:
        """Set processing state."""
        if self.processing_in_progress != processing:
            self.processing_in_progress = processing
            self.processing_state_changed.emit(processing)
            self.state_changed.emit()

    def add_camera_dialog(self, dialog: Any) -> None:
        """Add a camera dialog to track."""
        self.active_camera_dialogs.append(dialog)
        self.state_changed.emit()

    def remove_camera_dialog(self, dialog: Any) -> None:
        """Remove a camera dialog from tracking."""
        if dialog in self.active_camera_dialogs:
            self.active_camera_dialogs.remove(dialog)
            self.state_changed.emit()

    def update_button_states(self) -> None:
        """Update enabled states for all buttons based on current state."""
        # Process button: enabled when image is loaded
        self.buttons_enabled["process"] = bool(self.input_image_path)

        # Skeleton-related buttons: enabled when skeleton data exists
        has_skeleton = bool(self.skeleton_data)
        self.buttons_enabled["edit_skeleton"] = has_skeleton
        self.buttons_enabled["save_skeleton"] = has_skeleton
        self.buttons_enabled["generate_parts"] = has_skeleton
        self.buttons_enabled["extend_skeleton"] = has_skeleton
        self.buttons_enabled["lock_joints"] = has_skeleton

    def clear_all(self) -> None:
        """Clear all state data."""
        self.input_image_path = None
        self.character_dir = None
        self.current_temp_char_dir = None
        self.current_parts_info_path = None
        self.current_annotation_results = None
        self.skeleton_data = None
        self.is_editing_skeleton = False
        self.processing_in_progress = False
        self.active_camera_dialogs.clear()
        self.update_button_states()
        self.state_changed.emit()

    def on_parts_loaded_in_editor(self, loaded: bool) -> None:
        """React to parts being loaded in editor tab."""
        # This might affect button states or other UI elements
        self.state_changed.emit()

    def refresh_display(self) -> None:
        """Refresh the display state - placeholder for compatibility."""
        # This method is called during tab activation
        # Emit state changed to trigger any necessary UI updates
        self.state_changed.emit()
