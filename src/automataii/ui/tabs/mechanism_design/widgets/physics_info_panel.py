"""
실시간 물리량 표시 정보 패널
메커니즘의 각종 물리량을 실시간으로 모니터링하고 표시
"""

import math
from typing import Dict, Any, Optional, List
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, 
    QProgressBar, QGroupBox, QScrollArea, QGridLayout
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QPalette
import logging

logger = logging.getLogger(__name__)


class PhysicsDataCard(QFrame):
    """개별 물리량을 표시하는 카드 위젯"""
    
    def __init__(self, title: str, unit: str = "", icon: str = "📊"):
        super().__init__()
        self.title = title
        self.unit = unit
        self.icon = icon
        
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e3e9f0;
                border-radius: 8px;
                padding: 8px;
                margin: 2px;
            }
            QFrame:hover {
                border-color: #0d6efd;
                background-color: #f8f9ff;
            }
        """)
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        
        # 제목 행
        title_layout = QHBoxLayout()
        title_layout.setSpacing(6)
        
        self.icon_label = QLabel(self.icon)
        self.icon_label.setFont(QFont("", 14))
        title_layout.addWidget(self.icon_label)
        
        self.title_label = QLabel(self.title)
        self.title_label.setFont(QFont("", 10, QFont.Weight.Bold))
        self.title_label.setStyleSheet("color: #5c85d6;")
        title_layout.addWidget(self.title_label)
        
        title_layout.addStretch()
        layout.addLayout(title_layout)
        
        # 값 표시
        self.value_label = QLabel("--")
        self.value_label.setFont(QFont("", 16, QFont.Weight.Bold))
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_label.setStyleSheet("color: #2c3e50; margin: 4px 0px;")
        layout.addWidget(self.value_label)
        
        # 단위 표시
        if self.unit:
            self.unit_label = QLabel(self.unit)
            self.unit_label.setFont(QFont("", 9))
            self.unit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.unit_label.setStyleSheet("color: #7f8c8d;")
            layout.addWidget(self.unit_label)
        
    def update_value(self, value: float, status: str = "normal"):
        """값 업데이트 및 상태에 따른 색상 변경"""
        if isinstance(value, (int, float)):
            if abs(value) < 0.01:
                display_value = "0.00"
            elif abs(value) < 1:
                display_value = f"{value:.3f}"
            elif abs(value) < 100:
                display_value = f"{value:.2f}"
            else:
                display_value = f"{value:.1f}"
        else:
            display_value = str(value)
            
        self.value_label.setText(display_value)
        
        # 상태에 따른 색상 설정
        color_map = {
            "normal": "#2c3e50",
            "warning": "#f39c12", 
            "critical": "#e74c3c",
            "good": "#27ae60"
        }
        
        color = color_map.get(status, "#2c3e50")
        self.value_label.setStyleSheet(f"color: {color}; margin: 4px 0px;")


class RealTimePhysicsInfoPanel(QWidget):
    """실시간 물리량 정보 패널"""
    
    # 신호
    parameter_clicked = pyqtSignal(str)  # 매개변수 클릭 시 발생
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        # 데이터 저장
        self.current_mechanism_data = {}
        self.current_physics_data = {}
        
        # 업데이트 타이머
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_display)
        self.update_timer.start(100)  # 10Hz 업데이트
        
        self.setup_ui()
        logger.info("RealTimePhysicsInfoPanel initialized")
        
    def setup_ui(self):
        """UI 설정"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)
        
        # 제목
        title_label = QLabel("🔧 실시간 물리량 모니터")
        title_label.setFont(QFont("", 14, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #2c3e50; padding: 8px; background-color: #ecf0f1; border-radius: 6px;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)
        
        # 스크롤 영역
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                width: 8px;
                background-color: #f8f9fa;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background-color: #dee2e6;
                border-radius: 4px;
                min-height: 20px;
            }
        """)\n        \n        # 컨텐트 위젯\n        content_widget = QWidget()\n        content_layout = QVBoxLayout(content_widget)\n        content_layout.setContentsMargins(4, 4, 4, 4)\n        content_layout.setSpacing(12)\n        \n        # 기구학 정보 그룹\n        self.kinematics_group = self._create_kinematics_group()\n        content_layout.addWidget(self.kinematics_group)\n        \n        # 동역학 정보 그룹  \n        self.dynamics_group = self._create_dynamics_group()\n        content_layout.addWidget(self.dynamics_group)\n        \n        # 메커니즘 매개변수 그룹\n        self.parameters_group = self._create_parameters_group()\n        content_layout.addWidget(self.parameters_group)\n        \n        # 시스템 상태 그룹\n        self.status_group = self._create_status_group()\n        content_layout.addWidget(self.status_group)\n        \n        content_layout.addStretch()\n        \n        scroll_area.setWidget(content_widget)\n        main_layout.addWidget(scroll_area)\n        \n    def _create_kinematics_group(self) -> QGroupBox:\n        \"\"\"기구학 정보 그룹 생성\"\"\"\n        group = QGroupBox(\"기구학 (Kinematics)\")\n        group.setStyleSheet(\"\"\"\n            QGroupBox {\n                font-weight: bold;\n                border: 2px solid #3498db;\n                border-radius: 6px;\n                margin: 6px 0px;\n                padding-top: 12px;\n            }\n            QGroupBox::title {\n                subcontrol-origin: margin;\n                left: 12px;\n                padding: 0 8px 0 8px;\n                color: #3498db;\n            }\n        \"\"\")\n        \n        layout = QGridLayout(group)\n        layout.setSpacing(8)\n        \n        # 기구학 데이터 카드들\n        self.position_x_card = PhysicsDataCard(\"X 위치\", \"px\", \"📍\")\n        self.position_y_card = PhysicsDataCard(\"Y 위치\", \"px\", \"📍\")\n        self.velocity_card = PhysicsDataCard(\"속도\", \"px/s\", \"🏃\")\n        self.acceleration_card = PhysicsDataCard(\"가속도\", \"px/s²\", \"⚡\")\n        self.angle_card = PhysicsDataCard(\"각도\", \"°\", \"📐\")\n        self.angular_velocity_card = PhysicsDataCard(\"각속도\", \"°/s\", \"🔄\")\n        \n        # 2x3 그리드로 배치\n        layout.addWidget(self.position_x_card, 0, 0)\n        layout.addWidget(self.position_y_card, 0, 1)\n        layout.addWidget(self.velocity_card, 1, 0)\n        layout.addWidget(self.acceleration_card, 1, 1)\n        layout.addWidget(self.angle_card, 2, 0)\n        layout.addWidget(self.angular_velocity_card, 2, 1)\n        \n        return group\n        \n    def _create_dynamics_group(self) -> QGroupBox:\n        \"\"\"동역학 정보 그룹 생성\"\"\"\n        group = QGroupBox(\"동역학 (Dynamics)\")\n        group.setStyleSheet(\"\"\"\n            QGroupBox {\n                font-weight: bold;\n                border: 2px solid #e74c3c;\n                border-radius: 6px;\n                margin: 6px 0px;\n                padding-top: 12px;\n            }\n            QGroupBox::title {\n                subcontrol-origin: margin;\n                left: 12px;\n                padding: 0 8px 0 8px;\n                color: #e74c3c;\n            }\n        \"\"\")\n        \n        layout = QGridLayout(group)\n        layout.setSpacing(8)\n        \n        # 동역학 데이터 카드들\n        self.force_x_card = PhysicsDataCard(\"X 힘\", \"N\", \"➡️\")\n        self.force_y_card = PhysicsDataCard(\"Y 힘\", \"N\", \"⬆️\")\n        self.torque_card = PhysicsDataCard(\"토크\", \"N⋅m\", \"🔧\")\n        self.power_card = PhysicsDataCard(\"파워\", \"W\", \"⚡\")\n        self.energy_card = PhysicsDataCard(\"에너지\", \"J\", \"🔋\")\n        self.efficiency_card = PhysicsDataCard(\"효율\", \"%\", \"📈\")\n        \n        # 2x3 그리드로 배치\n        layout.addWidget(self.force_x_card, 0, 0)\n        layout.addWidget(self.force_y_card, 0, 1)\n        layout.addWidget(self.torque_card, 1, 0)\n        layout.addWidget(self.power_card, 1, 1)\n        layout.addWidget(self.energy_card, 2, 0)\n        layout.addWidget(self.efficiency_card, 2, 1)\n        \n        return group\n        \n    def _create_parameters_group(self) -> QGroupBox:\n        \"\"\"메커니즘 매개변수 그룹 생성\"\"\"\n        group = QGroupBox(\"메커니즘 매개변수\")\n        group.setStyleSheet(\"\"\"\n            QGroupBox {\n                font-weight: bold;\n                border: 2px solid #f39c12;\n                border-radius: 6px;\n                margin: 6px 0px;\n                padding-top: 12px;\n            }\n            QGroupBox::title {\n                subcontrol-origin: margin;\n                left: 12px;\n                padding: 0 8px 0 8px;\n                color: #f39c12;\n            }\n        \"\"\")\n        \n        layout = QGridLayout(group)\n        layout.setSpacing(8)\n        \n        # 메커니즘별 매개변수 카드들 (동적으로 생성됨)\n        self.parameter_cards = {}\n        \n        return group\n        \n    def _create_status_group(self) -> QGroupBox:\n        \"\"\"시스템 상태 그룹 생성\"\"\"\n        group = QGroupBox(\"시스템 상태\")\n        group.setStyleSheet(\"\"\"\n            QGroupBox {\n                font-weight: bold;\n                border: 2px solid #9b59b6;\n                border-radius: 6px;\n                margin: 6px 0px;\n                padding-top: 12px;\n            }\n            QGroupBox::title {\n                subcontrol-origin: margin;\n                left: 12px;\n                padding: 0 8px 0 8px;\n                color: #9b59b6;\n            }\n        \"\"\")\n        \n        layout = QGridLayout(group)\n        layout.setSpacing(8)\n        \n        # 시스템 상태 카드들\n        self.fps_card = PhysicsDataCard(\"FPS\", \"프레임/s\", \"🎬\")\n        self.update_rate_card = PhysicsDataCard(\"업데이트율\", \"Hz\", \"🔄\")\n        self.mechanism_count_card = PhysicsDataCard(\"메커니즘 수\", \"개\", \"🔧\")\n        self.active_forces_card = PhysicsDataCard(\"활성 힘\", \"개\", \"⚡\")\n        \n        # 2x2 그리드로 배치\n        layout.addWidget(self.fps_card, 0, 0)\n        layout.addWidget(self.update_rate_card, 0, 1)\n        layout.addWidget(self.mechanism_count_card, 1, 0)\n        layout.addWidget(self.active_forces_card, 1, 1)\n        \n        return group\n        \n    def update_mechanism_data(self, mechanism_data: Dict[str, Any]):\n        \"\"\"메커니즘 데이터 업데이트\"\"\"\n        self.current_mechanism_data = mechanism_data\n        self._update_parameter_cards()\n        \n    def update_physics_data(self, physics_data: Dict[str, Any]):\n        \"\"\"물리 데이터 업데이트\"\"\"\n        self.current_physics_data = physics_data\n        \n    def _update_display(self):\n        \"\"\"디스플레이 업데이트\"\"\"\n        try:\n            self._update_kinematics_display()\n            self._update_dynamics_display()\n            self._update_status_display()\n        except Exception as e:\n            logger.debug(f\"Display update error: {e}\")\n            \n    def _update_kinematics_display(self):\n        \"\"\"기구학 디스플레이 업데이트\"\"\"\n        physics_data = self.current_physics_data\n        \n        if not physics_data:\n            return\n            \n        # 위치 정보\n        position = physics_data.get(\"position\", {\"x\": 0, \"y\": 0})\n        self.position_x_card.update_value(position.get(\"x\", 0))\n        self.position_y_card.update_value(position.get(\"y\", 0))\n        \n        # 속도 정보\n        velocity = physics_data.get(\"velocity\", {\"magnitude\": 0})\n        vel_magnitude = velocity.get(\"magnitude\", 0)\n        status = \"good\" if vel_magnitude < 100 else \"warning\" if vel_magnitude < 500 else \"critical\"\n        self.velocity_card.update_value(vel_magnitude, status)\n        \n        # 가속도 정보\n        acceleration = physics_data.get(\"acceleration\", {\"magnitude\": 0})\n        acc_magnitude = acceleration.get(\"magnitude\", 0)\n        status = \"good\" if acc_magnitude < 1000 else \"warning\" if acc_magnitude < 5000 else \"critical\"\n        self.acceleration_card.update_value(acc_magnitude, status)\n        \n        # 각도 정보\n        angle = physics_data.get(\"angle\", 0)\n        angle_degrees = math.degrees(angle) if isinstance(angle, (int, float)) else 0\n        self.angle_card.update_value(angle_degrees % 360)\n        \n        # 각속도 정보\n        angular_velocity = physics_data.get(\"angular_velocity\", 0)\n        angular_vel_degrees = math.degrees(angular_velocity) if isinstance(angular_velocity, (int, float)) else 0\n        self.angular_velocity_card.update_value(angular_vel_degrees)\n        \n    def _update_dynamics_display(self):\n        \"\"\"동역학 디스플레이 업데이트\"\"\"\n        physics_data = self.current_physics_data\n        \n        if not physics_data:\n            return\n            \n        # 힘 정보\n        force = physics_data.get(\"force\", {\"x\": 0, \"y\": 0})\n        self.force_x_card.update_value(force.get(\"x\", 0))\n        self.force_y_card.update_value(force.get(\"y\", 0))\n        \n        # 토크 정보\n        torque = physics_data.get(\"torque\", 0)\n        torque_status = \"good\" if abs(torque) < 10 else \"warning\" if abs(torque) < 50 else \"critical\"\n        self.torque_card.update_value(torque, torque_status)\n        \n        # 파워 정보\n        power = physics_data.get(\"power\", 0)\n        power_status = \"good\" if power < 100 else \"warning\" if power < 500 else \"critical\"\n        self.power_card.update_value(power, power_status)\n        \n        # 에너지 정보\n        energy = physics_data.get(\"energy\", 0)\n        self.energy_card.update_value(energy)\n        \n        # 효율 정보\n        efficiency = physics_data.get(\"efficiency\", 0)\n        eff_status = \"critical\" if efficiency < 50 else \"warning\" if efficiency < 80 else \"good\"\n        self.efficiency_card.update_value(efficiency, eff_status)\n        \n    def _update_parameter_cards(self):\n        \"\"\"매개변수 카드들 업데이트\"\"\"\n        mechanism_data = self.current_mechanism_data\n        \n        if not mechanism_data:\n            return\n            \n        parameters = mechanism_data.get(\"parameters\", {})\n        \n        # 기존 카드들 제거\n        layout = self.parameters_group.layout()\n        for i in reversed(range(layout.count())):\n            child = layout.itemAt(i).widget()\n            if child:\n                child.setParent(None)\n                \n        # 새 카드들 생성\n        self.parameter_cards.clear()\n        row, col = 0, 0\n        \n        for param_name, param_value in parameters.items():\n            # 매개변수 타입에 따른 아이콘과 단위 설정\n            if \"length\" in param_name.lower() or \"distance\" in param_name.lower():\n                icon, unit = \"📏\", \"mm\"\n            elif \"angle\" in param_name.lower():\n                icon, unit = \"📐\", \"°\"\n            elif \"speed\" in param_name.lower() or \"velocity\" in param_name.lower():\n                icon, unit = \"🏃\", \"rpm\"\n            elif \"force\" in param_name.lower():\n                icon, unit = \"💪\", \"N\"\n            else:\n                icon, unit = \"⚙️\", \"\"\n                \n            card = PhysicsDataCard(param_name, unit, icon)\n            card.update_value(param_value)\n            \n            # 클릭 이벤트 연결\n            card.mousePressEvent = lambda event, name=param_name: self.parameter_clicked.emit(name)\n            card.setCursor(Qt.CursorShape.PointingHandCursor)\n            \n            layout.addWidget(card, row, col)\n            self.parameter_cards[param_name] = card\n            \n            col += 1\n            if col >= 2:  # 2열로 배치\n                col = 0\n                row += 1\n                \n    def _update_status_display(self):\n        \"\"\"시스템 상태 디스플레이 업데이트\"\"\"\n        # FPS 계산 (단순화된 버전)\n        fps = 1000 / max(100, self.update_timer.interval())  # 대략적인 FPS\n        self.fps_card.update_value(fps)\n        \n        # 업데이트율\n        update_rate = 1000 / self.update_timer.interval()\n        self.update_rate_card.update_value(update_rate)\n        \n        # 메커니즘 수\n        mechanism_count = len(self.current_mechanism_data.get(\"mechanisms\", []))\n        self.mechanism_count_card.update_value(mechanism_count)\n        \n        # 활성 힘 수 (예제)\n        active_forces = len(self.current_physics_data.get(\"forces\", []))\n        self.active_forces_card.update_value(active_forces)\n        \n    def set_update_rate(self, rate_hz: float):\n        \"\"\"업데이트 주기 설정\"\"\"\n        interval_ms = int(1000 / max(1, rate_hz))\n        self.update_timer.setInterval(interval_ms)\n        logger.info(f\"Physics info panel update rate set to {rate_hz} Hz\")\n        \n    def clear_data(self):\n        \"\"\"모든 데이터 지우기\"\"\"\n        self.current_mechanism_data = {}\n        self.current_physics_data = {}\n        \n        # 모든 카드들을 기본값으로 리셋\n        cards = [\n            self.position_x_card, self.position_y_card, self.velocity_card, \n            self.acceleration_card, self.angle_card, self.angular_velocity_card,\n            self.force_x_card, self.force_y_card, self.torque_card,\n            self.power_card, self.energy_card, self.efficiency_card,\n            self.fps_card, self.update_rate_card, self.mechanism_count_card, \n            self.active_forces_card\n        ]\n        \n        for card in cards:\n            card.update_value(0)\n            \n        logger.info(\"Physics info panel data cleared\")