from pathlib import Path

from ms4n_helpers import make_episode

from automataii.application.ms4n import ExportResult, KitAssetViewModel
from automataii.presentation.qt.tabs.lab.presenter import LabPresenter


class FakeView:
    def __init__(self):
        self.assets = None
        self.summary = None
        self.trace = None
        self.rows = None
        self.export_result = None
        self.messages = []

    def set_kit_assets(self, assets):
        self.assets = tuple(assets)

    def set_episode_summary(self, summary):
        self.summary = summary

    def set_trace_duel_summary(self, summary):
        self.trace = summary

    def set_motion_autopsy_rows(self, rows):
        self.rows = tuple(rows)

    def show_export_result(self, result):
        self.export_result = result

    def show_lab_message(self, message):
        self.messages.append(message)


class FakeCatalog:
    def load(self, manifest_path):
        self.manifest_path = manifest_path

    def list_assets(self, pilot_priority):
        return (KitAssetViewModel("bar-board", "Bar Board Base", "kit/bar-board.svg", "svg"),)


class FakeExport:
    def __init__(self):
        self.called_with = None

    def export_bundle(self, episodes, output_dir):
        self.called_with = (tuple(episodes), output_dir)
        return ExportResult(output_dir=output_dir, files=(output_dir / "manifest.json",))


def test_presenter_loads_manifest_into_kit_panel():
    view = FakeView()
    presenter = LabPresenter(view, kit_catalog_service=FakeCatalog())
    presenter.load_manifest(Path("kit/ms4n-kit-manifest.json"))
    assert view.assets[0].asset_id == "bar-board"
    assert "MS4N Lab" not in view.assets[0].label


def test_presenter_saves_explanation_to_episode_draft():
    view = FakeView()
    presenter = LabPresenter(view)
    presenter.set_current_episode(make_episode(status="open"))
    presenter.save_explanation("I moved the pivot and the arm swung wider.")
    assert presenter.current_episode.learner_explanation.text.startswith("I moved")
    assert view.summary.learner_explanation_present is True


def test_export_button_calls_export_service_with_selected_directory(tmp_path):
    view = FakeView()
    export = FakeExport()
    presenter = LabPresenter(view, export_service=export)
    presenter.set_episodes((make_episode(),))
    presenter.export_bundle(tmp_path)
    assert export.called_with[0][0].episode_id == "ep_001"
    assert export.called_with[1] == tmp_path
    assert view.export_result.output_dir == tmp_path
