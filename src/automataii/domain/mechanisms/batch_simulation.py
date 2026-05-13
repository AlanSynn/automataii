"""
Batch Simulation Service for Animation Frame Generation.

Provides vectorized batch computation of mechanism states across
multiple input angles, reducing Python overhead for animations.

Architecture: Domain Layer
Pattern: Service

Performance Optimizations:
- Pre-allocates result arrays
- Batches mechanism computations
- Optional parallel execution via ThreadPoolExecutor
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import numpy.typing as npt

    from automataii.domain.mechanisms.core.protocols import Mechanism
    from automataii.domain.mechanisms.core.state import MechanismState

# Type alias for angle arrays (accept any floating type)
AngleArray = np.ndarray  # NDArray[np.floating[Any]]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BatchSimulationResult:
    """Result of batch mechanism simulation.

    Attributes:
        angles: Input angles (N,) in degrees
        positions: Position arrays per joint {joint_name: (N, 2)}
        success_mask: Boolean mask of successful computations (N,)
        states: Optional list of full MechanismState objects
    """

    angles: npt.NDArray[np.float64]
    positions: dict[str, npt.NDArray[np.float64]]
    success_mask: npt.NDArray[np.bool_]
    states: list[MechanismState] | None = None


class BatchSimulationService:
    """
    Service for batch mechanism simulation.

    Computes mechanism states for multiple input angles efficiently,
    useful for animation frame generation.

    Usage:
        service = BatchSimulationService()

        # Generate angles for one full rotation
        angles = np.linspace(0, 360, 180)

        # Compute all states at once
        result = service.simulate_batch(mechanism, params, angles)

        # Access vectorized positions
        joint_a_positions = result.positions["A"]  # (180, 2)
    """

    def __init__(
        self,
        max_workers: int | None = None,
        enable_parallel: bool = False,
    ) -> None:
        """
        Initialize batch simulation service.

        Args:
            max_workers: Max threads for parallel mode (default: CPU count)
            enable_parallel: Enable parallel computation (default: False)
        """
        self._max_workers = max_workers
        self._enable_parallel = enable_parallel

    def simulate_batch(
        self,
        mechanism: Mechanism,
        parameters: dict[str, float],
        angles: AngleArray,
        include_states: bool = False,
    ) -> BatchSimulationResult:
        """
        Simulate mechanism across multiple input angles.

        Args:
            mechanism: Mechanism instance to simulate
            parameters: Mechanism parameters
            angles: (N,) array of input angles in degrees
            include_states: Include full MechanismState objects

        Returns:
            BatchSimulationResult with vectorized positions
        """
        n_angles = len(angles)

        # Pre-allocate arrays
        positions: dict[str, npt.NDArray[np.float64]] = {}
        success_mask = np.ones(n_angles, dtype=bool)
        states: list[MechanismState] | None = [] if include_states else None

        if self._enable_parallel and n_angles > 10:
            return self._simulate_parallel(
                mechanism, parameters, angles, include_states
            )

        # Sequential simulation
        for i, angle in enumerate(angles):
            try:
                state = mechanism.compute_state(parameters, float(angle))

                # Extract positions
                for joint_name, pos in state.positions.items():
                    if joint_name not in positions:
                        positions[joint_name] = np.zeros((n_angles, 2))
                    positions[joint_name][i] = pos

                if states is not None:
                    states.append(state)

            except Exception as e:
                logger.debug(f"Simulation failed at angle {angle}: {e}")
                success_mask[i] = False

        return BatchSimulationResult(
            angles=angles,
            positions=positions,
            success_mask=success_mask,
            states=states,
        )

    def _simulate_parallel(
        self,
        mechanism: Mechanism,
        parameters: dict[str, float],
        angles: npt.NDArray[np.float64],
        include_states: bool,
    ) -> BatchSimulationResult:
        """
        Parallel batch simulation using ThreadPoolExecutor.

        Note: Due to GIL, this is only beneficial for I/O-bound operations
        or when using NumPy's released-GIL operations.
        """
        n_angles = len(angles)
        positions: dict[str, npt.NDArray[np.float64]] = {}
        success_mask = np.ones(n_angles, dtype=bool)
        states_list: list[MechanismState | None] = [None] * n_angles

        def compute_one(idx: int) -> tuple[int, MechanismState | None]:
            try:
                state = mechanism.compute_state(parameters, float(angles[idx]))
                return (idx, state)
            except Exception:
                return (idx, None)

        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            results = executor.map(compute_one, range(n_angles))

            for idx, state in results:
                if state is None:
                    success_mask[idx] = False
                    continue

                for joint_name, pos in state.positions.items():
                    if joint_name not in positions:
                        positions[joint_name] = np.zeros((n_angles, 2))
                    positions[joint_name][idx] = pos

                if include_states:
                    states_list[idx] = state

        states = [s for s in states_list if s is not None] if include_states else None

        return BatchSimulationResult(
            angles=angles,
            positions=positions,
            success_mask=success_mask,
            states=states,
        )

    def generate_animation_frames(
        self,
        mechanism: Mechanism,
        parameters: dict[str, float],
        num_frames: int = 60,
        start_angle: float = 0.0,
        end_angle: float = 360.0,
    ) -> BatchSimulationResult:
        """
        Generate animation frames for a full mechanism cycle.

        Convenience method that generates evenly-spaced angles
        and computes all states.

        Args:
            mechanism: Mechanism to animate
            parameters: Mechanism parameters
            num_frames: Number of frames to generate
            start_angle: Starting angle in degrees
            end_angle: Ending angle in degrees

        Returns:
            BatchSimulationResult for animation
        """
        if isinstance(num_frames, bool) or not isinstance(num_frames, int):
            raise ValueError(f"num_frames must be an integer, got {type(num_frames)}")
        if num_frames <= 0:
            raise ValueError(f"num_frames must be positive, got {num_frames}")
        if not np.isfinite(float(start_angle)) or not np.isfinite(float(end_angle)):
            raise ValueError(
                f"start_angle and end_angle must be finite, got {start_angle}, {end_angle}"
            )

        angles = np.linspace(start_angle, end_angle, num_frames, endpoint=False)
        return self.simulate_batch(mechanism, parameters, angles, include_states=False)

    def compute_motion_path(
        self,
        mechanism: Mechanism,
        parameters: dict[str, float],
        joint_name: str,
        resolution: int = 180,
    ) -> npt.NDArray[np.float64] | None:
        """
        Compute motion path for a specific joint.

        Args:
            mechanism: Mechanism instance
            parameters: Mechanism parameters
            joint_name: Name of joint to track
            resolution: Number of path points

        Returns:
            (N, 2) array of path points, or None if joint not found
        """
        if isinstance(resolution, bool) or not isinstance(resolution, int):
            raise ValueError(f"resolution must be an integer, got {type(resolution)}")
        if resolution <= 0:
            raise ValueError(f"resolution must be positive, got {resolution}")

        result = self.generate_animation_frames(
            mechanism, parameters, num_frames=resolution
        )

        if joint_name not in result.positions:
            logger.warning(f"Joint '{joint_name}' not found in mechanism")
            return None

        return result.positions[joint_name]


# Default service instance
_default_service: BatchSimulationService | None = None


def get_batch_simulation_service() -> BatchSimulationService:
    """Get or create the default batch simulation service."""
    global _default_service
    if _default_service is None:
        _default_service = BatchSimulationService()
    return _default_service
