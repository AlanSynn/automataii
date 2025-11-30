import math

import pytest

from automataii.domain.mechanisms.core.state import SafetyLevel
from automataii.domain.mechanisms.linkages.fourbar.compute import FourBarMechanism, FourBarParameters


class TestFourBarParameters:
    def test_creation_with_defaults(self):
        params = FourBarParameters(
            ground_link=150.0,
            input_link=40.0,
            coupler_link=120.0,
            output_link=130.0,
            input_angle=0.0,
        )
        assert params.ground_link == 150.0
        assert params.input_link == 40.0
        assert params.coupler_link == 120.0
        assert params.output_link == 130.0
        assert params.input_angle == 0.0
        assert params.ground_pivot1 is None
        assert params.ground_pivot2 is None

    def test_creation_with_custom_pivots(self):
        # Domain code uses tuples, not Qt types
        gp1 = (0.0, 0.0)
        gp2 = (100.0, 0.0)
        params = FourBarParameters(
            ground_link=100.0,
            input_link=40.0,
            coupler_link=120.0,
            output_link=130.0,
            input_angle=0.0,
            ground_pivot1=gp1,
            ground_pivot2=gp2,
        )
        assert params.ground_pivot1 == gp1
        assert params.ground_pivot2 == gp2

    def test_immutability(self):
        params = FourBarParameters(
            ground_link=150.0,
            input_link=40.0,
            coupler_link=120.0,
            output_link=130.0,
            input_angle=0.0,
        )
        with pytest.raises(AttributeError):
            params.ground_link = 200.0


class TestFourBarMechanism:
    def test_initialization_with_defaults(self):
        mech = FourBarMechanism()
        assert mech.mechanism_type == "fourbar"
        assert "ground_link" in mech.required_parameters
        assert "input_link" in mech.required_parameters
        assert "coupler_link" in mech.required_parameters
        assert "output_link" in mech.required_parameters

    def test_initialization_with_custom_parameters(self):
        params = {
            "ground_link": 200.0,
            "input_link": 50.0,
            "coupler_link": 150.0,
            "output_link": 140.0,
        }
        mech = FourBarMechanism(params)
        assert mech._parameters.ground_link == 200.0
        assert mech._parameters.input_link == 50.0

    def test_compute_state_crank_rocker(self):
        mech = FourBarMechanism()
        params = {
            "ground_link": 150.0,
            "input_link": 40.0,
            "coupler_link": 120.0,
            "output_link": 130.0,
        }
        state = mech.compute_state(params, 45.0)

        assert "O1" in state.positions
        assert "O4" in state.positions
        assert "A" in state.positions
        assert "B" in state.positions
        assert state.safety_status.level == SafetyLevel.SAFE
        assert "Crank-Rocker" in state.safety_status.message
        assert state.forces is not None
        assert "input" in state.forces
        assert "reaction_O1" in state.forces

    def test_compute_state_different_angles(self):
        mech = FourBarMechanism()
        params = {
            "ground_link": 150.0,
            "input_link": 40.0,
            "coupler_link": 120.0,
            "output_link": 130.0,
        }

        state_0 = mech.compute_state(params, 0.0)
        state_90 = mech.compute_state(params, 90.0)
        state_180 = mech.compute_state(params, 180.0)

        assert state_0.positions["A"] != state_90.positions["A"]
        assert state_90.positions["A"] != state_180.positions["A"]
        assert state_0.positions["B"] != state_90.positions["B"]

    def test_compute_state_with_custom_pivots(self):
        mech = FourBarMechanism()
        # Domain code uses tuples, not Qt types
        params = {
            "ground_link": 150.0,
            "input_link": 40.0,
            "coupler_link": 120.0,
            "output_link": 130.0,
            "ground_pivot1": (-100.0, 50.0),
            "ground_pivot2": (100.0, 50.0),
        }
        state = mech.compute_state(params, 45.0)

        O1 = state.positions["O1"]
        O4 = state.positions["O4"]
        assert abs(O1[0] - (-100)) < 0.1
        assert abs(O1[1] - 50) < 0.1
        assert abs(O4[0] - 100) < 0.1
        assert abs(O4[1] - 50) < 0.1

    def test_grashof_double_crank(self):
        mech = FourBarMechanism()
        params = {
            "ground_link": 40.0,
            "input_link": 100.0,
            "coupler_link": 100.0,
            "output_link": 100.0,
        }
        state = mech.compute_state(params, 0.0)
        assert "Double-Crank" in state.safety_status.message

    def test_grashof_triple_rocker(self):
        mech = FourBarMechanism()
        params = {
            "ground_link": 50.0,
            "input_link": 100.0,
            "coupler_link": 150.0,
            "output_link": 120.0,
        }
        state = mech.compute_state(params, 0.0)
        assert state.safety_status.level in [SafetyLevel.WARNING, SafetyLevel.DANGER]

    def test_transmission_angle_quality(self):
        mech = FourBarMechanism()
        params = {
            "ground_link": 150.0,
            "input_link": 40.0,
            "coupler_link": 120.0,
            "output_link": 130.0,
        }
        state = mech.compute_state(params, 45.0)
        assert (
            "T.A.:" in state.safety_status.message
            or "transmission" in state.safety_status.message.lower()
        )

    def test_metadata_contains_angles(self):
        mech = FourBarMechanism()
        params = {
            "ground_link": 150.0,
            "input_link": 40.0,
            "coupler_link": 120.0,
            "output_link": 130.0,
        }
        state = mech.compute_state(params, 45.0)
        assert "input_angle" in state.metadata
        assert "output_angle" in state.metadata
        assert state.metadata["input_angle"] == 45.0

    def test_validate_parameters_success(self):
        mech = FourBarMechanism()
        params = {
            "ground_link": 150.0,
            "input_link": 40.0,
            "coupler_link": 120.0,
            "output_link": 130.0,
        }
        mech.validate_parameters(params)

    def test_validate_parameters_missing(self):
        mech = FourBarMechanism()
        params = {"ground_link": 150.0, "input_link": 40.0}
        with pytest.raises(ValueError, match="Missing required parameters"):
            mech.validate_parameters(params)

    def test_validate_parameters_negative(self):
        mech = FourBarMechanism()
        params = {
            "ground_link": -150.0,
            "input_link": 40.0,
            "coupler_link": 120.0,
            "output_link": 130.0,
        }
        with pytest.raises(ValueError, match="must be positive"):
            mech.validate_parameters(params)

    def test_validate_parameters_zero(self):
        mech = FourBarMechanism()
        params = {
            "ground_link": 150.0,
            "input_link": 0.0,
            "coupler_link": 120.0,
            "output_link": 130.0,
        }
        with pytest.raises(ValueError, match="must be positive"):
            mech.validate_parameters(params)

    def test_continuity_across_angles(self):
        mech = FourBarMechanism()
        params = {
            "ground_link": 150.0,
            "input_link": 40.0,
            "coupler_link": 120.0,
            "output_link": 130.0,
        }

        prev_state = mech.compute_state(params, 0.0)
        for angle in range(1, 360, 10):
            state = mech.compute_state(params, float(angle))
            prev_B = prev_state.positions["B"]
            curr_B = state.positions["B"]
            distance = math.hypot(curr_B[0] - prev_B[0], curr_B[1] - prev_B[1])
            assert distance < 50, f"Large jump at angle {angle}: {distance}"
            prev_state = state
