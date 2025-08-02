"""
Four-Bar Linkage 수정된 _update_positions 메서드
주요 개선사항:
1. Branch detection 및 연속성 유지
2. Grashof 조건 확인
3. 특이점 처리
4. Assembly mode 관리
"""

import math
from typing import Dict, Any, Tuple

def _update_positions_fixed(self, time: float):
    """Updated positions with kinematic accuracy and continuity."""
    # Calculate crank angle based on time and speed
    speed = self.get_parameter("speed", 1.0)
    self.crank_angle = time * speed * 2.0
    
    # Get link lengths
    link1_len = self.get_parameter("link1_length", 50.0)
    link2_len = self.get_parameter("link2_length", 80.0)
    link3_len = self.get_parameter("link3_length", 60.0)
    base_len = self.get_parameter("base_length", 100.0)
    
    # Check Grashof condition first
    if not self._is_valid_grashof_condition(link1_len, link2_len, link3_len, base_len):
        # If invalid, keep current position or show error state
        return
    
    # Calculate crank end position
    self.crank_end.x = self.fixed_pivot_a.x + link1_len * math.cos(self.crank_angle)
    self.crank_end.y = self.fixed_pivot_a.y + link1_len * math.sin(self.crank_angle)
    
    # Calculate rocker end position using proper kinematic analysis
    try:
        # Vector from crank end to fixed pivot B
        dx = self.fixed_pivot_b.x - self.crank_end.x
        dy = self.fixed_pivot_b.y - self.crank_end.y
        d = math.sqrt(dx * dx + dy * dy)
        
        # Check triangle inequality (mechanism can close)
        if d <= link2_len + link3_len and abs(link2_len - link3_len) <= d:
            # Calculate two possible solutions
            cos_beta = (link3_len * link3_len + d * d - link2_len * link2_len) / (2 * link3_len * d)
            cos_beta = max(-1.0, min(1.0, cos_beta))
            beta = math.acos(cos_beta)
            
            alpha = math.atan2(dy, dx)
            
            # Two possible rocker angles
            rocker_angle_1 = alpha + beta  # Upper solution
            rocker_angle_2 = alpha - beta  # Lower solution
            
            # Choose solution based on assembly mode continuity
            rocker_angle = self._choose_continuous_solution(
                rocker_angle_1, rocker_angle_2, 
                getattr(self, 'previous_rocker_angle', rocker_angle_1)
            )
            
            # Update rocker end position
            self.rocker_end.x = self.fixed_pivot_b.x + link3_len * math.cos(rocker_angle)
            self.rocker_end.y = self.fixed_pivot_b.y + link3_len * math.sin(rocker_angle)
            
            # Store for next iteration
            self.previous_rocker_angle = rocker_angle
            
    except (ValueError, ZeroDivisionError):
        # Kinematic singularity - maintain last valid position
        pass

def _is_valid_grashof_condition(self, link1, link2, link3, base):
    """Check if linkage satisfies Grashof condition for continuous motion."""
    links = [link1, link2, link3, base]
    links.sort()
    shortest = links[0]
    longest = links[3]
    others = links[1] + links[2]
    
    # Grashof condition: s + l <= p + q
    return shortest + longest <= others

def _choose_continuous_solution(self, angle1, angle2, previous_angle):
    """Choose the solution that maintains continuity."""
    # Calculate angular distance for both solutions
    diff1 = abs(self._angle_difference(angle1, previous_angle))
    diff2 = abs(self._angle_difference(angle2, previous_angle))
    
    # Choose the closer solution
    return angle1 if diff1 < diff2 else angle2

def _angle_difference(self, angle1, angle2):
    """Calculate the shortest angular difference between two angles."""
    diff = angle1 - angle2
    while diff > math.pi:
        diff -= 2 * math.pi
    while diff < -math.pi:
        diff += 2 * math.pi
    return diff