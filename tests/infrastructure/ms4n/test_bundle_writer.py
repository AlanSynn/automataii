import json

from ms4n_helpers import make_episode

from automataii.infrastructure.ms4n.bundle_writer import BundleWriter


def test_bundle_writer_writes_manifest_facilitator_and_trace_files(tmp_path):
    writer = BundleWriter(tmp_path)
    episode = make_episode()
    facilitator = writer.write_facilitator_moves(
        (episode,), tmp_path / "research" / "facilitator.csv"
    )
    trace = writer.write_trace_snapshot_json(
        episode, "before", tmp_path / "traces" / "ep_001_before.json"
    )
    manifest = writer.write_manifest((episode,), (facilitator, trace))
    assert facilitator.exists()
    assert trace.exists()
    trace_payload = json.loads(trace.read_text())
    assert trace_payload["schema_version"] == "ms4n.trace_snapshot.v1"
    assert trace_payload["snapshot_role"] == "before"
    payload = json.loads(manifest.read_text())
    assert payload["schema_version"] == "ms4n.export.v1"
    assert payload["episode_count"] == 1
