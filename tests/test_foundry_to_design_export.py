"""
Test Mechanism Foundry to Design tab export workflow.

Verifies that mechanisms can be exported from Foundry and imported
into the Design tab with correct parameter mapping.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestMechanismInstantiationService:
    """Test MechanismInstantiationService Foundry export functionality."""

    def test_create_layer_data_from_foundry_four_bar(self):
        """Test creating layer data from Foundry four-bar export."""
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )

        service = MechanismInstantiationService()

        # Foundry four_bar parameters
        foundry_params = {
            "ground_link": 150.0,
            "input_link": 40.0,
            "coupler_link": 120.0,
            "output_link": 130.0,
            "input_angle": 30.0,
        }

        layer_data = service.create_layer_data_from_foundry(
            mechanism_type="four_bar",
            parameters=foundry_params,
            pivot_point=(0.0, 0.0),
            part_name="right_arm",
            scene_position=(400.0, 300.0),
        )

        assert layer_data is not None
        assert layer_data["type"] == "4_bar_linkage"
        assert layer_data["part_name"] == "right_arm"
        assert layer_data["source"] == "foundry"

        # Verify parameter mapping
        params = layer_data["params"]
        assert params["l1"] == 150.0  # ground_link -> l1
        assert params["l2"] == 40.0   # input_link -> l2
        assert params["l3"] == 120.0  # coupler_link -> l3
        assert params["l4"] == 130.0  # output_link -> l4

    def test_create_layer_data_from_foundry_cam(self):
        """Test creating layer data from Foundry cam_follower export."""
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )

        service = MechanismInstantiationService()

        # Foundry cam_follower parameters
        foundry_params = {
            "cam_radius": 60.0,
            "cam_offset": 20.0,
            "follower_length": 100.0,
            "cam_lobes": 2,
            "profile_harmonic": 0.4,
        }

        layer_data = service.create_layer_data_from_foundry(
            mechanism_type="cam_follower",
            parameters=foundry_params,
            pivot_point=(0.0, 0.0),
            part_name="left_leg",
            scene_position=(500.0, 400.0),
        )

        assert layer_data is not None
        assert layer_data["type"] == "cam"
        assert layer_data["part_name"] == "left_leg"
        assert layer_data["source"] == "foundry"

        # Verify CAM-specific configuration
        assert "cam_position" in layer_data
        assert layer_data["cam_scale_factor"] == 1.0
        assert layer_data["rod_length_multiplier"] == 1.0

        # Verify parameter mapping
        params = layer_data["params"]
        assert params["base_radius"] == 60.0    # cam_radius -> base_radius
        assert params["eccentricity"] == 20.0   # cam_offset -> eccentricity
        assert params["follower_rod_length"] == 100.0  # follower_length -> follower_rod_length
        assert params["cam_lobes"] == 2
        assert params["profile_harmonic"] == 0.4

    def test_create_layer_data_from_foundry_gear(self):
        """Test creating layer data from Foundry gear_train export."""
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )

        service = MechanismInstantiationService()

        # Foundry gear_train parameters
        foundry_params = {
            "gear1_teeth": 12,
            "gear2_teeth": 18,
            "input_torque": 200.0,
        }

        layer_data = service.create_layer_data_from_foundry(
            mechanism_type="gear_train",
            parameters=foundry_params,
            pivot_point=(0.0, 0.0),
            part_name=None,
        )

        assert layer_data is not None
        assert layer_data["type"] == "gear"
        assert layer_data["source"] == "foundry"

        # Verify gear key_points are created
        assert "gear1_center" in layer_data["key_points"]
        assert "gear2_center" in layer_data["key_points"]

    def test_mechanism_id_uniqueness(self):
        """Test that each created layer has unique ID."""
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )

        service = MechanismInstantiationService()

        ids = set()
        for _ in range(10):
            layer_data = service.create_layer_data_from_foundry(
                mechanism_type="four_bar",
                parameters={"ground_link": 100.0},
                pivot_point=(0.0, 0.0),
            )
            ids.add(layer_data["id"])

        assert len(ids) == 10  # All IDs should be unique


class TestFoundryViewExportSignal:
    """Test MechanismFoundryView export signal emission."""

    def test_export_signal_exists(self):
        """Test that export_to_design_requested signal exists."""
        from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import (
            MechanismFoundryView,
        )

        # Check signal attribute exists on class
        assert hasattr(MechanismFoundryView, "export_to_design_requested")


class TestMechanismDesignTabImport:
    """Test MechanismDesignTab import functionality."""

    def test_import_method_exists(self):
        """Test that import_mechanism_from_foundry method exists."""
        from automataii.presentation.qt.tabs.mechanism_design.tab import (
            MechanismDesignTab,
        )

        assert hasattr(MechanismDesignTab, "import_mechanism_from_foundry")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
