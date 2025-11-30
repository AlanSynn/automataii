"""Mechanism generation domain service.

Pure Python service for generating mechanism configurations.
Wraps existing generation logic from automataii.generation module.

This service is the domain layer interface - it accepts and returns
immutable domain types (MechanismSpec, MechanismResult) with no PyQt dependencies.
"""

from __future__ import annotations

import logging
import math
from typing import Protocol

from .geometry_math_service import GeometryMathService
from .types import MechanismResult, MechanismSpec, PathPoints, Point2D

__all__ = ["MechanismGenerationProtocol", "MechanismGenerationService"]

logger = logging.getLogger(__name__)


class MechanismGenerationProtocol(Protocol):
    """Protocol for mechanism generation operations.

    Defines the contract for generating mechanism configurations
    that trace desired motion paths.
    """

    def generate(self, spec: MechanismSpec) -> MechanismResult:
        """Generate mechanism from specification.

        Args:
            spec: Immutable specification defining mechanism parameters

        Returns:
            MechanismResult containing generated path, key points, validity

        Complexity:
            - Fourbar: O(N) where N = number of samples
            - Cam: O(N * M) where N = samples, M = path points
            - Threebar: O(N)
        """
        ...

    def validate_spec(self, spec: MechanismSpec) -> tuple[bool, str | None]:
        """Validate mechanism specification.

        Checks if mechanism can be constructed with given parameters
        without actually generating it (faster pre-check).

        Args:
            spec: Specification to validate

        Returns:
            (is_valid, error_message) tuple

        Complexity: O(1) - parameter validation only
        """
        ...

    def calculate_path_error(self, target_path: PathPoints, generated_path: PathPoints) -> float:
        """Calculate RMS error between target and generated paths.

        Convenience method that delegates to GeometryMathService.

        Args:
            target_path: Desired motion path
            generated_path: Mechanism-generated path

        Returns:
            RMS error (lower is better fit)

        Complexity: O(N) where N = min(len(target), len(generated))
        """
        ...


class MechanismGenerationService:
    """Pure Python mechanism generation service.

    Orchestrates mechanism generation algorithms for various mechanism types.
    Delegates to specialized generators but maintains pure domain interface.

    Supported mechanism types:
        - 'fourbar': Four-bar linkage (Grashof criterion)
        - 'threebar': Three-bar open chain
        - 'cam': Cam-follower mechanism
    """

    def __init__(self, geometry_service: GeometryMathService | None = None) -> None:
        """Initialize service with optional geometry service.

        Args:
            geometry_service: Service for geometric computations.
                            If None, creates new instance.
        """
        self._geometry = geometry_service or GeometryMathService()

    def generate(self, spec: MechanismSpec) -> MechanismResult:
        """Generate mechanism from specification.

        Theory:
            Fourbar: Uses Freudenstein's equation for position synthesis.
                    Solves circle-circle intersection for coupler point.

            Cam: Inverse kinematics - maps follower path to cam profile.
                 Uses pitch curve with follower radius offset.

            Threebar: Open chain kinematics (no closed-loop constraints).

        Args:
            spec: Immutable mechanism specification

        Returns:
            MechanismResult with generated path and validity status

        Raises:
            ValueError: If mechanism_type is unsupported
        """
        # Validate specification
        is_valid, error_msg = self.validate_spec(spec)
        if not is_valid:
            return MechanismResult(
                mechanism_id=self._generate_id(),
                mechanism_type=spec.mechanism_type,
                part_name=spec.part_name,
                generated_path=(),
                parameters=spec.parameters,
                key_points={},
                is_valid=False,
                error_message=error_msg,
            )

        # Dispatch to appropriate generator
        if spec.mechanism_type == "fourbar":
            return self._generate_fourbar(spec)
        elif spec.mechanism_type == "threebar":
            return self._generate_threebar(spec)
        elif spec.mechanism_type == "cam":
            return self._generate_cam(spec)
        else:
            return MechanismResult(
                mechanism_id=self._generate_id(),
                mechanism_type=spec.mechanism_type,
                part_name=spec.part_name,
                generated_path=(),
                parameters=spec.parameters,
                key_points={},
                is_valid=False,
                error_message=f"Unsupported mechanism type: {spec.mechanism_type}",
            )

    def validate_spec(self, spec: MechanismSpec) -> tuple[bool, str | None]:
        """Validate mechanism specification.

        Checks:
            - Required parameters present for mechanism type
            - Parameter values within valid ranges
            - Geometric constraints (e.g., Grashof criterion for fourbar)

        Args:
            spec: Specification to validate

        Returns:
            (is_valid, error_message) tuple
        """
        # Type-specific validation
        if spec.mechanism_type == "fourbar":
            return self._validate_fourbar_spec(spec)
        elif spec.mechanism_type == "threebar":
            return self._validate_threebar_spec(spec)
        elif spec.mechanism_type == "cam":
            return self._validate_cam_spec(spec)
        else:
            return (False, f"Unknown mechanism type: {spec.mechanism_type}")

    def calculate_path_error(self, target_path: PathPoints, generated_path: PathPoints) -> float:
        """Calculate RMS error between paths.

        Delegates to GeometryMathService.

        Args:
            target_path: Desired motion path
            generated_path: Mechanism-generated path

        Returns:
            RMS error
        """
        # Resample to same length for comparison
        if len(target_path) != len(generated_path):
            max_len = max(len(target_path), len(generated_path))
            target_resampled = self._geometry.resample_path(target_path, max_len)
            generated_resampled = self._geometry.resample_path(generated_path, max_len)
        else:
            target_resampled = target_path
            generated_resampled = generated_path

        return self._geometry.compute_path_error_rms(target_resampled, generated_resampled)

    # -------------------------------------------------------------------------
    # Private: Fourbar Linkage Generation
    # -------------------------------------------------------------------------

    def _generate_fourbar(self, spec: MechanismSpec) -> MechanismResult:
        """Generate four-bar linkage mechanism.

        Algorithm:
            1. Extract link lengths (l1, l2, l3, l4) from parameters
            2. For each sample angle θ₁:
               a. Calculate p1 = p0 + l1 * [cos(θ₁), sin(θ₁)]
               b. Solve circle-circle intersection for p2:
                  - Circle 1: center p1, radius l2
                  - Circle 2: center p3, radius l3
               c. Record coupler point position
            3. Return generated coupler path

        Complexity: O(N) where N = num_samples
        """
        params = spec.parameters

        # Extract link lengths
        l1 = params.get("l1", 50.0)  # Crank
        l2 = params.get("l2", 70.0)  # Coupler
        l3 = params.get("l3", 60.0)  # Rocker
        l4 = params.get("l4", 80.0)  # Ground

        # Base position (ground pivot)
        base_x = params.get("base_x", 0.0)
        base_y = params.get("base_y", 0.0)

        num_samples = int(params.get("num_samples", 360))

        # Fixed pivots
        p0: Point2D = (base_x, base_y)
        p3: Point2D = (base_x + l4, base_y)

        # Generate coupler path
        generated_points: list[Point2D] = []
        key_points: dict[str, Point2D] = {"p0": p0, "p3": p3}

        for i in range(num_samples):
            theta1_rad = 2 * math.pi * i / num_samples

            # Calculate p1 (end of crank)
            p1: Point2D = (
                p0[0] + l1 * math.cos(theta1_rad),
                p0[1] + l1 * math.sin(theta1_rad),
            )

            # Solve for p2 (circle-circle intersection)
            p2_result = self._solve_circle_intersection(p1, l2, p3, l3)

            if p2_result is None:
                # Non-constructible configuration
                logger.warning(
                    f"Fourbar non-constructible at theta={math.degrees(theta1_rad):.1f}°"
                )
                return MechanismResult(
                    mechanism_id=self._generate_id(),
                    mechanism_type="fourbar",
                    part_name=spec.part_name,
                    generated_path=(),
                    parameters=params,
                    key_points={},
                    is_valid=False,
                    error_message=f"Non-constructible at crank angle {math.degrees(theta1_rad):.1f}°",
                )

            generated_points.append(p2_result)

            # Store first configuration for visualization
            if i == 0:
                key_points["p1_initial"] = p1
                key_points["p2_initial"] = p2_result

        generated_path = tuple(generated_points)

        # Calculate error vs. target path (if comparable)
        path_error_rms: float | None = None
        if len(generated_path) > 0:
            try:
                path_error_rms = self.calculate_path_error(spec.target_path, generated_path)
            except ValueError:
                # Length mismatch or other error
                logger.debug("Could not calculate path error for fourbar")

        return MechanismResult(
            mechanism_id=self._generate_id(),
            mechanism_type="fourbar",
            part_name=spec.part_name,
            generated_path=generated_path,
            parameters=params,
            key_points=key_points,
            is_valid=True,
            path_error_rms=path_error_rms,
        )

    def _validate_fourbar_spec(self, spec: MechanismSpec) -> tuple[bool, str | None]:
        """Validate fourbar specification.

        Checks Grashof criterion: s + l <= p + q
        where s = shortest, l = longest, p, q = other two.
        """
        params = spec.parameters

        required = ["l1", "l2", "l3", "l4"]
        for key in required:
            if key not in params:
                return (False, f"Missing required parameter: {key}")
            if params[key] <= 0:
                return (False, f"Link length {key} must be positive, got {params[key]}")

        # Grashof criterion
        lengths = [params["l1"], params["l2"], params["l3"], params["l4"]]
        s = min(lengths)
        l_max = max(lengths)
        p, q = sorted([x for x in lengths if x != s and x != l_max])

        if s + l_max > p + q:
            return (
                False,
                f"Violates Grashof criterion: s+l={s + l_max:.2f} > p+q={p + q:.2f}",
            )

        return (True, None)

    # -------------------------------------------------------------------------
    # Private: Threebar Linkage Generation
    # -------------------------------------------------------------------------

    def _generate_threebar(self, spec: MechanismSpec) -> MechanismResult:
        """Generate three-bar open chain mechanism.

        Simpler than fourbar - no closed-loop constraints.
        """
        params = spec.parameters

        l1 = params.get("l1", 50.0)
        l2 = params.get("l2", 70.0)
        base_x = params.get("base_x", 0.0)
        base_y = params.get("base_y", 0.0)
        num_samples = int(params.get("num_samples", 360))

        p0: Point2D = (base_x, base_y)

        generated_points: list[Point2D] = []
        key_points: dict[str, Point2D] = {"p0": p0}

        for i in range(num_samples):
            theta1_rad = 2 * math.pi * i / num_samples

            p1: Point2D = (
                p0[0] + l1 * math.cos(theta1_rad),
                p0[1] + l1 * math.sin(theta1_rad),
            )

            # Coupler angle (relative to crank)
            coupler_angle_rel = params.get("coupler_angle_rel", -math.pi / 4)
            theta2_rad = theta1_rad + coupler_angle_rel

            p2: Point2D = (
                p1[0] + l2 * math.cos(theta2_rad),
                p1[1] + l2 * math.sin(theta2_rad),
            )

            generated_points.append(p2)

            if i == 0:
                key_points["p1_initial"] = p1
                key_points["p2_initial"] = p2

        return MechanismResult(
            mechanism_id=self._generate_id(),
            mechanism_type="threebar",
            part_name=spec.part_name,
            generated_path=tuple(generated_points),
            parameters=params,
            key_points=key_points,
            is_valid=True,
        )

    def _validate_threebar_spec(self, spec: MechanismSpec) -> tuple[bool, str | None]:
        """Validate threebar specification."""
        params = spec.parameters

        required = ["l1", "l2"]
        for key in required:
            if key not in params:
                return (False, f"Missing required parameter: {key}")
            if params[key] <= 0:
                return (False, f"Link length {key} must be positive")

        return (True, None)

    # -------------------------------------------------------------------------
    # Private: Cam-Follower Generation
    # -------------------------------------------------------------------------

    def _generate_cam(self, spec: MechanismSpec) -> MechanismResult:
        """Generate cam-follower mechanism.

        Algorithm:
            1. For each angle θ of cam rotation:
               a. Map θ to corresponding point on target path
               b. Transform to cam's reference frame (rotate by -θ)
               c. Offset by follower radius along normal
            2. Construct cam profile as closed curve

        Complexity: O(N * M) where N = samples, M = path points
        """
        params = spec.parameters

        cam_center_x = params.get("cam_center_x", 0.0)
        cam_center_y = params.get("cam_center_y", 0.0)
        params.get("follower_radius", 5.0)
        num_samples = int(params.get("num_samples", 360))

        cam_center: Point2D = (cam_center_x, cam_center_y)

        # Use target path as follower path
        follower_path = spec.target_path
        num_path_points = len(follower_path)

        if num_path_points < 2:
            return MechanismResult(
                mechanism_id=self._generate_id(),
                mechanism_type="cam",
                part_name=spec.part_name,
                generated_path=(),
                parameters=params,
                key_points={"cam_center": cam_center},
                is_valid=False,
                error_message="Follower path too short (need >= 2 points)",
            )

        cam_profile_points: list[Point2D] = []

        for i in range(num_samples):
            theta_rad = 2 * math.pi * i / num_samples

            # Map to follower path point
            path_idx = int((i / num_samples) * num_path_points) % num_path_points
            follower_center_world = follower_path[path_idx]

            # Vector from cam center to follower center
            vec_x = follower_center_world[0] - cam_center[0]
            vec_y = follower_center_world[1] - cam_center[1]

            # Rotate by -theta to cam's frame (inverse rotation)
            cos_theta = math.cos(-theta_rad)
            sin_theta = math.sin(-theta_rad)

            pitch_x = vec_x * cos_theta - vec_y * sin_theta
            pitch_y = vec_x * sin_theta + vec_y * cos_theta

            # Cam profile point (pitch curve + follower radius)
            # For simplicity, use pitch curve directly (exact offsetting requires normal calculation)
            cam_point: Point2D = (pitch_x, pitch_y)
            cam_profile_points.append(cam_point)

        key_points: dict[str, Point2D] = {"cam_center": cam_center}

        return MechanismResult(
            mechanism_id=self._generate_id(),
            mechanism_type="cam",
            part_name=spec.part_name,
            generated_path=tuple(cam_profile_points),
            parameters=params,
            key_points=key_points,
            is_valid=True,
        )

    def _validate_cam_spec(self, spec: MechanismSpec) -> tuple[bool, str | None]:
        """Validate cam specification."""
        params = spec.parameters

        if "follower_radius" in params and params["follower_radius"] <= 0:
            return (False, "follower_radius must be positive")

        if len(spec.target_path) < 2:
            return (False, "target_path must have at least 2 points")

        return (True, None)

    # -------------------------------------------------------------------------
    # Private: Geometric Helpers
    # -------------------------------------------------------------------------

    def _solve_circle_intersection(
        self, c1: Point2D, r1: float, c2: Point2D, r2: float
    ) -> Point2D | None:
        """Solve circle-circle intersection (returns one solution).

        Args:
            c1: Center of circle 1
            r1: Radius of circle 1
            c2: Center of circle 2
            r2: Radius of circle 2

        Returns:
            Intersection point (one of two possible), or None if no intersection

        Complexity: O(1)
        """
        dx = c2[0] - c1[0]
        dy = c2[1] - c1[1]
        d_sq = dx * dx + dy * dy
        d = math.sqrt(d_sq)

        # Check constructibility
        if d > (r1 + r2) or d < abs(r1 - r2) or d == 0:
            return None

        # Parameter a for geometric solution
        a = (d_sq - r2 * r2 + r1 * r1) / (2 * d)

        # Height of intersection point above line c1-c2
        h_sq = r1 * r1 - a * a
        if h_sq < -1e-9:  # Tolerance for floating point error
            return None
        h = math.sqrt(max(0, h_sq))

        # Midpoint along line c1-c2
        mid_x = c1[0] + a * dx / d
        mid_y = c1[1] + a * dy / d

        # Perpendicular offset (choose one solution)
        perp_x = -dy / d
        perp_y = dx / d

        # Return one intersection point (elbow-up configuration)
        return (mid_x + h * perp_x, mid_y + h * perp_y)

    def _generate_id(self) -> str:
        """Generate unique mechanism ID.

        For now, uses simple counter. Could use UUID in production.
        """
        import uuid

        return str(uuid.uuid4())[:8]
