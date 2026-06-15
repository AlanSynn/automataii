from automataii.shared.physical_kit import (
    CAM_PRESETS,
    DEFAULT_GRID_CELL_CM,
    DEFAULT_GRID_PITCH_MM,
    DEFAULT_PHYSICAL_KIT_PROFILE,
    GEAR_PRESETS,
    GRID_PITCH_CHOICES,
    LINKAGE_LENGTH_CELLS,
    CamPreset,
    GearPreset,
    GridPitchChoice,
    PhysicalKitProfile,
    allowed_gear_teeth,
    allowed_linkage_lengths_mm,
    gear_center_distance,
    gear_radius_for_teeth,
    gear_teeth_for_radius,
    nearest_cam_preset,
    nearest_gear_radius_mm,
    physical_context_from_settings,
    physical_profile_from_key,
    snap_physical_params,
)


def test_physical_kit_default_grid_and_variant_counts() -> None:
    assert DEFAULT_GRID_PITCH_MM == 20.4
    assert DEFAULT_GRID_CELL_CM == 2.04
    assert DEFAULT_PHYSICAL_KIT_PROFILE.default_pitch_mm == DEFAULT_GRID_PITCH_MM
    assert DEFAULT_PHYSICAL_KIT_PROFILE.grid_pitch_choices == GRID_PITCH_CHOICES
    assert DEFAULT_PHYSICAL_KIT_PROFILE.linkage_length_cells == LINKAGE_LENGTH_CELLS
    assert DEFAULT_PHYSICAL_KIT_PROFILE.gear_presets == GEAR_PRESETS
    assert DEFAULT_PHYSICAL_KIT_PROFILE.cam_presets == CAM_PRESETS
    assert DEFAULT_PHYSICAL_KIT_PROFILE.gear_radius_per_tooth_mm == 3.0
    assert DEFAULT_PHYSICAL_KIT_PROFILE.default_gear_clearance_mm == 2.0
    assert {choice.key: choice.pitch_mm for choice in GRID_PITCH_CHOICES} == {
        "ms4n": 20.4,
        "2cm": 20.0,
        "2_5cm": 25.0,
    }
    assert LINKAGE_LENGTH_CELLS == (2, 4, 6, 8)
    assert len(GEAR_PRESETS) == 4
    assert len(CAM_PRESETS) == 4


def test_linkage_lengths_follow_selected_board_pitch() -> None:
    assert allowed_linkage_lengths_mm(2.0) == (40.0, 80.0, 120.0, 160.0)
    assert allowed_linkage_lengths_mm(2.5) == (50.0, 100.0, 150.0, 200.0)


def test_physical_context_uses_supported_pitch_presets_when_enabled() -> None:
    context = physical_context_from_settings(True, 2.31)

    assert context.enabled is True
    assert context.grid_pitch_choice == "2_5cm"
    assert context.grid_cell_cm == 2.5
    assert context.as_params()["physical_profile_key"] == DEFAULT_PHYSICAL_KIT_PROFILE.key


def test_unknown_physical_profile_key_warns_before_defaulting(caplog) -> None:
    profile = physical_profile_from_key("missing-kit")

    assert profile == DEFAULT_PHYSICAL_KIT_PROFILE
    assert "Unknown physical kit profile key 'missing-kit'" in caplog.text


def test_gear_presets_are_limited_and_radius_backed() -> None:
    assert allowed_gear_teeth() == (16, 20, 24, 32)
    assert gear_radius_for_teeth(16) == 48.0
    assert gear_radius_for_teeth(24) == 72.0
    assert gear_teeth_for_radius(75.0) == 24
    assert nearest_gear_radius_mm(75.0) == 72.0


def test_helpers_accept_explicit_physical_profile_variants() -> None:
    variant = PhysicalKitProfile(
        key="test-kit",
        label="Test kit",
        default_pitch_mm=30.0,
        grid_pitch_choices=(GridPitchChoice("3cm", "3.0 cm board", 30.0),),
        linkage_length_cells=(1, 3),
        gear_presets=(GearPreset("g10", "G10", 10), GearPreset("g14", "G14", 14)),
        cam_presets=(
            CamPreset("test", "Test cam", 1.0, 0.0, 1, 0.0, 90.0, 90.0, 90.0),
        ),
        gear_radius_per_tooth_mm=2.0,
        default_gear_clearance_mm=5.0,
    )

    assert allowed_linkage_lengths_mm(3.0, profile=variant) == (30.0, 90.0)
    assert allowed_gear_teeth(profile=variant) == (10, 14)
    assert gear_radius_for_teeth(14, profile=variant) == 28.0

    snapped = snap_physical_params(
        "gear_train",
        {"gear1_teeth": 13, "gear2_teeth": 9},
        profile=variant,
    )

    assert snapped["gear1_teeth"] == 14
    assert snapped["gear2_teeth"] == 10
    assert snapped["gear1_radius"] == 28.0
    assert snapped["gear2_radius"] == 20.0
    assert snapped["gear_clearance"] == 5.0


def test_single_gear_preset_profile_does_not_crash_center_distance() -> None:
    single_gear_profile = PhysicalKitProfile(
        key="one-gear-kit",
        label="One gear kit",
        default_pitch_mm=20.0,
        grid_pitch_choices=(GridPitchChoice("2cm", "2.0 cm board", 20.0),),
        linkage_length_cells=(2,),
        gear_presets=(GearPreset("g12", "G12", 12),),
        cam_presets=(
            CamPreset("circle", "Circle", 1.0, 0.0, 1, 0.0, 90.0, 90.0, 90.0),
        ),
        gear_radius_per_tooth_mm=2.5,
        default_gear_clearance_mm=4.0,
    )

    assert allowed_gear_teeth(profile=single_gear_profile) == (12,)
    assert gear_center_distance(None, None, profile=single_gear_profile) == 64.0


def test_gear_snapping_preserves_physical_pair_contract() -> None:
    snapped_from_teeth = snap_physical_params(
        "gear_train",
        {"gear1_teeth": "12", "gear2_teeth": "18"},
    )
    assert snapped_from_teeth["gear1_teeth"] == 16
    assert snapped_from_teeth["gear2_teeth"] == 20
    assert snapped_from_teeth["gear1_radius"] == 48.0
    assert snapped_from_teeth["gear2_radius"] == 60.0

    snapped_from_radii = snap_physical_params(
        "gear_train",
        {"gear1_radius": 45.0, "gear2_radius": 75.0},
    )
    assert snapped_from_radii["gear1_teeth"] == 16
    assert snapped_from_radii["gear2_teeth"] == 24
    assert snapped_from_radii["r1"] == 48.0
    assert snapped_from_radii["r2"] == 72.0


def test_linkage_and_cam_snapping_use_board_pitch() -> None:
    linkage = snap_physical_params(
        "four_bar",
        {"l1": 62.0, "l2": 118.0, "l3": 173.0, "l4": 220.0},
        2.5,
    )
    assert (linkage["l1"], linkage["l2"], linkage["l3"], linkage["l4"]) == (
        50.0,
        100.0,
        150.0,
        200.0,
    )
    assert (linkage["L1"], linkage["L2"], linkage["L3"], linkage["L4"]) == (
        50.0,
        100.0,
        150.0,
        200.0,
    )

    cam = snap_physical_params(
        "cam_follower",
        {"base_radius": 52.0, "eccentricity": 24.0, "cam_lobes": 1},
        2.5,
    )
    assert cam["physical_cam_preset"] == nearest_cam_preset(cam, 2.5).key
    assert cam["base_radius"] in {preset.params_mm(2.5)["base_radius"] for preset in CAM_PRESETS}
    assert cam["eccentricity"] in {
        preset.params_mm(2.5)["eccentricity"] for preset in CAM_PRESETS
    }
    assert {"rise_deg", "high_dwell_deg", "return_deg"}.issubset(cam)
