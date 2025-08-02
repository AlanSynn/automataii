"""
Performance Optimizer for Parametric Editing System

Provides advanced performance optimization techniques for real-time
parametric editing, including update throttling, batching, and caching.

Author: AI Engineering Assistant
Architecture: Performance-first design with monitoring and adaptive behavior
"""

import logging
import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from threading import RLock
from typing import Any

from PyQt6.QtCore import QObject, QTimer
from PyQt6.QtCore import pyqtSignal as Signal

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics for monitoring system health."""

    update_count: int = 0
    validation_count: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    throttled_updates: int = 0
    batched_updates: int = 0
    total_processing_time: float = 0.0
    peak_memory_usage: int = 0
    average_update_time: float = 0.0
    last_update_time: float = 0.0

    def get_cache_hit_rate(self) -> float:
        """Calculate cache hit rate percentage."""
        total_requests = self.cache_hits + self.cache_misses
        return (self.cache_hits / total_requests * 100) if total_requests > 0 else 0.0

    def get_updates_per_second(self) -> float:
        """Calculate updates per second."""
        if self.total_processing_time > 0:
            return self.update_count / self.total_processing_time
        return 0.0


@dataclass
class UpdateRequest:
    """Represents a parameter update request."""

    mechanism_id: str
    param_name: str
    new_value: Any
    timestamp: float
    priority: int = 0  # Higher values = higher priority
    batch_id: str | None = None

    def __post_init__(self):
        if self.timestamp == 0:
            self.timestamp = time.time()


class PerformanceOptimizer(QObject):
    """
    Advanced performance optimizer for parametric editing.

    Features:
    - Adaptive update throttling based on system load
    - Intelligent batching of related updates
    - Result caching with LRU eviction
    - Memory usage monitoring and optimization
    - Performance metrics and adaptive behavior
    - Thread-safe operations
    """

    # Signals for performance monitoring
    performance_warning = Signal(str)  # Warning message
    performance_critical = Signal(str)  # Critical performance issue
    metrics_updated = Signal(dict)  # Updated metrics

    def __init__(self, parent=None):
        super().__init__(parent)

        # Thread safety
        self._lock = RLock()

        # Performance configuration
        self.base_throttle_ms = 16  # Target 60 FPS (16ms per frame)
        self.max_throttle_ms = 100  # Maximum throttle delay
        self.adaptive_throttling = True
        self.cache_size_limit = 1000  # Maximum cached results
        self.batch_timeout_ms = 50  # Maximum time to wait for batch
        self.memory_limit_mb = 100  # Memory usage warning threshold

        # Update queues and timers
        self.update_queue: deque = deque()
        self.priority_queue: deque = deque()  # High priority updates
        self.batch_groups: dict[str, list[UpdateRequest]] = defaultdict(list)

        # Throttling system
        self.throttle_timer = QTimer()
        self.throttle_timer.timeout.connect(self._process_throttled_updates)
        self.throttle_timer.setSingleShot(True)

        # Batch processing timer
        self.batch_timer = QTimer()
        self.batch_timer.timeout.connect(self._process_batched_updates)
        self.batch_timer.setSingleShot(True)

        # Caching system
        self.result_cache: dict[str, Any] = {}
        self.cache_access_order: deque = deque()  # LRU tracking
        self.cache_timestamps: dict[str, float] = {}

        # Performance monitoring
        self.metrics = PerformanceMetrics()
        self.load_history: deque = deque(maxlen=100)  # Recent load measurements
        self.update_times: deque = deque(maxlen=50)  # Recent update times

        # Adaptive behavior
        self.current_throttle_ms = self.base_throttle_ms
        self.last_load_check = time.time()
        self.load_check_interval = 1.0  # Check load every second

        # Callbacks
        self.update_callbacks: dict[str, Callable] = {}
        self.validation_callbacks: dict[str, Callable] = {}

        logger.info("PerformanceOptimizer initialized with adaptive throttling")

    def register_update_callback(self, mechanism_type: str, callback: Callable):
        """Register callback for mechanism updates."""
        with self._lock:
            self.update_callbacks[mechanism_type] = callback

    def register_validation_callback(self, mechanism_type: str, callback: Callable):
        """Register callback for parameter validation."""
        with self._lock:
            self.validation_callbacks[mechanism_type] = callback

    def queue_update(
        self,
        mechanism_id: str,
        param_name: str,
        new_value: Any,
        priority: int = 0,
        batch_id: str | None = None,
    ) -> bool:
        """
        Queue a parameter update for optimized processing.

        Args:
            mechanism_id: Mechanism identifier
            param_name: Parameter name
            new_value: New parameter value
            priority: Update priority (0=normal, 1=high, 2=critical)
            batch_id: Optional batch identifier for grouping

        Returns:
            True if queued successfully
        """
        try:
            with self._lock:
                request = UpdateRequest(
                    mechanism_id=mechanism_id,
                    param_name=param_name,
                    new_value=new_value,
                    priority=priority,
                    batch_id=batch_id,
                )

                # Route to appropriate queue
                if priority >= 2:
                    # Critical updates bypass throttling
                    self.priority_queue.append(request)
                    self._process_priority_updates()
                elif batch_id:
                    # Batched updates
                    self.batch_groups[batch_id].append(request)
                    self._schedule_batch_processing()
                else:
                    # Normal throttled updates
                    self.update_queue.append(request)
                    self._schedule_throttled_processing()

                return True

        except Exception as e:
            logger.error(f"Failed to queue update: {e}")
            return False

    def _schedule_throttled_processing(self):
        """Schedule throttled update processing."""
        if not self.throttle_timer.isActive():
            self.throttle_timer.start(self.current_throttle_ms)

    def _schedule_batch_processing(self):
        """Schedule batch processing."""
        if not self.batch_timer.isActive():
            self.batch_timer.start(self.batch_timeout_ms)

    def _process_priority_updates(self):
        """Process high-priority updates immediately."""
        with self._lock:
            while self.priority_queue:
                request = self.priority_queue.popleft()
                self._execute_update(request)

    def _process_throttled_updates(self):
        """Process throttled updates."""
        start_time = time.time()
        processed_count = 0

        with self._lock:
            # Process updates in batches to avoid blocking
            max_batch_size = 10

            while self.update_queue and processed_count < max_batch_size:
                request = self.update_queue.popleft()
                self._execute_update(request)
                processed_count += 1

            # Schedule next batch if more updates remain
            if self.update_queue:
                self._schedule_throttled_processing()

        # Update performance metrics
        processing_time = time.time() - start_time
        self.update_times.append(processing_time)
        self._update_adaptive_throttling()

    def _process_batched_updates(self):
        """Process batched updates."""
        with self._lock:
            for batch_id, requests in self.batch_groups.items():
                if requests:
                    self._execute_batch(batch_id, requests)
                    self.metrics.batched_updates += 1

            self.batch_groups.clear()

    def _execute_update(self, request: UpdateRequest):
        """Execute a single update request."""
        try:
            start_time = time.time()

            # Check cache first
            cache_key = self._get_cache_key(request)
            cached_result = self._get_cached_result(cache_key)

            if cached_result is not None:
                self.metrics.cache_hits += 1
                result = cached_result
            else:
                self.metrics.cache_misses += 1

                # Execute update
                result = self._perform_update(request)

                # Cache result
                self._cache_result(cache_key, result)

            # Update metrics
            processing_time = time.time() - start_time
            self.metrics.total_processing_time += processing_time
            self.metrics.update_count += 1
            self.metrics.last_update_time = time.time()

            # Calculate average update time
            if self.metrics.update_count > 0:
                self.metrics.average_update_time = (
                    self.metrics.total_processing_time / self.metrics.update_count
                )

            logger.debug(
                f"Executed update for {request.mechanism_id}.{request.param_name} in {processing_time:.3f}s"
            )

        except Exception as e:
            logger.error(f"Failed to execute update: {e}")

    def _execute_batch(self, batch_id: str, requests: list[UpdateRequest]):
        """Execute a batch of related updates."""
        try:
            start_time = time.time()

            # Group requests by mechanism
            mechanism_groups = defaultdict(list)
            for request in requests:
                mechanism_groups[request.mechanism_id].append(request)

            # Process each mechanism group
            for mechanism_id, mech_requests in mechanism_groups.items():
                self._perform_batch_update(mechanism_id, mech_requests)

            # Update metrics
            processing_time = time.time() - start_time
            self.metrics.total_processing_time += processing_time
            self.metrics.update_count += len(requests)

            logger.debug(
                f"Executed batch {batch_id} with {len(requests)} updates in {processing_time:.3f}s"
            )

        except Exception as e:
            logger.error(f"Failed to execute batch {batch_id}: {e}")

    def _perform_update(self, request: UpdateRequest) -> Any:
        """Perform the actual update operation."""
        # This would call the appropriate mechanism update callback
        # For now, return a placeholder result
        return {"status": "success", "request": request}

    def _perform_batch_update(self, mechanism_id: str, requests: list[UpdateRequest]) -> Any:
        """Perform batch update for a mechanism."""
        # Group all parameter changes for this mechanism
        param_changes = {}
        for request in requests:
            param_changes[request.param_name] = request.new_value

        # Execute single batch update
        return {"status": "batch_success", "mechanism_id": mechanism_id, "changes": param_changes}

    def _get_cache_key(self, request: UpdateRequest) -> str:
        """Generate cache key for update request."""
        return f"{request.mechanism_id}_{request.param_name}_{hash(str(request.new_value))}"

    def _get_cached_result(self, cache_key: str) -> Any | None:
        """Get cached result if available and valid."""
        if cache_key in self.result_cache:
            # Move to end for LRU
            self.cache_access_order.remove(cache_key)
            self.cache_access_order.append(cache_key)
            return self.result_cache[cache_key]
        return None

    def _cache_result(self, cache_key: str, result: Any):
        """Cache update result with LRU eviction."""
        # Remove oldest entries if cache is full
        while len(self.result_cache) >= self.cache_size_limit:
            oldest_key = self.cache_access_order.popleft()
            del self.result_cache[oldest_key]
            del self.cache_timestamps[oldest_key]

        # Add new result
        self.result_cache[cache_key] = result
        self.cache_access_order.append(cache_key)
        self.cache_timestamps[cache_key] = time.time()

    def _update_adaptive_throttling(self):
        """Update throttling based on current system load."""
        if not self.adaptive_throttling:
            return

        current_time = time.time()
        if current_time - self.last_load_check < self.load_check_interval:
            return

        # Calculate recent load
        recent_load = self._calculate_system_load()
        self.load_history.append(recent_load)

        # Adjust throttling based on load
        if recent_load > 0.8:  # High load
            self.current_throttle_ms = min(self.max_throttle_ms, self.current_throttle_ms * 1.2)
            self.performance_warning.emit(f"High system load detected: {recent_load:.2f}")
        elif recent_load < 0.3:  # Low load
            self.current_throttle_ms = max(self.base_throttle_ms, self.current_throttle_ms * 0.9)

        self.last_load_check = current_time

    def _calculate_system_load(self) -> float:
        """Calculate current system load based on update times."""
        if not self.update_times:
            return 0.0

        # Use recent update times as proxy for load
        recent_times = list(self.update_times)[-10:]  # Last 10 updates
        avg_time = sum(recent_times) / len(recent_times)

        # Normalize to 0-1 range (assuming 50ms is "high load")
        load = min(1.0, avg_time / 0.05)
        return load

    def get_performance_metrics(self) -> dict[str, Any]:
        """Get comprehensive performance metrics."""
        with self._lock:
            return {
                "update_count": self.metrics.update_count,
                "validation_count": self.metrics.validation_count,
                "cache_hit_rate": self.metrics.get_cache_hit_rate(),
                "cache_hits": self.metrics.cache_hits,
                "cache_misses": self.metrics.cache_misses,
                "throttled_updates": self.metrics.throttled_updates,
                "batched_updates": self.metrics.batched_updates,
                "total_processing_time": self.metrics.total_processing_time,
                "average_update_time": self.metrics.average_update_time,
                "updates_per_second": self.metrics.get_updates_per_second(),
                "current_throttle_ms": self.current_throttle_ms,
                "queue_size": len(self.update_queue),
                "priority_queue_size": len(self.priority_queue),
                "batch_groups": len(self.batch_groups),
                "cache_size": len(self.result_cache),
                "recent_load": self.load_history[-1] if self.load_history else 0.0,
                "memory_usage_mb": self._estimate_memory_usage(),
            }

    def _estimate_memory_usage(self) -> float:
        """Estimate current memory usage in MB."""
        # Rough estimation based on cached data
        cache_size = len(self.result_cache) * 0.001  # Assume 1KB per cache entry
        queue_size = len(self.update_queue) * 0.0001  # Assume 0.1KB per queue entry
        return cache_size + queue_size

    def optimize_memory(self):
        """Perform memory optimization."""
        with self._lock:
            # Clear old cache entries
            current_time = time.time()
            cache_ttl = 300  # 5 minutes

            expired_keys = [
                key
                for key, timestamp in self.cache_timestamps.items()
                if current_time - timestamp > cache_ttl
            ]

            for key in expired_keys:
                del self.result_cache[key]
                del self.cache_timestamps[key]
                if key in self.cache_access_order:
                    self.cache_access_order.remove(key)

            # Trim load history
            if len(self.load_history) > 50:
                self.load_history = deque(list(self.load_history)[-50:], maxlen=100)

            # Trim update times
            if len(self.update_times) > 25:
                self.update_times = deque(list(self.update_times)[-25:], maxlen=50)

            logger.info(
                f"Memory optimization completed. Removed {len(expired_keys)} expired cache entries"
            )

    def reset_metrics(self):
        """Reset performance metrics."""
        with self._lock:
            self.metrics = PerformanceMetrics()
            self.load_history.clear()
            self.update_times.clear()
            logger.info("Performance metrics reset")

    def set_throttling_mode(self, adaptive: bool, base_ms: int = None):
        """Configure throttling behavior."""
        with self._lock:
            self.adaptive_throttling = adaptive
            if base_ms is not None:
                self.base_throttle_ms = base_ms
                self.current_throttle_ms = base_ms

            logger.info(
                f"Throttling mode: {'adaptive' if adaptive else 'fixed'} at {self.base_throttle_ms}ms"
            )

    def clear_cache(self):
        """Clear all cached results."""
        with self._lock:
            self.result_cache.clear()
            self.cache_access_order.clear()
            self.cache_timestamps.clear()
            logger.info("Performance cache cleared")

    def shutdown(self):
        """Shutdown optimizer and cleanup resources."""
        with self._lock:
            # Stop timers
            self.throttle_timer.stop()
            self.batch_timer.stop()

            # Clear all data
            self.update_queue.clear()
            self.priority_queue.clear()
            self.batch_groups.clear()
            self.clear_cache()

            # Final metrics
            final_metrics = self.get_performance_metrics()
            logger.info(f"PerformanceOptimizer shutdown. Final metrics: {final_metrics}")


class PerformanceProfiler:
    """Context manager for profiling performance-critical sections."""

    def __init__(self, name: str, optimizer: PerformanceOptimizer):
        self.name = name
        self.optimizer = optimizer
        self.start_time = 0

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        logger.debug(f"Performance profile [{self.name}]: {duration:.3f}s")

        # Update optimizer metrics
        if hasattr(self.optimizer, "metrics"):
            self.optimizer.metrics.total_processing_time += duration
