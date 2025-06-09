"""Path sampling utilities for animation."""

import logging
from typing import List, Optional, Tuple
import numpy as np

from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPainterPath


class PathSampler:
    """Utilities for sampling points along paths."""
    
    @staticmethod
    def sample_painter_path(path: QPainterPath, 
                          num_samples: int) -> List[QPointF]:
        """Sample points uniformly along a QPainterPath.
        
        Args:
            path: The path to sample
            num_samples: Number of samples to take
            
        Returns:
            List of sampled points
        """
        if path.isEmpty() or num_samples < 2:
            return []
        
        samples = []
        for i in range(num_samples):
            t = i / (num_samples - 1)
            point = path.pointAtPercent(t)
            samples.append(point)
        
        logging.debug(f"Sampled {num_samples} points from painter path")
        return samples
    
    @staticmethod
    def sample_points_uniform(points: List[QPointF], 
                            num_samples: int) -> List[QPointF]:
        """Sample points uniformly from a list of points.
        
        Args:
            points: Original points
            num_samples: Number of samples to take
            
        Returns:
            List of sampled points
        """
        if not points or num_samples < 2:
            return []
        
        if len(points) == 1:
            return [points[0]] * num_samples
        
        # Calculate cumulative distances
        distances = [0.0]
        for i in range(1, len(points)):
            dx = points[i].x() - points[i-1].x()
            dy = points[i].y() - points[i-1].y()
            dist = (dx*dx + dy*dy)**0.5
            distances.append(distances[-1] + dist)
        
        total_length = distances[-1]
        if total_length < 0.001:
            return [points[0]] * num_samples
        
        # Sample at uniform distances
        samples = []
        for i in range(num_samples):
            target_dist = (i / (num_samples - 1)) * total_length
            
            # Find segment containing target distance
            for j in range(1, len(distances)):
                if distances[j] >= target_dist:
                    # Interpolate within segment
                    segment_start = distances[j-1]
                    segment_end = distances[j]
                    segment_length = segment_end - segment_start
                    
                    if segment_length > 0:
                        t = (target_dist - segment_start) / segment_length
                    else:
                        t = 0
                    
                    # Linear interpolation
                    p1 = points[j-1]
                    p2 = points[j]
                    x = p1.x() + (p2.x() - p1.x()) * t
                    y = p1.y() + (p2.y() - p1.y()) * t
                    
                    samples.append(QPointF(x, y))
                    break
            else:
                # Use last point
                samples.append(points[-1])
        
        return samples
    
    @staticmethod
    def smooth_path(points: List[QPointF], 
                   window_size: int = 5) -> List[QPointF]:
        """Apply smoothing to a path using moving average.
        
        Args:
            points: Original points
            window_size: Size of smoothing window
            
        Returns:
            Smoothed points
        """
        if not points or len(points) < window_size:
            return points
        
        # Convert to numpy arrays for easier processing
        x_coords = np.array([p.x() for p in points])
        y_coords = np.array([p.y() for p in points])
        
        # Apply moving average
        kernel = np.ones(window_size) / window_size
        x_smooth = np.convolve(x_coords, kernel, mode='same')
        y_smooth = np.convolve(y_coords, kernel, mode='same')
        
        # Handle edges
        half_window = window_size // 2
        x_smooth[:half_window] = x_coords[:half_window]
        x_smooth[-half_window:] = x_coords[-half_window:]
        y_smooth[:half_window] = y_coords[:half_window]
        y_smooth[-half_window:] = y_coords[-half_window:]
        
        # Convert back to QPointF
        smoothed = [QPointF(x, y) for x, y in zip(x_smooth, y_smooth)]
        
        logging.debug(f"Smoothed path with window size {window_size}")
        return smoothed
    
    @staticmethod
    def calculate_path_length(points: List[QPointF]) -> float:
        """Calculate total length of a path.
        
        Args:
            points: Path points
            
        Returns:
            Total path length
        """
        if not points or len(points) < 2:
            return 0.0
        
        total_length = 0.0
        for i in range(1, len(points)):
            dx = points[i].x() - points[i-1].x()
            dy = points[i].y() - points[i-1].y()
            total_length += (dx*dx + dy*dy)**0.5
        
        return total_length
    
    @staticmethod
    def get_point_at_distance(points: List[QPointF], 
                            distance: float) -> Optional[QPointF]:
        """Get point at specific distance along path.
        
        Args:
            points: Path points
            distance: Distance along path
            
        Returns:
            Point at distance, or None if invalid
        """
        if not points:
            return None
        
        if distance <= 0:
            return points[0]
        
        current_dist = 0.0
        for i in range(1, len(points)):
            dx = points[i].x() - points[i-1].x()
            dy = points[i].y() - points[i-1].y()
            segment_length = (dx*dx + dy*dy)**0.5
            
            if current_dist + segment_length >= distance:
                # Point is in this segment
                remaining = distance - current_dist
                if segment_length > 0:
                    t = remaining / segment_length
                else:
                    t = 0
                
                x = points[i-1].x() + dx * t
                y = points[i-1].y() + dy * t
                return QPointF(x, y)
            
            current_dist += segment_length
        
        # Distance exceeds path length
        return points[-1] if points else None