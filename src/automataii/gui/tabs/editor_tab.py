from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QGroupBox, QComboBox, QDoubleSpinBox, QCheckBox,
    QFormLayout, QListWidget, QScrollArea, QSizePolicy, QLabel
)
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt

from ..editor_view import EditorView # Assuming EditorView is in the parent directory

class EditorTab(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)

        # Left Control Panel
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFixedWidth(280)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        control_panel = QWidget()
        control_panel.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        panel_layout = QVBoxLayout(control_panel)
        panel_layout.setContentsMargins(10, 10, 10, 10)
        panel_layout.setSpacing(12)

        # Parts List Group
        parts_group = QGroupBox("Character Parts")
        parts_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        parts_layout = QVBoxLayout(parts_group)
        self.main_window.parts_list = QListWidget()
        self.main_window.parts_list.setToolTip("List of loaded character parts")
        self.main_window.parts_list.setMinimumHeight(100)
        parts_layout.addWidget(self.main_window.parts_list)
        panel_layout.addWidget(parts_group)

        # Selected Part Properties Group
        self.main_window.part_properties_group = QGroupBox("Selected Part Properties")
        self.main_window.part_properties_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.main_window.part_props = QFormLayout(self.main_window.part_properties_group)
        self.main_window.part_props.setSpacing(8)
        self.main_window.z_value_spin = QDoubleSpinBox()
        self.main_window.z_value_spin.setRange(-100, 100)
        self.main_window.z_value_spin.setSingleStep(0.1)
        self.main_window.z_value_spin.setToolTip("Adjust Z-depth (layering)")
        self.main_window.z_value_spin.setEnabled(False)
        self.main_window.fixed_part_check = QCheckBox("Fixed in Place")
        self.main_window.fixed_part_check.setToolTip("If checked, this part will not move during simulation (unless it is the root of a chain being driven by IK).")
        self.main_window.fixed_part_check.setEnabled(False)
        self.main_window.part_props.addRow("Z-Value:", self.main_window.z_value_spin)
        self.main_window.part_props.addRow(self.main_window.fixed_part_check)
        self.main_window.part_properties_group.setEnabled(False)
        self.main_window.part_properties_group.setVisible(False)
        panel_layout.addWidget(self.main_window.part_properties_group)

        # # Assembly & Joints Group
        # assembly_group = QGroupBox("Assembly & Joints")
        # assembly_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        # assembly_layout = QHBoxLayout(assembly_group)
        # assembly_layout.setSpacing(10)
        # self.main_window.define_joint_btn = QPushButton("Joint")
        # self.main_window.define_joint_btn.setCheckable(True)
        # self.main_window.define_joint_btn.setToolTip("Click two parts in the view to define a joint between them")
        # self.main_window.define_joint_btn.setEnabled(False)
        # self.main_window.show_skeleton_btn = QPushButton("Skeleton")
        # self.main_window.show_skeleton_btn.setCheckable(True)
        # self.main_window.show_skeleton_btn.setToolTip("Temporarily display the skeleton structure and auto-generated joints")
        # self.main_window.show_skeleton_btn.setEnabled(False)
        # assembly_layout.addWidget(self.main_window.define_joint_btn)
        # assembly_layout.addWidget(self.main_window.show_skeleton_btn)
        # panel_layout.addWidget(assembly_group)

        # Motion Path Definition Group
        motion_path_group = QGroupBox("Motion Path")
        motion_path_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        motion_path_layout = QVBoxLayout(motion_path_group)
        self.main_window.define_motion_path_btn = QPushButton("Define Motion Path")
        self.main_window.define_motion_path_btn.setCheckable(True)
        self.main_window.define_motion_path_btn.setToolTip("Toggle mode to draw a motion path for the selected part.")
        self.main_window.define_motion_path_btn.setEnabled(False)
        motion_path_layout.addWidget(self.main_window.define_motion_path_btn)
        self.main_window.clear_motion_path_btn = QPushButton("Clear Motion Path")
        self.main_window.clear_motion_path_btn.setToolTip("Clear the motion path for the selected part.")
        self.main_window.clear_motion_path_btn.setEnabled(False)
        motion_path_layout.addWidget(self.main_window.clear_motion_path_btn)
        panel_layout.addWidget(motion_path_group)

        # Motion & Simulation Group
        motion_sim_group = QGroupBox("Motion & Simulation")
        motion_sim_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        motion_sim_layout = QFormLayout(motion_sim_group)
        motion_sim_layout.setSpacing(10)
        sim_button_layout = QHBoxLayout()
        sim_button_layout.setSpacing(6)
        style = self.style() # Or self.main_window.style()
        self.main_window.play_btn = QPushButton(style.standardIcon(self.main_window.style().StandardPixmap.SP_MediaPlay), "")
        self.main_window.play_btn.setToolTip("Play Simulation")
        self.main_window.stop_btn = QPushButton(style.standardIcon(self.main_window.style().StandardPixmap.SP_MediaStop), "")
        self.main_window.stop_btn.setToolTip("Stop Simulation")
        self.main_window.stop_btn.setEnabled(False)
        self.main_window.reset_sim_btn = QPushButton(style.standardIcon(self.main_window.style().StandardPixmap.SP_BrowserReload), "")
        self.main_window.reset_sim_btn.setToolTip("Restart Simulation")
        self.main_window.reset_sim_btn.setEnabled(False)
        sim_button_layout.addWidget(self.main_window.play_btn)
        sim_button_layout.addWidget(self.main_window.stop_btn)
        sim_button_layout.addWidget(self.main_window.reset_sim_btn)
        motion_sim_layout.addRow(sim_button_layout)
        panel_layout.addWidget(motion_sim_group)

        # Mechanism Design Group
        mech_design_group = QGroupBox("Mechanism Design")
        mech_design_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        mech_design_layout = QVBoxLayout(mech_design_group)
        mech_design_layout.setSpacing(10)
        self.main_window.toggle_anchors_btn = QCheckBox("Show Test Anchors")
        self.main_window.toggle_anchors_btn.setToolTip("Show/hide draggable test anchor points in the scene.")
        mech_design_layout.addWidget(self.main_window.toggle_anchors_btn)
        mech_type_layout = QFormLayout()
        self.main_window.mechanism_type_combo = QComboBox()
        self.main_window.mechanism_type_combo.addItems([
            "Cam & Follower", "3-Bar Linkage", "4-Bar Linkage", "Gears (Simple Pair)"
        ])
        self.main_window.mechanism_type_combo.setToolTip("Select the type of mechanism to generate")
        mech_type_layout.addRow("Type:", self.main_window.mechanism_type_combo)
        mech_design_layout.addLayout(mech_type_layout)
        self.main_window.mech_inputs_container = QWidget()
        self.main_window.mech_inputs_layout = QVBoxLayout(self.main_window.mech_inputs_container)
        self.main_window.mech_inputs_layout.setContentsMargins(0, 5, 0, 0)
        self.main_window.mech_inputs_layout.setSpacing(8)
        mech_design_layout.addWidget(self.main_window.mech_inputs_container)
        self.main_window.cam_inputs_group = QGroupBox("Cam Settings")
        cam_inputs_layout = QVBoxLayout(self.main_window.cam_inputs_group)
        self.main_window.select_cam_center_btn = QPushButton("Select Cam Center")
        self.main_window.select_cam_center_btn.setToolTip("Click in the scene to set the cam rotation center (default: torso center)")
        cam_inputs_layout.addWidget(self.main_window.select_cam_center_btn)
        self.main_window.mech_inputs_layout.addWidget(self.main_window.cam_inputs_group)
        self.main_window.three_bar_inputs_group = QGroupBox("3-Bar Linkage Settings")
        three_bar_layout = QVBoxLayout(self.main_window.three_bar_inputs_group)
        self.main_window.select_pivot_a_3bar_btn = QPushButton("Select Fixed Pivot A")
        self.main_window.select_pivot_a_3bar_btn.setToolTip("Click in the scene to set the first fixed pivot")
        three_bar_layout.addWidget(self.main_window.select_pivot_a_3bar_btn)
        self.main_window.mech_inputs_layout.addWidget(self.main_window.three_bar_inputs_group)
        self.main_window.four_bar_inputs_group = QGroupBox("4-Bar Linkage Settings")
        four_bar_layout = QVBoxLayout(self.main_window.four_bar_inputs_group)
        self.main_window.select_pivot_a_4bar_btn = QPushButton("Select Fixed Pivot A")
        self.main_window.select_pivot_a_4bar_btn.setToolTip("Click in the scene to set the first fixed pivot")
        four_bar_layout.addWidget(self.main_window.select_pivot_a_4bar_btn)
        self.main_window.select_pivot_d_4bar_btn = QPushButton("Select Fixed Pivot D")
        self.main_window.select_pivot_d_4bar_btn.setToolTip("Click in the scene to set the second fixed pivot")
        four_bar_layout.addWidget(self.main_window.select_pivot_d_4bar_btn)
        self.main_window.mech_inputs_layout.addWidget(self.main_window.four_bar_inputs_group)
        self.main_window.gear_inputs_group = QGroupBox("Gear Settings")
        gear_inputs_layout = QFormLayout(self.main_window.gear_inputs_group)
        gear_button_layout = QHBoxLayout()
        self.main_window.select_driver_center_btn = QPushButton("Driver Center")
        self.main_window.select_driver_center_btn.setToolTip("Click to set driver gear center")
        self.main_window.select_driven_center_btn = QPushButton("Driven Center")
        self.main_window.select_driven_center_btn.setToolTip("Click to set driven gear center")
        gear_button_layout.addWidget(self.main_window.select_driver_center_btn)
        gear_button_layout.addWidget(self.main_window.select_driven_center_btn)
        gear_inputs_layout.addRow("Select Centers:", gear_button_layout)
        self.main_window.gear_ratio_spin = QDoubleSpinBox()
        self.main_window.gear_ratio_spin.setRange(0.01, 100.0)
        self.main_window.gear_ratio_spin.setSingleStep(0.1)
        self.main_window.gear_ratio_spin.setValue(1.0)
        self.main_window.gear_ratio_spin.setToolTip("Set gear ratio (Driven Radius / Driver Radius)")
        gear_inputs_layout.addRow("Gear Ratio:", self.main_window.gear_ratio_spin)
        self.main_window.mech_inputs_layout.addWidget(self.main_window.gear_inputs_group)
        self.main_window.generate_mechanism_btn = QPushButton("Generate Mechanism")
        self.main_window.generate_mechanism_btn.setToolTip("Generate the selected mechanism based on the current setup")
        self.main_window.generate_mechanism_btn.setEnabled(False)
        mech_design_layout.addWidget(self.main_window.generate_mechanism_btn)
        mech_design_layout.addStretch()
        panel_layout.addWidget(mech_design_group)

        self.main_window._update_mechanism_inputs_ui(self.main_window.mechanism_type_combo.currentText()) # Call method on main_window

        # Mechanism Layers Group
        self.main_window.layer_group = QGroupBox("Mechanism Layers")
        self.main_window.layer_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.main_window.layer_layout = QVBoxLayout(self.main_window.layer_group)
        self.main_window.layer_layout.setSpacing(6)
        panel_layout.addWidget(self.main_window.layer_group)

        # Export Group
        export_group = QGroupBox("Export")
        export_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        export_layout = QVBoxLayout(export_group)
        self.main_window.blueprint_btn = QPushButton(" Generate Blueprint (SVG)")
        self.main_window.blueprint_btn.setToolTip("Generate an SVG blueprint of all parts for fabrication")
        export_layout.addWidget(self.main_window.blueprint_btn)
        panel_layout.addWidget(export_group)

        # Character Alignment Group
        alignment_group = QGroupBox("Character Alignment")
        alignment_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        alignment_layout = QVBoxLayout(alignment_group)
        self.main_window.save_alignment_btn = QPushButton("Save Current Alignment")
        self.main_window.save_alignment_btn.setToolTip("Save the current character position as the default alignment for this character.")
        self.main_window.save_alignment_btn.setEnabled(False)
        alignment_layout.addWidget(self.main_window.save_alignment_btn)
        panel_layout.addWidget(alignment_group)

        panel_layout.addStretch()
        scroll_area.setWidget(control_panel)

        # Right View Area (Editor)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(5, 5, 5, 5)
        right_layout.setSpacing(5)

        zoom_toolbar = QWidget()
        zoom_layout = QHBoxLayout(zoom_toolbar)
        zoom_layout.setContentsMargins(10, 8, 10, 8)
        zoom_layout.setSpacing(8)
        zoom_layout.addStretch()

        self.main_window.zoom_combo = QComboBox()
        self.main_window.zoom_combo.setEditable(True)
        self.main_window.zoom_combo.setFixedSize(70, 28)
        self.main_window.zoom_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #d0d7de;
                border-radius: 6px;
                padding: 4px 8px;
                background-color: white;
                font-size: 12px;
            }
            QComboBox:hover {
                border-color: #586069;
            }
        """)
        zoom_levels = ["50%", "75%", "90%", "100%", "125%", "150%", "200%"]
        self.main_window.zoom_combo.addItems(zoom_levels)
        self.main_window.zoom_combo.setCurrentText("100%")
        self.main_window.zoom_combo.setToolTip("Zoom level")

        self.main_window.fit_btn = QPushButton("Fit")
        self.main_window.fit_btn.setFixedSize(45, 28)
        self.main_window.fit_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid #d0d7de;
                border-radius: 6px;
                padding: 4px 8px;
                background-color: white;
                font-size: 12px;
                color: #24292f;
            }
            QPushButton:hover {
                background-color: #f6f8fa;
                border-color: #586069;
            }
            QPushButton:pressed {
                background-color: #e9ecef;
            }
        """)
        self.main_window.fit_btn.setToolTip("Zoom to fit all items")

        zoom_layout.addWidget(self.main_window.zoom_combo)
        zoom_layout.addWidget(self.main_window.fit_btn)

        # The scene and view are managed by the main_window
        right_layout.addWidget(self.main_window.editor_view, 1)

        zoom_toolbar.setParent(right_panel)
        zoom_toolbar.setStyleSheet("""
            QWidget {
                background-color: rgba(248, 249, 250, 0.9);
                border: 1px solid rgba(208, 215, 222, 0.8);
                border-radius: 8px;
            }
        """)
        zoom_toolbar.show()

        def position_editor_zoom_toolbar():
            toolbar_width = zoom_toolbar.sizeHint().width()
            toolbar_height = zoom_toolbar.sizeHint().height()
            x = right_panel.width() - toolbar_width - 20
            y = right_panel.height() - toolbar_height - 20
            zoom_toolbar.setGeometry(x, y, toolbar_width, toolbar_height)

        original_show_event = right_panel.showEvent
        def new_show_event(event):
            original_show_event(event)
            position_editor_zoom_toolbar()
        right_panel.showEvent = new_show_event

        original_resize_event = right_panel.resizeEvent
        def new_resize_event(event):
            original_resize_event(event)
            position_editor_zoom_toolbar()
        right_panel.resizeEvent = new_resize_event

        layout.addWidget(scroll_area)
        layout.addWidget(right_panel, 1)
        self.setLayout(layout)