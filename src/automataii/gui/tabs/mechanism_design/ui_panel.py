# mechanism_design/ui_panel.py

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QPushButton, QListWidget, 
    QListWidgetItem, QHBoxLayout, QScrollArea, QLabel, QStyle, QCheckBox
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QBrush, QColor

class MechanismControlPanel(QWidget):
    """
    (View) 메커니즘 탭의 좌측 컨트롤 패널 UI.
    - UI 요소 생성 및 레이아웃 담당
    - 사용자 액션 발생 시 시그널(예: recommendation_requested) 발생
    - 외부 상태 변경에 따라 UI를 업데이트하는 슬롯 제공
    """
    recommendation_requested = pyqtSignal()
    play_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()
    reset_clicked = pyqtSignal()
    parametric_mode_toggled = pyqtSignal(bool)
    export_blueprint_requested = pyqtSignal()
    part_selected = pyqtSignal(str)
    part_toggled = pyqtSignal(str)
    mechanism_toggled = pyqtSignal(str) # mechanism_id
    debug_mode_toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = parent.state # Get state from parent tab
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFixedWidth(300)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        control_panel = QWidget()
        panel_layout = QVBoxLayout(control_panel)
        panel_layout.setContentsMargins(10, 10, 10, 10)
        panel_layout.setSpacing(15)

        # 1. Parts List Group
        parts_group = QGroupBox("1. Parts for Mechanisms")
        parts_group.setStyleSheet("""
            QGroupBox {
                background-color: #ffffff;
                border: 1px solid #e3e9f0;
                border-radius: 9px;
                padding: 18px;
                margin-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 10px;
                margin-left: 15px;
                font-size: 12pt;
                font-weight: bold;
                color: #5c85d6;
                background-color: #ffffff;
            }
        """)
        parts_layout = QVBoxLayout(parts_group)
        self.parts_list = QListWidget()
        self.parts_list.setToolTip("Click to toggle mechanism generation for a part. Black text: path available. Gray text: no path.")
        self.parts_list.setMinimumHeight(180)
        self.parts_list.setStyleSheet("""
            QListWidget {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                padding: 4px;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 8px 12px;
                margin: 2px;
                border-radius: 4px;
                border: 1px solid transparent;
            }
            QListWidget::item:selected {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #0078D7, stop: 1 #005a9e);
                color: white;
                border: 1px solid #004578;
            }
            QListWidget::item:hover {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
            }
        """)
        parts_layout.addWidget(self.parts_list)
        panel_layout.addWidget(parts_group)

        # 2. Mechanism Generation Group
        generation_group = QGroupBox("2. Mechanism Generation")
        generation_group.setStyleSheet(parts_group.styleSheet()) # Reuse style
        generation_layout = QVBoxLayout(generation_group)

        self.recommendation_btn = QPushButton("Get Mechanism")
        self.recommendation_btn.setEnabled(False)
        self.recommendation_btn.setToolTip("Get mechanism recommendations for the selected part")
        self.recommendation_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60; color: white; border: none;
                padding: 8px 16px; border-radius: 4px; font-size: 13px;
            }
            QPushButton:hover { background-color: #229954; }
            QPushButton:disabled { background-color: #bdc3c7; color: #7f8c8d; }
        """)
        generation_layout.addWidget(self.recommendation_btn)

        self.parametric_mode_btn = QPushButton("Parametric Edit")
        self.parametric_mode_btn.setToolTip("Enable interactive parameter editing")
        self.parametric_mode_btn.setEnabled(False)
        self.parametric_mode_btn.setCheckable(True)
        self.parametric_mode_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db; color: white; border: none;
                padding: 8px 16px; border-radius: 4px; font-size: 13px;
            }
            QPushButton:hover { background-color: #2980b9; }
            QPushButton:checked { background-color: #e74c3c; }
            QPushButton:disabled { background-color: #bdc3c7; color: #7f8c8d; }
        """)
        generation_layout.addWidget(self.parametric_mode_btn)
        panel_layout.addWidget(generation_group)

        # 3. Animation Group
        animation_group = QGroupBox("3. Animation")
        animation_group.setStyleSheet(parts_group.styleSheet()) # Reuse style
        animation_layout = QVBoxLayout(animation_group)
        
        style = self.style()
        anim_button_layout = QHBoxLayout()
        anim_button_layout.setSpacing(12)

        self.play_btn = QPushButton(style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay), "")
        self.play_btn.setToolTip("Play Animation")
        self.play_btn.setEnabled(False)

        self.stop_btn = QPushButton(style.standardIcon(QStyle.StandardPixmap.SP_MediaStop), "")
        self.stop_btn.setToolTip("Stop Animation")
        self.stop_btn.setEnabled(False)

        self.reset_btn = QPushButton(style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload), "")
        self.reset_btn.setToolTip("Reset Animation")
        self.reset_btn.setEnabled(False)

        anim_button_layout.addStretch()
        anim_button_layout.addWidget(self.play_btn)
        anim_button_layout.addWidget(self.stop_btn)
        anim_button_layout.addWidget(self.reset_btn)
        anim_button_layout.addStretch()

        animation_layout.addLayout(anim_button_layout)
        panel_layout.addWidget(animation_group)

        # 4. Blueprint Export Group
        export_group = QGroupBox("4. Blueprint Export")
        export_group.setStyleSheet(parts_group.styleSheet()) # Reuse style
        export_layout = QVBoxLayout(export_group)

        self.export_blueprint_btn = QPushButton("Export Blueprint")
        self.export_blueprint_btn.setEnabled(False)
        self.export_blueprint_btn.setToolTip("Export character and mechanisms to SVG")
        self.export_blueprint_btn.setStyleSheet("""
            QPushButton {
                background-color: #8e44ad; color: white; border: none;
                padding: 8px 16px; border-radius: 4px; font-size: 13px;
            }
            QPushButton:hover { background-color: #7d3c98; }
            QPushButton:disabled { background-color: #bdc3c7; color: #7f8c8d; }
        """)
        export_layout.addWidget(self.export_blueprint_btn)
        
        info_label = QLabel("Exports to a single large-format blueprint (1200x1600mm)")
        info_label.setStyleSheet("color: #666; font-size: 10px; font-style: italic;")
        export_layout.addWidget(info_label)
        panel_layout.addWidget(export_group)

        # 5. Debug Group
        debug_group = QGroupBox("5. Debug")
        debug_group.setStyleSheet(parts_group.styleSheet())
        debug_layout = QVBoxLayout(debug_group)
        self.debug_mode_checkbox = QCheckBox("Show Debug Visuals")
        debug_layout.addWidget(self.debug_mode_checkbox)
        panel_layout.addWidget(debug_group)

        panel_layout.addStretch(1)
        scroll_area.setWidget(control_panel)
        main_layout.addWidget(scroll_area)

    def _connect_signals(self):
        self.recommendation_btn.clicked.connect(self.recommendation_requested)
        self.play_btn.clicked.connect(self.play_clicked)
        self.stop_btn.clicked.connect(self.stop_clicked)
        self.reset_btn.clicked.connect(self.reset_clicked)
        self.parametric_mode_btn.toggled.connect(self.parametric_mode_toggled)
        self.export_blueprint_btn.clicked.connect(self.export_blueprint_requested)
        self.debug_mode_checkbox.toggled.connect(self.debug_mode_toggled)
        
        self.parts_list.itemClicked.connect(self._on_part_item_clicked)
        self.parts_list.itemSelectionChanged.connect(self._on_selection_changed)

    def _on_part_item_clicked(self, item: QListWidgetItem):
        part_name = item.data(Qt.ItemDataRole.UserRole)
        mechanism_id = item.data(Qt.ItemDataRole.UserRole + 1)

        if mechanism_id:
            self.mechanism_toggled.emit(mechanism_id)
        else:
            self.part_toggled.emit(part_name)

    def _on_selection_changed(self):
        selected_items = self.parts_list.selectedItems()
        if selected_items:
            part_name = selected_items[0].data(Qt.ItemDataRole.UserRole)
            self.part_selected.emit(part_name)
        else:
            self.part_selected.emit("")

    def update_ui_from_state(self):
        """Updates the entire UI panel based on the current state."""
        self._update_parts_list()
        self._update_button_states()

    def _update_parts_list(self):
        """Updates only the parts list widget, blocking signals to prevent recursion."""
        self.parts_list.blockSignals(True)
        
        current_selection = self.state.selected_part_name
        
        self.parts_list.clear()
        # Sort to show parts with paths first, then by name
        sorted_parts = sorted(
            self.state.parts_data.keys(), 
            key=lambda p: (p not in self.state.path_data, p)
        )
        
        item_to_select = None
        for name in sorted_parts:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, name)
            
            has_path = name in self.state.path_data and self.state.path_data[name] and not self.state.path_data[name].isEmpty()
            part_is_enabled = self.state.part_enabled_state.get(name, False)
            
            mechanism_id = None
            mechanism_is_enabled = False
            for mid, layer in self.state.mechanism_layers.items():
                if layer.get("part_name") == name:
                    mechanism_id = mid
                    mechanism_is_enabled = self.state.mechanism_enabled_state.get(mid, False)
                    break

            item.setData(Qt.ItemDataRole.UserRole + 1, mechanism_id)

            if mechanism_id:
                color = QColor("#27ae60") if mechanism_is_enabled else QColor("#9b59b6")
                item.setForeground(QBrush(color))
                item.setText(f"{name} (Mechanism {'On' if mechanism_is_enabled else 'Off'})")
            elif has_path:
                color = QColor("black") if part_is_enabled else QColor("gray")
                item.setForeground(QBrush(color))
                item.setText(name)
            else:
                item.setForeground(QBrush(QColor("lightgray")))
                item.setText(name)

            self.parts_list.addItem(item)
            if name == current_selection:
                item_to_select = item
        
        if item_to_select:
            item_to_select.setSelected(True)

        self.parts_list.blockSignals(False)

    def _update_button_states(self):
        """Updates the enabled state of the panel's buttons."""
        has_enabled_paths = any(
            self.state.part_enabled_state.get(name) for name, path in self.state.path_data.items() if path and not path.isEmpty()
        )
        has_mechanisms = bool(self.state.mechanism_layers)
        
        self.recommendation_btn.setEnabled(has_enabled_paths and bool(self.state.selected_part_name))
        self.play_btn.setEnabled(has_mechanisms)
        self.stop_btn.setEnabled(has_mechanisms)
        self.reset_btn.setEnabled(has_mechanisms)
        self.parametric_mode_btn.setEnabled(has_mechanisms)
        self.export_blueprint_btn.setEnabled(has_mechanisms)
