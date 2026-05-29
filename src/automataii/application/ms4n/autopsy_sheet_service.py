"""Markdown autopsy-sheet rendering for Lab facilitation records."""

from __future__ import annotations

from automataii.domain.ms4n import BreakdownRepairEpisode


class AutopsySheetService:
    """Render one compact human-readable sheet per breakdown/repair episode."""

    def render_markdown(self, episode: BreakdownRepairEpisode) -> str:
        symptom = (
            episode.breakdown_events[0].symptom if episode.breakdown_events else "not-recorded"
        )
        causes = (
            ", ".join(episode.breakdown_events[0].suspected_causes)
            if episode.breakdown_events
            else "not-recorded"
        )
        repair = episode.repair_actions[0].action_type if episode.repair_actions else "not-recorded"
        explanation = episode.learner_explanation.text or (
            f"Absent: {episode.learner_explanation.absence_note}"
            if episode.learner_explanation.absence_note
            else "not-recorded"
        )
        facilitator = (
            "; ".join(f"{move.move_type}: {move.note}" for move in episode.facilitator_moves)
            or "not-recorded"
        )
        return "\n".join(
            [
                f"# Motion Autopsy: {episode.episode_id}",
                "",
                f"- Status: {episode.status}",
                f"- Mechanism: {episode.mechanism_type} ({episode.mechanism_id})",
                f"- Part: {episode.part_name}",
                f"- Breakdown symptom: {symptom}",
                f"- Suspected causes: {causes}",
                f"- Repair action: {repair}",
                f"- Learner explanation: {explanation}",
                f"- Facilitator moves: {facilitator}",
                f"- Change count: {episode.change_count}",
                f"- Repair count: {episode.repair_count}",
                f"- Trace delta: {episode.trace_delta_summary}",
                "",
            ]
        )
