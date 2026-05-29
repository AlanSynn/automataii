from automataii.domain.ms4n import (
    BreakdownEvent,
    BreakdownRepairEpisode,
    FacilitatorMove,
    LearnerExplanation,
    MechanicalChange,
    MechanismStateSnapshot,
    RepairAction,
)
from automataii.domain.ms4n.trace import summarize_trace


def make_snapshot(snapshot_id="before", points=None):
    if points is None:
        points = ((0, 0.0, 0.0), (1, 3.0, 4.0))
    return MechanismStateSnapshot(
        snapshot_id=snapshot_id,
        mechanism_id="mech_1",
        mechanism_type="4_bar_linkage",
        part_name="arm",
        parameters={"bar_length": 120.0},
        key_points={"pivot": (0.0, 0.0)},
        trace_points=tuple(points),
        trace_summary=summarize_trace(tuple(points)),
    )


def make_episode(status="repaired"):
    before = make_snapshot("before")
    after = make_snapshot("after", ((0, 0.0, 0.0), (1, 5.0, 0.0)))
    return BreakdownRepairEpisode(
        episode_id="ep_001",
        session_id="session_fake_001",
        participant_hash="p_hash_fake",
        mechanism_id="mech_1",
        mechanism_type="4_bar_linkage",
        part_name="arm",
        kit_asset_ids=("bar-board", "ms4n-01-linkage-bars"),
        status=status,
        before_snapshot=before,
        breakdown_events=(BreakdownEvent("jam", ("pivot_spacing",)),),
        primary_changes=(MechanicalChange("move_pivot", "pivot", [0.0, 0.0], [10.0, 0.0]),),
        repair_actions=(RepairAction("move_pivot", "pivot", [0.0, 0.0], [10.0, 0.0]),),
        after_snapshot=after,
        learner_explanation=LearnerExplanation("Moving the pivot changed the arm swing."),
        facilitator_moves=(
            FacilitatorMove("predict_observe_explain", "Asked learner to compare traces."),
        ),
    )
