import pytest
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    import sys
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


def test_view_instantiation(qapp):
    from automataii.ui.tabs.mechanism_foundry.foundry_view import MechanismFoundryView
    
    view = MechanismFoundryView()
    
    assert view.current_mechanism is not None
    assert view.mechanism_selector is not None
    assert view.mechanism_selector.count() > 0


def test_view_initial_four_bar_loaded(qapp):
    from automataii.ui.tabs.mechanism_foundry.foundry_view import MechanismFoundryView
    
    view = MechanismFoundryView()
    
    assert view.current_mechanism.mechanism_type == "fourbar"
    assert len(view.parameter_sliders) == 4
    assert "ground_link" in view.current_parameters
    assert "input_link" in view.current_parameters


def test_view_mechanism_switching(qapp):
    from automataii.ui.tabs.mechanism_foundry.foundry_view import MechanismFoundryView
    
    view = MechanismFoundryView()
    initial_items = len(view.scene.items())
    
    view.mechanism_selector.setCurrentIndex(1)
    view._on_mechanism_changed(1)
    
    assert view.current_mechanism.mechanism_type == "cam_follower"
    assert "cam_radius" in view.current_parameters


def test_view_animation_tick(qapp):
    from automataii.ui.tabs.mechanism_foundry.foundry_view import MechanismFoundryView
    
    view = MechanismFoundryView()
    initial_angle = view.current_angle
    
    view._on_animation_tick()
    
    assert view.current_angle == (initial_angle + 4.0) % 360.0


def test_view_rendering_creates_scene_items(qapp):
    from automataii.ui.tabs.mechanism_foundry.foundry_view import MechanismFoundryView
    
    view = MechanismFoundryView()
    
    mechanism_items = [
        item for item in view.scene.items()
        if hasattr(item, "data") and item.data(0) == "mechanism_item"
    ]
    
    assert len(mechanism_items) > 0
