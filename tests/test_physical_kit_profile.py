from pytest import LogCaptureFixture

from automataii.shared.physical_kit import (
    CAM_PRESETS,
    DEFAULT_BOARD_COLUMNS,
    DEFAULT_BOARD_ROWS,
    DEFAULT_GRID_CELL_CM,
    DEFAULT_GRID_PITCH_MM,
    DEFAULT_HOLE_DIAMETER_MM,
    DEFAULT_PHYSICAL_KIT_PROFILE,
    FOLLOWER_PRESETS,
    GEAR_PRESETS,
    GRID_PITCH_CHOICES,
    LINKAGE_LENGTH_CELLS,
    CamPreset,
    GearPreset,
    GridPitchChoice,
    PhysicalKitProfile,
    allowed_gear_teeth,
    allowed_linkage_lengths_mm,
    fabrication_ready_params,
    gear_attachment_grid_offsets_mm,
    gear_attachment_radii_mm,
    gear_center_distance,
    gear_radius_for_teeth,
    gear_teeth_for_radius,
    nearest_cam_preset,
    nearest_gear_radius_mm,
    physical_context_from_settings,
    physical_kit_preset_summary,
    physical_profile_from_key,
    snap_physical_params,
)


def test_physical_kit_default_grid_and_variant_counts() -> None:
    assert DEFAULT_GRID_PITCH_MM == 20.0
    assert DEFAULT_GRID_CELL_CM == 2.0
    assert DEFAULT_HOLE_DIAMETER_MM == 4.0
    assert DEFAULT_BOARD_ROWS == 15
    assert DEFAULT_BOARD_COLUMNS == 15
    assert DEFAULT_PHYSICAL_KIT_PROFILE.default_pitch_mm == DEFAULT_GRID_PITCH_MM
    assert DEFAULT_PHYSICAL_KIT_PROFILE.hole_diameter_mm == DEFAULT_HOLE_DIAMETER_MM
    assert DEFAULT_PHYSICAL_KIT_PROFILE.board_rows == DEFAULT_BOARD_ROWS
    assert DEFAULT_PHYSICAL_KIT_PROFILE.board_columns == DEFAULT_BOARD_COLUMNS
    assert DEFAULT_PHYSICAL_KIT_PROFILE.grid_pitch_choices == GRID_PITCH_CHOICES
    assert DEFAULT_PHYSICAL_KIT_PROFILE.linkage_length_cells == LINKAGE_LENGTH_CELLS
    assert DEFAULT_PHYSICAL_KIT_PROFILE.gear_presets == GEAR_PRESETS
    assert DEFAULT_PHYSICAL_KIT_PROFILE.cam_presets == CAM_PRESETS
    assert DEFAULT_PHYSICAL_KIT_PROFILE.follower_presets == FOLLOWER_PRESETS
    assert DEFAULT_PHYSICAL_KIT_PROFILE.gear_radius_per_tooth_mm == 1.25
    assert DEFAULT_PHYSICAL_KIT_PROFILE.default_gear_clearance_mm == 0.0
    assert {choice.key: choice.pitch_mm for choice in GRID_PITCH_CHOICES} == {
        "2cm": 20.0,
        "ms4n": 20.4,
        "2_5cm": 25.0,
    }
    assert LINKAGE_LENGTH_CELLS == (2, 4, 6, 8)
    assert len(GEAR_PRESETS) == 4
    assert len(CAM_PRESETS) == 4
    assert len(FOLLOWER_PRESETS) == 4
    assert {preset.contact_style for preset in FOLLOWER_PRESETS} == {
        "round_nose",
        "roller_pin",
        "flat_shoe",
        "linkage_output",
    }
    assert tuple(preset.body_cells for preset in FOLLOWER_PRESETS) == (3, 4, 5, 6)
    assert tuple(preset.guide_slot_travel_cells for preset in FOLLOWER_PRESETS) == (
        1.0,
        1.0,
        1.25,
        1.5,
    )


def test_linkage_lengths_follow_selected_board_pitch() -> None:
    assert allowed_linkage_lengths_mm(2.0) == (40.0, 80.0, 120.0, 160.0)
    assert allowed_linkage_lengths_mm(2.5) == (50.0, 100.0, 150.0, 200.0)


def test_physical_context_uses_supported_pitch_presets_when_enabled() -> None:
    context = physical_context_from_settings(True, 2.31)

    assert context.enabled is True
    assert context.grid_pitch_choice == "2_5cm"
    assert context.grid_cell_cm == 2.5
    assert context.as_params()["physical_profile_key"] == DEFAULT_PHYSICAL_KIT_PROFILE.key
    assert context.as_params()["hole_diameter_mm"] == DEFAULT_HOLE_DIAMETER_MM
    assert context.as_params()["board_rows"] == DEFAULT_BOARD_ROWS
    assert context.as_params()["board_columns"] == DEFAULT_BOARD_COLUMNS


def test_unknown_physical_profile_key_warns_before_defaulting(
    caplog: LogCaptureFixture,
) -> None:
    profile = physical_profile_from_key("missing-kit")

    assert profile == DEFAULT_PHYSICAL_KIT_PROFILE
    assert "Unknown physical kit profile key 'missing-kit'" in caplog.text


def test_gear_presets_are_limited_and_radius_backed() -> None:
    assert allowed_gear_teeth() == (8, 24, 40, 56)
    assert tuple(preset.label for preset in GEAR_PRESETS) == (
        "G1 / 1-space gear",
        "G3 / 3-space gear",
        "G5 / 5-space gear",
        "G7 / 7-space gear",
    )
    assert gear_radius_for_teeth(8) == 10.0
    assert gear_radius_for_teeth(56) == 70.0
    assert gear_teeth_for_radius(45.0) == 40
    assert nearest_gear_radius_mm(45.0) == 50.0
    for first in GEAR_PRESETS:
        for second in GEAR_PRESETS:
            center_distance = gear_center_distance(first.radius_mm, second.radius_mm)
            assert center_distance % DEFAULT_GRID_PITCH_MM == 0.0


def test_helpers_accept_explicit_physical_profile_variants() -> None:
    variant = PhysicalKitProfile(
        key="test-kit",
        label="Test kit",
        default_pitch_mm=30.0,
        grid_pitch_choices=(GridPitchChoice("3cm", "3.0 cm board", 30.0),),
        linkage_length_cells=(1, 3),
        gear_presets=(GearPreset("g10", "G10", 10), GearPreset("g14", "G14", 14)),
        cam_presets=(CamPreset("test", "Test cam", 1.0, 0.0, 1, 0.0, 90.0, 90.0, 90.0),),
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
        cam_presets=(CamPreset("circle", "Circle", 1.0, 0.0, 1, 0.0, 90.0, 90.0, 90.0),),
        gear_radius_per_tooth_mm=2.5,
        default_gear_clearance_mm=4.0,
    )

    assert allowed_gear_teeth(profile=single_gear_profile) == (12,)
    assert gear_center_distance(None, None, profile=single_gear_profile) == 64.0


def test_gear_snapping_preserves_physical_pair_contract() -> None:
    snapped_from_teeth = snap_physical_params(
        "gear_train",
        {"gear1_teeth": "8", "gear2_teeth": "56"},
    )
    assert snapped_from_teeth["gear1_teeth"] == 8
    assert snapped_from_teeth["gear2_teeth"] == 56
    assert snapped_from_teeth["gear1_radius"] == 10.0
    assert snapped_from_teeth["gear2_radius"] == 70.0

    snapped_from_radii = snap_physical_params(
        "gear_train",
        {"gear1_radius": 45.0, "gear2_radius": 75.0},
    )
    assert snapped_from_radii["gear1_teeth"] == 40
    assert snapped_from_radii["gear2_teeth"] == 56
    assert snapped_from_radii["r1"] == 50.0
    assert snapped_from_radii["r2"] == 70.0


def test_gear_linkage_and_planetary_snap_to_fabricated_linkage_lengths() -> None:
    gear_linkage = snap_physical_params(
        "gear_linkage",
        {
            "gear1_teeth": 13,
            "gear2_teeth": 47,
            "linkage_arm_length": 93.0,
            "linkage_pin_radius": 37.0,
        },
        2.0,
    )
    assert gear_linkage["gear1_teeth"] == 8
    assert gear_linkage["gear2_teeth"] == 40
    assert gear_linkage["linkage_arm_length"] == 80.0
    assert gear_linkage["linkage_pin_radius"] in gear_attachment_radii_mm(
        gear_linkage["gear2_radius"],
        2.0,
    )

    planetary = snap_physical_params(
        "planetary_gear",
        {
            "sun_teeth": 13,
            "planet_teeth": 47,
            "planet_count": 0,
            "carrier_arm_length": 131.0,
        },
        2.5,
    )
    assert planetary["sun_teeth"] == 8
    assert planetary["planet_teeth"] == 24
    assert planetary["planet_count"] == 1
    assert planetary["carrier_arm_length"] == 150.0
    assert planetary["arm_length"] == 150.0
    assert planetary["physical_ring_gear"] == "ring-g8-g24"


def test_gear_linkage_pin_snaps_to_fabricated_attachment_holes() -> None:
    snapped = snap_physical_params(
        "gear_linkage",
        {"gear1_teeth": 24, "gear2_teeth": 24, "linkage_pin_radius": 7.0},
        2.0,
    )

    assert snapped["gear2_teeth"] == 24
    assert snapped["linkage_pin_radius"] == 20.0
    assert snapped["linkage_pin_radius"] in gear_attachment_radii_mm(
        snapped["gear2_radius"],
        2.0,
    )


def test_planetary_snapping_stays_on_fabricated_ring_recipe() -> None:
    snapped = snap_physical_params(
        "planetary_gear",
        {"sun_teeth": 56, "planet_teeth": 40, "planet_count": 4},
        2.0,
    )

    assert snapped["sun_teeth"] == 8
    assert snapped["planet_teeth"] == 24
    assert snapped["r_sun"] == 10.0
    assert snapped["r_planet"] == 30.0
    assert snapped["physical_ring_gear"] == "ring-g8-g24"


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
    assert cam["eccentricity"] in {preset.params_mm(2.5)["eccentricity"] for preset in CAM_PRESETS}
    assert {"rise_deg", "high_dwell_deg", "return_deg"}.issubset(cam)


def test_fabrication_ready_params_adds_context_and_snaps_missing_ui_payloads() -> None:
    ready = fabrication_ready_params(
        "four_bar",
        {"l1": 45.1, "l2": 11.8, "l3": 80.2, "l4": 60.6},
    )

    assert ready["grid_system_enabled"] is True
    assert ready["grid_cell_cm"] == DEFAULT_GRID_CELL_CM
    assert ready["physical_profile_key"] == DEFAULT_PHYSICAL_KIT_PROFILE.key
    assert ready["hole_diameter_mm"] == DEFAULT_HOLE_DIAMETER_MM
    assert ready["fabrication_ready_preset_mode"] is True
    assert (ready["l1"], ready["l2"], ready["l3"], ready["l4"]) == (
        40.0,
        40.0,
        80.0,
        80.0,
    )


def test_fabrication_ready_params_preserves_explicit_custom_mode() -> None:
    ready = fabrication_ready_params(
        "gear_train",
        {"gear1_teeth": 13, "gear2_teeth": 17, "grid_system_enabled": False},
    )

    assert ready["grid_system_enabled"] is False
    assert ready["fabrication_ready_preset_mode"] is False
    assert ready["gear1_teeth"] == 13
    assert ready["gear2_teeth"] == 17


def test_physical_kit_summary_names_enforced_part_contract() -> None:
    assert physical_kit_preset_summary() == "G1/G3/G5/G7 gears + S10 spacer + 4 mm holes"


def test_gear_attachment_grid_offsets_match_fabrication_scale() -> None:
    offsets_by_radius = {
        10.0: gear_attachment_grid_offsets_mm(10.0),
        30.0: gear_attachment_grid_offsets_mm(30.0),
        50.0: gear_attachment_grid_offsets_mm(50.0),
        70.0: gear_attachment_grid_offsets_mm(70.0),
    }

    assert {radius: len(offsets) for radius, offsets in offsets_by_radius.items()} == {
        10.0: 0,
        30.0: 4,
        50.0: 12,
        70.0: 28,
    }
    for offsets in offsets_by_radius.values():
        for dx, dy in offsets:
            assert dx % DEFAULT_GRID_PITCH_MM == 0.0
            assert dy % DEFAULT_GRID_PITCH_MM == 0.0
            assert (dx, dy) != (0.0, 0.0)
