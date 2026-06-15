from automataii.application.mechanism_foundry import (
    canonical_mechanism_type,
    is_visible_foundry_mechanism_type,
)
from automataii.application.mechanism_foundry.controller import (
    MechanismFoundryController,
    build_mechanism_configs,
)
from automataii.shared.physical_kit import (
    CamPreset,
    GearPreset,
    GridPitchChoice,
    PhysicalKitProfile,
)


def test_canonical_mechanism_type_normalizes_foundry_aliases():
    assert canonical_mechanism_type(" fourbar ") == "four_bar"
    assert canonical_mechanism_type("four_bar_linkage") == "four_bar"
    assert canonical_mechanism_type("4_bar_linkage") == "four_bar"
    assert canonical_mechanism_type(" CAM ") == "cam_follower"
    assert canonical_mechanism_type("gear") == "gear_train"
    assert canonical_mechanism_type("planetary_gear") == "gear_train"
    assert canonical_mechanism_type("slider-crank") == "slider_crank"


def test_canonical_mechanism_type_passes_unknown_keys_through():
    assert canonical_mechanism_type(" custom_mechanism ") == "custom_mechanism"


def test_visible_foundry_mechanism_type_exposes_physical_kit_mechanisms():
    assert is_visible_foundry_mechanism_type("fourbar") is True
    assert is_visible_foundry_mechanism_type("cam") is True
    assert is_visible_foundry_mechanism_type("gear_train") is True
    assert is_visible_foundry_mechanism_type("planetary_gear") is True
    assert is_visible_foundry_mechanism_type("slider-crank") is False


def test_foundry_controller_builds_configs_from_selected_grid_pitch():
    configs = build_mechanism_configs(grid_cell_cm=2.5)
    four_bar = configs["four_bar"].initial_parameters()

    assert four_bar["input_link"] == 50.0
    assert four_bar["ground_link"] == 200.0

    controller = MechanismFoundryController(grid_cell_cm=2.5)
    controller_params = controller.initial_parameters("four_bar")

    assert controller_params["input_link"] == 50.0
    assert controller_params["ground_link"] == 200.0


def test_foundry_configs_tolerate_smaller_explicit_profile_shapes():
    profile = PhysicalKitProfile(
        key="small-test-kit",
        label="Small test kit",
        default_pitch_mm=30.0,
        grid_pitch_choices=(GridPitchChoice("3cm", "3.0 cm board", 30.0),),
        linkage_length_cells=(1, 3),
        gear_presets=(GearPreset("g10", "G10", 10), GearPreset("g14", "G14", 14)),
        cam_presets=(CamPreset("circle", "Circle", 1.0, 0.0, 1, 0.0, 90, 90, 90),),
        gear_radius_per_tooth_mm=2.0,
        default_gear_clearance_mm=5.0,
    )

    configs = build_mechanism_configs(profile=profile, grid_cell_cm=3.0)

    assert configs["four_bar"].initial_parameters()["ground_link"] == 90.0
    assert configs["four_bar"].initial_parameters()["input_link"] == 30.0
    assert configs["gear_train"].initial_parameters()["gear1_teeth"] == 10
    assert configs["gear_train"].initial_parameters()["gear2_teeth"] == 14
    assert configs["cam_follower"].initial_parameters()["cam_radius"] == 30.0
