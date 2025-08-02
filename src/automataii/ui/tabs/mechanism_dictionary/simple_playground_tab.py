"""
Simple Mechanism Playground Tab - 단순하고 직관적인 메커니즘 실험 탭

핵심 가치:
1. 즉시성 - 바로 클릭하고 실험  
2. 직관성 - 복잡한 분석 패널 제거
3. 상호작용성 - 실시간 파라미터 조정
4. 시각적 명확성 - 메커니즘 동작이 바로 보임
"""

import logging
from typing import Optional, Dict, Any
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QPixmap, QPainter, QColor, QBrush, QPen
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QSplitter, 
    QScrollArea, QFrame, QLabel, QPushButton, QGroupBox,
    QGridLayout, QSlider, QListWidget, QListWidgetItem,
    QGraphicsView, QGraphicsScene, QSizePolicy
)

from automataii.ui.tabs.base.tab import BaseTab
from .state_manager import MechanismDictionaryStateManager
from .styling import ModernStyling

logger = logging.getLogger(__name__)


class MechanismLibraryWidget(QWidget):
    """시각적 메커니즘 라이브러리 - 직관적인 선택 인터페이스"""
    
    mechanism_selected = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(300)
        self._setup_ui()
        self._populate_mechanisms()
    
    def _setup_ui(self):
        """라이브러리 UI 설정"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # 제목
        title = QLabel("🔧 Mechanism Library")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {ModernStyling.COLORS['primary']}; margin-bottom: 8px;")
        layout.addWidget(title)
        
        # 간단한 설명
        desc = QLabel("Click any mechanism to start experimenting!")
        desc.setStyleSheet(f"color: {ModernStyling.COLORS['on_surface_variant']}; font-size: 12px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        # 메커니즘 리스트 (아이콘 뷰)
        self.mechanism_list = QListWidget()
        self.mechanism_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.mechanism_list.setIconSize(self.mechanism_list.iconSize() * 2)
        self.mechanism_list.setGridSize(self.mechanism_list.gridSize() * 1.2)
        self.mechanism_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.mechanism_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {ModernStyling.COLORS['surface']};
                border: 1px solid {ModernStyling.COLORS['outline']};
                border-radius: 8px;
                padding: 8px;
            }}
            QListWidget::item {{
                background-color: {ModernStyling.COLORS['surface_container']};
                border: 1px solid {ModernStyling.COLORS['outline_variant']};
                border-radius: 6px;
                padding: 8px;
                margin: 4px;
            }}
            QListWidget::item:hover {{
                background-color: {ModernStyling.COLORS['surface_container_high']};
                border-color: {ModernStyling.COLORS['primary']};
            }}
            QListWidget::item:selected {{
                background-color: {ModernStyling.COLORS['primary_container']};
                border-color: {ModernStyling.COLORS['primary']};
                color: {ModernStyling.COLORS['on_primary_container']};
            }}
        """)
        
        self.mechanism_list.itemClicked.connect(self._on_mechanism_clicked)
        layout.addWidget(self.mechanism_list)
        
        layout.addStretch()
    
    def _populate_mechanisms(self):
        """메커니즘 리스트 채우기 - 카탈로그에서 동적으로 로드"""
        from automataii.domain.fabrication.mechanisms.catalog_manager import CatalogManager
        
        catalog_manager = CatalogManager()
        categories = catalog_manager.get_categories()
        
        # 아이콘 매핑
        icon_map = {
            "four_bar": "🔗",
            "simple_gear_train": "⚙️", 
            "planetary_gear": "🪐",
            "simple_cam": "🥪",
            "geneva_drive": "⭐"
        }
        
        for category in categories:
            for mechanism in category.mechanisms:
                icon = icon_map.get(mechanism.id, "🔧")
                display_name = f"{icon} {mechanism.name.replace(' ', '\n')}"
                
                item = QListWidgetItem(display_name)
                item.setData(Qt.ItemDataRole.UserRole, mechanism.id)
                item.setToolTip(f"{mechanism.name}\n{mechanism.description}")
                self.mechanism_list.addItem(item)
    
    def _on_mechanism_clicked(self, item):
        """메커니즘 선택 처리"""
        mechanism_id = item.data(Qt.ItemDataRole.UserRole)
        self.mechanism_selected.emit(mechanism_id)


class SimpleParameterPanel(QWidget):
    """단순한 파라미터 제어 패널"""
    
    parameter_changed = pyqtSignal(str, float)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.sliders = {}
        self._setup_ui()
    
    def _setup_ui(self):
        """파라미터 패널 UI 설정"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        
        # 제목
        title = QLabel("🎛️ Controls")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {ModernStyling.COLORS['primary']}; margin-bottom: 8px;")
        layout.addWidget(title)
        
        # 파라미터 컨테이너
        self.param_container = QVBoxLayout()
        layout.addLayout(self.param_container)
        
        # 기본 메시지
        self.default_message = QLabel("Select a mechanism to see controls")
        self.default_message.setStyleSheet(f"color: {ModernStyling.COLORS['on_surface_variant']}; font-style: italic;")
        self.default_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.default_message)
        
        layout.addStretch()
    
    def clear_parameters(self):
        """모든 파라미터 지우기"""
        # 기존 슬라이더 제거
        while self.param_container.count():
            child = self.param_container.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        self.sliders.clear()
        self.default_message.show()
    
    def add_parameter(self, name: str, display_name: str, value: float, min_val: float, max_val: float):
        """파라미터 슬라이더 추가"""
        logger.debug(f"Adding parameter slider: {name} ({display_name}) = {value} [{min_val}, {max_val}]")
        self.default_message.hide()
        
        # 파라미터 그룹
        group = QGroupBox(display_name)
        group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                border: 1px solid {ModernStyling.COLORS['outline_variant']};
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px 0 4px;
            }}
        """)
        
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(4)
        
        # 값 표시 레이블
        value_label = QLabel(f"{value:.1f}")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_label.setStyleSheet(f"color: {ModernStyling.COLORS['primary']}; font-weight: bold;")
        group_layout.addWidget(value_label)
        
        # 슬라이더
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setMinimum(int(min_val * 10))
        slider.setMaximum(int(max_val * 10))
        slider.setValue(int(value * 10))
        slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                border: 1px solid {ModernStyling.COLORS['outline_variant']};
                height: 6px;
                background: {ModernStyling.COLORS['surface_variant']};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {ModernStyling.COLORS['primary']};
                border: 1px solid {ModernStyling.COLORS['primary_dark']};
                width: 18px;
                margin: -6px 0;
                border-radius: 9px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {ModernStyling.COLORS['primary_light']};
            }}
            QSlider::sub-page:horizontal {{
                background: {ModernStyling.COLORS['primary']};
                border-radius: 3px;
            }}
        """)
        
        # 슬라이더 값 변경 연결
        def on_slider_changed(val):
            new_value = val / 10.0
            value_label.setText(f"{new_value:.1f}")
            self.parameter_changed.emit(name, new_value)
        
        slider.valueChanged.connect(on_slider_changed)
        group_layout.addWidget(slider)
        
        # 범위 표시
        range_label = QLabel(f"{min_val:.1f} ← → {max_val:.1f}")
        range_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        range_label.setStyleSheet(f"color: {ModernStyling.COLORS['on_surface_variant']}; font-size: 10px;")
        group_layout.addWidget(range_label)
        
        self.param_container.addWidget(group)
        self.sliders[name] = (slider, value_label)
        
        # Force layout update and repaint
        self.updateGeometry()
        self.update()


class SimpleVisualizationWidget(QWidget):
    """단순한 메커니즘 시각화 위젯"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self.current_mechanism = None
        
        # 애니메이션 타이머
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._update_animation)
        self.animation_time = 0.0
        self.is_playing = False
    
    def _setup_ui(self):
        """시각화 UI 설정"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # 제어 버튼
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(16, 8, 16, 8)
        
        self.play_button = QPushButton("▶️ Play")
        self.play_button.setFixedHeight(40)
        self.play_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {ModernStyling.COLORS['primary']};
                color: {ModernStyling.COLORS['on_primary']};
                border: none;
                border-radius: 6px;
                font-weight: bold;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: {ModernStyling.COLORS['primary_light']};
            }}
            QPushButton:pressed {{
                background-color: {ModernStyling.COLORS['primary_dark']};
            }}
        """)
        self.play_button.clicked.connect(self._toggle_animation)
        
        self.reset_button = QPushButton("🔄 Reset")
        self.reset_button.setFixedHeight(40)
        self.reset_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {ModernStyling.COLORS['surface_variant']};
                color: {ModernStyling.COLORS['on_surface_variant']};
                border: 1px solid {ModernStyling.COLORS['outline']};
                border-radius: 6px;
                font-weight: bold;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: {ModernStyling.COLORS['surface_container_high']};
            }}
        """)
        self.reset_button.clicked.connect(self._reset_animation)
        
        controls_layout.addWidget(self.play_button)
        controls_layout.addWidget(self.reset_button)
        controls_layout.addStretch()
        
        layout.addLayout(controls_layout)
        
        # 그래픽스 뷰
        self.graphics_view = QGraphicsView()
        self.graphics_scene = QGraphicsScene()
        self.graphics_view.setScene(self.graphics_scene)
        self.graphics_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.graphics_view.setStyleSheet(f"""
            QGraphicsView {{
                background-color: {ModernStyling.COLORS['surface_container']};
                border: 1px solid {ModernStyling.COLORS['outline']};
                border-radius: 8px;
            }}
        """)
        
        # 기본 메시지
        self._show_welcome_message()
        
        layout.addWidget(self.graphics_view)
    
    def _show_welcome_message(self):
        """환영 메시지 표시"""
        self.graphics_scene.clear()
        text_item = self.graphics_scene.addText("👈 Select a mechanism from the library to begin!", 
                                               QFont("Segoe UI", 14))
        text_item.setDefaultTextColor(QColor(ModernStyling.COLORS['on_surface_variant']))
        
        # 중앙 정렬
        rect = text_item.boundingRect()
        text_item.setPos(-rect.width()/2, -rect.height()/2)
    
    def load_mechanism(self, mechanism):
        """메커니즘 로드"""
        self.current_mechanism = mechanism
        self.graphics_scene.clear()
        
        if mechanism:
            # 실제 메커니즘 렌더링 (간단화)
            self._render_mechanism()
            # 뷰를 메커니즘에 맞게 자동 조정
            self._fit_view_to_mechanism()
        else:
            self._show_welcome_message()
    
    def _fit_view_to_mechanism(self):
        """뷰를 메커니즘에 맞게 자동 조정"""
        if self.current_mechanism and hasattr(self.current_mechanism, 'points'):
            if not self.current_mechanism.points:
                return
            
            # 메커니즘의 경계 계산
            min_x = min(point.x for point in self.current_mechanism.points)
            max_x = max(point.x for point in self.current_mechanism.points)
            min_y = min(point.y for point in self.current_mechanism.points)
            max_y = max(point.y for point in self.current_mechanism.points)
            
            # 여백 추가
            margin = 50
            rect_width = (max_x - min_x) + 2 * margin
            rect_height = (max_y - min_y) + 2 * margin
            
            # 뷰 사각형 설정
            from PyQt6.QtCore import QRectF
            view_rect = QRectF(min_x - margin, min_y - margin, rect_width, rect_height)
            self.graphics_view.fitInView(view_rect, Qt.AspectRatioMode.KeepAspectRatio)
            
            # 약간 축소해서 여백 확보
            self.graphics_view.scale(0.9, 0.9)
    
    def _render_mechanism(self):
        """메커니즘 렌더링 (실제 메커니즘 데이터 사용)"""
        if not self.current_mechanism:
            return
        
        self.graphics_scene.clear()
        
        # 실제 메커니즘의 포인트와 링크 데이터 사용
        if hasattr(self.current_mechanism, 'points') and hasattr(self.current_mechanism, 'links'):
            self._render_real_mechanism()
        else:
            # 폴백: 간단한 시각화
            mech_type = self.current_mechanism.get_mechanism_type()
            if "linkage" in mech_type:
                self._render_linkage()
            elif "gear" in mech_type:
                self._render_gear()
            elif "cam" in mech_type:
                self._render_cam()
            else:
                self._render_generic()
    
    def _render_real_mechanism(self):
        """실제 메커니즘 데이터를 사용한 정확한 렌더링"""
        pen_link = QPen(QColor(ModernStyling.COLORS['primary']), 3)
        pen_joint = QPen(QColor(ModernStyling.COLORS['primary_dark']), 2)
        brush_fixed = QBrush(QColor(ModernStyling.COLORS['error']))  # 빨간색: 고정점
        brush_moving = QBrush(QColor(ModernStyling.COLORS['secondary']))  # 노란색: 이동점
        
        # 링크 그리기
        for link in self.current_mechanism.links:
            if hasattr(link, 'point1') and hasattr(link, 'point2'):
                p1 = link.point1
                p2 = link.point2
                self.graphics_scene.addLine(p1.x, p1.y, p2.x, p2.y, pen_link)
        
        # 포인트(조인트) 그리기
        for point in self.current_mechanism.points:
            radius = 6 if point.fixed else 4
            brush = brush_fixed if point.fixed else brush_moving
            
            # 포인트 그리기
            self.graphics_scene.addEllipse(
                point.x - radius, point.y - radius, 
                radius * 2, radius * 2, 
                pen_joint, brush
            )
            
            # 포인트 라벨 (고정점만)
            if point.fixed:
                text = self.graphics_scene.addText("⚓", QFont("Segoe UI", 8))
                text.setPos(point.x - 8, point.y - 20)
                text.setDefaultTextColor(QColor(ModernStyling.COLORS['error']))
        
        # 메커니즘 타입 라벨
        type_text = self.current_mechanism.get_mechanism_type().replace('_', ' ').title()
        label = self.graphics_scene.addText(type_text, QFont("Segoe UI", 10, QFont.Weight.Bold))
        label.setPos(-100, 100)
        label.setDefaultTextColor(QColor(ModernStyling.COLORS['primary']))
        
        # 현재 시간 표시
        time_text = f"t = {self.animation_time:.1f}s"
        time_label = self.graphics_scene.addText(time_text, QFont("Segoe UI", 9))
        time_label.setPos(50, 100)
        time_label.setDefaultTextColor(QColor(ModernStyling.COLORS['on_surface_variant']))
    
    def _render_linkage(self):
        """링키지 렌더링"""
        # 간단한 링키지 표현
        pen = QPen(QColor(ModernStyling.COLORS['primary']), 3)
        
        # 링크들
        self.graphics_scene.addLine(-100, 0, 100, 0, pen)
        self.graphics_scene.addLine(100, 0, 50, -80, pen)
        self.graphics_scene.addLine(50, -80, -50, -80, pen)
        self.graphics_scene.addLine(-50, -80, -100, 0, pen)
        
        # 조인트들
        brush = QBrush(QColor(ModernStyling.COLORS['secondary']))
        self.graphics_scene.addEllipse(-105, -5, 10, 10, pen, brush)
        self.graphics_scene.addEllipse(95, -5, 10, 10, pen, brush)
        self.graphics_scene.addEllipse(45, -85, 10, 10, pen, brush)
        self.graphics_scene.addEllipse(-55, -85, 10, 10, pen, brush)
    
    def _render_gear(self):
        """기어 렌더링"""
        pen = QPen(QColor(ModernStyling.COLORS['primary']), 2)
        brush = QBrush(QColor(ModernStyling.COLORS['primary_container']))
        
        # 두 개의 기어
        self.graphics_scene.addEllipse(-80, -40, 80, 80, pen, brush)
        self.graphics_scene.addEllipse(20, -40, 80, 80, pen, brush)
    
    def _render_cam(self):
        """캠 렌더링"""
        pen = QPen(QColor(ModernStyling.COLORS['primary']), 2)
        brush = QBrush(QColor(ModernStyling.COLORS['primary_container']))
        
        # 캠과 팔로워
        self.graphics_scene.addEllipse(-40, -40, 80, 80, pen, brush)
        self.graphics_scene.addRect(35, -60, 10, 120, pen, brush)
    
    def _render_generic(self):
        """일반적인 메커니즘 렌더링"""
        pen = QPen(QColor(ModernStyling.COLORS['primary']), 2)
        brush = QBrush(QColor(ModernStyling.COLORS['primary_container']))
        
        self.graphics_scene.addRect(-50, -50, 100, 100, pen, brush)
        
        text = self.graphics_scene.addText(self.current_mechanism.get_mechanism_type().replace('_', '\n').title(),
                                         QFont("Segoe UI", 10))
        text.setDefaultTextColor(QColor(ModernStyling.COLORS['on_primary_container']))
        text.setPos(-25, -10)
    
    def _toggle_animation(self):
        """애니메이션 토글"""
        if self.is_playing:
            self.animation_timer.stop()
            self.play_button.setText("▶️ Play")
            self.is_playing = False
        else:
            self.animation_timer.start(50)  # 20 FPS
            self.play_button.setText("⏸️ Pause")
            self.is_playing = True
    
    def _reset_animation(self):
        """애니메이션 리셋"""
        self.animation_timer.stop()
        self.animation_time = 0.0
        self.play_button.setText("▶️ Play")
        self.is_playing = False
        self._render_mechanism()
    
    def _update_animation(self):
        """애니메이션 업데이트"""
        self.animation_time += 0.05
        if self.current_mechanism and hasattr(self.current_mechanism, '_update_positions'):
            self.current_mechanism._update_positions(self.animation_time)
            self._render_mechanism()


class SimpleMechanismPlaygroundTab(BaseTab):
    """단순하고 직관적인 메커니즘 플레이그라운드 탭"""
    
    def __init__(self, main_window, parent=None):
        super().__init__(main_window, parent)
        self.state_manager = MechanismDictionaryStateManager()
        self.current_mechanism = None
        self._setup_ui()
        self._connect_signals()
        
        logger.info("SimpleMechanismPlaygroundTab initialized")
    
    def _setup_ui(self):
        """UI 설정"""
        # 메인 레이아웃 (좌우 분할)
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 좌측: 메커니즘 라이브러리
        self.library_widget = MechanismLibraryWidget()
        main_layout.addWidget(self.library_widget)
        
        # 우측: 플레이그라운드 영역
        playground_widget = QWidget()
        playground_layout = QVBoxLayout(playground_widget)
        playground_layout.setContentsMargins(0, 0, 0, 0)
        playground_layout.setSpacing(0)
        
        # 상단: 시각화 영역
        self.visualization_widget = SimpleVisualizationWidget()
        playground_layout.addWidget(self.visualization_widget, 2)  # 2/3 공간
        
        # 하단: 파라미터 제어
        self.parameter_panel = SimpleParameterPanel()
        self.parameter_panel.setMaximumHeight(300)  # 높이 증가로 더 많은 슬라이더 수용
        self.parameter_panel.setMinimumHeight(150)  # 최소 높이 보장
        self.parameter_panel.setStyleSheet(f"""
            QWidget {{
                background-color: {ModernStyling.COLORS['surface_container']};
                border: 1px solid {ModernStyling.COLORS['outline']};
                border-radius: 8px;
            }}
        """)
        playground_layout.addWidget(self.parameter_panel, 1)  # 1/3 공간
        
        main_layout.addWidget(playground_widget, 1)
        
        # 전체 스타일링
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {ModernStyling.COLORS['background']};
                color: {ModernStyling.COLORS['on_background']};
            }}
        """)
    
    def _connect_signals(self):
        """시그널 연결"""
        self.library_widget.mechanism_selected.connect(self._on_mechanism_selected)
        self.parameter_panel.parameter_changed.connect(self._on_parameter_changed)
    
    def _on_mechanism_selected(self, mechanism_id: str):
        """메커니즘 선택 처리"""
        logger.info(f"Selected mechanism: {mechanism_id}")
        
        # 상태 관리자를 통해 메커니즘 인스턴스 생성
        self.state_manager.set_current_mechanism(mechanism_id)
        mechanism = self.state_manager.get_current_mechanism_instance()
        
        logger.info(f"Mechanism instance created: {mechanism is not None}")
        if mechanism:
            logger.info(f"Mechanism type: {type(mechanism)}")
            logger.info(f"Mechanism has get_parameter_info: {hasattr(mechanism, 'get_parameter_info')}")
            
            self.current_mechanism = mechanism
            
            # 시각화 업데이트
            self.visualization_widget.load_mechanism(mechanism)
            
            # 파라미터 패널 업데이트
            self._update_parameter_panel(mechanism)
        else:
            logger.warning(f"Failed to create mechanism instance for: {mechanism_id}")
    
    def _update_parameter_panel(self, mechanism):
        """파라미터 패널 업데이트"""
        self.parameter_panel.clear_parameters()
        
        if hasattr(mechanism, 'get_parameter_info'):
            param_info = mechanism.get_parameter_info()
            logger.info(f"Parameter info for {mechanism.get_mechanism_type()}: {list(param_info.keys())}")
            
            # 주요 파라미터만 표시 (최대 5개로 증가)
            important_params = []
            # Four-Bar Linkage의 모든 파라미터 포함
            priority_params = [
                'link1_length', 'link2_length', 'link3_length', 'base_length', 'speed',
                'radius', 'gear1_teeth', 'gear2_teeth', 'cam_radius', 'num_slots'
            ]
            
            for param_name in priority_params:
                if param_name in param_info:
                    important_params.append((param_name, param_info[param_name]))
                    if len(important_params) >= 5:
                        break
            
            # 남은 파라미터들도 추가 (최대 5개까지)
            for name, info in param_info.items():
                if name not in priority_params and len(important_params) < 5:
                    important_params.append((name, info))
            
            # 파라미터 슬라이더 추가
            logger.info(f"Adding {len(important_params)} parameter sliders")
            for name, info in important_params:
                current_value = mechanism.get_parameter(name, info.get('min', 0))
                logger.debug(f"Adding parameter: {name} = {current_value}")
                self.parameter_panel.add_parameter(
                    name=name,
                    display_name=info.get('name', name.replace('_', ' ').title()),
                    value=current_value,
                    min_val=info.get('min', 0),
                    max_val=info.get('max', 100)
                )
            
            logger.info(f"✓ Successfully added {len(important_params)} parameter controls")
            
            # Force UI refresh
            self.parameter_panel.updateGeometry()
            self.parameter_panel.update()
        else:
            logger.warning(f"Mechanism does not have get_parameter_info method: {type(mechanism)}")
    
    def _on_parameter_changed(self, param_name: str, value: float):
        """파라미터 변경 처리"""
        if self.current_mechanism:
            self.current_mechanism.set_parameter(param_name, value)
            # 실시간 시각화 업데이트
            self.visualization_widget._render_mechanism()
            logger.debug(f"Parameter {param_name} changed to {value}")
    
    def activate_tab(self):
        """탭 활성화 시"""
        super().activate_tab()
        logger.info("Simple Mechanism Playground tab activated")
    
    def deactivate_tab(self):
        """탭 비활성화 시"""
        super().deactivate_tab()
        # 애니메이션 정지
        if hasattr(self.visualization_widget, 'animation_timer'):
            self.visualization_widget.animation_timer.stop()
        logger.info("Simple Mechanism Playground tab deactivated")