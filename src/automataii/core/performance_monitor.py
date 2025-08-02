"""
Performance Monitoring and Optimization

Provides performance monitoring, profiling, and optimization utilities
for the Automataii application.
"""

import time
import functools
import logging
import threading
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from collections import defaultdict, deque
import psutil
import gc

from PyQt6.QtCore import QObject, QTimer, pyqtSignal


@dataclass
class PerformanceMetrics:
    """Performance metrics container."""
    function_name: str
    call_count: int = 0
    total_time: float = 0.0
    average_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    last_call_time: float = 0.0
    recent_times: deque = field(default_factory=lambda: deque(maxlen=100))


class PerformanceMonitor(QObject):
    """
    Performance monitoring system for application optimization.
    
    Features:
    - Function call timing and profiling
    - Memory usage monitoring
    - Event loop performance tracking
    - Resource leak detection
    - Performance metrics aggregation
    """
    
    # Signals for performance alerts
    performance_alert = pyqtSignal(str, float)  # metric_name, value
    memory_warning = pyqtSignal(float)  # memory_usage_mb
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        
        # Performance tracking
        self.metrics: Dict[str, PerformanceMetrics] = {}
        self.start_times: Dict[str, float] = {}
        self.enabled = True
        
        # Memory monitoring
        self.memory_samples = deque(maxlen=1000)
        self.memory_threshold_mb = 500  # Alert threshold
        
        # Resource monitoring
        self.graphics_items_count = 0
        self.signal_connections_count = 0
        
        # Setup monitoring timer
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self._collect_system_metrics)
        self.monitor_timer.start(5000)  # Collect every 5 seconds
        
        # Thread safety
        self.lock = threading.RLock()
        
        self.logger.info("PerformanceMonitor initialized")
    
    def enable_monitoring(self, enabled: bool = True):
        """Enable or disable performance monitoring."""
        self.enabled = enabled
        if enabled:
            self.monitor_timer.start(5000)
        else:
            self.monitor_timer.stop()
    
    def start_timer(self, operation_name: str):
        """Start timing an operation."""
        if not self.enabled:
            return
        
        with self.lock:
            self.start_times[operation_name] = time.perf_counter()
    
    def end_timer(self, operation_name: str) -> float:
        """End timing an operation and record metrics."""
        if not self.enabled:
            return 0.0
        
        end_time = time.perf_counter()
        
        with self.lock:
            start_time = self.start_times.get(operation_name)
            if start_time is None:
                self.logger.warning(f"No start time found for operation: {operation_name}")
                return 0.0
            
            duration = end_time - start_time
            del self.start_times[operation_name]
            
            # Update metrics
            if operation_name not in self.metrics:
                self.metrics[operation_name] = PerformanceMetrics(operation_name)
            
            metrics = self.metrics[operation_name]
            metrics.call_count += 1
            metrics.total_time += duration
            metrics.average_time = metrics.total_time / metrics.call_count
            metrics.min_time = min(metrics.min_time, duration)
            metrics.max_time = max(metrics.max_time, duration)
            metrics.last_call_time = duration
            metrics.recent_times.append(duration)
            
            # Check for performance alerts
            self._check_performance_alerts(operation_name, duration)
            
            return duration
    
    def record_metric(self, metric_name: str, value: float):
        """Record a custom performance metric."""
        if not self.enabled:
            return
        
        with self.lock:
            if metric_name not in self.metrics:
                self.metrics[metric_name] = PerformanceMetrics(metric_name)
            
            metrics = self.metrics[metric_name]
            metrics.call_count += 1
            metrics.total_time += value  # Using total_time as accumulator
            metrics.average_time = metrics.total_time / metrics.call_count
            metrics.min_time = min(metrics.min_time, value)
            metrics.max_time = max(metrics.max_time, value)
            metrics.last_call_time = value
            metrics.recent_times.append(value)
    
    def _collect_system_metrics(self):
        """Collect system-level performance metrics."""
        if not self.enabled:
            return
        
        try:
            # Memory usage
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            self.memory_samples.append(memory_mb)
            
            # Check memory threshold
            if memory_mb > self.memory_threshold_mb:
                self.memory_warning.emit(memory_mb)
            
            # CPU usage
            cpu_percent = process.cpu_percent()
            self.record_metric("cpu_usage_percent", cpu_percent)
            
            # Record system metrics
            self.record_metric("memory_usage_mb", memory_mb)
            self.record_metric("graphics_items_count", self.graphics_items_count)
            self.record_metric("signal_connections_count", self.signal_connections_count)
            
            # Garbage collection stats
            gc_stats = gc.get_stats()
            if gc_stats:
                self.record_metric("gc_generation0_collections", gc_stats[0]['collections'])
                self.record_metric("gc_generation0_collected", gc_stats[0]['collected'])
            
        except Exception as e:
            self.logger.warning(f"Error collecting system metrics: {e}")
    
    def _check_performance_alerts(self, operation_name: str, duration: float):
        """Check for performance issues and emit alerts."""
        # Define thresholds for different operations
        thresholds = {
            "animation_frame": 0.016,  # 60 FPS = 16ms per frame
            "ik_solve": 0.010,         # 10ms for IK solving
            "path_drawing": 0.005,     # 5ms for path operations
            "scene_update": 0.020,     # 20ms for scene updates
        }
        
        # Check operation-specific thresholds
        for pattern, threshold in thresholds.items():
            if pattern in operation_name.lower() and duration > threshold:
                self.performance_alert.emit(f"{operation_name}_slow", duration)
                self.logger.warning(f"Performance alert: {operation_name} took {duration:.3f}s (threshold: {threshold:.3f}s)")
                break
        
        # Check for general slow operations
        if duration > 0.100:  # 100ms general threshold
            self.performance_alert.emit(f"{operation_name}_very_slow", duration)
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of all performance metrics."""
        with self.lock:
            summary = {}
            
            for name, metrics in self.metrics.items():
                summary[name] = {
                    "call_count": metrics.call_count,
                    "total_time": metrics.total_time,
                    "average_time": metrics.average_time,
                    "min_time": metrics.min_time,
                    "max_time": metrics.max_time,
                    "last_call_time": metrics.last_call_time,
                    "recent_average": sum(metrics.recent_times) / len(metrics.recent_times) if metrics.recent_times else 0.0
                }
            
            # Add memory summary
            if self.memory_samples:
                summary["memory_stats"] = {
                    "current_mb": self.memory_samples[-1],
                    "average_mb": sum(self.memory_samples) / len(self.memory_samples),
                    "peak_mb": max(self.memory_samples),
                    "samples_count": len(self.memory_samples)
                }
            
            return summary
    
    def get_slow_operations(self, threshold: float = 0.050) -> Dict[str, PerformanceMetrics]:
        """Get operations that are slower than threshold."""
        with self.lock:
            slow_ops = {}
            for name, metrics in self.metrics.items():
                if metrics.average_time > threshold or metrics.max_time > threshold * 2:
                    slow_ops[name] = metrics
            return slow_ops
    
    def reset_metrics(self):
        """Reset all performance metrics."""
        with self.lock:
            self.metrics.clear()
            self.start_times.clear()
            self.memory_samples.clear()
        
        self.logger.info("Performance metrics reset")
    
    def update_resource_counts(self, graphics_items: int = None, signal_connections: int = None):
        """Update resource usage counts."""
        if graphics_items is not None:
            self.graphics_items_count = graphics_items
        if signal_connections is not None:
            self.signal_connections_count = signal_connections
    
    def log_metrics_summary(self):
        """Log a summary of performance metrics."""
        summary = self.get_metrics_summary()
        
        self.logger.info("=== Performance Metrics Summary ===")
        
        # Log slow operations
        slow_ops = self.get_slow_operations()
        if slow_ops:
            self.logger.warning(f"Slow operations detected: {list(slow_ops.keys())}")
            for name, metrics in slow_ops.items():
                self.logger.warning(f"  {name}: avg={metrics.average_time:.3f}s, max={metrics.max_time:.3f}s")
        
        # Log memory usage
        if "memory_stats" in summary:
            mem_stats = summary["memory_stats"]
            self.logger.info(f"Memory usage: current={mem_stats['current_mb']:.1f}MB, "
                           f"average={mem_stats['average_mb']:.1f}MB, peak={mem_stats['peak_mb']:.1f}MB")
        
        # Log top time-consuming operations
        operations_by_total = sorted(
            [(name, data) for name, data in summary.items() if "total_time" in data],
            key=lambda x: x[1]["total_time"],
            reverse=True
        )[:5]
        
        if operations_by_total:
            self.logger.info("Top time-consuming operations:")
            for name, data in operations_by_total:
                self.logger.info(f"  {name}: {data['total_time']:.3f}s total "
                               f"({data['call_count']} calls, avg={data['average_time']:.3f}s)")
    
    def shutdown(self):
        """Shutdown performance monitoring."""
        self.monitor_timer.stop()
        self.log_metrics_summary()
        self.logger.info("PerformanceMonitor shutdown")


def profile_function(func: Callable) -> Callable:
    """
    Decorator to profile function execution time.
    
    Usage:
    @profile_function
    def my_function():
        pass
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Get global performance monitor (you'd need to implement this)
        monitor = getattr(wrapper, '_performance_monitor', None)
        if not monitor:
            return func(*args, **kwargs)
        
        operation_name = f"{func.__module__}.{func.__qualname__}"
        monitor.start_timer(operation_name)
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            monitor.end_timer(operation_name)
    
    return wrapper


class PerformanceContext:
    """Context manager for timing code blocks."""
    
    def __init__(self, monitor: PerformanceMonitor, operation_name: str):
        self.monitor = monitor
        self.operation_name = operation_name
    
    def __enter__(self):
        self.monitor.start_timer(self.operation_name)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.monitor.end_timer(self.operation_name)


# Global performance monitor instance
_global_performance_monitor: Optional[PerformanceMonitor] = None


def get_global_performance_monitor() -> Optional[PerformanceMonitor]:
    """Get the global performance monitor instance."""
    return _global_performance_monitor


def set_global_performance_monitor(monitor: PerformanceMonitor):
    """Set the global performance monitor instance."""
    global _global_performance_monitor
    _global_performance_monitor = monitor


def time_operation(operation_name: str):
    """Context manager for timing operations using global monitor."""
    monitor = get_global_performance_monitor()
    if monitor:
        return PerformanceContext(monitor, operation_name)
    else:
        # No-op context manager if no monitor available
        class NoOpContext:
            def __enter__(self): return self
            def __exit__(self, *args): pass
        return NoOpContext()