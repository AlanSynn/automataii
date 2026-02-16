"""
Animation Cache - Pre-computed data for efficient mechanism animation.

Eliminates per-frame allocations by caching numpy arrays and using
vectorized operations for coordinate transforms.

Design Pattern: Flyweight (shared pre-computed data)
"""
from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np
from PyQt6.QtCore import QPointF

if TYPE_CHECKING:
    pass


@dataclass(slots=True)
class LinkageCache:
    """Cached data for linkage mechanisms (4-bar, 5-bar, 6-bar).

    Pre-converts joint positions from lists to numpy arrays for O(1) frame access.
    """
    # Pre-converted position arrays: shape (num_frames, 2)
    p1_positions: np.ndarray
    p2_positions: np.ndarray
    p3_positions: np.ndarray
    p4_positions: np.ndarray
    p5_positions: np.ndarray | None = None  # 5-bar, 6-bar
    p6_positions: np.ndarray | None = None  # 6-bar only

    num_frames: int = 0
    coupler_point_offset: np.ndarray = field(default_factory=lambda: np.array([0.0, 0.0]))

    @classmethod
    def from_simulation_data(
        cls,
        joint_positions: dict[str, list],
        params: dict[str, Any] | None = None,
    ) -> LinkageCache:
        """Create cache from simulation data.

        Time Complexity: O(n) where n = num_frames (one-time cost)
        """
        p1 = np.array(joint_positions.get("p1_positions", [[0, 0]]))
        p2 = np.array(joint_positions.get("p2_positions", [[0, 0]]))
        p3 = np.array(joint_positions.get("p3_positions", [[0, 0]]))
        p4 = np.array(joint_positions.get("p4_positions", [[0, 0]]))

        p5 = None
        p6 = None
        if "p5_positions" in joint_positions:
            p5 = np.array(joint_positions["p5_positions"])
        if "p6_positions" in joint_positions:
            p6 = np.array(joint_positions["p6_positions"])

        coupler_offset = np.array([0.0, 0.0])
        if params:
            coupler_offset = np.array([
                params.get("coupler_point_x", 0.0),
                params.get("coupler_point_y", 0.0),
            ])

        return cls(
            p1_positions=p1,
            p2_positions=p2,
            p3_positions=p3,
            p4_positions=p4,
            p5_positions=p5,
            p6_positions=p6,
            num_frames=len(p1),
            coupler_point_offset=coupler_offset,
        )

    def get_frame_positions(
        self,
        frame_index: int,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Get positions for a single frame. O(1) access."""
        idx = max(0, min(frame_index, self.num_frames - 1))
        return (
            self.p1_positions[idx],
            self.p2_positions[idx],
            self.p3_positions[idx],
            self.p4_positions[idx],
        )

    def get_frame_positions_5bar(
        self,
        frame_index: int,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Get positions for 5-bar frame. O(1) access."""
        idx = max(0, min(frame_index, self.num_frames - 1))
        p5 = self.p5_positions[idx] if self.p5_positions is not None else np.array([0, 0])
        return (
            self.p1_positions[idx],
            self.p2_positions[idx],
            self.p3_positions[idx],
            self.p4_positions[idx],
            p5,
        )

    def get_frame_positions_6bar(
        self,
        frame_index: int,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Get positions for 6-bar frame. O(1) access."""
        idx = max(0, min(frame_index, self.num_frames - 1))
        p5 = self.p5_positions[idx] if self.p5_positions is not None else np.array([0, 0])
        p6 = self.p6_positions[idx] if self.p6_positions is not None else np.array([0, 0])
        return (
            self.p1_positions[idx],
            self.p2_positions[idx],
            self.p3_positions[idx],
            self.p4_positions[idx],
            p5,
            p6,
        )


@dataclass(slots=True)
class CamCache:
    """Cached data for cam mechanism.

    Pre-computes base profile points; rotation is applied via matrix multiplication.
    """
    # Base profile in local coordinates: shape (num_points, 2)
    base_profile: np.ndarray
    num_points: int

    # Cam parameters (for follower calculation)
    base_radius: float
    cam_offset: float
    cam_lobes: int
    profile_harmonic: float
    rod_length: float

    # Cached rotation matrix (updated per frame)
    _cos_angle: float = 1.0
    _sin_angle: float = 0.0

    @classmethod
    def from_params(
        cls,
        params: dict[str, Any],
        scale_factor: float = 1.0,
        rod_multiplier: float = 1.0,
        num_points: int = 72,
    ) -> CamCache:
        """Create cache from cam parameters.

        Time Complexity: O(num_points) (one-time cost)
        """
        base_radius = params.get("base_radius", params.get("cam_radius", 60.0)) * scale_factor
        cam_offset = params.get("eccentricity", params.get("cam_offset", 20.0)) * scale_factor
        cam_lobes = int(params.get("cam_lobes", 1))
        profile_harmonic = params.get("profile_harmonic", 0.3)
        rod_length = params.get("follower_rod_length", params.get("follower_length", 100.0)) * rod_multiplier

        # Pre-compute base profile (unrotated)
        theta = np.linspace(0, 2 * np.pi, num_points, endpoint=False)
        primary_var = cam_offset * np.cos(cam_lobes * theta)
        secondary_var = (cam_offset * profile_harmonic) * np.cos(2 * cam_lobes * theta)
        r = base_radius + primary_var + secondary_var

        # Convert to Cartesian (base profile, no rotation)
        base_profile = np.column_stack([r * np.cos(theta), r * np.sin(theta)])

        return cls(
            base_profile=base_profile,
            num_points=num_points,
            base_radius=base_radius,
            cam_offset=cam_offset,
            cam_lobes=cam_lobes,
            profile_harmonic=profile_harmonic,
            rod_length=rod_length,
        )

    def get_rotated_profile(self, angle: float) -> np.ndarray:
        """Get cam profile rotated by angle. O(n) but vectorized.

        Uses pre-computed base profile and rotation matrix.
        """
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)

        # Rotation matrix multiplication: [cos -sin; sin cos] @ [x; y]
        rotated = np.empty_like(self.base_profile)
        rotated[:, 0] = self.base_profile[:, 0] * cos_a - self.base_profile[:, 1] * sin_a
        rotated[:, 1] = self.base_profile[:, 0] * sin_a + self.base_profile[:, 1] * cos_a

        return rotated

    def get_contact_radius(self, cam_angle: float) -> float:
        """Calculate contact radius at follower position for given cam angle."""
        # Follower is at theta = -π/2 in scene coordinates
        # In cam's rotating frame, this is at angle = -π/2 - cam_angle
        follower_theta = -np.pi / 2 - cam_angle

        primary = self.cam_offset * np.cos(self.cam_lobes * follower_theta)
        secondary = (self.cam_offset * self.profile_harmonic) * np.cos(2 * self.cam_lobes * follower_theta)

        return float(self.base_radius + primary + secondary)


@dataclass(slots=True)
class GearCache:
    """Cached data for gear mechanisms."""
    # Gear 1
    gear1_center: np.ndarray
    gear1_radius: float

    # Gear 2
    gear2_center: np.ndarray
    gear2_radius: float

    # Gear ratio (r1/r2) for counter-rotation
    gear_ratio: float

    # Pre-computed angles if from simulation
    gear1_angles: np.ndarray | None = None
    gear2_angles: np.ndarray | None = None
    num_frames: int = 0

    @classmethod
    def from_params(
        cls,
        params: dict[str, Any],
        gear_data: dict[str, Any] | None = None,
    ) -> GearCache:
        """Create cache from gear parameters."""
        r1 = float(params.get("r1", params.get("gear1_radius", 30)))
        r2 = float(params.get("r2", params.get("gear2_radius", 50)))
        if r1 <= 0:
            r1 = 1.0
        if r2 <= 0:
            r2 = 1.0
        distance = r1 + r2

        gear1_angles = None
        gear2_angles = None
        num_frames = 0

        if gear_data:
            if "gear1_angles" in gear_data:
                gear1_angles = np.array(gear_data["gear1_angles"])
                num_frames = len(gear1_angles)
            if "gear2_angles" in gear_data:
                gear2_angles = np.array(gear_data["gear2_angles"])

        return cls(
            gear1_center=np.array([0.0, 0.0]),
            gear1_radius=r1,
            gear2_center=np.array([distance, 0.0]),
            gear2_radius=r2,
            gear_ratio=r1 / r2 if abs(r2) > 1e-9 else 1.0,
            gear1_angles=gear1_angles,
            gear2_angles=gear2_angles,
            num_frames=num_frames,
        )

    def get_angles(self, time: float) -> tuple[float, float]:
        """Get gear rotation angles for given time."""
        if self.gear1_angles is not None and self.gear2_angles is not None and self.num_frames > 0:
            normalized_time = (time / (2 * np.pi)) % 1.0
            frame_index = int(normalized_time * (self.num_frames - 1))
            frame_index = max(0, min(frame_index, self.num_frames - 1))

            full_rotations = int(time / (2 * np.pi))
            theta1 = float(self.gear1_angles[frame_index] + full_rotations * 2 * np.pi)
            theta2 = float(self.gear2_angles[frame_index] + full_rotations * 2 * np.pi * (-self.gear_ratio))
            return theta1, theta2
        else:
            theta1 = time
            theta2 = -time * self.gear_ratio
            return theta1, theta2


@dataclass(slots=True)
class PlanetaryGearCache:
    """Cached data for planetary gear mechanism."""
    r_sun: float
    r_planet: float
    arm_length: float

    # Pre-computed positions if from simulation
    sun_centers: np.ndarray | None = None
    planet_centers: np.ndarray | None = None
    tracking_points: np.ndarray | None = None
    num_frames: int = 0

    @classmethod
    def from_params(
        cls,
        params: dict[str, Any],
        gear_positions: dict[str, Any] | None = None,
    ) -> PlanetaryGearCache:
        """Create cache from planetary gear parameters."""
        r_sun = params.get("r_sun", 20)
        r_planet = params.get("r_planet", 30)
        arm_length = params.get("arm_length", 15)

        sun_centers = None
        planet_centers = None
        tracking_points = None
        num_frames = 0

        if gear_positions:
            if "sun_centers" in gear_positions:
                sun_centers = np.array(gear_positions["sun_centers"])
                num_frames = len(sun_centers)
            if "planet_centers" in gear_positions:
                planet_centers = np.array(gear_positions["planet_centers"])
            if "tracking_points" in gear_positions:
                tracking_points = np.array(gear_positions["tracking_points"])

        return cls(
            r_sun=r_sun,
            r_planet=r_planet,
            arm_length=arm_length,
            sun_centers=sun_centers,
            planet_centers=planet_centers,
            tracking_points=tracking_points,
            num_frames=num_frames,
        )

    def get_positions(
        self,
        time: float,
        reverse: bool = False,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Get sun center, planet center, and tracking point positions."""
        normalized_time = time / (2 * math.pi)
        if reverse:
            normalized_time = 1.0 - normalized_time

        if (self.planet_centers is not None and
            self.sun_centers is not None and
            self.tracking_points is not None and
            self.num_frames > 0):
            frame_index = int(normalized_time * (self.num_frames - 1))
            frame_index = max(0, min(frame_index, self.num_frames - 1))

            sun = self.sun_centers[frame_index]
            planet = self.planet_centers[frame_index]
            tracking = self.tracking_points[frame_index]
        else:
            # Fallback calculation
            orbital_angle = time
            rotation_angle = -time * (self.r_sun / self.r_planet)

            sun = np.array([0.0, 0.0])
            planet = sun + (self.r_sun + self.r_planet) * np.array([
                np.cos(orbital_angle), np.sin(orbital_angle)
            ])
            tracking = planet + self.arm_length * np.array([
                np.cos(rotation_angle), np.sin(rotation_angle)
            ])

        return sun, planet, tracking


class AnimationCacheManager:
    """Manages animation caches for all mechanisms.

    Creates and stores caches when mechanisms are added;
    provides O(1) access during animation.
    """

    def __init__(self) -> None:
        self._linkage_caches: dict[str, LinkageCache] = {}
        self._cam_caches: dict[str, CamCache] = {}
        self._gear_caches: dict[str, GearCache] = {}
        self._planetary_caches: dict[str, PlanetaryGearCache] = {}

    def build_cache(self, mechanism_id: str, layer_data: dict[str, Any]) -> None:
        """Build appropriate cache for mechanism type."""
        mech_type = layer_data.get("type", "")
        params = layer_data.get("params", {})
        full_sim = layer_data.get("full_simulation_data", {})

        if mech_type in ("4_bar_linkage", "5_bar_linkage", "6_bar_linkage"):
            joint_positions = full_sim.get("joint_positions", {})
            if joint_positions:
                self._linkage_caches[mechanism_id] = LinkageCache.from_simulation_data(
                    joint_positions, params
                )

        elif mech_type == "cam":
            scale_factor = layer_data.get("cam_scale_factor", 1.0)
            rod_multiplier = layer_data.get("rod_length_multiplier", 1.0)
            self._cam_caches[mechanism_id] = CamCache.from_params(
                params, scale_factor, rod_multiplier
            )

        elif mech_type == "gear":
            gear_data = full_sim.get("gear_data", {})
            self._gear_caches[mechanism_id] = GearCache.from_params(params, gear_data)

        elif mech_type == "planetary_gear":
            gear_positions = full_sim.get("gear_positions", {})
            self._planetary_caches[mechanism_id] = PlanetaryGearCache.from_params(
                params, gear_positions
            )

    def get_linkage_cache(self, mechanism_id: str) -> LinkageCache | None:
        return self._linkage_caches.get(mechanism_id)

    def get_cam_cache(self, mechanism_id: str) -> CamCache | None:
        return self._cam_caches.get(mechanism_id)

    def get_gear_cache(self, mechanism_id: str) -> GearCache | None:
        return self._gear_caches.get(mechanism_id)

    def get_planetary_cache(self, mechanism_id: str) -> PlanetaryGearCache | None:
        return self._planetary_caches.get(mechanism_id)

    def remove_cache(self, mechanism_id: str) -> None:
        """Remove all caches for a mechanism."""
        self._linkage_caches.pop(mechanism_id, None)
        self._cam_caches.pop(mechanism_id, None)
        self._gear_caches.pop(mechanism_id, None)
        self._planetary_caches.pop(mechanism_id, None)

    def clear(self) -> None:
        """Clear all caches."""
        self._linkage_caches.clear()
        self._cam_caches.clear()
        self._gear_caches.clear()
        self._planetary_caches.clear()


def batch_transform_points(
    points: np.ndarray,
    transform_fn: Callable[[np.ndarray], QPointF],
) -> list[QPointF]:
    """Transform multiple points efficiently.

    Args:
        points: Array of shape (n, 2)
        transform_fn: Function that transforms a single point

    Returns:
        List of QPointF in scene coordinates

    Note: For true vectorization, the transform function itself
    would need to accept arrays. This provides a cleaner interface
    while still avoiding per-point np.array() creation.
    """
    return [transform_fn(pt) for pt in points]


def create_rotation_matrix(angle: float) -> np.ndarray:
    """Create 2x2 rotation matrix."""
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[c, -s], [s, c]])
