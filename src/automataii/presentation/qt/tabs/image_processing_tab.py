import logging
import os
import re
import tempfile
import time
import uuid
from pathlib import Path

import cv2
import numpy as np
import yaml
from PyQt6.QtCore import QSettings, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QGraphicsScene,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from automataii.domain.animation.body_parts_extractor import BodyPartsExtractor
from automataii.domain.animation.image_to_annotations import (
    IMAGE_TEMP_SESSION_MARKER,
    AnnotationResults,
    image_to_annotations,
)
from automataii.domain.animation.part_definitions import BODY_PARTS
from automataii.infrastructure.telemetry import telemetry_span
from automataii.presentation.qt.dialogs.camera_dialog import CameraDialog
from automataii.presentation.qt.image_view import ImageProcessingView
from automataii.presentation.qt.shared import blocked_signals
from automataii.presentation.qt.tabs.image_processing.components import SkeletonToolsHandler
from automataii.presentation.qt.widgets.common.styles import StyleFactory
from automataii.presentation.qt.widgets.processing_steps_group import ProcessingStepsGroup
from automataii.utils.paths import get_session_temp_dir, resolve_path


class ImageProcessingTab(QWidget):
    parts_generated = pyqtSignal(dict, str)
    skeleton_updated = pyqtSignal(dict)
    request_editor_tab_switch = pyqtSignal()
    character_preset_loaded = pyqtSignal(str)

    def __init__(self, main_window, parent=None, editing_mode: bool = False):
        super().__init__(parent)
        self.main_window = main_window
        self.editing_mode = editing_mode

        self.input_image_path: str | None = None
        self.character_dir: str | None = None
        self.current_temp_char_dir: str | None = None
        self.current_annotation_results: AnnotationResults | None = None
        self.skeleton_data: dict | None = None
        self._manual_part_metadata: dict | None = None
        self.active_camera_dialogs: list = []
        self._input_source: str | None = None
        self.auto_assign_on_input: bool = False
        self.assign_character_btn: QPushButton | None = None
        self.sample_image_buttons: list[QPushButton] = []
        self._settings = QSettings("MotionSmith", "CharacterOutput")
        saved_output_dir = self._settings.value("output_dir", "", str)
        self.output_dir: str | None = saved_output_dir or None
        self._output_dir_user_selected: bool = bool(saved_output_dir)
        self.output_location_label: QLabel | None = None
        self.choose_output_dir_btn: QPushButton | None = None

        self.image_proc_scene = QGraphicsScene(self)
        self.image_proc_view = ImageProcessingView(self.image_proc_scene, self)

        self.processing_steps_group = ProcessingStepsGroup()
        self.processing_steps_group.setVisible(False)

        # Initialize extracted components
        self._skeleton_tools = SkeletonToolsHandler(parent=self)
        self._skeleton_tools.configure_callbacks(
            get_skeleton_manager=lambda: self.main_window.skeleton_manager
            if self.main_window
            else None,
            get_skeleton_data=lambda: self.skeleton_data,
            update_view=self._update_skeleton_view,
            get_status_bar=lambda: self.main_window.statusBar() if self.main_window else None,
        )
        self._skeleton_tools.skeleton_modified.connect(self._on_skeleton_modified)

        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        control_panel = QWidget()
        control_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        panel_layout = QVBoxLayout(control_panel)
        panel_layout.setContentsMargins(5, 10, 5, 10)
        panel_layout.setSpacing(10)

        input_group = QGroupBox("Input Drawing")
        input_layout = QVBoxLayout(input_group)
        input_layout.setSpacing(10)
        self.load_image_btn = QPushButton("Load Image File")
        self.capture_image_btn = QPushButton("Capture Camera")
        sample_label = QLabel("Example Character")
        sample_label.setStyleSheet("font-weight: bold; color: #495057;")
        input_layout.addWidget(sample_label)
        self.sample_image_buttons = []
        for sample_path in self._sample_image_paths(limit=2):
            button = QPushButton(f"Use {sample_path.stem.title()} Example")
            button.setToolTip(f"Load example character image: {sample_path.name}")
            button.clicked.connect(
                lambda _checked=False, path=sample_path: self._load_sample_image(path)
            )
            input_layout.addWidget(button)
            self.sample_image_buttons.append(button)
        input_layout.addWidget(self.load_image_btn)
        input_layout.addWidget(self.capture_image_btn)
        panel_layout.addWidget(input_group)

        panel_layout.addWidget(self.processing_steps_group)

        editing_group = QGroupBox("Recognition Editing")
        editing_layout = QVBoxLayout(editing_group)
        editing_layout.setSpacing(10)

        self.manual_segmentation_btn = QPushButton("Edit Parts / Skeleton / Boxes")
        self.manual_segmentation_btn.setToolTip(
            "Open the manual editor to redefine body-part boundaries, select joints, "
            "and create rectangular boxes from selected joints."
        )
        self.manual_segmentation_btn.clicked.connect(self.open_manual_segmentation_editor)
        self.manual_segmentation_btn.setEnabled(False)  # Enabled when image is loaded
        editing_layout.addWidget(self.manual_segmentation_btn)

        self.edit_skeleton_btn = QPushButton("Edit Skeleton Joints")
        self.edit_skeleton_btn.setToolTip("Enable direct dragging of detected skeleton joints.")
        self.edit_skeleton_btn.clicked.connect(self.edit_skeleton)
        self.edit_skeleton_btn.setEnabled(False)
        editing_layout.addWidget(self.edit_skeleton_btn)

        self.save_skeleton_btn = QPushButton("Save Skeleton")
        self.save_skeleton_btn.setToolTip("Save the current edited skeleton to char_cfg.yaml.")
        self.save_skeleton_btn.clicked.connect(self.save_skeleton)
        self.save_skeleton_btn.setEnabled(False)
        editing_layout.addWidget(self.save_skeleton_btn)

        panel_layout.addWidget(editing_group)

        view_controls_group = QGroupBox("View Controls")
        view_controls_group.setStyleSheet(StyleFactory.group_box_style())
        view_controls_layout = QVBoxLayout(view_controls_group)

        zoom_controls_layout = QHBoxLayout()
        zoom_controls_layout.setSpacing(6)

        # Use shared StyleFactory for consistent zoom button styling
        zoom_style = StyleFactory.zoom_button_style()

        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.setToolTip("Zoom In")
        self.zoom_in_btn.setStyleSheet(zoom_style)
        zoom_controls_layout.addWidget(self.zoom_in_btn)

        self.zoom_out_btn = QPushButton("−")
        self.zoom_out_btn.setToolTip("Zoom Out")
        self.zoom_out_btn.setStyleSheet(zoom_style)
        zoom_controls_layout.addWidget(self.zoom_out_btn)

        self.zoom_fit_btn = QPushButton("⌖")
        self.zoom_fit_btn.setToolTip("Zoom to Fit")
        self.zoom_fit_btn.setStyleSheet(zoom_style)
        zoom_controls_layout.addWidget(self.zoom_fit_btn)

        self.zoom_reset_btn = QPushButton("1:1")
        self.zoom_reset_btn.setToolTip("Reset Zoom (100%)")
        self.zoom_reset_btn.setStyleSheet(zoom_style)
        self.zoom_reset_btn.setMinimumWidth(35)
        zoom_controls_layout.addWidget(self.zoom_reset_btn)

        view_controls_layout.addLayout(zoom_controls_layout)
        panel_layout.addWidget(view_controls_group)

        # Character replacement group (manual trigger only)
        char_group = QGroupBox("Character Setup")
        char_layout = QVBoxLayout(char_group)
        self.assign_character_btn = QPushButton("Replace Character")
        self.assign_character_btn.setToolTip(
            "Replace the current dummy character with a processed user image"
        )
        self.assign_character_btn.setEnabled(False)
        self.assign_character_btn.clicked.connect(self._assign_character_from_image)
        char_layout.addWidget(self.assign_character_btn)
        panel_layout.addWidget(char_group)

        output_group = QGroupBox("Download / Output Location")
        output_layout = QVBoxLayout(output_group)
        self.output_location_label = QLabel()
        self.output_location_label.setWordWrap(True)
        self.output_location_label.setObjectName("characterOutputLocationLabel")
        self.choose_output_dir_btn = QPushButton("Choose Save Folder…")
        self.choose_output_dir_btn.setToolTip(
            "Choose where generated character parts and parts_info.json will be saved"
        )
        self.choose_output_dir_btn.clicked.connect(self._choose_output_folder)
        output_layout.addWidget(self.output_location_label)
        output_layout.addWidget(self.choose_output_dir_btn)
        panel_layout.addWidget(output_group)
        self._update_output_location_label()

        panel_layout.addStretch()

        # Right View Area (ImageProcessingView is owned by MainWindow but displayed here)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(5, 5, 5, 5)
        right_layout.setSpacing(5)

        zoom_toolbar = QWidget()
        zoom_layout = QHBoxLayout(zoom_toolbar)
        zoom_layout.setContentsMargins(10, 8, 10, 8)
        zoom_layout.setSpacing(8)
        zoom_layout.addStretch()

        self.image_zoom_combo = QComboBox()
        self.image_zoom_combo.setEditable(True)
        self.image_zoom_combo.setMinimumWidth(80)
        self.image_zoom_combo.setMaximumWidth(120)
        self.image_zoom_combo.setFixedHeight(28)
        self.image_zoom_combo.setStyleSheet(
            """
            QComboBox {
                border: 1px solid #d0d7de;
                border-radius: 6px;
                padding: 4px 4px;
                background-color: white;
                font-size: 12px;
            }
            QComboBox:hover {
                border-color: #586069;
            }
        """
        )
        zoom_levels = ["50%", "75%", "90%", "100%", "125%", "150%", "200%"]
        self.image_zoom_combo.addItems(zoom_levels)
        self.image_zoom_combo.setCurrentText("100%")
        self.image_zoom_combo.setToolTip("Zoom level")

        self.image_fit_btn = QPushButton("Fit")
        self.image_fit_btn.setMinimumWidth(45)
        self.image_fit_btn.setMaximumWidth(75)
        self.image_fit_btn.setFixedHeight(28)
        self.image_fit_btn.setStyleSheet(
            """
            QPushButton {
                border: 1px solid #d0d7de;
                border-radius: 4px;
                padding: 4px 4px;
                background-color: white;
                font-size: 13px;
                color: #24292f;
            }
            QPushButton:hover {
                background-color: #f6f8fa;
                border-color: #586069;
            }
            QPushButton:pressed {
                background-color: #e9ecef;
            }
        """
        )
        self.image_fit_btn.setToolTip("Zoom to fit all items")

        zoom_layout.addWidget(self.image_zoom_combo)
        zoom_layout.addWidget(self.image_fit_btn)

        # ImageProcessingView is managed by MainWindow, passed in __init__
        right_layout.addWidget(self.image_proc_view, 1)

        zoom_toolbar.setParent(right_panel)
        zoom_toolbar.setStyleSheet(
            """
            QWidget {
                background-color: rgba(248, 249, 250, 0.9);
                border: 1px solid rgba(208, 215, 222, 0.8);
                border-radius: 1px;
            }
        """
        )
        zoom_toolbar.show()

        def position_image_zoom_toolbar():
            if not right_panel.isVisible() or not zoom_toolbar.isVisible():
                return
            toolbar_width = zoom_toolbar.sizeHint().width()
            toolbar_height = zoom_toolbar.sizeHint().height()
            x = right_panel.width() - toolbar_width - 10  # Adjusted padding
            y = right_panel.height() - toolbar_height - 10  # Adjusted padding
            zoom_toolbar.setGeometry(x, y, toolbar_width, toolbar_height)

        original_show_event = right_panel.showEvent

        def new_show_event(event):
            original_show_event(event)
            position_image_zoom_toolbar()

        right_panel.showEvent = new_show_event

        original_resize_event = right_panel.resizeEvent

        def new_resize_event(event):
            original_resize_event(event)
            position_image_zoom_toolbar()

        right_panel.resizeEvent = new_resize_event

        # Ensure toolbar is repositioned initially if already visible
        if right_panel.isVisible():
            QApplication.instance().processEvents()  # Allow layout to settle
            position_image_zoom_toolbar()

        control_scroll = QScrollArea(self)
        control_scroll.setWidgetResizable(True)
        control_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        control_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        control_scroll.setMinimumWidth(220)
        control_scroll.setMaximumWidth(440)
        control_scroll.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        control_panel.setMinimumWidth(200)
        control_scroll.setWidget(control_panel)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setHandleWidth(8)
        splitter.setChildrenCollapsible(True)
        splitter.addWidget(control_scroll)
        splitter.addWidget(right_panel)
        splitter.setCollapsible(0, True)
        splitter.setCollapsible(1, False)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 900])

        layout.addWidget(splitter)
        self.setLayout(layout)

        self.load_image_btn.clicked.connect(self.load_input_image)
        self.capture_image_btn.clicked.connect(self.capture_image)
        self.processing_steps_group.processImageClicked.connect(self.process_image)
        self.processing_steps_group.editSkeletonClicked.connect(self.edit_skeleton)
        self.processing_steps_group.saveSkeletonClicked.connect(self.save_skeleton)
        self.processing_steps_group.generatePartsClicked.connect(self.create_parts_from_skeleton)
        self.processing_steps_group.extendSkeletonClicked.connect(self.extend_skeleton)
        self.processing_steps_group.lockJointsClicked.connect(self.show_lock_joints_dialog)

        self.image_zoom_combo.currentTextChanged.connect(self._handle_image_zoom_change)
        self.image_fit_btn.clicked.connect(self._handle_image_zoom_change_fit)

        self.zoom_in_btn.clicked.connect(lambda: self.image_proc_view.zoom(1))
        self.zoom_out_btn.clicked.connect(lambda: self.image_proc_view.zoom(-1))
        self.zoom_fit_btn.clicked.connect(self.image_proc_view.zoom_to_fit)
        self.zoom_reset_btn.clicked.connect(self.image_proc_view.reset_view)
        self.update_button_states()

    def _sample_image_paths(self, *, limit: int = 2) -> list[Path]:
        """Return bundled sample drawings for the sample-first character flow."""
        search_dirs: list[Path] = []
        for raw in ("examples", "src/examples", "resources/examples/raw"):
            try:
                candidate = Path(resolve_path(raw))
            except Exception:
                continue
            if candidate.exists() and candidate not in search_dirs:
                search_dirs.append(candidate)

        supported = {".png", ".jpg", ".jpeg", ".bmp"}
        samples: list[Path] = []
        seen: set[Path] = set()
        preferred_names = ("girl", "boy")
        for base in search_dirs:
            if not base.is_dir():
                continue
            files = [
                path
                for path in base.iterdir()
                if path.is_file() and path.suffix.lower() in supported
            ]
            files.sort(
                key=lambda path: (
                    preferred_names.index(path.stem.lower())
                    if path.stem.lower() in preferred_names
                    else len(preferred_names),
                    path.name.lower(),
                )
            )
            for path in files:
                resolved = path.resolve()
                if resolved in seen:
                    continue
                samples.append(path)
                seen.add(resolved)
                if len(samples) >= limit:
                    return samples
        return samples

    def _is_bundled_sample_path(self, image_path: str) -> bool:
        try:
            target = Path(image_path).resolve()
        except Exception:
            return False
        return any(target == sample.resolve() for sample in self._sample_image_paths())

    def _load_sample_image(self, image_path: Path) -> bool:
        """Load and auto-apply a bundled sample image from Character Selection."""
        path = str(image_path)
        if not image_path.exists():
            QMessageBox.warning(self, "Sample Missing", f"Could not find sample image:\n{path}")
            return False
        if not self.image_proc_view.load_image(path):
            QMessageBox.warning(self, "Load Error", f"Could not load sample image:\n{path}")
            return False
        self._on_input_ready(
            image_path=path,
            source="sample",
            status_prefix="Loaded sample image",
        )
        self._auto_apply_loaded_image_to_editor()
        return True

    def _default_output_root(self) -> Path:
        if self.input_image_path:
            return Path(self.input_image_path).expanduser().resolve().parent
        return Path.home()

    @staticmethod
    def _safe_output_name(raw_name: str) -> str:
        name = re.sub(r"[^A-Za-z0-9._-]+", "_", raw_name).strip("._-")
        return name or "character"

    def _suggested_output_folder(self) -> Path:
        source_name = Path(self.input_image_path).stem if self.input_image_path else "character"
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        return self._default_output_root() / f"{self._safe_output_name(source_name)}_{timestamp}"

    def _ensure_output_dir(self) -> Path | None:
        if self.output_dir:
            output_dir = Path(self.output_dir)
        else:
            suggested = self._suggested_output_folder()
            chosen = QFileDialog.getExistingDirectory(
                self,
                "Choose Save Folder for Generated Character Parts",
                str(suggested.parent),
            )
            if not chosen:
                self._update_output_location_label()
                return None
            output_dir = Path(chosen)
            self.output_dir = str(output_dir)
            self._output_dir_user_selected = True
            self._settings.setValue("output_dir", str(output_dir))
        output_dir.mkdir(parents=True, exist_ok=True)
        self._update_output_location_label()
        return output_dir

    def _choose_output_folder(self) -> None:
        initial = self.output_dir or str(self._suggested_output_folder().parent)
        chosen = QFileDialog.getExistingDirectory(self, "Choose Save Folder", initial)
        if not chosen:
            return
        self.output_dir = chosen
        self._output_dir_user_selected = True
        self._settings.setValue("output_dir", chosen)
        self._update_output_location_label()

    def _update_output_location_label(self) -> None:
        if self.output_location_label is None:
            return
        if self.output_dir:
            label = f"Will save generated parts to:\n{self.output_dir}"
        else:
            label = (
                "No save folder selected.\n"
                "Choose a folder when you generate parts or use Choose Save Folder…"
            )
        self.output_location_label.setText(label)

    def _infer_character_dir(self, image_path: str) -> str:
        potential_char_dir = os.path.dirname(image_path)
        if (
            os.path.exists(os.path.join(potential_char_dir, "character_data"))
            or os.path.exists(os.path.join(potential_char_dir, "output"))
            or os.path.exists(os.path.join(potential_char_dir, "parts_info.json"))
        ):
            return potential_char_dir
        if os.path.basename(potential_char_dir) in ["source_images", "input_images", "images"]:
            return os.path.dirname(potential_char_dir)
        return potential_char_dir

    def _on_input_ready(self, image_path: str, source: str, status_prefix: str) -> None:
        self.input_image_path = image_path
        self.character_dir = self._infer_character_dir(image_path)
        self._input_source = source
        self.current_annotation_results = None
        self.current_temp_char_dir = None
        self.skeleton_data = None
        self._manual_part_metadata = None
        if not self._output_dir_user_selected:
            self.output_dir = None
            self._update_output_location_label()
        if self.image_proc_view:
            self.image_proc_view.load_skeleton(None)
        if hasattr(self, "manual_segmentation_btn"):
            self.manual_segmentation_btn.setEnabled(True)
        # Keep detailed workflow controls hidden by default.
        # They can be re-enabled from Options (advanced processing toggle).
        self.processing_steps_group.setVisible(False)
        status_bar = self.main_window.statusBar() if self.main_window else None
        if status_bar:
            status_bar.showMessage(f"{status_prefix}: {os.path.basename(image_path)}")
        self.update_button_states()

    def _auto_apply_loaded_image_to_editor(self) -> bool:
        """Run processing + parts generation and handoff to editor in one flow."""
        self.process_image()
        if (
            not self.current_annotation_results
            or not self.current_temp_char_dir
            or not self.skeleton_data
        ):
            return False

        generated = self.create_parts_from_skeleton(show_success_dialog=False)
        return generated

    def load_input_image(self, *, auto_apply: bool = True):
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Load Input Image",
            self.character_dir or "",
            "Image Files (*.png *.jpg *.jpeg *.bmp)",
        )
        if not filepath:
            return
        if self.image_proc_view.load_image(filepath):
            self._on_input_ready(
                image_path=filepath,
                source="file",
                status_prefix="Loaded input image",
            )
            if auto_apply:
                self._auto_apply_loaded_image_to_editor()
        else:
            QMessageBox.warning(self, "Load Error", f"Could not load image: {filepath}")

    def open_manual_segmentation_editor(self):
        """Open interactive manual segmentation editor"""
        if not self.input_image_path:
            QMessageBox.warning(
                self, "No Image", "Please load an image first before opening the manual editor."
            )
            return

        try:
            from automataii.presentation.qt.interactive_segmentation_editor import (
                InteractiveSegmentationEditor,
            )

            # Create dialog
            editor_dialog = InteractiveSegmentationEditor(
                image_path=self.input_image_path, skeleton_data=self.skeleton_data, parent=self
            )

            # Show dialog and handle result
            if editor_dialog.exec() == QDialog.DialogCode.Accepted:
                self.skeleton_data = editor_dialog.get_skeleton_data()
                self._manual_part_metadata = editor_dialog.get_part_metadata()
                if self.image_proc_view and self.skeleton_data:
                    self.image_proc_view.load_skeleton(self.skeleton_data)

                # Get the edited segmentation results
                edited_results = editor_dialog.get_segmentation_results()

                if edited_results:
                    # Apply the manually edited segmentation results
                    self._apply_manual_segmentation_results(edited_results)
                    self.main_window.statusBar().showMessage(
                        "Manual segmentation applied successfully!"
                    )
                else:
                    self.main_window.statusBar().showMessage("No segmentation changes were made.")
            else:
                self.main_window.statusBar().showMessage("Manual segmentation editing cancelled.")

        except ImportError as e:
            QMessageBox.critical(
                self,
                "Import Error",
                f"Could not load interactive segmentation editor: {e}\n\n"
                "Make sure all required dependencies are installed.",
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Editor Error", f"Error opening manual segmentation editor: {e}"
            )

    def _apply_manual_segmentation_results(self, segmentation_results):
        """Apply manually edited segmentation results to the current workflow"""
        try:
            # Save the manual segmentation results
            if self.character_dir:
                output_dir = os.path.join(self.character_dir, "manual_segmentation")
                os.makedirs(output_dir, exist_ok=True)

                # Save individual part masks
                for part_name, mask_data in segmentation_results.items():
                    if mask_data is not None and len(mask_data) > 0:
                        mask_path = os.path.join(output_dir, f"{part_name}_mask.png")
                        cv2.imwrite(mask_path, mask_data)

                # Update the current workflow with manual results
                self.current_annotation_results = segmentation_results

                # Trigger parts generation with manual data
                self._generate_parts_from_manual_segmentation(segmentation_results)

                QMessageBox.information(
                    self, "Success", f"Manual segmentation results saved to:\n{output_dir}"
                )
            else:
                QMessageBox.warning(
                    self, "No Directory", "No character directory set. Results were not saved."
                )

        except Exception as e:
            QMessageBox.critical(
                self, "Apply Error", f"Error applying manual segmentation results: {e}"
            )

    def _generate_parts_from_manual_segmentation(self, segmentation_results):
        """Generate body parts from manual segmentation results"""
        try:
            # Create body parts using manual segmentation masks
            # This integrates with the existing parts generation workflow

            if not self.character_dir or not self.input_image_path:
                return

            # Create character data structure
            char_data = {
                "width": 0,  # Will be set from image
                "height": 0,
                "parts": {},
                "skeleton": self.skeleton_data.get("skeleton", []) if self.skeleton_data else [],
                "joint_map": self.skeleton_data.get("joint_map", {}) if self.skeleton_data else {},
            }

            # Load original image to get dimensions
            import cv2

            original_image = cv2.imread(self.input_image_path, cv2.IMREAD_UNCHANGED)
            if original_image is not None:
                char_data["height"], char_data["width"] = original_image.shape[:2]

            # Process each part from manual segmentation
            for part_name, mask_data in segmentation_results.items():
                if mask_data is not None and len(mask_data) > 0:
                    # Extract part information from mask
                    part_info = self._extract_part_info_from_mask(
                        part_name, mask_data, original_image
                    )
                    if part_info:
                        char_data["parts"][part_name] = part_info

            # Emit signal to main window
            if char_data["parts"]:
                self.parts_generated.emit(char_data, self.character_dir)
                self.main_window.statusBar().showMessage(
                    f"Generated {len(char_data['parts'])} body parts from manual segmentation"
                )

        except Exception as e:
            QMessageBox.critical(
                self, "Generation Error", f"Error generating parts from manual segmentation: {e}"
            )

    def _assign_character_from_image(self) -> None:
        """
        Assign character from the currently prepared image input.

        Input must come from either "Load Image File" or "Capture Camera".
        """
        if not self.input_image_path:
            # If image is not loaded yet, loading will auto-process/replace.
            self.load_input_image(auto_apply=True)
            if not self.input_image_path:
                return
            # auto_apply=True already executed process + parts generation path.
            # Avoid running it again in this handler.
            return

        if (
            not self.current_annotation_results
            or not self.current_temp_char_dir
            or not self.skeleton_data
        ):
            self.process_image()

        if (
            not self.current_annotation_results
            or not self.current_temp_char_dir
            or not self.skeleton_data
        ):
            QMessageBox.warning(
                self,
                "Assign Failed",
                "Character processing did not complete. Check image quality and try again.",
            )
            return

        self.create_parts_from_skeleton(show_success_dialog=False)

    def open_character_assignment_dialog(self):
        """
        Backward-compatible alias for old call sites.

        Historically this opened a preset picker; now assignment is image-driven.
        """
        self._assign_character_from_image()

    def _is_dummy_mechanism_design_session(self) -> bool:
        """
        Return True when the app is currently using a dummy character while
        Mechanism Design already contains user work (mechanism layers).
        """
        mw = self.main_window
        if mw is None:
            return False

        design_tab = getattr(mw, "mechanism_design_tab", None)
        mechanism_layers = getattr(design_tab, "mechanism_layers", None)
        has_design_work = isinstance(mechanism_layers, dict) and bool(mechanism_layers)
        if not has_design_work:
            return False

        # First, inspect known project directory hints.
        project_dir = getattr(getattr(mw, "project_data_manager", None), "project_dir", None)
        if project_dir and "dummy" in str(project_dir).lower():
            return True

        # Fallback: inspect loaded part image paths.
        parts_candidates: list[dict] = []
        for candidate in (
            getattr(design_tab, "parts_data", None),
            getattr(getattr(mw, "editor_tab", None), "current_parts_info", None),
            getattr(getattr(mw, "project_data_manager", None), "parts", None),
        ):
            if isinstance(candidate, dict) and candidate:
                parts_candidates.append(candidate)

        for parts in parts_candidates:
            for part in parts.values():
                image_path = str(getattr(part, "image_path", "") or "")
                if image_path and "dummy" in image_path.lower():
                    return True

        return False

    def _extract_part_info_from_mask(self, part_name: str, mask: any, original_image: any) -> dict:
        """Extract part information from a segmentation mask"""
        try:
            import cv2
            import numpy as np

            # Find bounding box of the mask
            if hasattr(mask, "shape"):
                # mask is numpy array
                mask_array = mask
            else:
                # Convert to numpy array if needed
                mask_array = np.array(mask)

            # Find non-zero pixels
            coords = np.column_stack(np.where(mask_array > 0))
            if len(coords) == 0:
                return None

            # Calculate bounding box
            y_min, x_min = coords.min(axis=0)
            y_max, x_max = coords.max(axis=0)

            roi_width = x_max - x_min + 1
            roi_height = y_max - y_min + 1

            # Extract part texture from original image
            if original_image is not None:
                part_texture = original_image[y_min : y_max + 1, x_min : x_max + 1]
                part_mask_roi = mask_array[y_min : y_max + 1, x_min : x_max + 1]

                # Create RGBA image with transparency
                if len(part_texture.shape) == 3:
                    part_rgba = cv2.cvtColor(part_texture, cv2.COLOR_BGR2BGRA)
                else:
                    part_rgba = cv2.cvtColor(part_texture, cv2.COLOR_GRAY2BGRA)

                # Apply mask as alpha channel
                part_rgba[:, :, 3] = part_mask_roi

                # Save part image
                if self.character_dir:
                    parts_dir = os.path.join(self.character_dir, "manual_parts")
                    os.makedirs(parts_dir, exist_ok=True)
                    part_image_path = os.path.join(parts_dir, f"{part_name}.png")
                    cv2.imwrite(part_image_path, part_rgba)

            manual_metadata = self._manual_part_metadata or {}
            anchor_by_part = manual_metadata.get("part_anchor_joints", {})
            joint_positions = manual_metadata.get("joint_positions", {})
            anchor_joint_id = anchor_by_part.get(part_name) or BODY_PARTS.get(part_name, {}).get(
                "anchor_joint"
            )
            local_pivot_offset = [float(roi_width / 2), float(roi_height / 2)]
            if anchor_joint_id in joint_positions:
                anchor_x, anchor_y = joint_positions[anchor_joint_id]
                local_pivot_offset = [float(anchor_x - x_min), float(anchor_y - y_min)]

            # Create part info structure
            part_info = {
                "name": part_name,
                "roi": [float(x_min), float(y_min), float(roi_width), float(roi_height)],
                "image_path": f"manual_parts/{part_name}.png",
                "local_pivot_offset": local_pivot_offset,
                "z_value": 0.0,
                "fixed": False,
                "fill_color": "rgba(128,128,128,0.5)",
            }
            if anchor_joint_id:
                part_info["anchor_joint_id"] = anchor_joint_id

            return part_info

        except Exception as e:
            print(f"Error extracting part info for {part_name}: {e}")
            return None

    def _load_image_from_path(self, image_path: str):
        """Load an image directly from a given path (used by landing tab)."""
        if not os.path.exists(image_path):
            return False

        if self.image_proc_view.load_image(image_path):
            self._on_input_ready(
                image_path=image_path,
                source="sample" if self._is_bundled_sample_path(image_path) else "file",
                status_prefix="Loaded input image",
            )
            self._auto_apply_loaded_image_to_editor()
            return True
        else:
            QMessageBox.warning(self, "Load Error", f"Could not load image: {image_path}")
            return False

    def _write_camera_capture_temp(self, image: np.ndarray) -> str:
        """Write a camera capture under an isolated app temp session."""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        session_id = f"camera_capture_{timestamp}_{uuid.uuid4().hex}"
        session_dir = get_session_temp_dir(session_id=session_id, clear_existing=False)
        (session_dir / IMAGE_TEMP_SESSION_MARKER).touch(exist_ok=True)
        temp_path = session_dir / "capture.png"
        if not cv2.imwrite(str(temp_path), image):
            raise OSError(f"Failed to write camera capture to {temp_path}")
        return str(temp_path)

    def capture_image(self):
        try:
            dialog = CameraDialog(self)
            self.active_camera_dialogs.append(dialog)
            dialog.finished.connect(
                lambda: (
                    self.active_camera_dialogs.remove(dialog)
                    if dialog in self.active_camera_dialogs
                    else None
                )
            )

            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.captured_image is not None:
                try:
                    temp_path = self._write_camera_capture_temp(dialog.captured_image)
                    if self.image_proc_view.load_image(temp_path):
                        self._on_input_ready(
                            image_path=temp_path,
                            source="camera",
                            status_prefix="Loaded captured image",
                        )
                    else:
                        QMessageBox.warning(
                            self,
                            "Load Error",
                            "Failed to load captured image into view.",
                        )
                except Exception as e:
                    QMessageBox.critical(self, "Save Error", f"Could not save captured image: {e}")
        except Exception as e:
            QMessageBox.critical(self, "Camera Error", f"Could not open camera: {e}")

    def process_image(self):
        """
        Processes the loaded input image using image_to_annotations.
        This will generate char_cfg.yaml, texture.png, mask.png etc. in a temp dir.
        Then, it loads the skeleton data from the generated char_cfg.yaml.
        """
        if not self.input_image_path:
            QMessageBox.warning(self, "Warning", "No input image loaded.")
            self.update_button_states()
            return

        with telemetry_span(
            "ui.image_processing.process_image",
            editing_mode=self.editing_mode,
            input_source="file",
        ) as span:
            self.main_window.statusBar().showMessage("Processing image...")
            QApplication.processEvents()  # Ensure UI updates

            progress_dialog = QProgressDialog("Processing image, please wait...", None, 0, 0, self)
            progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            progress_dialog.setCancelButton(None)  # No cancel button for now
            progress_dialog.show()
            QApplication.processEvents()

            try:
                annotation_results = image_to_annotations(self.input_image_path)

                if annotation_results and annotation_results.get("char_cfg_path"):
                    self.current_annotation_results = annotation_results
                    self.current_temp_char_dir = annotation_results["output_dir"]
                    char_cfg_file_path = annotation_results["char_cfg_path"]

                    self.main_window.statusBar().showMessage(
                        f"Image processed. Temp files at {self.current_temp_char_dir}",
                        5000,
                    )

                    if self.load_skeleton_data_from_config(
                        char_cfg_file_path,
                        emit_signal=False,
                    ):
                        if self.image_proc_view.load_image(annotation_results["texture_path"]):
                            self.image_proc_view.load_skeleton(self.skeleton_data)
                            span.set(
                                status="success",
                                skeleton_loaded=bool(self.skeleton_data),
                                output_dir=self.current_temp_char_dir,
                            )
                        else:
                            span.set(status="failure", reason="texture_load_failed")
                    else:
                        span.set(status="failure", reason="skeleton_load_failed")
                        QMessageBox.critical(
                            self,
                            "Error",
                            f"Failed to load skeleton from {char_cfg_file_path}",
                        )
                else:
                    self.current_annotation_results = None
                    self.current_temp_char_dir = None
                    span.set(status="failure", reason="annotation_failure")
                    QMessageBox.critical(
                        self, "Error", "Image processing (image_to_annotations) failed."
                    )
                    self.main_window.statusBar().showMessage("Image processing failed.", 5000)

            except Exception as e:
                span.set(status="error", error=str(e))
                self.current_annotation_results = None
                self.current_temp_char_dir = None
                QMessageBox.critical(self, "Processing Error", f"An unexpected error occurred: {e}")
                self.main_window.statusBar().showMessage(f"Processing error: {e}", 5000)
            finally:
                progress_dialog.close()

        self.update_button_states()

    def load_skeleton_data_from_config(
        self,
        char_cfg_filepath: str,
        *,
        emit_signal: bool = False,
    ) -> bool:
        if not char_cfg_filepath or not os.path.exists(char_cfg_filepath):
            if char_cfg_filepath:  # Only show error if a path was given but invalid
                QMessageBox.warning(
                    self,
                    "Load Error",
                    f"Skeleton file not found: {os.path.basename(char_cfg_filepath)}",
                )
            return False

        try:
            with open(char_cfg_filepath, encoding="utf-8") as f:
                loaded_skeleton_data = yaml.safe_load(f)
            if (
                not loaded_skeleton_data or "skeleton" not in loaded_skeleton_data
            ):  # Basic validation
                raise ValueError("Invalid or empty skeleton file format.")

            if self.image_proc_view.load_skeleton(loaded_skeleton_data):
                self.skeleton_data = loaded_skeleton_data
                # Update character_dir if loading skeleton from a different location and it seems valid
                potential_char_dir = os.path.dirname(char_cfg_filepath)
                if os.path.exists(os.path.join(potential_char_dir, "image.png")):  # Heuristic
                    self.character_dir = potential_char_dir

                status_bar = self.main_window.statusBar() if self.main_window else None
                if status_bar:
                    status_bar.showMessage(
                        f"Loaded skeleton: {os.path.basename(char_cfg_filepath)}"
                    )
                # Keep image-processing skeleton local by default.
                # Global skeleton should be updated when character replacement
                # is committed through parts/project load flow.
                if emit_signal:
                    self.skeleton_updated.emit(self.skeleton_data)
                self.update_button_states()  # Update states, which will include the new group
                return True
            else:
                raise RuntimeError("ImageProcessingView failed to load skeleton data.")

        except Exception as e:
            QMessageBox.critical(self, "Load Skeleton Error", f"Failed to load skeleton: {e}")
            return False

    def edit_skeleton(self):
        if not self.image_proc_view.joints:  # Check if joints are loaded in the view
            QMessageBox.information(
                self,
                "Edit Skeleton",
                "No skeleton loaded to edit. Please process an image or load a skeleton first.",
            )
            return
        # The view itself should handle the editability of joints. This button might just serve as a toggle or focus.
        self.image_proc_view.set_edit_mode(True)  # Assuming view has such a method
        self.main_window.statusBar().showMessage("Skeleton editing enabled. Drag joints to modify.")

    def save_skeleton(self):
        if not self.image_proc_view.joints:
            QMessageBox.warning(self, "Save Error", "No skeleton data loaded to save.")
            return

        default_path = (
            os.path.join(self.character_dir, "char_cfg.yaml")
            if self.character_dir
            else "char_cfg.yaml"
        )
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save Skeleton As", default_path, "YAML Files (*.yaml *.yml)"
        )

        if not save_path:
            return

        try:
            current_skeleton_data = self.image_proc_view.get_skeleton_data()
            if not current_skeleton_data:
                raise ValueError("Could not retrieve skeleton data from view.")

            with open(save_path, "w", encoding="utf-8") as f:
                yaml.dump(current_skeleton_data, f, default_flow_style=None, sort_keys=False)

            self.skeleton_data = current_skeleton_data  # Update internal state
            status_bar = self.main_window.statusBar() if self.main_window else None
            if status_bar:
                status_bar.showMessage(f"Skeleton saved to {os.path.basename(save_path)}")
            # Keep edited skeleton local in Image Processing tab.
            # Character replacement flow will publish authoritative skeleton.
            # self.skeleton_updated.emit(self.skeleton_data)

        except Exception as e:
            QMessageBox.critical(self, "Save Skeleton Error", f"Could not save skeleton: {e}")

    def create_parts_from_skeleton(self, *, show_success_dialog: bool = True) -> bool:
        """Initiates part creation using BodyPartsExtractor based on current skeleton and image."""
        if (
            not self.current_annotation_results
            or not self.current_annotation_results.get("texture_path")
            or not self.current_annotation_results.get("char_cfg_path")
            or not self.current_temp_char_dir
        ):
            QMessageBox.warning(
                self,
                "Missing Data",
                "Cannot create parts. Texture, char_cfg, or temp directory not available. Please process image first.",
            )
            return False

        status_bar = self.main_window.statusBar() if self.main_window else None
        if status_bar:
            status_bar.showMessage("Generating character parts...", 5000)

        progress_dialog = QProgressDialog("Generating body parts...", "Cancel", 0, 0, self)
        progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        progress_dialog.setAutoClose(True)
        progress_dialog.show()
        QApplication.processEvents()  # Ensure dialog shows

        try:
            bpe_output_dir = self._ensure_output_dir()
            if bpe_output_dir is None:
                if status_bar:
                    status_bar.showMessage(
                        "Parts generation cancelled: no save folder selected.", 3000
                    )
                progress_dialog.close()
                return False

            # Keep annotation-generated texture/mask coordinate system intact.
            # Only refresh texture/image from input when dimensions exactly match
            # the generated mask. Otherwise parts can fragment due to ROI mismatch.
            self._refresh_texture_from_input_if_compatible(Path(self.current_temp_char_dir))

            self.body_parts_extractor = BodyPartsExtractor(
                char_dir=str(
                    self.current_temp_char_dir
                ),  # This is the input dir containing char_cfg, texture, mask
                output_dir=str(
                    bpe_output_dir
                ),  # This is where parts_info.json and part SVGs should go
            )

            self.body_parts_extractor.process()

            actual_bpe_output_dir_from_extractor = Path(self.body_parts_extractor.output_dir)

            expected_parts_info_path = actual_bpe_output_dir_from_extractor / "parts_info.json"

            if not expected_parts_info_path.exists():
                QMessageBox.critical(
                    self,
                    "Parts Generation Error",
                    f"parts_info.json was not created by BodyPartsExtractor at the expected location:\\n{expected_parts_info_path}\\n\\nPlease check the application logs for errors from BodyPartsExtractor.",
                )
                progress_dialog.close()
                return False
            self.current_parts_info_path = str(expected_parts_info_path)

            progress_dialog.close()
            msg_parts_generated = "Character parts generated successfully"
            msg_parts_generated += f"\nSaved to:\n{actual_bpe_output_dir_from_extractor}"
            if show_success_dialog:
                QMessageBox.information(self, "Parts Generated", msg_parts_generated)
            status_bar = self.main_window.statusBar() if self.main_window else None
            if status_bar:
                status_bar.showMessage(
                    f"Character parts saved to {actual_bpe_output_dir_from_extractor}",
                    8000,
                )

            if self.current_annotation_results:
                # Pass the actual_bpe_output_dir_from_extractor where parts_info.json resides
                self.parts_generated.emit(
                    self.current_annotation_results,
                    str(actual_bpe_output_dir_from_extractor),
                )
            self.update_button_states()
            return True

        except Exception as e:
            progress_dialog.close()
            QMessageBox.critical(self, "Part Creation Error", f"An error occurred: {e}")
            return False
        finally:
            if progress_dialog.isVisible():
                progress_dialog.close()

    def _refresh_texture_from_input_if_compatible(self, char_dir: Path) -> bool:
        """Refresh texture/image from input only when mask dimensions match."""
        if not self.input_image_path:
            return False

        input_path = Path(self.input_image_path)
        if not input_path.exists():
            return False

        mask_path = char_dir / "mask.png"
        texture_path = char_dir / "texture.png"
        image_path = char_dir / "image.png"
        if not mask_path.exists() or not texture_path.exists():
            return False

        input_img = cv2.imread(str(input_path), cv2.IMREAD_UNCHANGED)
        mask_img = cv2.imread(str(mask_path), cv2.IMREAD_UNCHANGED)
        if input_img is None or mask_img is None:
            return False

        input_h, input_w = input_img.shape[:2]
        mask_h, mask_w = mask_img.shape[:2]
        if input_h != mask_h or input_w != mask_w:
            logging.info(
                "ImageProcessingTab: Keeping annotation texture (input=%sx%s, mask=%sx%s).",
                input_w,
                input_h,
                mask_w,
                mask_h,
            )
            return False

        import shutil

        shutil.copy2(input_path, texture_path)
        shutil.copy2(input_path, image_path)
        logging.info(
            "ImageProcessingTab: Refreshed texture/image from input (size=%sx%s).",
            input_w,
            input_h,
        )
        return True

    def _handle_image_zoom_change(self, zoom_text: str):
        """Handle zoom change from the combo box."""
        try:
            if zoom_text.lower() == "fit":
                self.image_proc_view.zoom_to_fit()
                return

            if zoom_text.endswith("%"):
                zoom_value = float(zoom_text[:-1]) / 100.0
            else:
                zoom_value = float(zoom_text)

            zoom_value = max(0.1, min(zoom_value, 10.0))

            self.image_proc_view.set_zoom_level(zoom_value)

            with blocked_signals(self.image_zoom_combo):
                self.image_zoom_combo.setCurrentText(f"{int(zoom_value * 100)}%")

        except ValueError:
            with blocked_signals(self.image_zoom_combo):
                self.image_zoom_combo.setCurrentText("100%")
            self.image_proc_view.set_zoom_level(1.0)
        except Exception:
            logging.debug("Suppressed exception", exc_info=True)

    def _handle_image_zoom_change_fit(self):
        self.image_proc_view.zoom_to_fit()
        current_scale = self.image_proc_view.transform().m11()
        zoom_percent = int(current_scale * 100)
        with blocked_signals(self.image_zoom_combo):
            self.image_zoom_combo.setCurrentText(f"{zoom_percent}%")

    def update_button_states(self):
        """Updates the enabled/disabled state of buttons based on current tab state."""
        has_image = bool(self.input_image_path)
        has_skeleton = bool(self.skeleton_data)

        self.processing_steps_group.set_buttons_enabled_state(
            process_enabled=has_image,
            edit_enabled=has_skeleton,
            save_enabled=has_skeleton,
            generate_enabled=(has_skeleton and has_image),
            skeleton_tools_enabled=has_skeleton,
        )
        if hasattr(self, "manual_segmentation_btn"):
            self.manual_segmentation_btn.setEnabled(has_image)
        if hasattr(self, "edit_skeleton_btn"):
            self.edit_skeleton_btn.setEnabled(has_skeleton)
        if hasattr(self, "save_skeleton_btn"):
            self.save_skeleton_btn.setEnabled(has_skeleton)
        if self.assign_character_btn is not None:
            is_dummy_session = self._is_dummy_mechanism_design_session()
            enable_replace = is_dummy_session
            self.assign_character_btn.setEnabled(enable_replace)
            if enable_replace and not has_image:
                self.assign_character_btn.setToolTip(
                    "Dummy mechanism session detected. Click to load an image and replace character."
                )
            elif enable_replace:
                self.assign_character_btn.setToolTip(
                    "Replace dummy character using the loaded image"
                )
            else:
                self.assign_character_btn.setToolTip(
                    "Replace Character is available when a dummy character session exists in Mechanism Design"
                )

    def _has_loaded_preview_image(self) -> bool:
        """Return True when the image view currently has a valid pixmap loaded."""
        return bool(
            self.image_proc_view
            and self.image_proc_view.image_item
            and not self.image_proc_view.image_item.pixmap().isNull()
        )

    def _collect_character_preview_dirs(self) -> list[Path]:
        """Collect character/project directories that may hold preview assets."""
        mw = self.main_window
        candidate_dirs: list[Path] = []

        def _add_dir(path_like: str | Path | None) -> None:
            if not path_like:
                return
            try:
                path = Path(path_like)
            except Exception:
                return
            if not path.exists():
                return
            if path.is_file():
                path = path.parent
            if path not in candidate_dirs:
                candidate_dirs.append(path)

        _add_dir(self.character_dir)
        _add_dir(self.current_temp_char_dir)
        if mw is not None:
            _add_dir(getattr(mw, "current_temp_char_dir", None))
            project_data_manager = getattr(mw, "project_data_manager", None)
            _add_dir(getattr(project_data_manager, "project_dir", None))
            project_state_manager = getattr(mw, "project_state_manager", None)
            state = getattr(project_state_manager, "state", None)
            _add_dir(getattr(state, "project_dir", None) if state is not None else None)

        return candidate_dirs

    def _iter_character_preview_candidates(self, preview_names: tuple[str, ...]):
        """
        Yield candidate preview image paths from current project/character contexts.

        Priority:
        1) Active character/project directories.
        2) Known preview files in those directories.
        """
        for base_dir in self._collect_character_preview_dirs():
            for filename in preview_names:
                candidate = base_dir / filename
                if candidate.exists() and candidate.is_file():
                    yield str(candidate)

    def _iter_parts_data_candidates(self) -> list[dict]:
        """Collect loaded part dictionaries from tabs/managers in priority order."""
        mw = self.main_window
        if mw is None:
            return []

        candidates: list[dict] = []
        for maybe_parts in (
            getattr(getattr(mw, "editor_tab", None), "current_parts_info", None),
            getattr(getattr(mw, "mechanism_design_tab", None), "parts_data", None),
            getattr(getattr(mw, "project_data_manager", None), "parts", None),
        ):
            if isinstance(maybe_parts, dict) and maybe_parts:
                candidates.append(maybe_parts)
        return candidates

    def _resolve_part_image_path(self, raw_path: str, base_dirs: list[Path]) -> Path | None:
        """Resolve absolute image path for a part image."""
        if not raw_path:
            return None

        candidate = Path(raw_path)
        if candidate.is_absolute():
            return candidate if candidate.exists() else None
        if candidate.exists():
            return candidate

        for base_dir in base_dirs:
            full_path = base_dir / candidate
            if full_path.exists():
                return full_path
        return None

    def _create_composited_parts_preview(self) -> str | None:
        """
        Build a preview image from part PNGs using ROI placement.

        This avoids showing segmentation/debug visuals when no full texture exists.
        """
        base_dirs = self._collect_character_preview_dirs()
        for parts_dict in self._iter_parts_data_candidates():
            layered_parts: list[tuple[float, float, float, float, float, Path]] = []
            for part in parts_dict.values():
                roi = getattr(part, "roi", None)
                if not isinstance(roi, list | tuple) or len(roi) < 4:
                    continue
                try:
                    x = float(roi[0])
                    y = float(roi[1])
                    w = float(roi[2])
                    h = float(roi[3])
                except (TypeError, ValueError):
                    continue
                if w <= 0.0 or h <= 0.0:
                    continue

                image_path = str(getattr(part, "image_path", "") or "")
                resolved_path = self._resolve_part_image_path(image_path, base_dirs)
                if resolved_path is None:
                    continue

                try:
                    z_value = float(getattr(part, "z_value", 0.0) or 0.0)
                except (TypeError, ValueError):
                    z_value = 0.0
                layered_parts.append((z_value, x, y, w, h, resolved_path))

            if not layered_parts:
                continue

            min_x = min(item[1] for item in layered_parts)
            min_y = min(item[2] for item in layered_parts)
            max_x = max(item[1] + item[3] for item in layered_parts)
            max_y = max(item[2] + item[4] for item in layered_parts)

            canvas_w = max(1, int(round(max_x - min_x)))
            canvas_h = max(1, int(round(max_y - min_y)))
            canvas = np.zeros((canvas_h, canvas_w, 4), dtype=np.uint8)

            for _z, x, y, w, h, part_image_path in sorted(
                layered_parts,
                key=lambda item: item[0],
            ):
                src = cv2.imread(str(part_image_path), cv2.IMREAD_UNCHANGED)
                if src is None:
                    continue

                if src.ndim == 2:
                    src = cv2.cvtColor(src, cv2.COLOR_GRAY2BGRA)
                elif src.shape[2] == 3:
                    src = cv2.cvtColor(src, cv2.COLOR_BGR2BGRA)

                target_w = max(1, int(round(w)))
                target_h = max(1, int(round(h)))
                if src.shape[1] != target_w or src.shape[0] != target_h:
                    interpolation = (
                        cv2.INTER_AREA
                        if src.shape[1] > target_w or src.shape[0] > target_h
                        else cv2.INTER_LINEAR
                    )
                    src = cv2.resize(src, (target_w, target_h), interpolation=interpolation)

                dst_x = int(round(x - min_x))
                dst_y = int(round(y - min_y))
                x1 = max(0, dst_x)
                y1 = max(0, dst_y)
                x2 = min(canvas_w, dst_x + target_w)
                y2 = min(canvas_h, dst_y + target_h)
                if x2 <= x1 or y2 <= y1:
                    continue

                src_crop = src[y1 - dst_y : y2 - dst_y, x1 - dst_x : x2 - dst_x]
                dst_crop = canvas[y1:y2, x1:x2]

                alpha = (src_crop[:, :, 3].astype(np.float32) / 255.0)[:, :, None]
                dst_crop[:, :, :3] = (
                    src_crop[:, :, :3].astype(np.float32) * alpha
                    + dst_crop[:, :, :3].astype(np.float32) * (1.0 - alpha)
                ).astype(np.uint8)
                dst_crop[:, :, 3] = np.maximum(dst_crop[:, :, 3], src_crop[:, :, 3])

            preview_dir = Path(tempfile.gettempdir()) / "automataii" / "preview_cache"
            preview_dir.mkdir(parents=True, exist_ok=True)
            preview_path = preview_dir / f"parts_preview_{int(time.time() * 1000)}.png"
            if cv2.imwrite(str(preview_path), canvas):
                return str(preview_path)

        return None

    def _try_load_external_character_preview(self) -> bool:
        """
        Load a preview image for externally loaded characters (dummy/project load).

        This keeps the Image Processing tab visually in sync even when no input
        image was manually loaded in this tab.
        """
        if not self.image_proc_view:
            return False
        if self._has_loaded_preview_image():
            return True

        # Prefer "real" previews first.
        for candidate in self._iter_character_preview_candidates(("image.png", "texture.png")):
            if self.image_proc_view.load_image(candidate):
                logging.info(
                    "ImageProcessingTab: Loaded external character preview image: %s",
                    candidate,
                )
                return True

        # If no texture/image exists (e.g., dummy character), build composited preview from parts.
        composited = self._create_composited_parts_preview()
        if composited and self.image_proc_view.load_image(composited):
            logging.info(
                "ImageProcessingTab: Loaded composited parts preview image: %s",
                composited,
            )
            return True

        # Last-resort preview assets.
        for candidate in self._iter_character_preview_candidates(
            ("segmentation_vis.png", "mask.png")
        ):
            if self.image_proc_view.load_image(candidate):
                logging.info(
                    "ImageProcessingTab: Loaded fallback preview image: %s",
                    candidate,
                )
                return True
        return False

    def on_parts_loaded_in_editor(self, _loaded: bool):
        """
        Slot to be called when parts are loaded/cleared in the editor.
        Updates the state of UI elements in this tab.
        """
        # This method is more about reacting to external changes (EditorTab loading parts)
        # rather than this tab initiating the load *into* EditorTab.
        # If `loaded` is True, it means a project is active.
        # If `loaded` is False, project might have been cleared.

        # If parts are loaded elsewhere, this tab might want to reflect that state,
        # e.g., by enabling/disabling certain buttons.
        # However, the primary flow is:
        # 1. This tab generates data (image_to_annotations -> char_cfg, BPE -> parts_info)
        # 2. This tab emits `parts_generated` with paths.
        # 3. MainWindow receives this, tells ProjectDataManager to load from these paths.
        # 4. ProjectDataManager emits `project_data_loaded`.
        # 5. MainWindow tells EditorTab to populate from ProjectDataManager.
        # So, this slot might be less critical if the above flow is robust.

        if _loaded:
            self._try_load_external_character_preview()
        self.update_button_states()  # General state update

    def on_skeleton_updated_externally(self, skeleton_data: dict | None):
        """
        Slot for when skeleton data is updated from an external source
        (e.g., loaded directly into SkeletonManager by MainWindow).
        Updates the view in this tab if a texture is loaded.
        """
        self.skeleton_data = skeleton_data
        if self.skeleton_data and not self._has_loaded_preview_image():
            self._try_load_external_character_preview()

        if self._has_loaded_preview_image() and self.skeleton_data:
            self.image_proc_view.load_skeleton(self.skeleton_data)
        elif not self.skeleton_data:
            if self.image_proc_view:
                self.image_proc_view.load_skeleton(None)
        self.update_button_states()

    def clear_display_and_data(self) -> None:
        """Clear all display content and reset internal data.

        Called when project load fails or when a new project is started.
        Resets:
        - Image display (scene clear)
        - Skeleton data
        - Annotation results
        - Path references
        """
        logging.info("ImageProcessingTab: Clearing display and data")

        # Clear image and all view overlays/runtime items.
        if self.image_proc_view:
            self.image_proc_view.clear_display()
        elif self.image_proc_scene:
            self.image_proc_scene.clear()

        # Reset internal data
        self.input_image_path = None
        self.character_dir = None
        self.current_temp_char_dir = None
        self.current_annotation_results = None
        self.skeleton_data = None
        self._input_source = None
        if not self._output_dir_user_selected:
            self.output_dir = None
        self._update_output_location_label()

        # Update UI state
        self.update_button_states()

    def _toggle_detailed_processing_visibility(self, visible: bool):
        """Slot to control the visibility of the detailed processing steps group."""
        self.processing_steps_group.setVisible(visible)

    def extend_skeleton(self):
        """Extends the skeleton lengths by 10%.

        Delegates to SkeletonToolsHandler component.
        """
        self._skeleton_tools.extend_skeleton(factor=1.1)

    def show_lock_joints_dialog(self):
        """Shows a dialog for locking/unlocking specific joints.

        Delegates to SkeletonToolsHandler component.
        """
        self._skeleton_tools.show_lock_joints_dialog()

    def _update_skeleton_view(self, skeleton_data: dict) -> None:
        """Update skeleton in view after modification.

        Callback for SkeletonToolsHandler.
        """
        self.skeleton_data = skeleton_data
        if self.image_proc_view:
            self.image_proc_view.load_skeleton(skeleton_data)

    def _on_skeleton_modified(self, skeleton_data: dict) -> None:
        """Handle skeleton modification from SkeletonToolsHandler.

        Updates internal state after skeleton tools modify the skeleton.
        """
        self.skeleton_data = skeleton_data
        self.update_button_states()
