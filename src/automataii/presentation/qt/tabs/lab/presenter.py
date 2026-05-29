"""Presenter for the user-facing Lab tab."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from automataii.application.ms4n import EpisodeService, ExportService, KitCatalogService
from automataii.domain.ms4n import BreakdownRepairEpisode
from automataii.presentation.qt.tabs.lab.view_protocol import LabViewProtocol


class LabPresenter:
    """Thin UI presenter; backend package names remain MS4N while labels say Lab."""

    def __init__(
        self,
        view: LabViewProtocol,
        *,
        kit_catalog_service: KitCatalogService | None = None,
        episode_service: EpisodeService | None = None,
        export_service: ExportService | None = None,
    ) -> None:
        self._view = view
        self._kit_catalog_service = kit_catalog_service or KitCatalogService()
        self._episode_service = episode_service or EpisodeService()
        self._export_service = export_service or ExportService()
        self._episodes: list[BreakdownRepairEpisode] = []
        self._current_episode: BreakdownRepairEpisode | None = None

    @property
    def current_episode(self) -> BreakdownRepairEpisode | None:
        return self._current_episode

    @property
    def episodes(self) -> tuple[BreakdownRepairEpisode, ...]:
        return tuple(self._episodes)

    def load_manifest(self, manifest_path: Path, *, pilot_priority: str = "P0") -> None:
        self._kit_catalog_service.load(manifest_path)
        self._view.set_kit_assets(self._kit_catalog_service.list_assets(pilot_priority))
        self._view.show_lab_message("Lab kit assets loaded")

    def set_episodes(self, episodes: Sequence[BreakdownRepairEpisode]) -> None:
        self._episodes = list(episodes)
        self._current_episode = self._episodes[-1] if self._episodes else None
        self._refresh_episode_views()

    def set_current_episode(self, episode: BreakdownRepairEpisode) -> None:
        self._current_episode = episode
        for index, existing in enumerate(self._episodes):
            if existing.episode_id == episode.episode_id:
                self._episodes[index] = episode
                break
        else:
            self._episodes.append(episode)
        self._refresh_episode_views()

    def save_explanation(self, text: str, *, absence_note: str = "") -> None:
        if self._current_episode is None:
            self._view.show_lab_message("No active Lab episode")
            return
        updated = self._episode_service.save_explanation(
            self._current_episode,
            text=text,
            absence_note=absence_note,
        )
        self.set_current_episode(updated)

    def export_bundle(self, output_dir: Path) -> None:
        result = self._export_service.export_bundle(tuple(self._episodes), output_dir)
        self._view.show_export_result(result)

    def _refresh_episode_views(self) -> None:
        if self._current_episode is None:
            self._view.set_motion_autopsy_rows(())
            self._view.set_trace_duel_summary({"available": False})
            return
        summary = self._episode_service.to_summary_view_model(self._current_episode)
        self._view.set_episode_summary(summary)
        self._view.set_trace_duel_summary(self._current_episode.trace_delta_summary)
        self._view.set_motion_autopsy_rows(
            (
                {
                    "episode_id": self._current_episode.episode_id,
                    "mechanism": self._current_episode.mechanism_type,
                    "status": self._current_episode.status,
                    "changes": self._current_episode.change_count,
                    "repairs": self._current_episode.repair_count,
                    "explanation": self._current_episode.learner_explanation.is_present,
                },
            )
        )
