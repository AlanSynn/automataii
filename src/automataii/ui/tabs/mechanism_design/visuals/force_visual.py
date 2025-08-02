"""
Force Arrow Visual - 메커니즘의 힘 벡터 시각화
macanism 프로젝트에서 영감을 받은 힘 표시 기능 구현
"""

import math
from typing import List, Dict, Any, Optional, Tuple
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsPathItem, QGraphicsEllipseItem, QGraphicsLineItem
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QPen, QBrush, QColor, QPainterPath, QPolygonF
import numpy as np
import logging

logger = logging.getLogger(__name__)


class ForceArrowVisual(QGraphicsPathItem):
    """
    힘 벡터를 화살표로 시각화하는 그래픽스 아이템
    
    Features:
    - 힘의 크기에 비례한 화살표 길이
    - 색상으로 구분되는 힘의 종류 (압축력/인장력)
    - 벡터 방향 표시
    - 애니메이션 지원
    """
    
    def __init__(self, force_vector: Tuple[float, float], position: Tuple[float, float], 
                 force_type: str = "tension", scale_factor: float = 1.0):
        super().__init__()
        
        self.force_vector = force_vector  # (fx, fy) in Newtons
        self.position = position  # (x, y) application point
        self.force_type = force_type  # "tension", "compression", "reaction"
        self.scale_factor = scale_factor  # Scale for visual representation
        
        self.setZValue(120)  # High Z-value to appear on top
        
        # Color scheme for different force types
        self.colors = {
            "tension": QColor("#e74c3c"),      # Red for tension
            "compression": QColor("#3498db"),   # Blue for compression  
            "reaction": QColor("#2ecc71"),      # Green for reaction forces
            "friction": QColor("#f39c12"),      # Orange for friction
            "applied": QColor("#9b59b6")        # Purple for applied forces
        }
        
        self.update_visual()
        
    def update_visual(self):
        """힘 벡터에 따라 화살표 모양 업데이트"""
        fx, fy = self.force_vector
        force_magnitude = math.sqrt(fx*fx + fy*fy)
        
        if force_magnitude < 1e-6:  # 힘이 너무 작으면 표시하지 않음
            self.setVisible(False)
            return
            
        self.setVisible(True)
        
        # 화살표 길이 계산 (힘의 크기에 비례)
        arrow_length = force_magnitude * self.scale_factor * 0.1  # 적절한 스케일링
        arrow_length = max(20, min(arrow_length, 150))  # 최소/최대 길이 제한
        
        # 힘의 방향 계산
        force_angle = math.atan2(fy, fx)
        
        # 화살표 그리기
        path = QPainterPath()
        
        # 화살표 시작점 (힘 적용점)
        start_x, start_y = self.position
        
        # 화살표 끝점
        end_x = start_x + arrow_length * math.cos(force_angle)
        end_y = start_y + arrow_length * math.sin(force_angle)
        
        # 메인 화살표 라인
        path.moveTo(start_x, start_y)
        path.lineTo(end_x, end_y)
        
        # 화살표 머리 부분
        arrow_head_length = arrow_length * 0.2
        arrow_head_width = arrow_length * 0.1
        
        # 화살표 머리의 각도
        head_angle1 = force_angle + math.pi - 0.5
        head_angle2 = force_angle + math.pi + 0.5
        
        # 화살표 머리 그리기
        head_point1_x = end_x + arrow_head_length * math.cos(head_angle1)
        head_point1_y = end_y + arrow_head_length * math.sin(head_angle1)
        
        head_point2_x = end_x + arrow_head_length * math.cos(head_angle2)  
        head_point2_y = end_y + arrow_head_length * math.sin(head_angle2)
        
        # 화살표 머리를 다각형으로 그리기
        arrow_head = QPolygonF([
            QPointF(end_x, end_y),
            QPointF(head_point1_x, head_point1_y),
            QPointF(head_point2_x, head_point2_y)
        ])
        
        path.addPolygon(arrow_head)
        
        self.setPath(path)
        
        # 색상 및 스타일 설정
        color = self.colors.get(self.force_type, self.colors["tension"])
        pen = QPen(color, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        brush = QBrush(color)
        
        self.setPen(pen)
        self.setBrush(brush)
        
        # 위치 설정
        self.setPos(0, 0)  # Path는 이미 절대 좌표로 그려짐
        
    def update_force(self, force_vector: Tuple[float, float], position: Tuple[float, float]):
        """힘 벡터 업데이트"""
        self.force_vector = force_vector
        self.position = position
        self.update_visual()
        
    def set_scale_factor(self, scale_factor: float):
        """스케일 팩터 변경"""
        self.scale_factor = scale_factor
        self.update_visual()
        
    def set_force_type(self, force_type: str):
        """힘 타입 변경"""
        self.force_type = force_type
        self.update_visual()


class ForceSystemVisualizer:
    """
    메커니즘의 전체 힘 시스템을 관리하고 시각화하는 클래스
    """
    
    def __init__(self, scene_manager):
        self.scene_manager = scene_manager
        self.force_arrows: Dict[str, ForceArrowVisual] = {}
        self.show_forces = False
        self.scale_factor = 1.0
        
        logger.info("ForceSystemVisualizer initialized")
        
    def calculate_linkage_forces(self, layer_data: Dict[str, Any], time: float) -> Dict[str, Dict]:
        """
        4절 링키지의 힘 계산
        간소화된 정적 해석을 수행
        """
        forces = {}
        
        try:
            # 시뮬레이션 데이터에서 현재 프레임의 위치 가져오기
            sim_data = layer_data.get("full_simulation_data", {})
            joint_positions = sim_data.get("joint_positions", {})
            
            if not joint_positions:
                logger.debug("No joint positions available for force calculation")
                return forces
                
            num_frames = len(joint_positions.get("p1_positions", []))
            if num_frames == 0:
                return forces
                
            frame_index = int((time % (2 * np.pi)) / (2 * np.pi) * num_frames) % num_frames
            
            # 현재 프레임의 조인트 위치들
            p1 = joint_positions.get("p1_positions", [])[frame_index]  # Ground pivot 1
            p2 = joint_positions.get("p2_positions", [])[frame_index]  # Ground pivot 2  
            p3 = joint_positions.get("p3_positions", [])[frame_index]  # Crank end
            p4 = joint_positions.get("p4_positions", [])[frame_index]  # Rocker end
            
            # 간소화된 힘 계산 (실제로는 더 복잡한 동역학 해석 필요)
            # 여기서는 교육적 목적으로 단순화된 힘을 계산
            
            # 입력 토크 (가정: 10 N⋅m)
            input_torque = 10.0
            
            # Link lengths
            link1_length = math.sqrt((p3[0] - p1[0])**2 + (p3[1] - p1[1])**2)
            link2_length = math.sqrt((p4[0] - p3[0])**2 + (p4[1] - p3[1])**2) 
            link3_length = math.sqrt((p2[0] - p4[0])**2 + (p2[1] - p4[1])**2)
            
            if link1_length < 1e-6:
                return forces
                
            # 입력 링크의 힘 (토크를 힘으로 변환)
            input_force_magnitude = input_torque / link1_length
            
            # 입력 링크 방향 (P1에서 P3로)
            input_direction = math.atan2(p3[1] - p1[1], p3[0] - p1[0])
            
            # 입력 힘은 입력 링크에 수직 (토크 생성)
            force_direction = input_direction + math.pi/2
            
            forces["input_force"] = {
                "vector": (input_force_magnitude * math.cos(force_direction),
                          input_force_magnitude * math.sin(force_direction)),
                "position": ((p1[0] + p3[0])/2, (p1[1] + p3[1])/2),  # 링크 중점
                "type": "applied"
            }
            
            # 반력 계산 (Ground pivot reactions)
            # 간소화: 입력력과 균형을 맞추는 반력
            forces["reaction_1"] = {
                "vector": (-input_force_magnitude/2 * math.cos(force_direction),
                          -input_force_magnitude/2 * math.sin(force_direction)),
                "position": p1,
                "type": "reaction"
            }
            
            forces["reaction_2"] = {
                "vector": (-input_force_magnitude/2 * math.cos(force_direction),
                          -input_force_magnitude/2 * math.sin(force_direction)),
                "position": p2,
                "type": "reaction"
            }
            
            # 커플러 링크의 내부 힘 (압축/인장)
            coupler_direction = math.atan2(p4[1] - p3[1], p4[0] - p3[0])
            coupler_force_magnitude = input_force_magnitude * 0.7  # 간소화된 계산
            
            forces["coupler_force"] = {
                "vector": (coupler_force_magnitude * math.cos(coupler_direction),
                          coupler_force_magnitude * math.sin(coupler_direction)),
                "position": ((p3[0] + p4[0])/2, (p3[1] + p4[1])/2),
                "type": "tension"
            }
            
        except Exception as e:
            logger.warning(f"Error calculating linkage forces: {e}")
            
        return forces
        
    def update_forces(self, layer_data: Dict[str, Any], time: float):
        """힘 시각화 업데이트"""
        if not self.show_forces:
            self.clear_forces()
            return
            
        # 메커니즘 타입에 따른 힘 계산
        mech_type = layer_data.get("type", "")
        
        if "4-Bar Linkage" in mech_type or "4_bar_linkage" in mech_type:
            forces = self.calculate_linkage_forces(layer_data, time)
        else:
            # 다른 메커니즘 타입들은 향후 구현
            forces = {}
            
        # 기존 화살표 제거
        self.clear_forces()
        
        # 새로운 힘 화살표 생성
        from automataii.ui.tabs.mechanism_design.utils import get_scene_transform_function
        transform = get_scene_transform_function(layer_data)
        
        for force_id, force_data in forces.items():
            vector = force_data["vector"]
            position = force_data["position"]
            force_type = force_data["type"]
            
            # 좌표계 변환
            scene_pos = transform(position)
            
            # ForceArrowVisual 생성
            arrow = ForceArrowVisual(
                force_vector=vector,
                position=(scene_pos.x(), scene_pos.y()),
                force_type=force_type,
                scale_factor=self.scale_factor
            )
            
            # 씬에 추가
            self.scene_manager.scene.addItem(arrow)
            self.force_arrows[force_id] = arrow
            
        logger.debug(f"Updated {len(forces)} force arrows")
        
    def clear_forces(self):
        """모든 힘 화살표 제거"""
        for arrow in self.force_arrows.values():
            if arrow.scene():
                self.scene_manager.scene.removeItem(arrow)
                
        self.force_arrows.clear()
        
    def set_show_forces(self, show: bool):
        """힘 표시 토글"""
        self.show_forces = show
        if not show:
            self.clear_forces()
            
    def set_scale_factor(self, scale: float):
        """힘 벡터 스케일 변경"""
        self.scale_factor = scale
        for arrow in self.force_arrows.values():
            arrow.set_scale_factor(scale)
            
    def cleanup(self):
        """리소스 정리"""
        self.clear_forces()
        logger.info("ForceSystemVisualizer cleaned up")