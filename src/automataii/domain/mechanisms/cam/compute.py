"""
Cam-follower mechanism computation module.

Architecture Note:
- This is DOMAIN layer - NO Qt dependencies allowed
- Use Point2D = tuple[float, float] instead of QPointF
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from automataii.domain.mechanisms.core.protocols import Mechanism
from automataii.domain.mechanisms.core.state import (
    ForceType,
    ForceVector,
    MechanismState,
    Point2D,
    SafetyLevel,
    SafetyStatus,
)


@dataclass(frozen=True)
class CamParameters:
    cam_radius: float
    cam_offset: float
    follower_length: float
    cam_angle: float
    cam_lobes: int = 1
    profile_harmonic: float = 0.3


class CamFollowerMechanism(Mechanism):
    def __init__(self, parameters: dict[str, float] | None = None):
        self._parameters = self._parse_parameters(parameters or {})

    @property
    def mechanism_type(self) -> str:
        return "cam_follower"

    @property
    def required_parameters(self) -> frozenset[str]:
        return frozenset(["cam_radius", "cam_offset", "follower_length"])

    def validate_parameters(self, parameters: dict[str, float]) -> None:
        required = self.required_parameters
        missing = required - parameters.keys()
        if missing:
            raise ValueError(f"Missing required parameters: {missing}")

        if parameters["cam_radius"] <= 0:
            raise ValueError(f"cam_radius must be positive, got {parameters['cam_radius']}")
        if parameters["cam_offset"] < 0:
            raise ValueError(f"cam_offset must be non-negative, got {parameters['cam_offset']}")
        if parameters["follower_length"] <= 0:
            raise ValueError(
                f"follower_length must be positive, got {parameters['follower_length']}"
            )

    def _parse_parameters(self, params: dict) -> CamParameters:
        return CamParameters(
            cam_radius=params.get("cam_radius", 60.0),
            cam_offset=params.get("cam_offset", 20.0),
            follower_length=params.get("follower_length", 100.0),
            cam_angle=params.get("cam_angle", 0.0),
            cam_lobes=int(params.get("cam_lobes", 1)),
            profile_harmonic=params.get("profile_harmonic", 0.3),
        )

    def compute_state(self, parameters: dict[str, float], input_angle: float) -> MechanismState:
        params_with_angle = {**parameters, "cam_angle": input_angle}
        self._parameters = self._parse_parameters(params_with_angle)
        params = self._parameters

        cam_center = (0.0, 0.0)
        cam_angle_rad = math.radians(params.cam_angle)

        contact_radius, cam_profile = self._compute_cam_profile(
            params.cam_radius, params.cam_offset, cam_angle_rad
        )

        follower_base_x = 0.0
        follower_base_y = -(contact_radius + params.follower_length)
        follower_base = (follower_base_x, follower_base_y)

        contact_x = 0.0
        contact_y = -contact_radius
        contact_point = (contact_x, contact_y)

        follower_end_x = 0.0
        follower_end_y = -contact_radius
        follower_end = (follower_end_x, follower_end_y)

        positions = {
            "cam_center": cam_center,
            "contact_point": contact_point,
            "follower_base": follower_base,
            "follower_end": follower_end,
        }

        displacement_amplitude = contact_radius - params.cam_radius
        follower_stress = (
            abs(displacement_amplitude) / params.cam_offset if params.cam_offset > 0 else 0
        )

        forces = self._compute_forces(
            cam_center,
            contact_point,
            follower_end,
            cam_angle_rad,
            contact_radius,
            follower_stress,
        )

        safety = self._evaluate_safety(params, contact_radius, follower_stress)

        return MechanismState(
            positions=positions,
            forces=forces,
            safety_status=safety,
            metadata={
                "stress": {"follower": -follower_stress * 0.6},
                "contact_radius": contact_radius,
                "displacement": displacement_amplitude,
                "cam_profile": cam_profile,
            },
        )

    def _compute_cam_profile(
        self, cam_radius: float, cam_offset: float, cam_angle: float
    ) -> tuple[float, list[tuple[float, float]]]:
        num_points = 72
        profile_points = []
        contact_radii = []
        params = self._parameters

        for i in range(num_points):
            theta = (i * 2 * math.pi) / num_points

            base_radius = cam_radius
            primary_variation = cam_offset * math.cos(params.cam_lobes * theta)
            secondary_variation = (cam_offset * params.profile_harmonic) * math.cos(
                2 * params.cam_lobes * theta
            )

            radius = base_radius + primary_variation + secondary_variation
            contact_radii.append(radius)

            rotated_theta = theta + cam_angle
            x = radius * math.cos(rotated_theta)
            y = radius * math.sin(rotated_theta)
            profile_points.append((x, y))

        follower_contact_theta = -math.pi / 2
        theta_normalized = (follower_contact_theta - cam_angle) % (2 * math.pi)

        base_radius = cam_radius
        primary_variation = cam_offset * math.cos(params.cam_lobes * theta_normalized)
        secondary_variation = (cam_offset * params.profile_harmonic) * math.cos(
            2 * params.cam_lobes * theta_normalized
        )
        contact_radius = base_radius + primary_variation + secondary_variation

        return contact_radius, profile_points

    def _compute_forces(
        self,
        cam_center: Point2D,
        contact_point: Point2D,
        follower_end: Point2D,
        cam_angle: float,
        contact_radius: float,
        follower_stress: float,
    ) -> dict[str, ForceVector]:
        forces = {}

        normal_angle_deg = math.degrees(cam_angle) + 90
        normal_force = max(5.0, abs(follower_stress) * 40)

        forces["cam_normal"] = ForceVector(
            position=contact_point,
            magnitude=normal_force,
            angle=normal_angle_deg,
            force_type=ForceType.REACTION,
            label="Normal",
        )

        friction_angle_deg = math.degrees(cam_angle)
        friction_force = normal_force * 0.15

        forces["cam_friction"] = ForceVector(
            position=contact_point,
            magnitude=friction_force,
            angle=friction_angle_deg,
            force_type=ForceType.FRICTION,
            label="Friction",
        )

        spring_force = abs(contact_radius - 60) * 0.5
        forces["spring"] = ForceVector(
            position=follower_end,
            magnitude=spring_force,
            angle=180.0,
            force_type=ForceType.APPLIED,
            label="Spring",
        )

        inertia_force = abs(follower_stress) * 20
        forces["follower_inertia"] = ForceVector(
            position=(follower_end[0] - 50, follower_end[1]),
            magnitude=inertia_force,
            angle=90.0 if follower_stress < 0 else 270.0,
            force_type=ForceType.APPLIED,
            label="Inertia",
        )

        return forces

    def _evaluate_safety(
        self, params: CamParameters, contact_radius: float, follower_stress: float
    ) -> SafetyStatus:
        issues = []

        contact_stress_ratio = abs(contact_radius - params.cam_radius) / params.cam_offset
        if contact_stress_ratio > 0.9:
            issues.append(f"High contact stress ({contact_stress_ratio:.1%})")

        if abs(follower_stress) > 0.8:
            issues.append(f"High follower stress ({abs(follower_stress):.2f})")

        cam_eccentricity = params.cam_offset / params.cam_radius
        if cam_eccentricity > 0.5:
            issues.append(f"High cam eccentricity ({cam_eccentricity:.2f})")

        if not issues:
            return SafetyStatus(SafetyLevel.SAFE, "All parameters within safe limits")

        if len(issues) >= 2 or abs(follower_stress) > 0.9:
            return SafetyStatus(
                SafetyLevel.DANGER,
                f"Critical issues: {'; '.join(issues)}",
                {"issues": issues, "stress": follower_stress},
            )

        return SafetyStatus(
            SafetyLevel.WARNING,
            f"Warning: {'; '.join(issues)}",
            {"issues": issues, "stress": follower_stress},
        )
