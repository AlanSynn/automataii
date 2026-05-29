from automataii.application.ms4n import EpisodeService
from automataii.domain.ms4n import BreakdownEvent, FacilitatorMove, MechanicalChange, RepairAction


def test_episode_service_creates_open_draft_with_fake_research_ids():
    service = EpisodeService()
    episode = service.start_episode(
        episode_id="ep_001",
        session_id="session_fake_001",
        participant_hash="p_hash_fake",
        mechanism_id="mech_1",
        mechanism_type="4_bar_linkage",
        part_name="arm",
        kit_asset_ids=("bar-board",),
    )
    payload = episode.to_dict()
    assert episode.status == "open"
    assert payload["participant_hash"] == "p_hash_fake"
    assert "participant_name" not in payload
    assert "email" not in payload


def test_episode_service_completes_repaired_lifecycle():
    service = EpisodeService()
    episode = service.start_episode(
        episode_id="ep_001",
        session_id="session_fake_001",
        participant_hash="p_hash_fake",
        mechanism_id="mech_1",
        mechanism_type="4_bar_linkage",
        part_name="arm",
        kit_asset_ids=("bar-board",),
    )
    before = service.make_snapshot(
        snapshot_id="before",
        mechanism_id="mech_1",
        mechanism_type="4_bar_linkage",
        part_name="arm",
        trace_points=((0, 0.0, 0.0), (1, 1.0, 0.0)),
    )
    after = service.make_snapshot(
        snapshot_id="after",
        mechanism_id="mech_1",
        mechanism_type="4_bar_linkage",
        part_name="arm",
        trace_points=((0, 0.0, 0.0), (1, 2.0, 0.0)),
    )
    episode = service.attach_before(episode, before)
    episode = service.record_breakdown(episode, BreakdownEvent("jam", ("pivot_spacing",)))
    episode = service.record_primary_change(
        episode, MechanicalChange("move_pivot", "pivot", [0, 0], [2, 0])
    )
    episode = service.record_repair(episode, RepairAction("move_pivot", "pivot", [0, 0], [2, 0]))
    episode = service.attach_after(episode, after)
    episode = service.save_explanation(episode, text="Pivot changed the swing.")
    episode = service.add_facilitator_move(
        episode, FacilitatorMove("trace_comparison", "Compared before/after.")
    )
    repaired = service.mark_repaired(episode)
    assert repaired.status == "repaired"
    assert repaired.change_count == 1
    assert repaired.repair_count == 1
    assert repaired.learner_explanation.is_present is True


def test_episode_service_keeps_incomplete_episode_open():
    service = EpisodeService()
    episode = service.start_episode(
        episode_id="ep_001",
        session_id="session_fake_001",
        participant_hash="p_hash_fake",
        mechanism_id="mech_1",
        mechanism_type="4_bar_linkage",
        part_name="arm",
        kit_asset_ids=("bar-board",),
    )
    assert episode.status == "open"
    assert episode.validate_for_p0().is_valid is True
