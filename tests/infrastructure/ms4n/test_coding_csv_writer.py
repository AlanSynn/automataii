import csv

from ms4n_helpers import make_episode

from automataii.infrastructure.ms4n.coding_csv_writer import CODING_CSV_HEADER, write_coding_csv


def test_coding_csv_writes_expected_header_order(tmp_path):
    path = write_coding_csv((make_episode(),), tmp_path / "coding.csv")
    header = path.read_text().splitlines()[0]
    assert header == ",".join(CODING_CSV_HEADER)


def test_coding_csv_flattens_trace_summary_not_raw_points_by_default(tmp_path):
    path = write_coding_csv((make_episode(),), tmp_path / "coding.csv")
    text = path.read_text()
    assert "trace_point_count" in text
    assert "trace_points" not in text


def test_coding_csv_escapes_commas_and_newlines(tmp_path):
    episode = make_episode()
    path = write_coding_csv((episode,), tmp_path / "coding.csv")
    rows = list(csv.DictReader(path.open()))
    assert len(rows) == 1
    assert "predict_observe_explain" in rows[0]["facilitator_moves"]
