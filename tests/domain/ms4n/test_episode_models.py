import json
from dataclasses import replace

from ms4n_helpers import make_episode

from automataii.domain.ms4n import LearnerExplanation, MechanicalChange, RepairAction
from automataii.domain.ms4n.episodes import MechanismStateSnapshot


def test_breakdown_episode_to_dict_is_json_safe():
    episode = make_episode()
    payload = episode.to_dict()
    json.dumps(payload, allow_nan=False)
    assert payload["schema_version"] == "ms4n.episode.v1"
    assert payload["episode_id"] == "ep_001"
    assert payload["session_id"] == "session_fake_001"
    assert payload["participant_hash"] == "p_hash_fake"
    assert payload["kit_asset_ids"] == ["bar-board", "ms4n-01-linkage-bars"]


def test_repaired_episode_requires_before_repair_after_and_explanation_or_absence_note():
    episode = make_episode()
    for candidate in (
        replace(episode, before_snapshot=None),
        replace(episode, repair_actions=()),
        replace(episode, after_snapshot=None),
        replace(episode, learner_explanation=LearnerExplanation()),
    ):
        result = candidate.validate_for_p0()
        assert result.is_valid is False


def test_unresolved_episode_allows_missing_repair_but_records_status():
    episode = replace(make_episode("unresolved"), repair_actions=(), after_snapshot=None)
    result = episode.validate_for_p0()
    assert result.is_valid is True
    assert episode.to_dict()["status"] == "unresolved"


def test_abandoned_episode_remains_exportable_without_claiming_repair():
    episode = replace(make_episode("abandoned"), repair_actions=(), after_snapshot=None)
    result = episode.validate_for_p0()
    assert result.is_valid is True
    assert episode.to_dict()["status"] == "abandoned"


def test_repaired_episode_rejects_more_than_one_primary_change():
    episode = make_episode()
    extra = MechanicalChange("swap_hole", "bar", "hole_1", "hole_2")
    candidate = replace(episode, primary_changes=(*episode.primary_changes, extra))
    result = candidate.validate_for_p0()
    assert result.is_valid is False
    assert "one primary change" in "; ".join(result.errors)


def test_repaired_episode_rejects_more_than_one_primary_repair():
    episode = make_episode()
    extra = RepairAction("realign_part", "arm", "left", "center")
    candidate = replace(episode, repair_actions=(*episode.repair_actions, extra))
    result = candidate.validate_for_p0()
    assert result.is_valid is False


def test_multi_change_episode_requires_constraint_violation_note_and_unresolved_status():
    episode = make_episode()
    extra = MechanicalChange("swap_hole", "bar", "hole_1", "hole_2")
    candidate = replace(
        episode, status="unresolved", primary_changes=(*episode.primary_changes, extra)
    )
    assert candidate.validate_for_p0().is_valid is False
    with_note = replace(
        candidate, constraint_violation_note="Two changes occurred before facilitator stopped."
    )
    assert with_note.validate_for_p0().is_valid is True


def test_snapshot_from_dict_rejects_malformed_trace_points_without_silent_filtering():
    payload = {
        "snapshot_id": "bad",
        "mechanism_id": "mech_1",
        "mechanism_type": "4_bar_linkage",
        "part_name": "arm",
        "trace_points": [[0, 0.0, 0.0], ["bad"]],
    }
    try:
        MechanismStateSnapshot.from_dict(payload)
    except ValueError as exc:
        assert "trace point" in str(exc)
    else:
        raise AssertionError("Malformed trace point should be rejected")
