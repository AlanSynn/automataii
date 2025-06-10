import logging
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QGroupBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QMessageBox,
)
from PyQt6.QtCore import pyqtSignal, QPointF
from PyQt6.QtCore import pyqtSlot
from PyQt6.QtGui import QPainterPath

from ..views.editor_view import EditorView
from PyQt6.QtWidgets import QGraphicsScene
from automataii.core.models import PartInfo

from ..dialogs.recommendation_dialog import (
    MECHANISM_TYPE_USER_DISPLAY_4_BAR,
    MECHANISM_TYPE_USER_DISPLAY_3_BAR,
    MECHANISM_TYPE_USER_DISPLAY_CAM,
)


class MechanismDesignTab(QWidget):
    """탭 전용 매커니즘 디자인 및 생성 기능"""
    
    # Signals for mechanism-related operations
    request_generate_mechanism = pyqtSignal(str, dict)  # mechanism_type, params
    request_generate_blueprint = pyqtSignal()
    mechanism_selection_changed = pyqtSignal(str)  # mechanism_type
    
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.debug_mode = getattr(main_window, "debug_mode", False)
        
        # Path data from editor tab
        self.path_data: Dict[str, QPainterPath] = {}
        self.selected_part_name: Optional[str] = None
        
        # Mechanism generation state
        self.current_mechanism_type: Optional[str] = None
        self.mechanism_params: Dict[str, Any] = {}
        
        # Graphics scene for mechanism preview
        self.mechanism_scene = QGraphicsScene(self)
        self.mechanism_view = EditorView(self.mechanism_scene, self)
        
        # UI Elements
        self.mechanism_type_combo: Optional[QComboBox] = None
        self.generate_mechanism_btn: Optional[QPushButton] = None
        self.mechanism_preview_group: Optional[QGroupBox] = None
        self.mechanism_params_group: Optional[QGroupBox] = None
        self.parts_selection_combo: Optional[QComboBox] = None
        self.blueprint_btn: Optional[QPushButton] = None
        
        # Mechanism parameters widgets
        self.cam_center_x_spin: Optional[QDoubleSpinBox] = None
        self.cam_center_y_spin: Optional[QDoubleSpinBox] = None
        self.cam_radius_spin: Optional[QDoubleSpinBox] = None
        self.linkage_length_spin: Optional[QDoubleSpinBox] = None
        self.gear_ratio_spin: Optional[QDoubleSpinBox] = None
        
        self._setup_ui()
        self._connect_signals()
        
    def _setup_ui(self):
        """UI 설정"""
        main_layout = QHBoxLayout(self)
        
        # Left panel - Controls
        left_panel = QWidget()
        left_panel.setMaximumWidth(300)
        left_layout = QVBoxLayout(left_panel)
        
        # Part selection
        part_selection_group = QGroupBox("타겟 파트 선택")
        part_selection_layout = QFormLayout(part_selection_group)
        
        self.parts_selection_combo = QComboBox()
        part_selection_layout.addRow("파트:", self.parts_selection_combo)
        
        left_layout.addWidget(part_selection_group)
        
        # Mechanism type selection
        mechanism_type_group = QGroupBox("매커니즘 타입")
        mechanism_type_layout = QFormLayout(mechanism_type_group)
        
        self.mechanism_type_combo = QComboBox()
        self.mechanism_type_combo.addItems([
            MECHANISM_TYPE_USER_DISPLAY_4_BAR,
            MECHANISM_TYPE_USER_DISPLAY_3_BAR,
            MECHANISM_TYPE_USER_DISPLAY_CAM,
            "Gear System",
            "Custom Linkage"
        ])
        mechanism_type_layout.addRow("타입:", self.mechanism_type_combo)
        
        left_layout.addWidget(mechanism_type_group)
        
        # Mechanism parameters
        self.mechanism_params_group = QGroupBox("매커니즘 파라미터")
        self._setup_mechanism_params()
        left_layout.addWidget(self.mechanism_params_group)
        
        # Generation buttons
        buttons_group = QGroupBox("생성")
        buttons_layout = QVBoxLayout(buttons_group)
        
        self.generate_mechanism_btn = QPushButton("매커니즘 생성")
        self.generate_mechanism_btn.setEnabled(False)
        buttons_layout.addWidget(self.generate_mechanism_btn)
        
        self.blueprint_btn = QPushButton("블루프린트 생성")
        self.blueprint_btn.setEnabled(False)
        buttons_layout.addWidget(self.blueprint_btn)
        
        left_layout.addWidget(buttons_group)
        left_layout.addStretch()
        
        # Right panel - Preview
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        self.mechanism_preview_group = QGroupBox("매커니즘 미리보기")
        preview_layout = QVBoxLayout(self.mechanism_preview_group)
        preview_layout.addWidget(self.mechanism_view)
        
        right_layout.addWidget(self.mechanism_preview_group)
        
        # Add panels to main layout
        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel, 1)
        
    def _setup_mechanism_params(self):
        """매커니즘 파라미터 UI 설정"""
        params_layout = QFormLayout(self.mechanism_params_group)
        
        # Cam parameters
        self.cam_center_x_spin = QDoubleSpinBox()
        self.cam_center_x_spin.setRange(-1000, 1000)
        self.cam_center_x_spin.setValue(0)
        params_layout.addRow("캠 중심 X:", self.cam_center_x_spin)
        
        self.cam_center_y_spin = QDoubleSpinBox()
        self.cam_center_y_spin.setRange(-1000, 1000)
        self.cam_center_y_spin.setValue(0)
        params_layout.addRow("캠 중심 Y:", self.cam_center_y_spin)
        
        self.cam_radius_spin = QDoubleSpinBox()
        self.cam_radius_spin.setRange(10, 500)
        self.cam_radius_spin.setValue(50)
        params_layout.addRow("캠 반지름:", self.cam_radius_spin)
        
        # Linkage parameters
        self.linkage_length_spin = QDoubleSpinBox()
        self.linkage_length_spin.setRange(10, 500)
        self.linkage_length_spin.setValue(100)
        params_layout.addRow("링키지 길이:", self.linkage_length_spin)
        
        # Gear parameters
        self.gear_ratio_spin = QDoubleSpinBox()
        self.gear_ratio_spin.setRange(0.1, 10.0)
        self.gear_ratio_spin.setValue(1.0)
        self.gear_ratio_spin.setSingleStep(0.1)
        params_layout.addRow("기어비:", self.gear_ratio_spin)
        
    def _connect_signals(self):
        """시그널 연결"""
        self.mechanism_type_combo.currentTextChanged.connect(self._on_mechanism_type_changed)
        self.parts_selection_combo.currentTextChanged.connect(self._on_part_selection_changed)
        self.generate_mechanism_btn.clicked.connect(self._on_generate_mechanism)
        self.blueprint_btn.clicked.connect(self._on_generate_blueprint)
        
        # Parameter changes
        self.cam_center_x_spin.valueChanged.connect(self._on_params_changed)
        self.cam_center_y_spin.valueChanged.connect(self._on_params_changed)
        self.cam_radius_spin.valueChanged.connect(self._on_params_changed)
        self.linkage_length_spin.valueChanged.connect(self._on_params_changed)
        self.gear_ratio_spin.valueChanged.connect(self._on_params_changed)
        
    @pyqtSlot(str)
    def _on_mechanism_type_changed(self, mechanism_type: str):
        """매커니즘 타입 변경"""
        self.current_mechanism_type = mechanism_type
        self.mechanism_selection_changed.emit(mechanism_type)
        self._update_ui_for_mechanism_type()
        
    def _update_ui_for_mechanism_type(self):
        """선택된 매커니즘 타입에 따라 UI 업데이트"""
        if not self.current_mechanism_type:
            return
            
        # Enable/disable parameter widgets based on mechanism type
        is_cam = "Cam" in self.current_mechanism_type
        is_linkage = "Bar" in self.current_mechanism_type or "Linkage" in self.current_mechanism_type
        is_gear = "Gear" in self.current_mechanism_type
        
        if self.cam_center_x_spin is not None:
            self.cam_center_x_spin.setVisible(is_cam)
        if self.cam_center_y_spin is not None:
            self.cam_center_y_spin.setVisible(is_cam)
        if self.cam_radius_spin is not None:
            self.cam_radius_spin.setVisible(is_cam)
        if self.linkage_length_spin is not None:
            self.linkage_length_spin.setVisible(is_linkage)
        if self.gear_ratio_spin is not None:
            self.gear_ratio_spin.setVisible(is_gear)
        
        self._check_generation_requirements()
        
    @pyqtSlot(str)
    def _on_part_selection_changed(self, part_name: str):
        """타겟 파트 선택 변경"""
        self.selected_part_name = part_name
        self._check_generation_requirements()
        
    def _check_generation_requirements(self):
        """매커니즘 생성 요구사항 체크"""
        if self.generate_mechanism_btn is None:
            return  # UI not initialized yet
            
        can_generate = bool(
            self.selected_part_name and 
            self.current_mechanism_type and
            self.selected_part_name in self.path_data
        )
        self.generate_mechanism_btn.setEnabled(can_generate)
        
    @pyqtSlot()
    def _on_params_changed(self):
        """파라미터 변경"""
        self._update_mechanism_params()
        
    def _update_mechanism_params(self):
        """현재 파라미터 값들을 수집"""
        self.mechanism_params = {
            "target_part_name": self.selected_part_name,
            "cam_center": QPointF(
                self.cam_center_x_spin.value(),
                self.cam_center_y_spin.value()
            ),
            "cam_radius": self.cam_radius_spin.value(),
            "linkage_length": self.linkage_length_spin.value(),
            "gear_ratio": self.gear_ratio_spin.value(),
        }
        
    @pyqtSlot()
    def _on_generate_mechanism(self):
        """매커니즘 생성 요청"""
        if not self.selected_part_name or not self.current_mechanism_type:
            QMessageBox.warning(self, "경고", "파트와 매커니즘 타입을 선택해주세요.")
            return
            
        self._update_mechanism_params()
        
        # Convert display name to internal type
        mechanism_type_mapping = {
            MECHANISM_TYPE_USER_DISPLAY_4_BAR: "4_bar_linkage",
            MECHANISM_TYPE_USER_DISPLAY_3_BAR: "3_bar_linkage", 
            MECHANISM_TYPE_USER_DISPLAY_CAM: "cam",
            "Gear System": "gear",
            "Custom Linkage": "custom_linkage"
        }
        
        internal_type = mechanism_type_mapping.get(self.current_mechanism_type, "4_bar_linkage")
        
        logging.info(f"Generating mechanism: {internal_type} for part {self.selected_part_name}")
        self.request_generate_mechanism.emit(internal_type, self.mechanism_params)
        if self.blueprint_btn is not None:
            self.blueprint_btn.setEnabled(True)
        
    @pyqtSlot()
    def _on_generate_blueprint(self):
        """블루프린트 생성 요청"""
        self.request_generate_blueprint.emit()
        
    def set_path_data_from_editor(self, path_data: Dict[str, QPainterPath]):
        """에디터 탭에서 패스 데이터 받기"""
        self.path_data = path_data.copy()
        self._update_parts_selection()
        self._check_generation_requirements()
        
    def _update_parts_selection(self):
        """파트 선택 콤보박스 업데이트"""
        if self.parts_selection_combo is not None:
            self.parts_selection_combo.clear()
            if self.path_data:
                self.parts_selection_combo.addItems(list(self.path_data.keys()))
            
    def set_parts_data(self, parts_data: Dict[str, PartInfo]):
        """파트 데이터 설정 (에디터 탭과 동기화)"""
        if parts_data and self.parts_selection_combo is not None:
            part_names = list(parts_data.keys())
            self.parts_selection_combo.clear()
            self.parts_selection_combo.addItems(part_names)
            
    def clear_mechanism_data(self):
        """매커니즘 데이터 초기화"""
        self.path_data.clear()
        self.selected_part_name = None
        self.current_mechanism_type = None
        self.mechanism_params.clear()
        
        if self.parts_selection_combo is not None:
            self.parts_selection_combo.clear()
        if self.mechanism_scene is not None:
            self.mechanism_scene.clear()
        if self.generate_mechanism_btn is not None:
            self.generate_mechanism_btn.setEnabled(False)
        if self.blueprint_btn is not None:
            self.blueprint_btn.setEnabled(False)
        
    @pyqtSlot(dict)
    def handle_mechanism_visuals(self, mechanism_graphics_data: dict):
        """매커니즘 시각화 데이터 처리"""
        if not mechanism_graphics_data:
            return
            
        # Clear previous mechanism visuals
        self.mechanism_scene.clear()
        
        # Add mechanism graphics to preview
        for item_data in mechanism_graphics_data.get("graphics_items", []):
            # Process mechanism graphics items
            # This would depend on the structure of mechanism_graphics_data
            pass
            
        # Update view
        self.mechanism_view.zoom_to_fit()
        
    def get_selected_part_name(self) -> Optional[str]:
        """선택된 파트 이름 반환"""
        return self.selected_part_name
        
    def get_current_mechanism_type(self) -> Optional[str]:
        """현재 매커니즘 타입 반환"""
        return self.current_mechanism_type