"""
Advanced motion analysis tools using Strategy Pattern.
Provides real-time kinematic analysis, path optimization, and visualization.
"""

import logging
import math
import numpy as np
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from collections import deque
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer, QPointF
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPolygonF
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QCheckBox, QSlider, QGroupBox, QTabWidget, QTextEdit,
    QComboBox, QProgressBar
)

from automataii.domain.fabrication.mechanisms.base_mechanism import BaseMechanism
from .styling import ModernStyling

logger = logging.getLogger(__name__)


@dataclass
class MotionPoint:
    """Represents a point in motion with kinematic properties."""
    position: QPointF
    velocity: QPointF
    acceleration: QPointF
    time: float
    angular_position: float = 0.0
    angular_velocity: float = 0.0
    angular_acceleration: float = 0.0


@dataclass
class AnalysisResult:
    """Container for motion analysis results."""
    analysis_type: str
    data: Dict[str, Any]
    visualization_elements: List[Any]
    statistics: Dict[str, float]
    recommendations: List[str]


class MotionAnalysisStrategy(ABC):
    """Abstract base class for motion analysis strategies."""
    
    def __init__(self, name: str):
        self.name = name
        self.enabled = True
        self.update_interval = 0.1  # seconds
        
    @abstractmethod
    def analyze(self, motion_history: List[MotionPoint], mechanism: BaseMechanism) -> AnalysisResult:
        """Perform motion analysis and return results."""
        pass
    
    @abstractmethod
    def get_visualization_elements(self, analysis_result: AnalysisResult) -> List[Any]:
        """Get elements for visualization overlay."""
        pass
    
    @abstractmethod
    def get_parameters(self) -> Dict[str, Any]:
        """Get analysis parameters that can be adjusted."""
        pass
    
    def set_parameter(self, name: str, value: Any):
        """Set an analysis parameter."""
        if hasattr(self, name):
            setattr(self, name, value)


class VelocityAnalysisStrategy(MotionAnalysisStrategy):
    """Strategy for velocity vector analysis."""
    
    def __init__(self):
        super().__init__("Velocity Analysis")
        self.vector_scale = 10.0
        self.min_velocity_threshold = 0.1
        self.show_instantaneous = True
        self.show_average = False
        
    def analyze(self, motion_history: List[MotionPoint], mechanism: BaseMechanism) -> AnalysisResult:
        """Analyze velocity vectors and patterns."""
        if len(motion_history) < 2:
            return AnalysisResult("velocity", {}, [], {}, [])
        
        # Calculate velocity statistics
        velocities = [math.sqrt(p.velocity.x()**2 + p.velocity.y()**2) for p in motion_history]
        
        if not velocities:
            return AnalysisResult("velocity", {}, [], {}, [])
        
        statistics = {
            "max_velocity": max(velocities),
            "min_velocity": min(velocities),
            "avg_velocity": sum(velocities) / len(velocities),
            "velocity_variation": max(velocities) - min(velocities)
        }
        
        # Generate recommendations
        recommendations = []
        if statistics["velocity_variation"] > statistics["avg_velocity"] * 0.5:
            recommendations.append("High velocity variation detected - consider smoothing the motion profile")
        
        if statistics["max_velocity"] > 100:  # threshold
            recommendations.append("High peak velocity - check for excessive accelerations")
        
        # Create visualization elements
        viz_elements = []
        for i, point in enumerate(motion_history[-20:]):  # Last 20 points
            if math.sqrt(point.velocity.x()**2 + point.velocity.y()**2) > self.min_velocity_threshold:
                viz_elements.append({
                    "type": "velocity_vector",
                    "position": point.position,
                    "velocity": point.velocity,
                    "scale": self.vector_scale
                })
        
        data = {
            "motion_points": motion_history,
            "velocity_profile": velocities,
            "analysis_time": motion_history[-1].time if motion_history else 0.0
        }
        
        return AnalysisResult("velocity", data, viz_elements, statistics, recommendations)
    
    def get_visualization_elements(self, analysis_result: AnalysisResult) -> List[Any]:
        """Get velocity vector visualization elements."""
        return analysis_result.visualization_elements
    
    def get_parameters(self) -> Dict[str, Any]:
        """Get velocity analysis parameters."""
        return {
            "vector_scale": {"type": "float", "min": 1.0, "max": 50.0, "value": self.vector_scale},
            "min_velocity_threshold": {"type": "float", "min": 0.01, "max": 1.0, "value": self.min_velocity_threshold},
            "show_instantaneous": {"type": "bool", "value": self.show_instantaneous},
            "show_average": {"type": "bool", "value": self.show_average}
        }


class AccelerationAnalysisStrategy(MotionAnalysisStrategy):
    """Strategy for acceleration analysis."""
    
    def __init__(self):
        super().__init__("Acceleration Analysis")
        self.vector_scale = 5.0
        self.smoothing_window = 5
        self.highlight_peaks = True
        
    def analyze(self, motion_history: List[MotionPoint], mechanism: BaseMechanism) -> AnalysisResult:
        """Analyze acceleration patterns."""
        if len(motion_history) < 3:
            return AnalysisResult("acceleration", {}, [], {}, [])
        
        # Calculate acceleration magnitudes
        accelerations = [math.sqrt(p.acceleration.x()**2 + p.acceleration.y()**2) for p in motion_history]
        
        if not accelerations:
            return AnalysisResult("acceleration", {}, [], {}, [])
        
        # Apply smoothing if enabled
        if self.smoothing_window > 1:
            smoothed_accelerations = self._apply_smoothing(accelerations, self.smoothing_window)
        else:
            smoothed_accelerations = accelerations
        
        statistics = {
            "max_acceleration": max(accelerations),
            "min_acceleration": min(accelerations),
            "avg_acceleration": sum(accelerations) / len(accelerations),
            "rms_acceleration": math.sqrt(sum(a**2 for a in accelerations) / len(accelerations))
        }
        
        # Detect acceleration peaks
        peaks = self._find_acceleration_peaks(smoothed_accelerations)
        
        recommendations = []
        if statistics["max_acceleration"] > statistics["avg_acceleration"] * 3:
            recommendations.append("High acceleration peaks detected - consider acceleration limiting")
        
        if len(peaks) > len(accelerations) * 0.1:  # More than 10% peaks
            recommendations.append("Frequent acceleration changes - motion may be jerky")
        
        # Create visualization elements
        viz_elements = []
        for i, point in enumerate(motion_history[-15:]):  # Last 15 points
            if i in peaks or not self.highlight_peaks:
                viz_elements.append({
                    "type": "acceleration_vector",
                    "position": point.position,
                    "acceleration": point.acceleration,
                    "scale": self.vector_scale,
                    "is_peak": i in peaks
                })
        
        data = {
            "motion_points": motion_history,
            "acceleration_profile": accelerations,
            "smoothed_profile": smoothed_accelerations,
            "peaks": peaks
        }
        
        return AnalysisResult("acceleration", data, viz_elements, statistics, recommendations)
    
    def _apply_smoothing(self, data: List[float], window: int) -> List[float]:
        """Apply moving average smoothing."""
        if len(data) < window:
            return data
        
        smoothed = []
        for i in range(len(data)):
            start = max(0, i - window // 2)
            end = min(len(data), i + window // 2 + 1)
            smoothed.append(sum(data[start:end]) / (end - start))
        
        return smoothed
    
    def _find_acceleration_peaks(self, accelerations: List[float]) -> List[int]:
        """Find peaks in acceleration profile."""
        if len(accelerations) < 3:
            return []
        
        peaks = []
        threshold = sum(accelerations) / len(accelerations) * 1.5  # 1.5x average
        
        for i in range(1, len(accelerations) - 1):
            if (accelerations[i] > accelerations[i-1] and 
                accelerations[i] > accelerations[i+1] and 
                accelerations[i] > threshold):
                peaks.append(i)
        
        return peaks
    
    def get_visualization_elements(self, analysis_result: AnalysisResult) -> List[Any]:
        """Get acceleration visualization elements."""
        return analysis_result.visualization_elements
    
    def get_parameters(self) -> Dict[str, Any]:
        """Get acceleration analysis parameters."""
        return {
            "vector_scale": {"type": "float", "min": 1.0, "max": 20.0, "value": self.vector_scale},
            "smoothing_window": {"type": "int", "min": 1, "max": 10, "value": self.smoothing_window},
            "highlight_peaks": {"type": "bool", "value": self.highlight_peaks}
        }


class TrajectoryAnalysisStrategy(MotionAnalysisStrategy):
    """Strategy for trajectory analysis and optimization."""
    
    def __init__(self):
        super().__init__("Trajectory Analysis")
        self.path_smoothness_weight = 0.5
        self.curvature_analysis = True
        self.optimization_enabled = False
        self.target_path = None  # Could be set for path following analysis
        
    def analyze(self, motion_history: List[MotionPoint], mechanism: BaseMechanism) -> AnalysisResult:
        """Analyze trajectory properties."""
        if len(motion_history) < 5:
            return AnalysisResult("trajectory", {}, [], {}, [])
        
        # Extract path points
        path_points = [p.position for p in motion_history]
        
        # Calculate path properties
        path_length = self._calculate_path_length(path_points)
        curvatures = self._calculate_curvature(path_points) if self.curvature_analysis else []
        smoothness = self._calculate_smoothness(path_points)
        
        statistics = {
            "path_length": path_length,
            "avg_curvature": sum(curvatures) / len(curvatures) if curvatures else 0.0,
            "max_curvature": max(curvatures) if curvatures else 0.0,
            "smoothness_index": smoothness,
            "efficiency": self._calculate_efficiency(path_points)
        }
        
        recommendations = []
        if smoothness < 0.7:  # Threshold for smoothness
            recommendations.append("Path has high roughness - consider smoothing optimization")
        
        if statistics["max_curvature"] > 0.1:  # High curvature threshold
            recommendations.append("Sharp turns detected - may cause high accelerations")
        
        # Generate optimization suggestions
        if self.optimization_enabled:
            optimized_path = self._optimize_path(path_points)
            recommendations.append("Path optimization available - click to apply suggested improvements")
        
        # Create visualization elements
        viz_elements = []
        
        # Path visualization
        viz_elements.append({
            "type": "trajectory_path",
            "points": path_points,
            "curvatures": curvatures
        })
        
        # Curvature heat map
        if curvatures:
            for i, (point, curvature) in enumerate(zip(path_points[1:-1], curvatures)):
                viz_elements.append({
                    "type": "curvature_indicator",
                    "position": point,
                    "curvature": curvature,
                    "index": i
                })
        
        data = {
            "path_points": path_points,
            "curvatures": curvatures,
            "motion_history": motion_history,
            "analysis_complete": True
        }
        
        return AnalysisResult("trajectory", data, viz_elements, statistics, recommendations)
    
    def _calculate_path_length(self, points: List[QPointF]) -> float:
        """Calculate total path length."""
        if len(points) < 2:
            return 0.0
        
        length = 0.0
        for i in range(1, len(points)):
            dx = points[i].x() - points[i-1].x()
            dy = points[i].y() - points[i-1].y()
            length += math.sqrt(dx*dx + dy*dy)
        
        return length
    
    def _calculate_curvature(self, points: List[QPointF]) -> List[float]:
        """Calculate curvature at each point."""
        if len(points) < 3:
            return []
        
        curvatures = []
        for i in range(1, len(points) - 1):
            # Three-point curvature calculation
            p1, p2, p3 = points[i-1], points[i], points[i+1]
            
            # Calculate vectors
            v1 = QPointF(p2.x() - p1.x(), p2.y() - p1.y())
            v2 = QPointF(p3.x() - p2.x(), p3.y() - p2.y())
            
            # Calculate curvature using cross product
            cross = v1.x() * v2.y() - v1.y() * v2.x()
            v1_mag = math.sqrt(v1.x()**2 + v1.y()**2)
            v2_mag = math.sqrt(v2.x()**2 + v2.y()**2)
            
            if v1_mag > 0 and v2_mag > 0:
                curvature = abs(cross) / (v1_mag * v2_mag)
            else:
                curvature = 0.0
            
            curvatures.append(curvature)
        
        return curvatures
    
    def _calculate_smoothness(self, points: List[QPointF]) -> float:
        """Calculate path smoothness index (0-1, higher is smoother)."""
        if len(points) < 3:
            return 1.0
        
        # Calculate second derivatives (change in direction)
        direction_changes = []
        for i in range(1, len(points) - 1):
            # Vectors before and after point
            v1 = QPointF(points[i].x() - points[i-1].x(), points[i].y() - points[i-1].y())
            v2 = QPointF(points[i+1].x() - points[i].x(), points[i+1].y() - points[i].y())
            
            # Normalize vectors
            v1_mag = math.sqrt(v1.x()**2 + v1.y()**2)
            v2_mag = math.sqrt(v2.x()**2 + v2.y()**2)
            
            if v1_mag > 0 and v2_mag > 0:
                v1_norm = QPointF(v1.x() / v1_mag, v1.y() / v1_mag)
                v2_norm = QPointF(v2.x() / v2_mag, v2.y() / v2_mag)
                
                # Calculate angle change
                dot_product = v1_norm.x() * v2_norm.x() + v1_norm.y() * v2_norm.y()
                angle_change = abs(math.acos(max(-1, min(1, dot_product))))
                direction_changes.append(angle_change)
        
        if not direction_changes:
            return 1.0
        
        # Smoothness is inverse of average direction change
        avg_change = sum(direction_changes) / len(direction_changes)
        smoothness = max(0, 1 - (avg_change / math.pi))  # Normalize to 0-1
        
        return smoothness
    
    def _calculate_efficiency(self, points: List[QPointF]) -> float:
        """Calculate path efficiency (straight line distance / actual path length)."""
        if len(points) < 2:
            return 1.0
        
        # Straight line distance from start to end
        start, end = points[0], points[-1]
        straight_distance = math.sqrt((end.x() - start.x())**2 + (end.y() - start.y())**2)
        
        # Actual path length
        actual_length = self._calculate_path_length(points)
        
        if actual_length > 0:
            return straight_distance / actual_length
        else:
            return 1.0
    
    def _optimize_path(self, points: List[QPointF]) -> List[QPointF]:
        """Optimize path for smoothness (placeholder implementation)."""
        # This would implement path optimization algorithms
        # For now, return original path
        return points.copy()
    
    def get_visualization_elements(self, analysis_result: AnalysisResult) -> List[Any]:
        """Get trajectory visualization elements."""
        return analysis_result.visualization_elements
    
    def get_parameters(self) -> Dict[str, Any]:
        """Get trajectory analysis parameters."""
        return {
            "path_smoothness_weight": {"type": "float", "min": 0.0, "max": 1.0, "value": self.path_smoothness_weight},
            "curvature_analysis": {"type": "bool", "value": self.curvature_analysis},
            "optimization_enabled": {"type": "bool", "value": self.optimization_enabled}
        }


class MotionAnalysisManager(QObject):
    """Manager for motion analysis strategies and real-time computation."""
    
    analysis_updated = pyqtSignal(dict)  # analysis_results
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Available analysis strategies
        self.strategies: Dict[str, MotionAnalysisStrategy] = {
            "velocity": VelocityAnalysisStrategy(),
            "acceleration": AccelerationAnalysisStrategy(),
            "trajectory": TrajectoryAnalysisStrategy()
        }
        
        # Motion data storage
        self.motion_history: deque = deque(maxlen=1000)  # Limit history size
        self.current_mechanism: Optional[BaseMechanism] = None
        
        # Analysis timing
        self.analysis_timer = QTimer()
        self.analysis_timer.timeout.connect(self._update_analysis)
        self.analysis_timer.setInterval(100)  # 10 Hz update rate
        
        # Results cache
        self.latest_results: Dict[str, AnalysisResult] = {}
        
    def set_mechanism(self, mechanism: BaseMechanism):
        """Set the mechanism to analyze."""
        self.current_mechanism = mechanism
        self.clear_history()
    
    def add_motion_point(self, position: QPointF, velocity: QPointF, acceleration: QPointF, time: float):
        """Add a new motion point to the analysis."""
        point = MotionPoint(
            position=position,
            velocity=velocity, 
            acceleration=acceleration,
            time=time
        )
        self.motion_history.append(point)
    
    def start_analysis(self):
        """Start real-time analysis updates."""
        self.analysis_timer.start()
        logger.debug("Motion analysis started")
    
    def stop_analysis(self):
        """Stop analysis updates."""
        self.analysis_timer.stop()
        logger.debug("Motion analysis stopped")
    
    def clear_history(self):
        """Clear motion history."""
        self.motion_history.clear()
        self.latest_results.clear()
    
    def enable_strategy(self, strategy_name: str, enabled: bool):
        """Enable or disable an analysis strategy."""
        if strategy_name in self.strategies:
            self.strategies[strategy_name].enabled = enabled
    
    def set_strategy_parameter(self, strategy_name: str, param_name: str, value: Any):
        """Set a parameter for a specific strategy."""
        if strategy_name in self.strategies:
            self.strategies[strategy_name].set_parameter(param_name, value)
    
    def get_strategy_parameters(self, strategy_name: str) -> Dict[str, Any]:
        """Get parameters for a specific strategy."""
        if strategy_name in self.strategies:
            return self.strategies[strategy_name].get_parameters()
        return {}
    
    def get_analysis_results(self) -> Dict[str, AnalysisResult]:
        """Get the latest analysis results."""
        return self.latest_results.copy()
    
    def _update_analysis(self):
        """Update analysis for all enabled strategies."""
        if not self.current_mechanism or len(self.motion_history) < 2:
            return
        
        motion_list = list(self.motion_history)
        updated_results = {}
        
        for name, strategy in self.strategies.items():
            if strategy.enabled:
                try:
                    result = strategy.analyze(motion_list, self.current_mechanism)
                    self.latest_results[name] = result
                    updated_results[name] = result
                except Exception as e:
                    logger.error(f"Error in {name} analysis: {e}")
        
        if updated_results:
            self.analysis_updated.emit(updated_results)
    
    def export_analysis_data(self) -> Dict[str, Any]:
        """Export analysis data for reporting."""
        export_data = {
            "timestamp": QTimer.singleShot,  # Current time
            "mechanism_type": self.current_mechanism.get_mechanism_type() if self.current_mechanism else "unknown",
            "motion_points_count": len(self.motion_history),
            "analysis_results": {}
        }
        
        for name, result in self.latest_results.items():
            export_data["analysis_results"][name] = {
                "statistics": result.statistics,
                "recommendations": result.recommendations
            }
        
        return export_data