# Currently Not in use

import logging
from typing import Optional, Dict, Any

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QScrollArea,
    QGroupBox,
    QTreeWidget,
    QTreeWidgetItem,
)
from PySide6.QtCore import Qt, Signal, QPointF

from automataii.gui.views.editor_view import EditorView
from automataii.core.models_pydantic import (
    MechanismModel,
    PartModel,
    LinkageMechanismModel,
    CamMechanismModel,
    GearMechanismModel,
    CharacterModel,
)

# from ..widgets.part_properties_widget import PartPropertiesWidget # Assuming this will also be converted
# from ..widgets.mechanism_properties_widget import MechanismPropertiesWidget # Assuming this will also be converted


class DesignerTab(QWidget):
    """Tab for designing and assembling mechanisms from parts."""

    # Signals to MainWindow or other managers
    mechanism_data_updated = Signal(
        MechanismModel
    )  # When a mechanism is created or significantly changed
    part_selection_changed = Signal(Optional[str])  # part_id or None
    request_add_mechanism_to_simulation = Signal(MechanismModel)
    status_message_updated = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("designerTab")

        self.current_character_model: Optional[CharacterModel] = None
        self.current_mechanisms: Dict[
            str, MechanismModel
        ] = {}  # Store mechanisms being designed
        self.active_mechanism_id: Optional[str] = None
        self.selected_part_id_in_editor: Optional[str] = None

        self._init_ui()
        self._connect_signals()
        self._update_ui_for_active_data()

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # Left Panel: Parts/Mechanisms Tree and Creation Buttons
        left_panel = QWidget()
        left_panel_layout = QVBoxLayout(left_panel)
        left_panel.setMinimumWidth(250)
        left_panel.setMaximumWidth(350)

        # Parts Tree (displaying parts of the loaded character)
        self.parts_tree_group = QGroupBox("Character Parts")
        parts_tree_layout = QVBoxLayout(self.parts_tree_group)
        self.parts_tree_widget = QTreeWidget()
        self.parts_tree_widget.setObjectName("designerPartsTree")
        self.parts_tree_widget.setHeaderHidden(True)
        # self.parts_tree_widget.setDragEnabled(True) # For drag-and-drop to editor
        parts_tree_layout.addWidget(self.parts_tree_widget)
        left_panel_layout.addWidget(self.parts_tree_group)

        # Mechanism Creation Buttons
        mechanism_creation_group = QGroupBox("Create New Mechanism")
        mechanism_creation_layout = QVBoxLayout(mechanism_creation_group)
        self.create_linkage_button = QPushButton("New Linkage")
        self.create_cam_button = QPushButton("New Cam-Follower")
        self.create_gear_button = QPushButton("New Gear Pair")
        mechanism_creation_layout.addWidget(self.create_linkage_button)
        mechanism_creation_layout.addWidget(self.create_cam_button)
        mechanism_creation_layout.addWidget(self.create_gear_button)
        left_panel_layout.addWidget(mechanism_creation_group)

        # Mechanisms List/Tree (displaying created mechanisms for this character)
        self.mechanisms_tree_group = QGroupBox("Designed Mechanisms")
        mechanisms_tree_layout = QVBoxLayout(self.mechanisms_tree_group)
        self.mechanisms_tree_widget = QTreeWidget()
        self.mechanisms_tree_widget.setObjectName("designerMechanismsTree")
        self.mechanisms_tree_widget.setHeaderLabels(["Name", "Type"])
        mechanisms_tree_layout.addWidget(self.mechanisms_tree_widget)
        left_panel_layout.addWidget(self.mechanisms_tree_group)

        left_panel_layout.addStretch(1)
        main_layout.addWidget(left_panel)

        # Center Panel: Editor View
        self.editor_view_group = QGroupBox("Mechanism Design Area")  # Title for clarity
        self.editor_view_group.setObjectName("designerEditorGroup")
        editor_view_layout = QVBoxLayout(self.editor_view_group)
        self.editor_view = EditorView(self)  # EditorView is a QGraphicsView subclass
        self.editor_view.setObjectName("designerEditorView")
        self.editor_view.setMinimumSize(500, 400)
        editor_view_layout.addWidget(self.editor_view)
        # Add editor toolbar here if EditorView doesn't manage its own
        main_layout.addWidget(self.editor_view_group, 1)  # Give it stretch factor

        # Right Panel: Properties Editor (Part & Mechanism)
        right_panel_scroll = QScrollArea()
        right_panel_scroll.setObjectName("designerRightPanelScroll")
        right_panel_scroll.setWidgetResizable(True)
        right_panel_scroll.setMinimumWidth(280)
        right_panel_scroll.setMaximumWidth(380)
        right_panel_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        right_panel_content = QWidget()
        right_panel_content.setObjectName("designerRightPanelContent")
        right_layout = QVBoxLayout(right_panel_content)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(15)

        # self.part_properties_widget = PartPropertiesWidget(self) # Placeholder
        # self.part_properties_widget.setObjectName("designerPartProps")
        # self.part_properties_widget.setVisible(False) # Show only when a part is selected
        # right_layout.addWidget(self.part_properties_widget)

        # self.mechanism_properties_widget = MechanismPropertiesWidget(self) # Placeholder
        # self.mechanism_properties_widget.setObjectName("designerMechProps")
        # self.mechanism_properties_widget.setVisible(False) # Show only when a mechanism is active
        # right_layout.addWidget(self.mechanism_properties_widget)

        # Temporary placeholder for properties
        self.properties_placeholder_label = QLabel(
            "Select a part or mechanism to see properties."
        )
        self.properties_placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.properties_placeholder_label.setWordWrap(True)
        right_layout.addWidget(self.properties_placeholder_label)

        right_layout.addStretch(1)
        right_panel_content.setLayout(right_layout)
        right_panel_scroll.setWidget(right_panel_content)
        main_layout.addWidget(right_panel_scroll)

    def _connect_signals(self):
        self.create_linkage_button.clicked.connect(self._create_new_linkage_mechanism)
        self.create_cam_button.clicked.connect(self._create_new_cam_mechanism)
        self.create_gear_button.clicked.connect(self._create_new_gear_mechanism)

        self.parts_tree_widget.itemClicked.connect(self._on_part_tree_item_clicked)
        self.mechanisms_tree_widget.itemClicked.connect(
            self._on_mechanism_tree_item_clicked
        )
        # self.mechanisms_tree_widget.itemDoubleClicked.connect(self._on_mechanism_tree_item_double_clicked)

        # Connect signals from EditorView
        if self.editor_view:
            self.editor_view.part_selected.connect(self._on_part_selected_in_editor)
            self.editor_view.part_moved.connect(
                self._on_part_moved_in_editor
            )  # (part_id, new_pos, new_rotation, new_scale)
            self.editor_view.mechanism_structure_changed.connect(
                self._on_mechanism_structure_changed_in_editor
            )  # (mechanism_id, change_details)
            # self.editor_view.background_clicked.connect(self._on_editor_background_clicked)

        # Connect signals from Property Widgets (once implemented)
        # if self.part_properties_widget:
        #     self.part_properties_widget.part_data_changed.connect(self._on_part_properties_changed)
        # if self.mechanism_properties_widget:
        #     self.mechanism_properties_widget.mechanism_data_changed.connect(self._on_mechanism_properties_changed)

    def _update_ui_for_active_data(self):
        # Update parts tree based on self.current_character_model
        self.parts_tree_widget.clear()
        if self.current_character_model and self.current_character_model.parts:
            for part_id, part_model in self.current_character_model.parts.items():
                item = QTreeWidgetItem(
                    self.parts_tree_widget, [part_model.name or part_id]
                )
                item.setData(0, Qt.ItemDataRole.UserRole, part_id)  # Store part_id
                # item.setIcon(0, QIcon(":/icons/part_icon.png")) # Example icon
            self.parts_tree_group.setTitle(
                f"Parts for: {self.current_character_model.name}"
            )
            self.parts_tree_widget.setEnabled(True)
        else:
            self.parts_tree_group.setTitle("Character Parts (None Loaded)")
            self.parts_tree_widget.setEnabled(False)

        # Update mechanisms tree based on self.current_mechanisms
        self.mechanisms_tree_widget.clear()
        if self.current_mechanisms:
            for mech_id, mech_model in self.current_mechanisms.items():
                item = QTreeWidgetItem(
                    self.mechanisms_tree_widget,
                    [mech_model.name or mech_id, str(mech_model.type.value)],
                )
                item.setData(0, Qt.ItemDataRole.UserRole, mech_id)
                # item.setIcon(0, QIcon(self._get_icon_for_mechanism_type(mech_model.type))) # Example icon
                if mech_id == self.active_mechanism_id:
                    self.mechanisms_tree_widget.setCurrentItem(item)
            self.mechanisms_tree_widget.setEnabled(True)
        else:
            self.mechanisms_tree_widget.setEnabled(False)

        # Enable/disable mechanism creation buttons
        can_create_mechanisms = self.current_character_model is not None
        self.create_linkage_button.setEnabled(can_create_mechanisms)
        self.create_cam_button.setEnabled(can_create_mechanisms)
        self.create_gear_button.setEnabled(can_create_mechanisms)

        # Update properties widgets visibility and content
        # This logic will be more complex with actual property widgets
        # if self.part_properties_widget and self.mechanism_properties_widget:
        active_part_model: Optional[PartModel] = None
        active_mech_model: Optional[MechanismModel] = None

        if (
            self.active_mechanism_id
            and self.active_mechanism_id in self.current_mechanisms
        ):
            active_mech_model = self.current_mechanisms[self.active_mechanism_id]
            # self.mechanism_properties_widget.load_mechanism_data(active_mech_model)
            # self.mechanism_properties_widget.setVisible(True)
            # self.part_properties_widget.setVisible(False)
            self.properties_placeholder_label.setText(
                f"Editing Mechanism: {active_mech_model.name}\nType: {active_mech_model.type.value}"
            )

            if (
                self.selected_part_id_in_editor
                and self.current_character_model
                and self.selected_part_id_in_editor
                in self.current_character_model.parts
            ):
                active_part_model = self.current_character_model.parts[
                    self.selected_part_id_in_editor
                ]
                # self.part_properties_widget.load_part_data(active_part_model)
                # self.part_properties_widget.setVisible(True)
                # self.mechanism_properties_widget.setVisible(False) # Or show both, or tab them
                self.properties_placeholder_label.setText(
                    f"Selected Part: {active_part_model.name} (from Character)\nMechanism: {active_mech_model.name}"
                )
            # elif self.selected_part_id_in_editor and active_mech_model.parts and self.selected_part_id_in_editor in active_mech_model.parts:
            # Part might belong to the mechanism itself, not the character (e.g. a ground link)
            # active_part_model = active_mech_model.parts[self.selected_part_id_in_editor]
            # self.part_properties_widget.load_part_data(active_part_model)
            # self.part_properties_widget.setVisible(True)
            # self.properties_placeholder_label.setText(f"Selected Part: {active_part_model.name} (from Mechanism)")

        elif (
            self.selected_part_id_in_editor
            and self.current_character_model
            and self.selected_part_id_in_editor in self.current_character_model.parts
        ):
            # Only a character part selected, no active mechanism for it (yet)
            active_part_model = self.current_character_model.parts[
                self.selected_part_id_in_editor
            ]
            # self.part_properties_widget.load_part_data(active_part_model)
            # self.part_properties_widget.setVisible(True)
            # self.mechanism_properties_widget.setVisible(False)
            self.properties_placeholder_label.setText(
                f"Selected Part: {active_part_model.name} (from Character)\nNo active mechanism."
            )
        else:
            # self.part_properties_widget.setVisible(False)
            # self.mechanism_properties_widget.setVisible(False)
            self.properties_placeholder_label.setText(
                "Select a part or mechanism to see properties."
            )

        # Update EditorView
        if self.editor_view:
            if self.active_mechanism_id and active_mech_model:
                self.editor_view.load_mechanism(
                    active_mech_model,
                    (
                        self.current_character_model.parts
                        if self.current_character_model
                        else None
                    ),
                )
            elif self.current_character_model:
                # No active mechanism, but character loaded. Show character parts for potential mechanism creation.
                self.editor_view.load_parts_only(self.current_character_model.parts)
            else:
                self.editor_view.clear_scene()
                self.editor_view.set_background_text(
                    "Load a Character (from Image Proc. tab) or create a Mechanism."
                )

    # --- Slot Handlers for UI Interactions --- #

    def _on_part_tree_item_clicked(self, item: QTreeWidgetItem, column: int):
        part_id = item.data(0, Qt.ItemDataRole.UserRole)
        if (
            part_id
            and self.current_character_model
            and part_id in self.current_character_model.parts
        ):
            self.selected_part_id_in_editor = part_id  # Tentative selection
            self.part_selection_changed.emit(part_id)
            self.status_message_updated.emit(
                f"Part '{self.current_character_model.parts[part_id].name}' selected from tree."
            )
            # Add part to editor view if an active mechanism exists, or highlight it if already there
            if self.active_mechanism_id and self.editor_view:
                self.editor_view.add_part_to_scene(
                    self.current_character_model.parts[part_id]
                )
                self.editor_view.select_part_item(part_id)
            elif self.editor_view:  # No active mechanism, just show the part
                self.editor_view.select_part_item(
                    part_id
                )  # Assumes parts are already loaded if character is there
        self._update_ui_for_active_data()

    def _on_mechanism_tree_item_clicked(self, item: QTreeWidgetItem, column: int):
        mech_id = item.data(0, Qt.ItemDataRole.UserRole)
        if mech_id and mech_id in self.current_mechanisms:
            self.active_mechanism_id = mech_id
            self.selected_part_id_in_editor = (
                None  # Clear part selection when switching mechanisms
            )
            self.part_selection_changed.emit(None)
            self.status_message_updated.emit(
                f"Mechanism '{self.current_mechanisms[mech_id].name}' selected."
            )
        self._update_ui_for_active_data()

    def _on_part_selected_in_editor(self, part_id: Optional[str]):
        self.selected_part_id_in_editor = part_id
        self.part_selection_changed.emit(part_id)
        if (
            part_id
            and self.current_character_model
            and part_id in self.current_character_model.parts
        ):
            self.status_message_updated.emit(
                f"Part '{self.current_character_model.parts[part_id].name}' selected in editor."
            )
        elif (
            part_id
            and self.active_mechanism_id
            and self.current_mechanisms[self.active_mechanism_id].parts
            and part_id in self.current_mechanisms[self.active_mechanism_id].parts
        ):
            self.status_message_updated.emit(
                f"Part '{self.current_mechanisms[self.active_mechanism_id].parts[part_id].name}' (mechanism-specific) selected in editor."
            )
        else:
            self.status_message_updated.emit("Editor selection cleared.")
        self._update_ui_for_active_data()

    def _on_part_moved_in_editor(
        self, part_id: str, new_pos: QPointF, new_rotation: float, new_scale: float
    ):
        # Update the PartModel in self.current_character_model.parts or in mechanism's parts
        # And then update the properties widget if it's showing this part.
        # Also, if the part is part of a mechanism, this might affect mechanism kinematics.
        target_part_model: Optional[PartModel] = None
        if (
            self.current_character_model
            and part_id in self.current_character_model.parts
        ):
            target_part_model = self.current_character_model.parts[part_id]
        elif (
            self.active_mechanism_id
            and self.current_mechanisms[self.active_mechanism_id].parts
            and part_id in self.current_mechanisms[self.active_mechanism_id].parts
        ):
            target_part_model = self.current_mechanisms[self.active_mechanism_id].parts[
                part_id
            ]

        if target_part_model:
            target_part_model.x = new_pos.x()
            target_part_model.y = new_pos.y()
            target_part_model.rotation = new_rotation
            target_part_model.scale = new_scale
            logging.debug(
                f"Part '{part_id}' moved/scaled. New state: x={new_pos.x():.1f}, y={new_pos.y():.1f}, rot={new_rotation:.1f}, scale={new_scale:.2f}"
            )
            # if self.part_properties_widget and self.selected_part_id_in_editor == part_id:
            #     self.part_properties_widget.load_part_data(target_part_model) # Refresh properties view
            self._update_ui_for_active_data()  # Refresh placeholder if needed

            # If this part is part of the active mechanism, we might need to re-solve kinematics
            if self.active_mechanism_id and self.current_mechanisms[
                self.active_mechanism_id
            ].is_part_of_mechanism(part_id):
                self._solve_and_update_active_mechanism()
        else:
            logging.warning(
                f"Moved part '{part_id}' not found in character or active mechanism models."
            )

    def _on_mechanism_structure_changed_in_editor(
        self, mechanism_id: str, change_details: Dict[str, Any]
    ):
        # E.g., a link added, joint connected, parameter changed through editor interaction
        if mechanism_id in self.current_mechanisms:
            active_mech = self.current_mechanisms[mechanism_id]
            # Apply changes from change_details to active_mech model
            # This is a placeholder for more specific update logic based on `change_details`
            logging.info(
                f"Mechanism '{mechanism_id}' structure changed via editor: {change_details}"
            )
            # Example: if a joint position was changed, update the point in the model.
            if "joint_updated" in change_details:
                joint_update_info = change_details[
                    "joint_updated"
                ]  # { 'joint_id': ..., 'new_pos': QPointF(...) }
                if (
                    hasattr(active_mech, "points")
                    and joint_update_info["joint_id"] in active_mech.points
                ):
                    active_mech.points[joint_update_info["joint_id"]] = (
                        joint_update_info["new_pos"]
                    )

            self._solve_and_update_active_mechanism()
            self.mechanism_data_updated.emit(active_mech)
            # if self.mechanism_properties_widget and self.active_mechanism_id == mechanism_id:
            #     self.mechanism_properties_widget.load_mechanism_data(active_mech)
            self._update_ui_for_active_data()  # Refresh placeholder if needed
        else:
            logging.warning(
                f"Structure change received for unknown mechanism_id: {mechanism_id}"
            )

    # --- Mechanism Creation Methods --- #

    def _create_new_mechanism_base(
        self, mech_type_enum, default_name_prefix: str
    ) -> Optional[MechanismModel]:
        if not self.current_character_model:
            QMessageBox.warning(
                self, "No Character", "A character must be loaded to create mechanisms."
            )
            return None

        new_mech_id = (
            f"{mech_type_enum.value.lower()}_{len(self.current_mechanisms) + 1}"
        )
        new_mech_name = f"{default_name_prefix} {len(self.current_mechanisms) + 1}"

        # Create a basic model instance based on type
        if mech_type_enum == LinkageMechanismModel.model_fields["type"].default:
            model = LinkageMechanismModel(
                id=new_mech_id, name=new_mech_name, type=mech_type_enum
            )
        elif mech_type_enum == CamMechanismModel.model_fields["type"].default:
            model = CamMechanismModel(
                id=new_mech_id, name=new_mech_name, type=mech_type_enum
            )
        elif mech_type_enum == GearMechanismModel.model_fields["type"].default:
            model = GearMechanismModel(
                id=new_mech_id, name=new_mech_name, type=mech_type_enum
            )
        else:
            logging.error(f"Unsupported mechanism type for creation: {mech_type_enum}")
            QMessageBox.critical(
                self, "Error", f"Cannot create mechanism of type: {mech_type_enum}"
            )
            return None

        self.current_mechanisms[new_mech_id] = model
        self.active_mechanism_id = new_mech_id
        self.status_message_updated.emit(f"Created new mechanism: {new_mech_name}")
        logging.info(
            f"Created new {mech_type_enum.value} mechanism: {new_mech_id} - '{new_mech_name}'"
        )
        self._update_ui_for_active_data()
        self.editor_view.set_mode(
            "edit_mechanism"
        )  # Switch editor to mechanism editing mode
        return model

    def _create_new_linkage_mechanism(self):
        self._create_new_mechanism_base(
            LinkageMechanismModel.model_fields["type"].default, "Linkage"
        )

    def _create_new_cam_mechanism(self):
        self._create_new_mechanism_base(
            CamMechanismModel.model_fields["type"].default, "Cam-Follower"
        )

    def _create_new_gear_mechanism(self):
        self._create_new_mechanism_base(
            GearMechanismModel.model_fields["type"].default, "Gear Pair"
        )

    # --- Data Handling & External Calls --- #

    def load_character_for_design(self, character_model: CharacterModel):
        self.current_character_model = character_model
        self.current_mechanisms.clear()  # Clear mechanisms from previous character
        self.active_mechanism_id = None
        self.selected_part_id_in_editor = None
        self.part_selection_changed.emit(None)

        self.status_message_updated.emit(
            f"Character '{character_model.name}' loaded for design."
        )
        logging.info(
            f"DesignerTab: Loaded character '{character_model.name}' (ID: {character_model.id})."
        )
        self._update_ui_for_active_data()
        # If character has pre-existing mechanisms, load them
        # if character_model.mechanisms:
        #     for mech_id, mech_data_dict in character_model.mechanisms.items():
        #         # Need to deserialize mech_data_dict into appropriate Pydantic model
        #         # mech_model = deserialize_mechanism_model(mech_data_dict) # Placeholder
        #         # if mech_model: self.current_mechanisms[mech_id] = mech_model
        #     self._update_ui_for_active_data()

    def get_current_mechanisms_for_export(self) -> Dict[str, Dict[str, Any]]:
        """Serializes current mechanisms to dicts for project saving."""
        exported_mechanisms = {}
        for mech_id, mech_model in self.current_mechanisms.items():
            exported_mechanisms[mech_id] = mech_model.model_dump(exclude_none=True)
        return exported_mechanisms

    def load_mechanisms_from_project_data(
        self, mechanisms_data: Dict[str, Dict[str, Any]]
    ):
        """Loads mechanisms from project file data (deserialized Pydantic models)."""
        self.current_mechanisms.clear()
        for mech_id, data_dict in mechanisms_data.items():
            # This requires robust deserialization based on 'type' field in data_dict
            # model_type_str = data_dict.get('type')
            # mech_model: Optional[MechanismModel] = None
            # if model_type_str == LinkageMechanismModel.model_fields['type'].default.value:
            #     mech_model = LinkageMechanismModel(**data_dict)
            # elif model_type_str == CamMechanismModel.model_fields['type'].default.value:
            #     mech_model = CamMechanismModel(**data_dict)
            # elif model_type_str == GearMechanismModel.model_fields['type'].default.value:
            #     mech_model = GearMechanismModel(**data_dict)
            # else:
            #     logging.warning(f"Unknown mechanism type '{model_type_str}' during project load for id {mech_id}")

            # Simplified approach if Pydantic models are directly passed (not dicts)
            # This depends on how MainWindow manages project loading/saving
            if isinstance(data_dict, MechanismModel):
                self.current_mechanisms[mech_id] = (
                    data_dict  # if data_dict is already a model instance
                )
            else:  # If it's a dict, need to parse (example above)
                logging.warning(
                    f"Mechanism data for {mech_id} is a dict, needs robust parsing. Skipping for now."
                )
                pass  # Implement robust parsing

        self.active_mechanism_id = None
        if self.current_mechanisms:
            self.active_mechanism_id = list(self.current_mechanisms.keys())[
                0
            ]  # Activate first one

        logging.info(
            f"Loaded {len(self.current_mechanisms)} mechanisms into DesignerTab from project data."
        )
        self._update_ui_for_active_data()

    def _solve_and_update_active_mechanism(self):
        if (
            not self.active_mechanism_id
            or self.active_mechanism_id not in self.current_mechanisms
        ):
            return

        mech_model = self.current_mechanisms[self.active_mechanism_id]
        # Placeholder: Call a kinematics solver based on mech_model.type
        # e.g., LinkageSolver.solve(mech_model)
        # The solver would update points, paths, etc., within the mech_model instance.
        logging.debug(
            f"Placeholder: Solving kinematics for mechanism '{mech_model.name}'"
        )

        # After solving, update the EditorView to reflect changes
        if self.editor_view:
            self.editor_view.update_mechanism_visualization(mech_model)

        # Potentially emit mechanism_data_updated if solution leads to significant changes
        self.mechanism_data_updated.emit(mech_model)
