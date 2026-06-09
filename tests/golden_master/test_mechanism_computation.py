"""
Golden Master Tests for Mechanism Computation.

These tests capture the expected output of mechanism computations
to ensure refactoring doesn't change the mathematical behavior.
"""

import pytest


class TestFourBarMechanismGoldenMaster:
    """Golden master tests for four-bar linkage computation."""

    @pytest.fixture
    def fourbar_mechanism(self):
        """Create a four-bar mechanism for testing."""
        try:
            from automataii.application.mechanism_foundry.catalog import (
                get_mechanism_catalog,
            )

            catalog = get_mechanism_catalog()
            return catalog.get("fourbar")
        except Exception:
            # Fallback to registry if catalog not available
            from automataii.domain.mechanisms.catalog.registry import MechanismRegistry

            registry = MechanismRegistry()
            try:
                return registry.get("fourbar")
            except Exception:
                return None

    def test_fourbar_state_at_0_degrees(self, golden_master, fourbar_mechanism):
        """Capture four-bar state at 0 degrees input angle."""
        if fourbar_mechanism is None:
            pytest.skip("Fourbar mechanism not registered")

        parameters = {
            "ground_link": 100.0,
            "input_link": 40.0,
            "coupler_link": 80.0,
            "output_link": 60.0,
        }

        state = fourbar_mechanism.compute_state(parameters, 0.0)

        snapshot = golden_master("fourbar_0deg")
        snapshot.assert_matches(
            {
                "positions": state.positions,
                "mechanism_type": fourbar_mechanism.mechanism_type,
            },
            message="Four-bar state at 0 degrees",
        )

    def test_fourbar_state_at_90_degrees(self, golden_master, fourbar_mechanism):
        """Capture four-bar state at 90 degrees input angle."""
        if fourbar_mechanism is None:
            pytest.skip("Fourbar mechanism not registered")

        parameters = {
            "ground_link": 100.0,
            "input_link": 40.0,
            "coupler_link": 80.0,
            "output_link": 60.0,
        }

        state = fourbar_mechanism.compute_state(parameters, 90.0)

        snapshot = golden_master("fourbar_90deg")
        snapshot.assert_matches(
            {
                "positions": state.positions,
                "mechanism_type": fourbar_mechanism.mechanism_type,
            },
            message="Four-bar state at 90 degrees",
        )

    def test_fourbar_state_at_180_degrees(self, golden_master, fourbar_mechanism):
        """Capture four-bar state at 180 degrees input angle."""
        if fourbar_mechanism is None:
            pytest.skip("Fourbar mechanism not registered")

        parameters = {
            "ground_link": 100.0,
            "input_link": 40.0,
            "coupler_link": 80.0,
            "output_link": 60.0,
        }

        state = fourbar_mechanism.compute_state(parameters, 180.0)

        snapshot = golden_master("fourbar_180deg")
        snapshot.assert_matches(
            {
                "positions": state.positions,
                "mechanism_type": fourbar_mechanism.mechanism_type,
            },
            message="Four-bar state at 180 degrees",
        )

    def test_fourbar_full_rotation(self, golden_master, fourbar_mechanism):
        """Capture four-bar positions through full rotation."""
        if fourbar_mechanism is None:
            pytest.skip("Fourbar mechanism not registered")

        parameters = {
            "ground_link": 100.0,
            "input_link": 40.0,
            "coupler_link": 80.0,
            "output_link": 60.0,
        }

        # Sample at 30-degree intervals
        positions_over_rotation = {}
        for angle in range(0, 360, 30):
            state = fourbar_mechanism.compute_state(parameters, float(angle))
            positions_over_rotation[str(angle)] = state.positions

        snapshot = golden_master("fourbar_full_rotation")
        snapshot.assert_matches(
            positions_over_rotation,
            message="Four-bar positions through full rotation",
        )


class TestCamMechanismGoldenMaster:
    """Golden master tests for cam-follower mechanism computation."""

    @pytest.fixture
    def cam_mechanism(self):
        """Create a cam mechanism for testing."""
        try:
            from automataii.application.mechanism_foundry.catalog import (
                get_mechanism_catalog,
            )

            catalog = get_mechanism_catalog()
            return catalog.get("cam_follower")
        except Exception:
            from automataii.domain.mechanisms.catalog.registry import MechanismRegistry

            registry = MechanismRegistry()
            try:
                return registry.get("cam_follower")
            except Exception:
                return None

    def test_cam_state_at_0_degrees(self, golden_master, cam_mechanism):
        """Capture cam state at 0 degrees."""
        if cam_mechanism is None:
            pytest.skip("Cam mechanism not registered")

        parameters = {
            "cam_radius": 50.0,
            "follower_offset": 0.0,
            "eccentricity": 20.0,
        }

        state = cam_mechanism.compute_state(parameters, 0.0)

        snapshot = golden_master("cam_0deg")
        snapshot.assert_matches(
            {
                "positions": state.positions,
                "mechanism_type": cam_mechanism.mechanism_type,
            },
            message="Cam state at 0 degrees",
        )

    def test_cam_full_rotation(self, golden_master, cam_mechanism):
        """Capture cam positions through full rotation."""
        if cam_mechanism is None:
            pytest.skip("Cam mechanism not registered")

        parameters = {
            "cam_radius": 50.0,
            "follower_offset": 0.0,
            "eccentricity": 20.0,
        }

        positions_over_rotation = {}
        for angle in range(0, 360, 30):
            state = cam_mechanism.compute_state(parameters, float(angle))
            positions_over_rotation[str(angle)] = state.positions

        snapshot = golden_master("cam_full_rotation")
        snapshot.assert_matches(
            positions_over_rotation,
            message="Cam positions through full rotation",
        )


class TestMechanismRegistryGoldenMaster:
    """Golden master tests for mechanism registry."""

    def test_registered_mechanisms(self, golden_master):
        """Capture list of registered mechanisms."""
        try:
            from automataii.application.mechanism_foundry.catalog import (
                get_mechanism_catalog,
            )

            catalog = get_mechanism_catalog()
            mechanism_types = sorted(catalog.list_types())
        except Exception:
            from automataii.domain.mechanisms.catalog.registry import MechanismRegistry

            registry = MechanismRegistry()
            mechanism_types = sorted(registry.list_types())

        snapshot = golden_master("registered_mechanisms")
        snapshot.assert_matches(
            {"types": mechanism_types},
            message="Registered mechanism types",
        )

    def test_mechanism_required_parameters(self, golden_master):
        """Capture required parameters for each mechanism type."""
        try:
            from automataii.application.mechanism_foundry.catalog import (
                get_mechanism_catalog,
            )

            catalog = get_mechanism_catalog()
            required_params = {}

            for mech_type in catalog.list_types():
                mechanism = catalog.get(mech_type)
                if mechanism and hasattr(mechanism, "required_parameters"):
                    required_params[mech_type] = sorted(mechanism.required_parameters)
        except Exception:
            from automataii.domain.mechanisms.catalog.registry import MechanismRegistry

            registry = MechanismRegistry()
            required_params = {}

            for mech_type in registry.list_types():
                mechanism = registry.get(mech_type)
                if mechanism:
                    required_params[mech_type] = sorted(mechanism.required_parameters)

        snapshot = golden_master("mechanism_required_params")
        snapshot.assert_matches(
            required_params,
            message="Required parameters for each mechanism",
        )
