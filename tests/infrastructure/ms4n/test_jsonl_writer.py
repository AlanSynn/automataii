import json

from ms4n_helpers import make_episode

from automataii.infrastructure.ms4n import write_episodes_jsonl


def test_jsonl_writer_writes_one_episode_per_line(tmp_path):
    episodes = (make_episode(), make_episode())
    path = write_episodes_jsonl(episodes, tmp_path / "episodes.jsonl")
    lines = [line for line in path.read_text().splitlines() if line]
    assert len(lines) == 2


def test_jsonl_writer_uses_stable_key_order(tmp_path):
    episode = make_episode()
    path_1 = write_episodes_jsonl((episode,), tmp_path / "a.jsonl")
    path_2 = write_episodes_jsonl((episode,), tmp_path / "b.jsonl")
    assert path_1.read_text().startswith('{"schema_version":')
    assert path_1.read_text() == path_2.read_text()


def test_jsonl_writer_round_trips_with_json_loads(tmp_path):
    path = write_episodes_jsonl((make_episode(),), tmp_path / "episodes.jsonl")
    payload = json.loads(path.read_text().splitlines()[0])
    assert payload["episode_id"] == "ep_001"
