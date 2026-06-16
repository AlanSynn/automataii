"""
Test Mechanism Foundry to Design tab export workflow.

Verifies that mechanisms can be exported from Foundry and imported
into the Design tab with correct parameter mapping.
"""

from __future__ import annotations

import inspect
import math
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest


class TestMechanismInstantiationService:
    """Test MechanismInstantiationService Foundry export functionality."""

    def test_instantiation_service_uses_2cm_physical_context_by_default(self):
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )

        service = MechanismInstantiationService()

        assert service._grid_cell_cm == pytest.approx(2.0)
        assert service._grid_pitch_choice == "2cm"

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
        assert params["l1"] == pytest.approx(150.0)  # ground_link -> l1
        assert params["l2"] == pytest.approx(40.0)  # input_link -> l2
        assert params["l3"] == pytest.approx(120.0)  # coupler_link -> l3
        assert params["l4"] == pytest.approx(130.0)  # output_link -> l4

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
            "output_point_mode": "contact_point",
            "reverse_direction": True,
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
        assert layer_data["cam_position"] == [500.0, 400.0]
        assert layer_data["key_points"]["cam_center"] == [500.0, 400.0]
        assert layer_data["reverse_direction"] is True

        # Verify parameter mapping
        params = layer_data["params"]
        assert params["base_radius"] == pytest.approx(16.0)
        assert params["eccentricity"] == pytest.approx(6.0)
        assert params["follower_rod_length"] == 100.0  # follower_length -> follower_rod_length
        assert params["cam_lobes"] == 2
        assert params["profile_harmonic"] == 0.2
        assert params["physical_cam_preset"] == "oval"
        assert params["rise_deg"] == 120.0
        assert params["high_dwell_deg"] == 30.0
        assert params["return_deg"] == 120.0
        assert params["output_point_mode"] == "contact_point"
        assert params["reverse_direction"] is True

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

    def test_create_layer_data_from_foundry_gear_linkage_keeps_linkage_contract(self):
        """Gear+linkage exports should remain recognizable in Design as a gear linkage."""
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )

        service = MechanismInstantiationService()
        layer_data = service.create_layer_data_from_foundry(
            mechanism_type="gear_linkage",
            parameters={
                "gear1_teeth": 12,
                "gear2_teeth": 18,
                "linkage_pin_radius": 12.0,
                "linkage_arm_length": 40.0,
                "input_angle": 30.0,
            },
            pivot_point=(0.0, 0.0),
            part_name=None,
        )

        assert layer_data is not None
        assert layer_data["type"] == "gear"
        assert layer_data["source_type"] == "gear_linkage"
        assert layer_data["params"]["gear_linkage_enabled"] is True
        assert layer_data["params"]["linkage_pin_radius"] == pytest.approx(12.0)
        assert layer_data["params"]["linkage_arm_length"] == pytest.approx(40.0)

    def test_create_layer_data_from_foundry_slider_crank(self):
        """Slider-crank exports should map to a valid internal 4-bar payload."""
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )

        service = MechanismInstantiationService()

        foundry_params = {
            "crank_length": 80.0,
            "rod_length": 140.0,
            "gas_pressure": 500.0,
            "input_angle": 35.0,
        }

        layer_data = service.create_layer_data_from_foundry(
            mechanism_type="slider_crank",
            parameters=foundry_params,
            pivot_point=(0.0, 0.0),
            part_name="torso",
            scene_position=(420.0, 310.0),
        )

        assert layer_data is not None
        assert layer_data["type"] == "4_bar_linkage"
        assert layer_data["source"] == "foundry"
        params = layer_data["params"]
        assert params["l2"] == pytest.approx(80.0)
        assert params["l3"] == pytest.approx(140.0)
        assert params["l4"] == pytest.approx(140.0)
        assert params["l1"] > 0.0
        assert params["crank_angle"] == 35.0

    def test_create_layer_data_from_foundry_preserves_four_bar_snapshot_geometry(self):
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )

        service = MechanismInstantiationService()
        layer_data = service.create_layer_data_from_foundry(
            mechanism_type="four_bar",
            parameters={
                "ground_link": 150.0,
                "input_link": 40.0,
                "coupler_link": 120.0,
                "output_link": 130.0,
                "input_angle": 30.0,
            },
            pivot_point=(0.0, 0.0),
            part_name="torso",
            scene_position=(400.0, 300.0),
            foundry_snapshot={
                "positions": {
                    "O1": [-75.0, 0.0],
                    "O4": [75.0, 0.0],
                    "A": [-40.0, 20.0],
                    "B": [60.0, 45.0],
                }
            },
        )

        key_points = layer_data["key_points"]
        assert key_points["ground_pivot_1"] == [325.0, 300.0]
        assert key_points["ground_pivot_2"] == [475.0, 300.0]
        assert key_points["crank_end"] == [360.0, 320.0]
        assert key_points["rocker_end"] == [460.0, 345.0]
        assert "coupler_point" in key_points
        assert layer_data["params"]["l1"] == 150.0
        assert layer_data["params"]["L1"] == 150.0
        assert layer_data["params"]["anchor1_x"] == 325.0
        assert layer_data["params"]["anchor1_y"] == 300.0
        assert layer_data["params"]["anchor2_x"] == 475.0
        assert layer_data["params"]["anchor2_y"] == 300.0
        assert layer_data["params"]["crank_x"] == 360.0
        assert layer_data["params"]["crank_y"] == 320.0
        assert layer_data["params"]["rocker_x"] == 460.0
        assert layer_data["params"]["rocker_y"] == 345.0
        assert layer_data["params"]["coupler_x"] == pytest.approx(key_points["coupler_point"][0])
        assert layer_data["params"]["coupler_y"] == pytest.approx(key_points["coupler_point"][1])
        assert layer_data["coordinate_space"] == "scene"
        assert layer_data["scene_anchor"] == [400.0, 300.0]

    def test_create_layer_data_from_foundry_ignores_incomplete_four_bar_snapshot(self):
        """Partial snapshots must not collapse missing joints into zero-length links."""
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )

        service = MechanismInstantiationService()
        layer_data = service.create_layer_data_from_foundry(
            mechanism_type="four_bar",
            parameters={
                "ground_link": 150.0,
                "input_link": 40.0,
                "coupler_link": 120.0,
                "output_link": 130.0,
                "input_angle": 0.0,
            },
            pivot_point=(0.0, 0.0),
            part_name="torso",
            scene_position=(400.0, 300.0),
            foundry_snapshot={
                "positions": {
                    "O1": [-75.0, 0.0],
                    "O4": [75.0, 0.0],
                }
            },
        )

        assert layer_data["params"]["l1"] == pytest.approx(150.0)
        assert layer_data["params"]["l2"] == pytest.approx(40.0)
        assert layer_data["key_points"]["crank_end"] != layer_data["key_points"]["ground_pivot_1"]

    def test_create_layer_data_from_foundry_accepts_explicit_aliases(self):
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )

        service = MechanismInstantiationService()

        fourbar = service.create_layer_data_from_foundry(
            mechanism_type=" FourBar ",
            parameters={"ground_link": 150.0, "input_link": 40.0},
            pivot_point=(0.0, 0.0),
            scene_position=(400.0, 300.0),
        )
        slider = service.create_layer_data_from_foundry(
            mechanism_type="slider-crank",
            parameters={"crank_length": 80.0, "rod_length": 140.0},
            pivot_point=(0.0, 0.0),
            scene_position=(400.0, 300.0),
        )

        assert fourbar["type"] == "4_bar_linkage"
        assert fourbar["source_type"] == "four_bar"
        assert slider["type"] == "4_bar_linkage"
        assert slider["source_type"] == "slider_crank"
        assert slider["approximated_as"] == "4_bar_linkage"

    def test_create_layer_data_from_foundry_rejects_malformed_type_payloads(self):
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
            UnsupportedMechanismTypeError,
        )

        service = MechanismInstantiationService()

        for bad_type in ("", "   ", None):
            with pytest.raises(UnsupportedMechanismTypeError):
                service.create_layer_data_from_foundry(
                    mechanism_type=bad_type,  # type: ignore[arg-type]
                    parameters={},
                    pivot_point=(0.0, 0.0),
                    scene_position=(400.0, 300.0),
                )

    def test_map_foundry_gear_string_teeth_do_not_concatenate_radius(self):
        """String tooth counts should be numeric, not Python string repetition."""
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )

        service = MechanismInstantiationService()
        params = service.map_foundry_params_to_internal(
            " Gear ",
            {"gear1_teeth": "12", "gear2_teeth": "18"},
        )

        assert params["gear1_teeth"] == 12
        assert params["gear2_teeth"] == 18
        assert params["r1"] == 18.0
        assert params["r2"] == 27.0
        assert params["gear1_radius"] == 18.0
        assert params["gear2_radius"] == 27.0

    def test_map_foundry_gear_honors_grid_disabled_freeform_teeth(self):
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )

        service = MechanismInstantiationService()
        params = service.map_foundry_params_to_internal(
            "gear_train",
            {"gear1_teeth": 12, "gear2_teeth": 18, "grid_system_enabled": False},
        )

        assert params["grid_system_enabled"] is False
        assert params["gear1_teeth"] == 12
        assert params["gear2_teeth"] == 18
        assert params["gear1_radius"] == 18.0
        assert params["gear2_radius"] == 27.0

    def test_create_foundry_gear_honors_grid_disabled_freeform_teeth(self):
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )

        service = MechanismInstantiationService()
        layer_data = service.create_layer_data_from_foundry(
            mechanism_type="gear_train",
            parameters={"gear1_teeth": 12, "gear2_teeth": 18, "grid_system_enabled": False},
            pivot_point=(0.0, 0.0),
            scene_position=(400.0, 300.0),
        )

        assert layer_data["params"]["grid_system_enabled"] is False
        assert layer_data["params"]["gear1_radius"] == 18.0
        assert layer_data["params"]["gear2_radius"] == 27.0
        assert layer_data["key_points"]["gear1_center"] == [376.5, 300.0]
        assert layer_data["key_points"]["gear2_center"] == [423.5, 300.0]

    def test_map_foundry_params_rejects_malformed_type_payload(self):
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
            UnsupportedMechanismTypeError,
        )

        service = MechanismInstantiationService()

        with pytest.raises(UnsupportedMechanismTypeError):
            service.map_foundry_params_to_internal(None, {})  # type: ignore[arg-type]

    def test_create_layer_data_from_foundry_preserves_cam_snapshot_center(self):
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )

        service = MechanismInstantiationService()
        layer_data = service.create_layer_data_from_foundry(
            mechanism_type="cam_follower",
            parameters={
                "cam_radius": 60.0,
                "cam_offset": 20.0,
                "follower_length": 100.0,
            },
            pivot_point=(0.0, 0.0),
            part_name="torso",
            scene_position=(520.0, 360.0),
            foundry_snapshot={
                "positions": {
                    "cam_center": [0.0, 0.0],
                    "follower_base": [0.0, -140.0],
                    "follower_end": [0.0, -70.0],
                    "contact_point": [0.0, -60.0],
                }
            },
        )

        assert layer_data["cam_position"] == [520.0, 360.0]
        assert layer_data["params"]["center_x"] == 520.0
        assert layer_data["params"]["center_y"] == 360.0
        assert layer_data["key_points"]["cam_center"] == [520.0, 360.0]
        assert layer_data["key_points"]["follower_base"] == [520.0, 220.0]

    def test_create_layer_data_from_foundry_anchors_to_snapshot_coupler_point(self):
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )

        service = MechanismInstantiationService()
        layer_data = service.create_layer_data_from_foundry(
            mechanism_type="four_bar",
            parameters={
                "ground_link": 150.0,
                "input_link": 40.0,
                "coupler_link": 120.0,
                "output_link": 130.0,
                "input_angle": 30.0,
            },
            pivot_point=(0.0, 0.0),
            part_name="torso",
            scene_position=(400.0, 300.0),
            foundry_snapshot={
                "positions": {
                    "O1": [-75.0, 0.0],
                    "O4": [75.0, 0.0],
                    "A": [-40.0, 20.0],
                    "B": [60.0, 45.0],
                    "coupler_point": [10.0, 15.0],
                }
            },
        )

        key_points = layer_data["key_points"]
        assert key_points["ground_pivot_1"] == [315.0, 285.0]
        assert key_points["ground_pivot_2"] == [465.0, 285.0]
        assert key_points["crank_end"] == [350.0, 305.0]
        assert key_points["rocker_end"] == [450.0, 330.0]
        assert key_points["coupler_point"] == [400.0, 300.0]
        assert layer_data["scene_anchor"] == [400.0, 300.0]
        assert layer_data["scene_anchor_key"] == "coupler_point"

    def test_create_layer_data_from_foundry_normalizes_blank_part_name(self):
        """Blank/whitespace part names should not be preserved in layer data."""
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )

        service = MechanismInstantiationService()

        layer_data = service.create_layer_data_from_foundry(
            mechanism_type="cam_follower",
            parameters={"cam_radius": 40.0},
            pivot_point=(0.0, 0.0),
            part_name="   ",
        )

        assert layer_data["part_name"] is None

    def test_recommendation_cam_configuration_sanitizes_bad_numeric_payloads(self):
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )

        service = MechanismInstantiationService()
        layer_data, graphics_data = service.create_layer_data_from_recommendation(
            mechanism_data={
                "type": " cam & follower ",
                "parameters": {
                    "base_radius": "bad",
                    "eccentricity": float("nan"),
                },
            },
            target_path=None,
            fallback_position=[math.nan, "bad"],
        )

        assert layer_data["type"] == "cam"
        assert layer_data["params"]["center_x"] == pytest.approx(400.0)
        assert layer_data["params"]["center_y"] == pytest.approx(300.0)
        assert math.isfinite(layer_data["cam_scale_factor"])
        assert graphics_data["transform_params"]["scale"] == 1.0

    def test_recommendation_layers_inherit_disabled_grid_context(self):
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )
        from automataii.shared.physical_kit import DEFAULT_HOLE_DIAMETER_MM

        service = MechanismInstantiationService()
        service.set_grid_system(False, 3.33)

        layer_data, graphics_data = service.create_layer_data_from_recommendation(
            mechanism_data={
                "type": "Gears",
                "parameters": {"gear1_teeth": 13, "gear2_teeth": 17},
            },
            target_path=None,
        )

        params = layer_data["params"]
        assert params["grid_system_enabled"] is False
        assert params["grid_cell_cm"] == pytest.approx(3.33)
        assert params["physical_profile_key"]
        assert params["hole_diameter_mm"] == DEFAULT_HOLE_DIAMETER_MM
        assert params["gear1_teeth"] == 13
        assert params["gear2_teeth"] == 17
        assert graphics_data["params"]["grid_system_enabled"] is False
        assert graphics_data["params"]["hole_diameter_mm"] == DEFAULT_HOLE_DIAMETER_MM

    def test_candidate_layers_inherit_disabled_grid_context(self):
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )
        from automataii.shared.physical_kit import DEFAULT_HOLE_DIAMETER_MM

        service = MechanismInstantiationService()
        service.set_grid_system(False, 2.75)

        layer_data = service.create_layer_data_from_candidate(
            candidate_data={
                "type": "Gears",
                "parameters": {"gear1_teeth": 13, "gear2_teeth": 17},
            },
            selected_part_name="arm",
            target_path=None,
            convert_params_fn=None,
            extract_key_points_fn=None,
        )

        params = layer_data["params"]
        assert params["grid_system_enabled"] is False
        assert params["grid_cell_cm"] == pytest.approx(2.75)
        assert params["physical_profile_key"]
        assert params["hole_diameter_mm"] == DEFAULT_HOLE_DIAMETER_MM
        assert params["gear1_teeth"] == 13
        assert params["gear2_teeth"] == 17

    def test_cam_recommendation_inherits_disabled_grid_context_without_snapping(self):
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )

        service = MechanismInstantiationService()
        service.set_grid_system(False, 2.75)

        layer_data, _graphics_data = service.create_layer_data_from_recommendation(
            mechanism_data={
                "type": "Cam & Follower",
                "parameters": {"base_radius": 53.0, "eccentricity": 19.0},
            },
            target_path=None,
        )

        params = layer_data["params"]
        assert params["grid_system_enabled"] is False
        assert params["base_radius"] == pytest.approx(53.0)
        assert params["eccentricity"] == pytest.approx(19.0)

    def test_cam_path_analysis_ignores_non_finite_converter_rows(self):
        from PyQt6.QtGui import QPainterPath

        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )

        service = MechanismInstantiationService()
        service.set_path_converter(lambda _path: np.array([[0.0, 0.0], [math.nan, 5.0]]))
        path = QPainterPath()
        path.moveTo(0.0, 0.0)
        path.lineTo(0.0, 10.0)

        cam_position, params = service.calculate_cam_position_from_path(
            path,
            fallback_position=[10.0, 20.0],
        )

        assert cam_position == [10.0, 20.0]
        assert params == {"center_x": 10.0, "center_y": 20.0}
        assert service.calculate_cam_eccentricity_from_path(path) == {}
        assert service.calculate_cam_params_for_vertical_path(path) == {}

    def test_foundry_scene_payloads_are_blueprint_safe_and_finite(self):
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )

        service = MechanismInstantiationService()
        layers = [
            service.create_layer_data_from_foundry(
                mechanism_type="four_bar",
                parameters={
                    "ground_link": 150.0,
                    "input_link": 40.0,
                    "coupler_link": 120.0,
                    "output_link": 130.0,
                },
                pivot_point=(0.0, 0.0),
                scene_position=(410.0, 320.0),
            ),
            service.create_layer_data_from_foundry(
                mechanism_type="cam_follower",
                parameters={
                    "cam_radius": 60.0,
                    "cam_offset": 20.0,
                    "follower_length": 100.0,
                },
                pivot_point=(0.0, 0.0),
                scene_position=(520.0, 360.0),
            ),
        ]

        required_keys = [
            {"ground_pivot_1", "ground_pivot_2", "crank_end", "rocker_end", "coupler_point"},
            {"cam_center"},
        ]
        for layer_data, required in zip(layers, required_keys, strict=True):
            assert layer_data["coordinate_space"] == "scene"
            assert set(layer_data["key_points"]) >= required
            assert set(layer_data["transform_params"]) >= {"center", "scale", "rotation"}
            for point in layer_data["key_points"].values():
                assert len(point) >= 2
                assert all(math.isfinite(float(value)) for value in point[:2])

    def test_create_layer_data_from_foundry_sanitizes_invalid_numeric_payloads(self):
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )

        service = MechanismInstantiationService()
        layer_data = service.create_layer_data_from_foundry(
            mechanism_type="four_bar",
            parameters={
                "ground_link": float("nan"),
                "input_link": "bad",
                "coupler_link": -1.0,
                "output_link": 0.0,
                "input_angle": float("inf"),
            },
            pivot_point=(math.nan, 0.0),
            scene_position=(math.inf, "bad"),
            foundry_snapshot={"positions": {"O1": [math.nan, 0.0]}},
        )

        assert layer_data["transform_params"]["center"] == [0.0, 0.0]
        assert layer_data["params"]["l1"] == pytest.approx(150.0)
        assert layer_data["params"]["l2"] == pytest.approx(40.0)
        assert layer_data["params"]["l3"] == pytest.approx(120.0)
        assert layer_data["params"]["l4"] == pytest.approx(130.0)
        for point in layer_data["key_points"].values():
            assert all(math.isfinite(value) for value in point)

    def test_map_foundry_params_sanitizes_bad_cam_gear_and_slider_values(self):
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )

        service = MechanismInstantiationService()

        cam = service.map_foundry_params_to_internal(
            "cam_follower",
            {
                "cam_radius": float("nan"),
                "cam_offset": -5.0,
                "follower_length": "bad",
                "cam_lobes": 0,
                "profile_harmonic": float("inf"),
            },
        )
        gear = service.map_foundry_params_to_internal(
            "gear_train",
            {"gear1_teeth": True, "gear2_teeth": "bad"},
        )
        slider = service.map_foundry_params_to_internal(
            "slider_crank",
            {"crank_length": float("nan"), "rod_length": -1.0, "gas_pressure": "bad"},
        )

        assert cam["base_radius"] == pytest.approx(18.0)
        assert cam["eccentricity"] == pytest.approx(9.0)
        assert cam["follower_rod_length"] == pytest.approx(100.0)
        assert cam["cam_lobes"] == 1
        assert cam["profile_harmonic"] == pytest.approx(0.35)
        assert cam["physical_cam_preset"] == "pear"
        assert gear["gear1_teeth"] == 12
        assert gear["gear2_teeth"] == 16
        assert slider["l2"] == pytest.approx(80.0)
        assert slider["l3"] == pytest.approx(140.0)
        assert slider["gas_pressure"] == pytest.approx(0.0)

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

    def test_map_foundry_params_to_internal_preserves_output_point_mode(self):
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )

        service = MechanismInstantiationService()

        linkage_params = service.map_foundry_params_to_internal(
            "four_bar",
            {"ground_link": 150.0, "output_point_mode": "joint_a"},
        )
        cam_params = service.map_foundry_params_to_internal(
            "cam_follower",
            {"cam_radius": 60.0, "output_point_mode": "follower_end"},
        )

        assert linkage_params["output_point_mode"] == "joint_a"
        assert cam_params["output_point_mode"] == "follower_base"


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

    def test_resolve_target_part_uses_existing_selection_when_valid(self):
        from automataii.presentation.qt.tabs.mechanism_design.tab import (
            MechanismDesignTab,
        )

        fake_tab = SimpleNamespace(
            selected_part_name="left_arm",
            parts_data={
                "head": SimpleNamespace(anchor_joint_id="neck"),
                "left_arm": SimpleNamespace(anchor_joint_id="left_elbow"),
            },
            _prompt_target_part_for_foundry_import=lambda _: "head",
            _select_part_in_list=lambda _: None,
        )

        part_name = MechanismDesignTab._resolve_target_part_for_foundry_import(fake_tab)
        assert part_name == "left_arm"

    def test_resolve_target_part_prompts_user_when_none_selected(self):
        from automataii.presentation.qt.tabs.mechanism_design.tab import (
            MechanismDesignTab,
        )

        selected: list[str] = []
        fake_tab = SimpleNamespace(
            selected_part_name=None,
            parts_data={
                "head": SimpleNamespace(anchor_joint_id="neck"),
                "torso": SimpleNamespace(anchor_joint_id="root"),
            },
            _prompt_target_part_for_foundry_import=lambda parts: "torso",
            _select_part_in_list=lambda part: selected.append(part),
            _mvp_presenter=SimpleNamespace(select_part=lambda _: None),
        )

        part_name = MechanismDesignTab._resolve_target_part_for_foundry_import(fake_tab)
        assert part_name == "torso"
        assert fake_tab.selected_part_name == "torso"
        assert selected == ["torso"]

    def test_resolve_foundry_import_scene_position_prefers_part_anchor_joint(self):
        from automataii.presentation.qt.tabs.mechanism_design.tab import (
            MechanismDesignTab,
        )

        fake_tab = SimpleNamespace(
            parts_data={
                "left_arm": SimpleNamespace(anchor_joint_id="left_shoulder", roi=[0, 0, 50, 20])
            },
            initial_skeleton_cache={
                "joints": {
                    "left_shoulder": {"position": [512.0, 274.0]},
                }
            },
            mechanism_view=None,
        )
        fake_tab._resolve_joint_scene_position_for_part = (
            lambda part_name: MechanismDesignTab._resolve_joint_scene_position_for_part(
                fake_tab, part_name
            )
        )

        position = MechanismDesignTab._resolve_foundry_import_scene_position(fake_tab, "left_arm")
        assert position == (512.0, 274.0)

    def test_resolve_joint_scene_position_prefers_part_item_anchor(self):
        from automataii.presentation.qt.tabs.mechanism_design.tab import (
            MechanismDesignTab,
        )

        class _DummyPoint:
            def __init__(self, x: float, y: float):
                self._x = x
                self._y = y

            def x(self) -> float:
                return self._x

            def y(self) -> float:
                return self._y

        class _DummyPartItem:
            def transformOriginPoint(self):
                return _DummyPoint(0.0, 0.0)

            def mapToScene(self, _point):
                return _DummyPoint(450.0, 260.0)

        fake_tab = SimpleNamespace(
            current_editor_items={"left_arm": _DummyPartItem()},
            parts_data={
                "left_arm": SimpleNamespace(anchor_joint_id="left_shoulder", roi=[0, 0, 50, 20])
            },
            initial_skeleton_cache=None,
        )

        position = MechanismDesignTab._resolve_joint_scene_position_for_part(fake_tab, "left_arm")
        assert position == (450.0, 260.0)


class TestMechanismDesignGridSettings:
    def test_design_tab_grid_defaults_use_2cm_pitch_choice(self):
        from automataii.presentation.qt.tabs.mechanism_design.tab import MechanismDesignTab

        tab = MechanismDesignTab.__new__(MechanismDesignTab)

        assert MechanismDesignTab._extract_grid_settings_from_foundry_parameters(
            tab,
            {"grid_system_enabled": True},
        ) == (True, 2.0)
        source = inspect.getsource(
            MechanismDesignTab._extract_grid_settings_from_foundry_parameters
        )
        assert '"ms4n"' not in source

    def test_snap_lengths_to_grid_2_5cm_for_four_bar(self):
        from automataii.presentation.qt.tabs.mechanism_design.tab import MechanismDesignTab

        tab = MechanismDesignTab.__new__(MechanismDesignTab)
        tab._grid_system_enabled = True
        tab._grid_cell_cm = 2.5

        snapped = MechanismDesignTab._snap_lengths_to_grid(
            tab,
            "four_bar",
            {"l2": 41.0, "l3": 59.9, "l4": 76.2},
        )

        assert snapped["l2"] == 50.0
        assert snapped["l3"] == 50.0
        assert snapped["l4"] == 100.0
        assert snapped["L2"] == 50.0
        assert snapped["L3"] == 50.0
        assert snapped["L4"] == 100.0

    def test_snap_lengths_to_grid_keeps_positive_lengths_on_grid(self):
        from automataii.presentation.qt.tabs.mechanism_design.tab import MechanismDesignTab

        tab = MechanismDesignTab.__new__(MechanismDesignTab)
        tab._grid_system_enabled = True
        tab._grid_cell_cm = 2.5

        snapped = MechanismDesignTab._snap_lengths_to_grid(
            tab,
            "four_bar",
            {"l2": 12.5, "l3": 1.0},
        )

        assert snapped["l2"] == 50.0
        assert snapped["l3"] == 50.0
        assert snapped["L2"] == 50.0
        assert snapped["L3"] == 50.0

    def test_extract_grid_settings_from_foundry_payload(self):
        from automataii.presentation.qt.tabs.mechanism_design.tab import MechanismDesignTab

        tab = MechanismDesignTab.__new__(MechanismDesignTab)
        tab._grid_system_enabled = True
        tab._grid_cell_cm = 2.5

        settings = MechanismDesignTab._extract_grid_settings_from_foundry_parameters(
            tab,
            {"grid_system_enabled": False, "grid_cell_cm": 5.0},
        )

        assert settings == (False, 5.0)

    def test_extract_grid_settings_parses_string_false(self):
        from automataii.presentation.qt.tabs.mechanism_design.tab import MechanismDesignTab

        tab = MechanismDesignTab.__new__(MechanismDesignTab)
        tab._grid_system_enabled = True
        tab._grid_cell_cm = 2.5

        settings = MechanismDesignTab._extract_grid_settings_from_foundry_parameters(
            tab,
            {"grid_system_enabled": "false", "grid_cell_cm": "2.5"},
        )

        assert settings == (False, 2.5)

    def test_foundry_mechanism_type_normalization_ignores_case_and_whitespace(self):
        from automataii.presentation.qt.tabs.mechanism_design.tab import MechanismDesignTab

        assert (
            MechanismDesignTab._normalize_foundry_mechanism_type(" Four_Bar_Linkage ") == "four_bar"
        )
        assert MechanismDesignTab._normalize_foundry_mechanism_type(" CAM ") == "cam_follower"
        assert "cam_offset" in MechanismDesignTab._length_param_keys_for_foundry_type(" CAM ")


class TestMechanismDesignPresenterPayloadCompat:
    """Ensure presenter accepts both legacy and normalized mechanism payload keys."""

    def test_handle_mechanism_visuals_accepts_id_type_payload(self):
        from automataii.presentation.qt.tabs.mechanism_design.presenter import (
            MechanismDesignPresenter,
        )

        presenter = MechanismDesignPresenter.__new__(MechanismDesignPresenter)
        presenter._tab = SimpleNamespace(_clear_animation_cache=MagicMock())
        presenter._reset_skeleton_to_initial = MagicMock()
        presenter._visual_item_manager = SimpleNamespace(safe_remove_visual_items=MagicMock())
        presenter._transform_service = SimpleNamespace(
            get_scene_transform=MagicMock(return_value=MagicMock(name="transform"))
        )
        presenter._create_mechanism_visuals = MagicMock(return_value=["item"])
        presenter._request_scene_update = MagicMock()
        presenter.mechanism_layers = {
            "mech_1": {
                "id": "mech_1",
                "type": "4_bar_linkage",
                "params": {"l1": 120.0, "l2": 40.0, "l3": 90.0, "l4": 95.0},
                "visual_items": [],
            }
        }

        MechanismDesignPresenter.handle_mechanism_visuals(
            presenter,
            {"id": "mech_1", "type": "4_bar_linkage"},
        )

        presenter._create_mechanism_visuals.assert_called_once()
        call_args = presenter._create_mechanism_visuals.call_args[0]
        assert call_args[0] == "4_bar_linkage"
        assert call_args[1]["mechanism_id"] == "mech_1"
        assert call_args[1]["mechanism_type"] == "4_bar_linkage"


class TestMechanismDesignTabUiState:
    """UI state must respect locally imported mechanisms from Foundry."""

    def test_update_all_ui_states_uses_local_layers_even_with_presenter_vm(self):
        from automataii.presentation.qt.tabs.mechanism_design.tab import MechanismDesignTab

        tab = MechanismDesignTab.__new__(MechanismDesignTab)
        tab._presenter_view_model = SimpleNamespace(
            parts=[SimpleNamespace(name="torso", enabled=True, has_layers=False)]
        )
        tab.mechanism_layers = {"foundry_1": {"id": "foundry_1", "part_name": "torso"}}
        tab.path_data = {}
        tab.part_enabled_state = {"torso": True}
        tab.parametric_mode_enabled = False
        tab.parts_data = {"torso": object()}
        tab._animation_controller = SimpleNamespace(is_animation_running=lambda: False)
        tab._connect_to_ik_manager = lambda: None

        recorded = {}
        tab.ui_state_manager = SimpleNamespace(
            update_button_states=lambda state: recorded.setdefault("state", state)
        )

        MechanismDesignTab._update_all_ui_states(tab)

        assert tab._current_ui_state.has_mechanisms is True
        assert recorded["state"].has_mechanisms is True


class TestAnchorMovementAliasSync:
    """Ensure 4-bar recomputation keeps parameter aliases consistent."""

    def test_recalculate_4bar_params_sets_lowercase_aliases(self):
        from automataii.presentation.qt.tabs.mechanism_design.services.anchor_movement_handler import (
            AnchorMovementHandler,
        )

        handler = AnchorMovementHandler()
        params: dict[str, float] = {}
        key_points = {
            "ground_pivot_1": [0.0, 0.0],
            "ground_pivot_2": [100.0, 0.0],
            "crank_end": [40.0, 0.0],
            "rocker_end": [80.0, 30.0],
        }

        handler._recalculate_4bar_params(key_points, params)

        assert params["l1"] == params["L1"]
        assert params["l2"] == params["L2"]
        assert params["l3"] == params["L3"]
        assert params["l4"] == params["L4"]


class TestMechanismDesignTabFoundryUpdate:
    """Test Foundry -> Design update path for linkage synchronization."""

    def test_update_from_foundry_syncs_linkage_aliases_and_refreshes(self):
        from automataii.presentation.qt.tabs.mechanism_design.tab import MechanismDesignTab

        layer_data = {
            "type": "4_bar_linkage",
            "foundry_synced": True,
            "params": {"l1": 100.0, "l2": 40.0, "l3": 90.0, "l4": 80.0, "L2": 40.0},
        }
        fake_tab = SimpleNamespace(
            mechanism_layers={"mech_1": layer_data},
            _suppress_foundry_sync=False,
            _mechanism_instantiation=SimpleNamespace(
                map_foundry_params_to_internal=MagicMock(
                    return_value={"l2": 55.0, "l3": 95.0, "l4": 85.0}
                )
            ),
            _regenerate_foundry_layer_simulation=MagicMock(),
            _visual_animator=SimpleNamespace(build_cache=MagicMock()),
            _render_mechanism_layer=MagicMock(),
            mechanism_scene=SimpleNamespace(update=MagicMock()),
        )

        MechanismDesignTab.update_from_foundry(
            fake_tab,
            mechanism_id="mech_1",
            mechanism_type="four_bar",
            parameters={"input_link": 55.0, "input_angle": 33.0},
        )

        updated = fake_tab.mechanism_layers["mech_1"]["params"]
        assert updated["l2"] == 55.0
        assert updated["L2"] == 55.0
        assert updated["crank_angle"] == 33.0
        fake_tab._regenerate_foundry_layer_simulation.assert_called_once_with("mech_1", layer_data)
        fake_tab._visual_animator.build_cache.assert_called_once_with("mech_1", layer_data)
        fake_tab._render_mechanism_layer.assert_called_once_with("mech_1")

    def test_update_from_foundry_applies_output_point_mode(self):
        from automataii.presentation.qt.tabs.mechanism_design.tab import MechanismDesignTab

        layer_data = {
            "type": "4_bar_linkage",
            "foundry_synced": True,
            "params": {"l1": 100.0, "l2": 40.0, "l3": 90.0, "l4": 80.0},
        }
        fake_tab = SimpleNamespace(
            mechanism_layers={"mech_1": layer_data},
            _suppress_foundry_sync=False,
            _mechanism_instantiation=SimpleNamespace(
                map_foundry_params_to_internal=MagicMock(
                    return_value={"output_point_mode": "joint_a"}
                )
            ),
            _regenerate_foundry_layer_simulation=MagicMock(),
            _visual_animator=SimpleNamespace(build_cache=MagicMock()),
            _render_mechanism_layer=MagicMock(),
            mechanism_scene=SimpleNamespace(update=MagicMock()),
        )

        MechanismDesignTab.update_from_foundry(
            fake_tab,
            mechanism_id="mech_1",
            mechanism_type="four_bar",
            parameters={"output_point_mode": "joint_a"},
        )

        assert fake_tab.mechanism_layers["mech_1"]["params"]["output_point_mode"] == "joint_a"

    def test_update_from_foundry_rebuilds_linkage_scene_geometry_for_angle_changes(self):
        from automataii.presentation.qt.tabs.mechanism_design.tab import MechanismDesignTab

        layer_data = {
            "type": "4_bar_linkage",
            "foundry_synced": True,
            "coordinate_space": "scene",
            "scene_anchor": [400.0, 300.0],
            "params": {
                "l1": 150.0,
                "l2": 40.0,
                "l3": 120.0,
                "l4": 130.0,
                "crank_angle": 30.0,
                "anchor1_x": 325.0,
                "anchor1_y": 300.0,
                "crank_x": 359.64,
                "crank_y": 320.0,
            },
            "key_points": {
                "ground_pivot_1": [325.0, 300.0],
                "ground_pivot_2": [475.0, 300.0],
                "crank_end": [359.64, 320.0],
                "rocker_end": [460.0, 345.0],
            },
        }
        fake_tab = SimpleNamespace(
            mechanism_layers={"mech_1": layer_data},
            _suppress_foundry_sync=False,
            _mechanism_instantiation=SimpleNamespace(
                map_foundry_params_to_internal=MagicMock(
                    return_value={
                        "l1": 150.0,
                        "l2": 40.0,
                        "l3": 120.0,
                        "l4": 130.0,
                        "input_angle": 75.0,
                        "crank_angle": 75.0,
                    }
                )
            ),
            _regenerate_foundry_layer_simulation=MagicMock(),
            _visual_animator=SimpleNamespace(build_cache=MagicMock()),
            _render_mechanism_layer=MagicMock(),
            mechanism_scene=SimpleNamespace(update=MagicMock()),
        )

        MechanismDesignTab.update_from_foundry(
            fake_tab,
            mechanism_id="mech_1",
            mechanism_type="four_bar",
            parameters={"input_angle": 75.0},
        )

        updated = layer_data["params"]
        key_points = layer_data["key_points"]
        expected_crank = [
            325.0 + 40.0 * math.cos(math.radians(75.0)),
            300.0 + 40.0 * math.sin(math.radians(75.0)),
        ]
        assert updated["crank_angle"] == pytest.approx(75.0)
        assert [updated["crank_x"], updated["crank_y"]] == pytest.approx(expected_crank)
        assert key_points["crank_end"] == pytest.approx(expected_crank)
        assert key_points["crank_end"] != pytest.approx([359.64, 320.0])

    def test_update_from_foundry_rebuilds_linkage_scene_geometry_for_ground_length(self):
        from automataii.presentation.qt.tabs.mechanism_design.tab import MechanismDesignTab

        layer_data = {
            "type": "4_bar_linkage",
            "foundry_synced": True,
            "coordinate_space": "scene",
            "scene_anchor": [400.0, 300.0],
            "params": {
                "l1": 150.0,
                "l2": 40.0,
                "l3": 120.0,
                "l4": 130.0,
                "anchor1_x": 325.0,
                "anchor1_y": 300.0,
                "anchor2_x": 475.0,
                "anchor2_y": 300.0,
            },
            "key_points": {
                "ground_pivot_1": [325.0, 300.0],
                "ground_pivot_2": [475.0, 300.0],
                "crank_end": [365.0, 300.0],
                "rocker_end": [450.0, 350.0],
            },
        }
        fake_tab = SimpleNamespace(
            mechanism_layers={"mech_1": layer_data},
            _suppress_foundry_sync=False,
            _mechanism_instantiation=SimpleNamespace(
                map_foundry_params_to_internal=MagicMock(
                    return_value={
                        "l1": 300.0,
                        "l2": 40.0,
                        "l3": 120.0,
                        "l4": 130.0,
                        "input_angle": 0.0,
                        "crank_angle": 0.0,
                    }
                )
            ),
            _regenerate_foundry_layer_simulation=MagicMock(),
            _visual_animator=SimpleNamespace(build_cache=MagicMock()),
            _render_mechanism_layer=MagicMock(),
            mechanism_scene=SimpleNamespace(update=MagicMock()),
        )

        MechanismDesignTab.update_from_foundry(
            fake_tab,
            mechanism_id="mech_1",
            mechanism_type="four_bar",
            parameters={"ground_link": 300.0},
        )

        key_points = layer_data["key_points"]
        assert key_points["ground_pivot_1"] == pytest.approx([250.0, 300.0])
        assert key_points["ground_pivot_2"] == pytest.approx([550.0, 300.0])
        assert layer_data["params"]["anchor1_x"] == pytest.approx(250.0)
        assert layer_data["params"]["anchor2_x"] == pytest.approx(550.0)
        assert layer_data["params"]["l1"] == pytest.approx(300.0)
        assert layer_data["params"]["L1"] == pytest.approx(300.0)

    def test_update_from_foundry_preserves_snapshot_coupler_anchor_on_scalar_sync(self):
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )
        from automataii.presentation.qt.tabs.mechanism_design.tab import MechanismDesignTab

        service = MechanismInstantiationService()
        layer_data = service.create_layer_data_from_foundry(
            mechanism_type="four_bar",
            parameters={
                "ground_link": 150.0,
                "input_link": 40.0,
                "coupler_link": 120.0,
                "output_link": 130.0,
                "input_angle": 30.0,
            },
            pivot_point=(0.0, 0.0),
            part_name="torso",
            scene_position=(400.0, 300.0),
            foundry_snapshot={
                "positions": {
                    "O1": [-75.0, 0.0],
                    "O4": [75.0, 0.0],
                    "A": [-40.0, 20.0],
                    "B": [60.0, 45.0],
                    "coupler_point": [10.0, 15.0],
                }
            },
        )
        layer_data["foundry_synced"] = True
        before_key_points = {key: list(value) for key, value in layer_data["key_points"].items()}
        params = layer_data["params"]
        mapped_update = {
            "l1": params["l1"],
            "l2": params["l2"],
            "l3": params["l3"],
            "l4": params["l4"],
            "input_angle": params["input_angle"],
            "crank_angle": params["crank_angle"],
            "coupler_point_x": params["coupler_point_x"],
            "coupler_point_y": params["coupler_point_y"],
        }
        fake_tab = SimpleNamespace(
            mechanism_layers={"mech_1": layer_data},
            _suppress_foundry_sync=False,
            _mechanism_instantiation=SimpleNamespace(
                map_foundry_params_to_internal=MagicMock(return_value=mapped_update)
            ),
            _regenerate_foundry_layer_simulation=MagicMock(),
            _visual_animator=SimpleNamespace(build_cache=MagicMock()),
            _render_mechanism_layer=MagicMock(),
            mechanism_scene=SimpleNamespace(update=MagicMock()),
        )

        MechanismDesignTab.update_from_foundry(
            fake_tab,
            mechanism_id="mech_1",
            mechanism_type="four_bar",
            parameters={"input_angle": params["input_angle"]},
        )

        key_points = layer_data["key_points"]
        assert key_points["coupler_point"] == pytest.approx([400.0, 300.0])
        assert key_points["ground_pivot_1"] == pytest.approx(
            before_key_points["ground_pivot_1"], abs=1e-6
        )
        assert key_points["ground_pivot_2"] == pytest.approx(
            before_key_points["ground_pivot_2"], abs=1e-6
        )
        assert layer_data["scene_anchor"] == [400.0, 300.0]
        assert layer_data["scene_anchor_key"] == "coupler_point"

    def test_update_from_foundry_refreshes_gear_geometry_and_cache(self):
        from automataii.presentation.qt.tabs.mechanism_design.components.animation_cache import (
            AnimationCacheManager,
        )
        from automataii.presentation.qt.tabs.mechanism_design.tab import MechanismDesignTab

        layer_data = {
            "type": "gear",
            "foundry_synced": True,
            "params": {
                "gear1_teeth": 12,
                "gear2_teeth": 18,
                "r1": 36.0,
                "r2": 54.0,
                "gear1_radius": 36.0,
                "gear2_radius": 54.0,
                "gear1_x": 55.0,
                "gear1_y": 100.0,
                "gear2_x": 145.0,
                "gear2_y": 100.0,
            },
            "key_points": {
                "gear1_center": [55.0, 100.0],
                "gear2_center": [145.0, 100.0],
            },
            "full_simulation_data": {},
        }
        cache_manager = AnimationCacheManager()
        build_cache = MagicMock(side_effect=cache_manager.build_cache)
        fake_tab = SimpleNamespace(
            mechanism_layers={"gear_1": layer_data},
            _suppress_foundry_sync=False,
            _mechanism_instantiation=SimpleNamespace(
                map_foundry_params_to_internal=MagicMock(
                    return_value={
                        "gear1_teeth": 18,
                        "gear2_teeth": 12,
                        "r1": 27.0,
                        "r2": 18.0,
                        "gear1_radius": 27.0,
                        "gear2_radius": 18.0,
                    }
                )
            ),
            _visual_animator=SimpleNamespace(build_cache=build_cache),
            _render_mechanism_layer=MagicMock(),
            mechanism_scene=SimpleNamespace(update=MagicMock()),
        )
        fake_tab._regenerate_foundry_layer_simulation = (
            lambda mechanism_id, data: MechanismDesignTab._regenerate_foundry_layer_simulation(
                fake_tab, mechanism_id, data
            )
        )

        MechanismDesignTab.update_from_foundry(
            fake_tab,
            mechanism_id="gear_1",
            mechanism_type="gear_train",
            parameters={"gear1_teeth": 20, "gear2_teeth": 10},
        )

        updated_params = layer_data["params"]
        updated_key_points = layer_data["key_points"]
        assert updated_params["gear1_radius"] == pytest.approx(27.0)
        assert updated_params["gear2_radius"] == pytest.approx(18.0)
        assert updated_key_points["gear1_center"] == pytest.approx([76.5, 100.0])
        assert updated_key_points["gear2_center"] == pytest.approx([123.5, 100.0])
        assert updated_params["gear1_x"] == pytest.approx(76.5)
        assert updated_params["gear2_x"] == pytest.approx(123.5)

        gear_data = layer_data["full_simulation_data"]["gear_data"]
        assert gear_data["gear1_centers"][0] == pytest.approx([76.5, 100.0])
        assert gear_data["gear2_centers"][0] == pytest.approx([123.5, 100.0])

        cache = cache_manager.get_gear_cache("gear_1")
        assert cache is not None
        assert cache.gear1_center.tolist() == pytest.approx([76.5, 100.0])
        assert cache.gear2_center.tolist() == pytest.approx([123.5, 100.0])
        build_cache.assert_called_once_with("gear_1", layer_data)
        fake_tab._render_mechanism_layer.assert_called_once_with("gear_1")


class TestMainWindowFoundryExportRouting:
    """Test MainWindow's Foundry -> Design route failure handling."""

    @staticmethod
    def _make_window(import_result=True, import_side_effect=None):
        from automataii.presentation.qt.main_window import MainWindow

        status_bar = SimpleNamespace(showMessage=MagicMock())
        import_method = MagicMock(return_value=import_result, side_effect=import_side_effect)
        window = SimpleNamespace(
            mechanism_design_tab=SimpleNamespace(
                import_mechanism_from_foundry=import_method,
            ),
            mechanism_foundry_tab=SimpleNamespace(
                set_synced_mechanism=MagicMock(),
                clear_synced_mechanism=MagicMock(),
            ),
            statusBar=MagicMock(return_value=status_bar),
            _mark_workflow_stage_complete=MagicMock(),
            _switch_to_mechanism_design_tab=MagicMock(),
        )
        window._clear_foundry_sync_target = lambda: MainWindow._clear_foundry_sync_target(window)
        return window

    def test_failed_foundry_export_import_clears_stale_sync_target(self):
        from automataii.presentation.qt.main_window import MainWindow

        window = self._make_window(import_result=False)

        MainWindow._handle_foundry_export_to_mechanism_tab(
            window,
            mechanism_id="foundry_bad",
            mechanism_type="unknown_custom",
            parameters={},
            pivot_point=(0.0, 0.0),
        )

        window.mechanism_foundry_tab.clear_synced_mechanism.assert_called_once()
        window.mechanism_foundry_tab.set_synced_mechanism.assert_not_called()
        window._switch_to_mechanism_design_tab.assert_called_once()

    def test_exception_during_foundry_export_import_clears_stale_sync_target(self):
        from automataii.presentation.qt.main_window import MainWindow

        window = self._make_window(import_side_effect=RuntimeError("import failed"))

        MainWindow._handle_foundry_export_to_mechanism_tab(
            window,
            mechanism_id="foundry_raises",
            mechanism_type="four_bar",
            parameters={},
            pivot_point=(0.0, 0.0),
        )

        window.mechanism_foundry_tab.clear_synced_mechanism.assert_called_once()
        window.mechanism_foundry_tab.set_synced_mechanism.assert_not_called()
        window._switch_to_mechanism_design_tab.assert_called_once()

    def test_missing_foundry_import_method_clears_stale_sync_target(self):
        from automataii.presentation.qt.main_window import MainWindow

        window = self._make_window(import_result=True)
        delattr(window.mechanism_design_tab, "import_mechanism_from_foundry")

        MainWindow._handle_foundry_export_to_mechanism_tab(
            window,
            mechanism_id="foundry_missing_import",
            mechanism_type="four_bar",
            parameters={},
            pivot_point=(0.0, 0.0),
        )

        window.mechanism_foundry_tab.clear_synced_mechanism.assert_called_once()
        window.mechanism_foundry_tab.set_synced_mechanism.assert_not_called()
        window._switch_to_mechanism_design_tab.assert_called_once()

    def test_successful_foundry_export_import_registers_sync_target(self):
        from automataii.presentation.qt.main_window import MainWindow

        window = self._make_window(import_result=True)

        MainWindow._handle_foundry_export_to_mechanism_tab(
            window,
            mechanism_id="foundry_ok",
            mechanism_type="four_bar",
            parameters={"ground_link": 100.0},
            pivot_point=(0.0, 0.0),
        )

        window.mechanism_foundry_tab.set_synced_mechanism.assert_called_once_with(
            "foundry_ok",
            "four_bar",
        )
        window.mechanism_foundry_tab.clear_synced_mechanism.assert_not_called()
        window._mark_workflow_stage_complete.assert_any_call("tab_mechanism_foundry")
        window._mark_workflow_stage_complete.assert_any_call("tab_mechanism_design")
        window._switch_to_mechanism_design_tab.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
