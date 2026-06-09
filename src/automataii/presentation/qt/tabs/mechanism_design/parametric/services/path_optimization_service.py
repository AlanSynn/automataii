"""
Path Optimization Service for 4-bar linkage parametric design.

This service provides path optimization functionality to match mechanism coupler paths
to user-defined target paths using scipy optimization algorithms.
"""

import logging
import math
from typing import Any, SupportsFloat, SupportsIndex, cast

import numpy as np
from PyQt6.QtCore import QObject, QPointF, QTimer
from PyQt6.QtCore import pyqtSignal as Signal
from scipy.optimize import least_squares

from ..controllers.parameter_controller import ParameterController

_FloatPayload = str | bytes | bytearray | SupportsFloat | SupportsIndex


def _finite_float(value: object, default: float) -> float:
    try:
        result = float(cast(_FloatPayload, value))
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _positive_finite_float(value: object, default: float, minimum: float = 0.0) -> float:
    result = _finite_float(value, default)
    return result if result > minimum else default


def _positive_int(value: object, default: int, minimum: int = 1, maximum: int | None = None) -> int:
    if isinstance(value, bool):
        return default
    raw = _finite_float(value, math.nan)
    if not math.isfinite(raw):
        return default
    result = max(minimum, int(raw))
    if maximum is not None:
        result = min(maximum, result)
    return result


def _finite_qpoint(value: object) -> QPointF | None:
    if isinstance(value, QPointF):
        x = _finite_float(value.x(), math.nan)
        y = _finite_float(value.y(), math.nan)
    elif isinstance(value, list | tuple) and len(value) >= 2:
        x = _finite_float(value[0], math.nan)
        y = _finite_float(value[1], math.nan)
    else:
        return None
    if not math.isfinite(x) or not math.isfinite(y):
        return None
    return QPointF(x, y)


class PathOptimizationService(QObject):
    """
    Service for optimizing 4-bar linkage parameters to match target paths.

    Features:
    - Target path definition and storage
    - Multi-objective optimization for path matching
    - Real-time progress monitoring
    - Constraint validation during optimization
    - Integration with ParameterController for updates

    Uses scipy.optimize.least_squares for robust optimization.
    """

    # Signals for optimization progress and completion
    optimization_started = Signal(str)  # mechanism_id
    optimization_progress = Signal(str, float)  # mechanism_id, progress (0-1)
    optimization_completed = Signal(str, dict)  # mechanism_id, results
    optimization_failed = Signal(str, str)  # mechanism_id, error_message

    def __init__(self, parameter_controller: ParameterController, parent=None):
        """
        Initialize path optimization service.

        Args:
            parameter_controller: Reference to ParameterController for mechanism updates
            parent: Qt parent object
        """
        super().__init__(parent)

        self.parameter_controller = parameter_controller

        # Target paths storage: mechanism_id -> target_path_points
        self.target_paths: dict[str, list[QPointF]] = {}

        # Optimization state
        self.active_optimizations: dict[str, bool] = {}  # mechanism_id -> is_running
        self.optimization_results: dict[str, dict] = {}  # mechanism_id -> results

        # Optimization parameters
        self.max_iterations = 100
        self.tolerance = 1e-6
        self.path_sample_count = 20  # Number of points to sample from mechanism path

        # Progress tracking
        self.progress_timer = QTimer()
        self.progress_timer.timeout.connect(self._update_progress)

        logging.debug("PathOptimizationService initialized")

    def has_target_path(self, mechanism_id: str) -> bool:
        """
        Check if mechanism has target path set.

        Args:
            mechanism_id: Mechanism ID

        Returns:
            True if target path exists
        """
        return bool(self._finite_target_path(mechanism_id))

    def _finite_target_path(self, mechanism_id: str) -> list[QPointF]:
        raw_path = self.target_paths.get(mechanism_id, [])
        if not isinstance(raw_path, list):
            return []
        finite_points: list[QPointF] = []
        for point in raw_path:
            finite_point = _finite_qpoint(point)
            if finite_point is not None:
                finite_points.append(finite_point)
        return finite_points

    def _get_mechanism_data(self, mechanism_id: str) -> dict[str, Any] | None:
        """Get mechanism data from parameter controller."""
        try:
            mechanism_tab = self.parameter_controller.mechanism_tab
            if hasattr(mechanism_tab, "mechanism_layers"):
                return mechanism_tab.mechanism_layers.get(mechanism_id)
            return None
        except Exception as e:
            logging.error(f"Failed to get mechanism data: {e}")
            return None

    def _extract_current_parameters(self, mechanism_data: dict[str, Any]) -> dict[str, float]:
        """Extract current mechanism parameters for optimization."""
        if not isinstance(mechanism_data, dict):
            return {}
        params = mechanism_data.get("params", {})
        if not isinstance(params, dict):
            return {}

        # For 4-bar linkage, we typically optimize l2, l3, l4
        # l1 is determined by anchor positions
        optimization_params = {}

        for param in ["l2", "l3", "l4", "theta2", "theta3"]:
            if param in params:
                value = _finite_float(params[param], math.nan)
                if not math.isfinite(value):
                    continue
                if param in {"l2", "l3", "l4"}:
                    value = max(5.0, value)
                optimization_params[param] = value

        return optimization_params

    def _run_optimization_async(
        self, mechanism_id: str, initial_params: dict[str, float], mechanism_data: dict[str, Any]
    ):
        """
        Run optimization asynchronously.

        For now, this uses a simple timer-based approach. In a full implementation,
        this would use QThread or asyncio for true asynchronous execution.
        """
        self.active_optimizations[mechanism_id] = True
        target_path = self._finite_target_path(mechanism_id)
        if len(target_path) < 2:
            self.optimization_failed.emit(
                mechanism_id, "Target path must contain at least two finite points"
            )
            self.active_optimizations[mechanism_id] = False
            return
        if not initial_params:
            self.optimization_failed.emit(
                mechanism_id, "No finite parameters available for optimization"
            )
            self.active_optimizations[mechanism_id] = False
            return

        # Create parameter vector for optimization
        param_names = list(initial_params.keys())
        x0 = np.array([_finite_float(initial_params[name], math.nan) for name in param_names])
        if not bool(np.isfinite(x0).all()):
            self.optimization_failed.emit(mechanism_id, "Initial parameters must be finite")
            self.active_optimizations[mechanism_id] = False
            return

        # Start progress tracking only after validation succeeds.
        self.progress_timer.start(100)  # Update every 100ms

        # Define bounds for parameters (prevent invalid configurations)
        bounds = self._get_parameter_bounds(param_names)

        try:
            # Define objective function
            def objective_function(x):
                return self._calculate_path_error(x, param_names, mechanism_data, target_path)

            # Run scipy optimization
            result = least_squares(
                objective_function,
                x0,
                bounds=bounds,
                max_nfev=_positive_int(self.max_iterations, 100, minimum=1),
                ftol=_positive_finite_float(self.tolerance, 1e-6),
                method="trf",  # Trust Region Reflective algorithm
            )

            # Process results
            self._process_optimization_result(mechanism_id, result, param_names)

        except Exception as e:
            logging.error(f"Optimization failed: {e}")
            self.optimization_failed.emit(mechanism_id, str(e))
        finally:
            self.active_optimizations[mechanism_id] = False
            self.progress_timer.stop()

    def _get_parameter_bounds(self, param_names: list[str]) -> tuple[list[float], list[float]]:
        """
        Get parameter bounds for optimization.

        Args:
            param_names: List of parameter names

        Returns:
            Tuple of (lower_bounds, upper_bounds)
        """
        lower_bounds = []
        upper_bounds = []

        for param in param_names:
            if param in ["l2", "l3", "l4"]:
                # Link length bounds
                lower_bounds.append(5.0)  # Minimum link length
                upper_bounds.append(400.0)  # Maximum link length
            elif param in ["theta2", "theta3"]:
                # Angle bounds (in radians)
                lower_bounds.append(-2 * math.pi)
                upper_bounds.append(2 * math.pi)
            else:
                # Default bounds
                lower_bounds.append(-1000.0)
                upper_bounds.append(1000.0)

        return (lower_bounds, upper_bounds)

    def _calculate_path_error(
        self,
        x: np.ndarray,
        param_names: list[str],
        mechanism_data: dict[str, Any],
        target_path: list[QPointF],
    ) -> np.ndarray:
        """
        Calculate error between mechanism path and target path.

        Args:
            x: Parameter values
            param_names: Parameter names
            mechanism_data: Mechanism data
            target_path: Target path points

        Returns:
            Error vector for least squares optimization
        """
        try:
            target_path = [point for point in target_path if _finite_qpoint(point) is not None]
            if not target_path:
                return np.ones(1) * 1000.0
            if not bool(np.isfinite(x).all()):
                return np.ones(len(target_path)) * 1000.0
            # Update mechanism parameters
            updated_params = {
                name: _finite_float(value, math.nan)
                for name, value in zip(param_names, x, strict=False)
            }
            if any(not math.isfinite(value) for value in updated_params.values()):
                return np.ones(len(target_path)) * 1000.0

            # Generate mechanism coupler path
            mechanism_path = self._generate_mechanism_path(updated_params, mechanism_data)

            if not mechanism_path:
                # Return high error if path generation failed
                return np.ones(len(target_path)) * 1000.0

            # Calculate point-to-point errors
            errors = []

            # Sample mechanism path to match target path length
            sampled_mech_path = self._sample_path_points(mechanism_path, len(target_path))

            for i, target_point in enumerate(target_path):
                if i < len(sampled_mech_path):
                    mech_point = sampled_mech_path[i]
                    dx = target_point.x() - mech_point.x()
                    dy = target_point.y() - mech_point.y()
                    if math.isfinite(dx) and math.isfinite(dy):
                        error = math.sqrt(dx * dx + dy * dy)
                    else:
                        error = 1000.0
                else:
                    error = 1000.0  # High error for missing points

                errors.append(error)

            return np.array(errors)

        except Exception as e:
            logging.error(f"Path error calculation failed: {e}")
            return np.ones(len(target_path)) * 1000.0

    def _generate_mechanism_path(
        self, params: dict[str, float], mechanism_data: dict[str, Any]
    ) -> list[QPointF] | None:
        """
        Generate coupler path for current mechanism parameters.

        Args:
            params: Mechanism parameters
            mechanism_data: Mechanism data

        Returns:
            List of coupler path points or None if generation failed
        """
        try:
            if not isinstance(mechanism_data, dict):
                return None
            # Get anchor positions
            key_points = mechanism_data.get("key_points", {})
            if not isinstance(key_points, dict):
                return None
            if "ground_pivot_1" not in key_points or "ground_pivot_2" not in key_points:
                return None

            anchor1 = _finite_qpoint(key_points["ground_pivot_1"])
            anchor2 = _finite_qpoint(key_points["ground_pivot_2"])
            if anchor1 is None or anchor2 is None:
                return None

            # Get link lengths
            l2 = _positive_finite_float(params.get("l2", 30.0), 30.0)
            l3 = _positive_finite_float(params.get("l3", 40.0), 40.0)
            l4 = _positive_finite_float(params.get("l4", 35.0), 35.0)

            # Calculate ground link length
            dx = anchor2.x() - anchor1.x()
            dy = anchor2.y() - anchor1.y()
            ground_length = math.sqrt(dx * dx + dy * dy)
            if not math.isfinite(ground_length) or ground_length <= 0.0:
                return None

            # Generate coupler path by rotating crank
            path_points = []

            sample_count = _positive_int(self.path_sample_count, 20, minimum=4, maximum=720)
            for theta2_deg in np.linspace(0.0, 360.0, sample_count, endpoint=False):
                theta2 = math.radians(theta2_deg)

                # Calculate crank joint position
                crank_x = anchor1.x() + l2 * math.cos(theta2)
                crank_y = anchor1.y() + l2 * math.sin(theta2)
                crank_joint = QPointF(crank_x, crank_y)

                # Solve for rocker angle using triangle closure
                rocker_solution = self._solve_rocker_angle(anchor2, crank_joint, l3, l4)

                if rocker_solution is not None:
                    theta3, rocker_joint = rocker_solution

                    # Calculate coupler point (assume midpoint of coupler link)
                    coupler_x = (crank_joint.x() + rocker_joint.x()) / 2
                    coupler_y = (crank_joint.y() + rocker_joint.y()) / 2
                    coupler_point = QPointF(coupler_x, coupler_y)

                    path_points.append(coupler_point)

            return path_points

        except Exception as e:
            logging.error(f"Mechanism path generation failed: {e}")
            return None

    def _solve_rocker_angle(
        self, anchor2: QPointF, crank_joint: QPointF, l3: float, l4: float
    ) -> tuple[float, QPointF] | None:
        """
        Solve for rocker angle given crank position.

        Args:
            anchor2: Ground pivot 2 position
            crank_joint: Crank joint position
            l3: Rocker length
            l4: Coupler length

        Returns:
            Tuple of (theta3, rocker_joint_pos) or None
        """
        try:
            anchor2_point = _finite_qpoint(anchor2)
            crank_point = _finite_qpoint(crank_joint)
            if anchor2_point is None or crank_point is None:
                return None
            l3 = _positive_finite_float(l3, math.nan)
            l4 = _positive_finite_float(l4, math.nan)
            if not math.isfinite(l3) or not math.isfinite(l4):
                return None
            # Distance from crank joint to anchor2
            dx = anchor2_point.x() - crank_point.x()
            dy = anchor2_point.y() - crank_point.y()
            d = math.sqrt(dx * dx + dy * dy)
            if not math.isfinite(d) or d <= 1e-9:
                return None

            # Check if triangle closure is possible
            if d > (l3 + l4) or d < abs(l3 - l4):
                return None

            # Use cosine rule to find rocker angle
            cos_alpha = (l3 * l3 + d * d - l4 * l4) / (2 * l3 * d)

            if not math.isfinite(cos_alpha):
                return None
            cos_alpha = min(1.0, max(-1.0, cos_alpha))

            alpha = math.acos(cos_alpha)
            gamma = math.atan2(dy, dx)

            # Take the first solution (could be improved to choose better solution)
            theta3 = gamma + alpha

            # Calculate rocker joint position
            rocker_x = anchor2_point.x() + l3 * math.cos(theta3)
            rocker_y = anchor2_point.y() + l3 * math.sin(theta3)
            rocker_joint = QPointF(rocker_x, rocker_y)

            return (theta3, rocker_joint)

        except Exception as e:
            logging.error(f"Rocker angle solving failed: {e}")
            return None

    def _sample_path_points(self, path: list[QPointF], target_count: int) -> list[QPointF]:
        """
        Sample path points to match target count.

        Args:
            path: Original path points
            target_count: Desired number of points

        Returns:
            Sampled path points
        """
        if not path or target_count <= 0:
            return []

        finite_path = [point for point in path if _finite_qpoint(point) is not None]
        if not finite_path:
            return []

        if len(finite_path) <= target_count:
            return list(finite_path)

        # Simple uniform sampling
        sampled = []
        for index in np.linspace(0, len(finite_path) - 1, target_count, dtype=int):
            sampled.append(finite_path[int(index)])

        return sampled

    def _process_optimization_result(self, mechanism_id: str, result, param_names: list[str]):
        """
        Process optimization result and update mechanism.

        Args:
            mechanism_id: Mechanism ID
            result: Scipy optimization result
            param_names: Parameter names
        """
        try:
            # Extract optimized parameters
            optimized_params = {
                name: _finite_float(value, math.nan)
                for name, value in zip(param_names, result.x, strict=False)
            }
            optimized_params = {
                name: value for name, value in optimized_params.items() if math.isfinite(value)
            }
            final_error = _finite_float(result.cost, 1000.0)
            iterations = _positive_int(result.nfev, 0, minimum=0)

            # Create result dictionary
            optimization_result = {
                "success": bool(result.success) and bool(optimized_params),
                "optimized_params": optimized_params,
                "final_error": final_error,
                "iterations": iterations,
                "message": str(result.message),
            }

            # Store results
            self.optimization_results[mechanism_id] = optimization_result

            if result.success:
                # Update mechanism with optimized parameters
                self._apply_optimized_parameters(mechanism_id, optimized_params)

                logging.info(f"Optimization successful for {mechanism_id}: error={result.cost:.4f}")
            else:
                logging.warning(f"Optimization failed for {mechanism_id}: {result.message}")

            # Emit completion signal
            self.optimization_completed.emit(mechanism_id, optimization_result)

        except Exception as e:
            logging.error(f"Failed to process optimization result: {e}")

    def _apply_optimized_parameters(self, mechanism_id: str, optimized_params: dict[str, float]):
        """
        Apply optimized parameters to mechanism through ParameterController.

        Args:
            mechanism_id: Mechanism ID
            optimized_params: Optimized parameter values
        """
        try:
            # Use ParameterController to apply changes
            for param_name, value in optimized_params.items():
                if not math.isfinite(_finite_float(value, math.nan)):
                    continue
                self.parameter_controller._on_parameter_changed(mechanism_id, param_name, value)

            logging.debug(f"Applied optimized parameters to {mechanism_id}")

        except Exception as e:
            logging.error(f"Failed to apply optimized parameters: {e}")

    def _update_progress(self):
        """Update optimization progress (placeholder)."""
        # In a full implementation, this would track actual optimization progress
        # For now, just emit a generic progress update
        for mechanism_id, is_running in self.active_optimizations.items():
            if is_running:
                # Emit progress signal (placeholder value)
                self.optimization_progress.emit(mechanism_id, 0.5)

    def _calculate_success_rate(self) -> float:
        """Calculate optimization success rate."""
        if not self.optimization_results:
            return 0.0

        successful = sum(
            1 for result in self.optimization_results.values() if result.get("success", False)
        )
        return successful / len(self.optimization_results)

    def __repr__(self) -> str:
        """String representation for debugging."""
        active_count = sum(self.active_optimizations.values())
        target_count = len(self.target_paths)
        return f"PathOptimizationService({target_count} targets, {active_count} active)"
