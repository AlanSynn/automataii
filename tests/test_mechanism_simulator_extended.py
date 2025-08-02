"""
Extended tests for the mechanism simulator with new mechanism types.

Tests simulation logic for cam, belt, and spring mechanisms.
"""

import pytest
import numpy as np
from src.automataii.domain.kinematics.mechanism_simulator import MechanismSimulator
from src.automataii.domain.kinematics.mechanism import MechanismType


class TestMechanismSimulatorExtended:
    """Test the enhanced mechanism simulator with new mechanism types."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.simulator = MechanismSimulator(time_steps=50)
    
    def test_cam_simulation(self):
        """Test cam mechanism simulation."""
        # Parameters: [base_radius, rise, offset, cam_center_x, cam_center_y, motion_law_type, dwell_start, dwell_end]
        params = np.array([30.0, 20.0, 10.0, 0.0, 0.0, 0, 0.0, 0.0])
        
        motion_curve = self.simulator.simulate_mechanism(MechanismType.CAM, params)
        
        # Verify motion curve properties
        assert motion_curve.points.shape[0] == self.simulator.time_steps
        assert motion_curve.points.shape[1] == 2
        assert motion_curve.period == 2 * np.pi
        
        # Verify follower motion is within expected range
        y_positions = motion_curve.points[:, 1]
        min_expected = params[0] + params[2]  # base_radius + offset
        max_expected = params[0] + params[1] + params[2]  # base_radius + rise + offset
        
        assert np.all(y_positions >= min_expected - 1), f"Y positions should be >= {min_expected}"
        assert np.all(y_positions <= max_expected + 1), f"Y positions should be <= {max_expected}"
        
        # Test different motion laws
        for motion_law in [0, 1, 2]:  # harmonic, cycloidal, polynomial
            params[5] = motion_law
            motion_curve = self.simulator.simulate_mechanism(MechanismType.CAM, params)
            assert motion_curve.points.shape[0] == self.simulator.time_steps
    
    def test_belt_simulation(self):
        """Test belt/pulley mechanism simulation."""
        # Parameters: [r1, r2, center1_x, center1_y, center2_x, center2_y, omega1, slip_coeff]
        params = np.array([40.0, 25.0, 0.0, 0.0, 120.0, 0.0, 1.0, 0.1])
        
        motion_curve = self.simulator.simulate_mechanism(MechanismType.BELT, params)
        
        # Verify motion curve properties
        assert motion_curve.points.shape[0] == self.simulator.time_steps
        assert motion_curve.points.shape[1] == 2
        assert motion_curve.period == 2 * np.pi
        
        # Verify points are within reasonable bounds
        x_positions = motion_curve.points[:, 0]
        y_positions = motion_curve.points[:, 1]
        
        # Points should be within the belt path area
        min_x = min(params[2], params[4]) - max(params[0], params[1])
        max_x = max(params[2], params[4]) + max(params[0], params[1])
        min_y = min(params[3], params[5]) - max(params[0], params[1])
        max_y = max(params[3], params[5]) + max(params[0], params[1])
        
        assert np.all(x_positions >= min_x), f"X positions should be >= {min_x}"
        assert np.all(x_positions <= max_x), f"X positions should be <= {max_x}"
        assert np.all(y_positions >= min_y), f"Y positions should be >= {min_y}"
        assert np.all(y_positions <= max_y), f"Y positions should be <= {max_y}"
    
    def test_belt_simulation_invalid_geometry(self):
        """Test belt simulation with invalid geometry (overlapping pulleys)."""
        # Parameters with pulleys too close together
        params = np.array([40.0, 25.0, 0.0, 0.0, 50.0, 0.0, 1.0, 0.0])  # Distance = 50, sum of radii = 65
        
        with pytest.raises(ValueError, match="too close together"):
            self.simulator.simulate_mechanism(MechanismType.BELT, params)
    
    def test_spring_simulation(self):
        """Test spring/damper mechanism simulation."""
        # Parameters: [k, c, m, x1, y1, x2, y2, rest_length, initial_velocity, external_force]
        params = np.array([100.0, 10.0, 1.0, 0.0, 0.0, 0.0, 120.0, 100.0, 0.0, 0.0])
        
        motion_curve = self.simulator.simulate_mechanism(MechanismType.SPRING, params)
        
        # Verify motion curve properties
        assert motion_curve.points.shape[0] == self.simulator.time_steps
        assert motion_curve.points.shape[1] == 2
        assert motion_curve.period == 2 * np.pi
        
        # Verify mass motion is reasonable
        positions = motion_curve.points
        
        # For underdamped system, expect oscillatory motion
        y_positions = positions[:, 1]
        y_range = np.max(y_positions) - np.min(y_positions)
        assert y_range > 0, "Spring system should show motion"
        
        # Verify motion is along the spring direction (vertical in this case)
        x_positions = positions[:, 0]
        x_variance = np.var(x_positions)
        assert x_variance < 1.0, "Motion should be primarily vertical"
    
    def test_spring_simulation_different_damping(self):
        """Test spring simulation with different damping conditions."""
        base_params = np.array([100.0, 10.0, 1.0, 0.0, 0.0, 0.0, 120.0, 100.0, 10.0, 0.0])
        
        # Test underdamped (low damping)
        params_underdamped = base_params.copy()
        params_underdamped[1] = 5.0  # Low damping
        motion_underdamped = self.simulator.simulate_mechanism(MechanismType.SPRING, params_underdamped)
        
        # Test critically damped
        params_critical = base_params.copy()
        params_critical[1] = 2 * np.sqrt(params_critical[0] * params_critical[2])  # Critical damping
        motion_critical = self.simulator.simulate_mechanism(MechanismType.SPRING, params_critical)
        
        # Test overdamped (high damping)
        params_overdamped = base_params.copy()
        params_overdamped[1] = 50.0  # High damping
        motion_overdamped = self.simulator.simulate_mechanism(MechanismType.SPRING, params_overdamped)
        
        # All should produce valid results
        for motion in [motion_underdamped, motion_critical, motion_overdamped]:
            assert motion.points.shape[0] == self.simulator.time_steps
            assert motion.points.shape[1] == 2
    
    def test_simulation_parameter_validation(self):
        """Test simulation parameter validation."""
        # Test insufficient parameters for each mechanism type
        
        # Cam with insufficient parameters (cam uses defaults, so no error expected)
        # Test that it at least runs and produces output
        result = self.simulator._simulate_cam(np.array([10.0, 20.0]), np.linspace(0, 2*np.pi, 10))
        assert result.shape[0] == 10, "Cam should still produce output with minimal parameters"
        
        # Belt with insufficient parameters
        with pytest.raises(ValueError, match="Belt simulation requires"):
            self.simulator._simulate_belt(np.array([10.0, 20.0]), np.linspace(0, 2*np.pi, 10))
        
        # Spring with insufficient parameters
        with pytest.raises(ValueError, match="Spring simulation requires"):
            self.simulator._simulate_spring(np.array([10.0, 20.0]), np.linspace(0, 2*np.pi, 10))
    
    def test_unknown_mechanism_type(self):
        """Test simulation with unknown mechanism type."""
        # Create a mock unknown mechanism type
        class UnknownMechanismType:
            pass
        
        unknown_type = UnknownMechanismType()
        params = np.array([1.0, 2.0, 3.0])
        
        with pytest.raises(ValueError, match="Unknown mechanism type"):
            self.simulator.simulate_mechanism(unknown_type, params)
    
    def test_motion_curve_consistency(self):
        """Test that motion curves are consistent across multiple runs."""
        params = np.array([30.0, 20.0, 10.0, 0.0, 0.0, 0, 0.0, 0.0])
        
        # Run simulation multiple times
        motion1 = self.simulator.simulate_mechanism(MechanismType.CAM, params)
        motion2 = self.simulator.simulate_mechanism(MechanismType.CAM, params)
        
        # Results should be identical for deterministic simulation
        np.testing.assert_array_almost_equal(motion1.points, motion2.points, decimal=10)
        assert motion1.period == motion2.period
    
    def test_simulation_edge_cases(self):
        """Test simulation with edge case parameters."""
        
        # Test cam with zero rise
        cam_params = np.array([30.0, 0.0, 10.0, 0.0, 0.0, 0, 0.0, 0.0])
        motion = self.simulator.simulate_mechanism(MechanismType.CAM, cam_params)
        assert motion.points.shape[0] == self.simulator.time_steps
        
        # Test spring with very low damping
        spring_params = np.array([100.0, 0.001, 1.0, 0.0, 0.0, 0.0, 120.0, 100.0, 0.0, 0.0])
        motion = self.simulator.simulate_mechanism(MechanismType.SPRING, spring_params)
        assert motion.points.shape[0] == self.simulator.time_steps
        
        # Test belt with no slip
        belt_params = np.array([40.0, 25.0, 0.0, 0.0, 120.0, 0.0, 1.0, 0.0])
        motion = self.simulator.simulate_mechanism(MechanismType.BELT, belt_params)
        assert motion.points.shape[0] == self.simulator.time_steps
    
    def test_performance_with_large_time_steps(self):
        """Test simulation performance with large number of time steps."""
        large_simulator = MechanismSimulator(time_steps=1000)
        params = np.array([30.0, 20.0, 10.0, 0.0, 0.0, 0, 0.0, 0.0])
        
        import time
        start_time = time.time()
        motion = large_simulator.simulate_mechanism(MechanismType.CAM, params)
        end_time = time.time()
        
        # Should complete within reasonable time (adjust threshold as needed)
        execution_time = end_time - start_time
        assert execution_time < 5.0, f"Simulation took too long: {execution_time:.2f}s"
        assert motion.points.shape[0] == 1000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])