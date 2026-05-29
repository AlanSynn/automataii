from types import SimpleNamespace

from PyQt6.QtCore import QPointF

from automataii.presentation.qt.tabs.mechanism_design.ms4n_snapshot_adapter import (
    MS4NSnapshotAdapter,
    build_snapshot_from_source,
)
from automataii.presentation.qt.tabs.mechanism_design.tab import MechanismDesignTab


class FakeSource:
    def __init__(self):
        self.calls = []

    def get_ms4n_snapshot_source(self, mechanism_id=None):
        self.calls.append(mechanism_id)
        return {
            "mechanism_id": mechanism_id or "mech_1",
            "mechanism_type": "4_bar_linkage",
            "part_name": "arm",
            "parameters": {"bar_length": 120.0},
            "key_points": {"pivot": [1.0, 2.0]},
            "trace_points": [[0.0, 0.0], [1.0, 1.0]],
            "coordinate_space": "scene",
        }


def test_adapter_consumes_public_snapshot_source_contract():
    fake = FakeSource()
    snapshot = MS4NSnapshotAdapter().capture(fake, mechanism_id="mech_public", snapshot_id="snap_1")
    assert fake.calls == ["mech_public"]
    assert snapshot.mechanism_id == "mech_public"


def test_adapter_returns_json_safe_snapshot():
    snapshot = MS4NSnapshotAdapter().capture(FakeSource(), snapshot_id="snap_1")
    payload = snapshot.to_dict()
    assert payload["key_points"]["pivot"] == [1.0, 2.0]
    assert payload["trace_points"] == [[0, 0.0, 0.0], [1, 1.0, 1.0]]
    assert all(type(point).__name__ != "QPointF" for point in payload["trace_points"])


def test_public_mechanism_design_snapshot_source_returns_plain_points():
    class FakeTraceManager:
        def get_trace_points(self, mechanism_id):
            assert mechanism_id == "mech_1"
            return [QPointF(0.0, 0.0), QPointF(1.0, 1.0)]

    tab_like = SimpleNamespace(
        mechanism_layers={
            "mech_1": {
                "type": "4_bar_linkage",
                "part_name": "arm",
                "params": {"bar_length": 120.0},
                "key_points": {"pivot": QPointF(1.0, 2.0)},
            }
        },
        mechanism_params={},
        current_mechanism_type="",
        selected_part_name="",
        _path_trace_manager=FakeTraceManager(),
    )
    source = MechanismDesignTab.get_ms4n_snapshot_source(tab_like, "mech_1")
    assert source["key_points"]["pivot"] == (1.0, 2.0)
    assert source["trace_points"] == [(0.0, 0.0), (1.0, 1.0)]
    assert all(type(point).__name__ != "QPointF" for point in source["trace_points"])


def test_adapter_rejects_malformed_trace_points_source():
    source = {
        "mechanism_id": "mech_1",
        "mechanism_type": "4_bar_linkage",
        "part_name": "arm",
        "trace_points": object(),
    }
    try:
        build_snapshot_from_source(source, snapshot_id="snap_1")
    except TypeError as exc:
        assert "trace_points" in str(exc)
    else:
        raise AssertionError("Malformed trace_points source should be rejected")
