from automataii.application.mechanism_foundry import (
    canonical_mechanism_type,
    is_visible_foundry_mechanism_type,
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


def test_visible_foundry_mechanism_type_hides_deferred_mechanisms():
    assert is_visible_foundry_mechanism_type("fourbar") is True
    assert is_visible_foundry_mechanism_type("cam") is True
    assert is_visible_foundry_mechanism_type("gear_train") is False
    assert is_visible_foundry_mechanism_type("planetary_gear") is False
    assert is_visible_foundry_mechanism_type("slider-crank") is False
