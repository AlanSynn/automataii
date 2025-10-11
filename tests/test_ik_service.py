from __future__ import annotations

from automataii.application.kinematics import IKService


def test_update_skeleton_sets_state():
    service = IKService()
    service.update_skeleton({"joint_map": {}})
    assert service.state.skeleton_data == {"joint_map": {}}


def test_animation_controls():
    service = IKService()
    service.set_animation_duration(5000)
    assert service.state.animation_duration_ms == 5000
    service.set_timing_profile("ease_in")
    assert service.state.timing_profile == "ease_in"
    service.start_animation()
    service.tick_animation(0.25)
    assert service.state.animation_running is True
    assert service.state.animation_time == 0.25
    service.reset_animation()
    assert service.state.animation_running is False
    assert service.state.animation_time == 0.0


def test_mechanism_targets():
    service = IKService()
    service.set_mechanism_target("arm", (10, 20))
    assert service.state.mechanism_targets["arm"] == (10.0, 20.0)
    service.clear_mechanism_target("arm")
    assert "arm" not in service.state.mechanism_targets
