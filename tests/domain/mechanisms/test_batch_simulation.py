"""
Tests for BatchSimulationService.

Validates vectorized batch simulation for animation frames.
"""

import numpy as np
import pytest

from automataii.domain.mechanisms.batch_simulation import (
    BatchSimulationResult,
    BatchSimulationService,
    get_batch_simulation_service,
)
from automataii.domain.mechanisms.cam.compute import CamFollowerMechanism
from automataii.domain.mechanisms.linkages.compute import UnifiedLinkageMechanism


class TestBatchSimulationService:
    """Test batch simulation service."""

    @pytest.fixture
    def service(self) -> BatchSimulationService:
        """Create fresh service instance."""
        return BatchSimulationService()

    @pytest.fixture
    def fourbar_mechanism(self):
        """Create a four-bar mechanism."""
        return UnifiedLinkageMechanism({"bar_count": 4})

    @pytest.fixture
    def fourbar_params(self) -> dict[str, float]:
        """Four-bar mechanism parameters."""
        return {
            "bar_count": 4,
            "ground_link": 100.0,
            "input_link": 50.0,
            "coupler_link": 80.0,
            "output_link": 60.0,
        }

    def test_simulate_batch_returns_result(
        self, service: BatchSimulationService, fourbar_mechanism, fourbar_params
    ):
        """Batch simulation returns BatchSimulationResult."""
        angles = np.linspace(0, 360, 10)
        result = service.simulate_batch(fourbar_mechanism, fourbar_params, angles)

        assert isinstance(result, BatchSimulationResult)
        assert len(result.angles) == 10
        assert len(result.success_mask) == 10

    def test_simulate_batch_positions_shape(
        self, service: BatchSimulationService, fourbar_mechanism, fourbar_params
    ):
        """Batch simulation produces correctly shaped position arrays."""
        angles = np.linspace(0, 360, 20)
        result = service.simulate_batch(fourbar_mechanism, fourbar_params, angles)

        # Should have positions for standard four-bar joints
        assert "O1" in result.positions
        assert "O4" in result.positions
        assert "A" in result.positions
        assert "B" in result.positions

        # Each position array should be (N, 2)
        assert result.positions["A"].shape == (20, 2)
        assert result.positions["B"].shape == (20, 2)

    def test_simulate_batch_all_successful(
        self, service: BatchSimulationService, fourbar_mechanism, fourbar_params
    ):
        """Batch simulation with valid params should all succeed."""
        angles = np.linspace(0, 360, 36)
        result = service.simulate_batch(fourbar_mechanism, fourbar_params, angles)

        # Most angles should succeed for a valid four-bar
        success_rate = np.mean(result.success_mask)
        assert success_rate > 0.8  # At least 80% should succeed

    def test_simulate_batch_with_states(
        self, service: BatchSimulationService, fourbar_mechanism, fourbar_params
    ):
        """Include full MechanismState objects when requested."""
        angles = np.linspace(0, 90, 5)
        result = service.simulate_batch(
            fourbar_mechanism, fourbar_params, angles, include_states=True
        )

        assert result.states is not None
        assert len(result.states) > 0

    def test_generate_animation_frames(
        self, service: BatchSimulationService, fourbar_mechanism, fourbar_params
    ):
        """Generate animation frames convenience method."""
        result = service.generate_animation_frames(
            fourbar_mechanism, fourbar_params, num_frames=60
        )

        assert len(result.angles) == 60
        assert result.angles[0] == 0.0
        # Last angle should be close to 360 but not exactly (endpoint=False)
        assert result.angles[-1] < 360.0

    def test_compute_motion_path(
        self, service: BatchSimulationService, fourbar_mechanism, fourbar_params
    ):
        """Compute motion path for specific joint."""
        path = service.compute_motion_path(
            fourbar_mechanism, fourbar_params, "A", resolution=36
        )

        assert path is not None
        assert path.shape == (36, 2)

    def test_compute_motion_path_invalid_joint(
        self, service: BatchSimulationService, fourbar_mechanism, fourbar_params
    ):
        """Return None for non-existent joint."""
        path = service.compute_motion_path(
            fourbar_mechanism, fourbar_params, "nonexistent_joint", resolution=10
        )

        assert path is None

    def test_default_service_singleton(self):
        """Default service getter returns same instance."""
        service1 = get_batch_simulation_service()
        service2 = get_batch_simulation_service()

        assert service1 is service2


class TestBatchSimulationPerformance:
    """Performance-related tests for batch simulation."""

    def test_batch_faster_than_sequential(self):
        """Batch simulation should be efficient."""
        import time

        service = BatchSimulationService()
        mechanism = UnifiedLinkageMechanism({"bar_count": 4})
        params = {
            "bar_count": 4,
            "ground_link": 100.0,
            "input_link": 50.0,
            "coupler_link": 80.0,
            "output_link": 60.0,
        }

        # Measure batch time
        angles = np.linspace(0, 360, 180)
        start = time.perf_counter()
        result = service.simulate_batch(mechanism, params, angles)
        batch_time = time.perf_counter() - start

        # Should complete quickly (< 1 second for 180 frames)
        assert batch_time < 1.0
        assert np.sum(result.success_mask) > 100  # Most should succeed

    def test_large_batch_handles_memory(self):
        """Large batch doesn't cause memory issues."""
        service = BatchSimulationService()
        mechanism = UnifiedLinkageMechanism({"bar_count": 4})
        params = {
            "bar_count": 4,
            "ground_link": 100.0,
            "input_link": 50.0,
            "coupler_link": 80.0,
            "output_link": 60.0,
        }

        # Generate 360 frames (1 degree per frame)
        result = service.generate_animation_frames(
            mechanism, params, num_frames=360
        )

        assert len(result.angles) == 360
        assert "A" in result.positions
        assert result.positions["A"].shape[0] == 360


class TestCamBatchSimulation:
    """Test batch simulation with cam mechanism."""

    def test_cam_batch_simulation(self):
        """Cam mechanism works with batch simulation."""
        service = BatchSimulationService()
        mechanism = CamFollowerMechanism()
        params = {
            "cam_radius": 60.0,
            "cam_offset": 20.0,
            "follower_length": 100.0,
        }

        angles = np.linspace(0, 360, 72)
        result = service.simulate_batch(mechanism, params, angles)

        assert len(result.angles) == 72
        assert np.all(result.success_mask)  # Cam should always succeed

        # Check cam-specific positions
        assert "cam_center" in result.positions
        assert "contact_point" in result.positions
