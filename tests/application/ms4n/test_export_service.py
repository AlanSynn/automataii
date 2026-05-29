import pytest
from ms4n_helpers import make_episode

from automataii.application.ms4n import ExportService
from automataii.domain.ms4n import BreakdownRepairEpisode
from automataii.infrastructure.ms4n import FilesystemExportWriter


def test_export_service_writes_required_p0_bundle_files(tmp_path):
    result = ExportService(writer=FilesystemExportWriter()).export_bundle(
        (make_episode(),), tmp_path
    )
    paths = {path.relative_to(tmp_path).as_posix() for path in result.files}
    assert paths == {
        "research/episodes.jsonl",
        "research/coding_sheet.csv",
        "research/facilitator_moves.csv",
        "traces/ep_001_before.json",
        "traces/ep_001_after.json",
        "autopsy/ep_001_sheet.md",
        "manifest.json",
    }


def test_export_service_rejects_invalid_repaired_episode(tmp_path):
    invalid = BreakdownRepairEpisode(
        episode_id="ep_invalid",
        session_id="session_fake_001",
        participant_hash="p_hash_fake",
        mechanism_id="mech_1",
        mechanism_type="4_bar_linkage",
        part_name="arm",
        kit_asset_ids=("bar-board",),
        status="repaired",
    )
    with pytest.raises(ValueError):
        ExportService(writer=FilesystemExportWriter()).export_bundle((invalid,), tmp_path)


def test_export_service_allows_abandoned_episode_without_claiming_repair(tmp_path):
    abandoned = make_episode("abandoned")
    result = ExportService(writer=FilesystemExportWriter()).export_bundle((abandoned,), tmp_path)
    paths = {path.relative_to(tmp_path).as_posix() for path in result.files}
    assert "traces/ep_001_before.json" in paths
    assert "traces/ep_001_after.json" in paths
