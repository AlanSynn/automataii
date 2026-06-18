from __future__ import annotations

import sys
from pathlib import Path

import pytest
from scripts import check_mypy_baseline as script


def test_error_signatures_ignore_line_numbers() -> None:
    output = "\n".join(
        [
            "src/automataii/presentation/qt/view.py:10: error: Bad thing  [misc]",
            "src/automataii/presentation/qt/view.py:99: error: Bad thing  [misc]",
        ]
    )

    assert script._error_signatures(output) == [
        "src/automataii/presentation/qt/view.py: error: Bad thing  [misc] | source:<unavailable>",
        "src/automataii/presentation/qt/view.py: error: Bad thing  [misc] | source:<unavailable>",
    ]


def test_summary_groups_legacy_qt_and_error_codes() -> None:
    summary = script._summary(
        [
            "src/automataii/presentation/qt/view.py: error: Bad thing  [misc] | source:x",
            "src/automataii/domain/animation/cv.py: error: Bad cv  [arg-type] | source:y",
            "src/automataii/domain/model.py: error: Bad core  [return-value] | source:z",
        ]
    )

    assert summary["layers"] == {
        "legacy-qt-ui": 1,
        "opencv-image-pipeline": 1,
        "domain-core": 1,
    }
    assert summary["error_codes"] == {"arg-type": 1, "misc": 1, "return-value": 1}


def test_missing_baseline_fails_without_self_blessing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing_baseline = tmp_path / "missing.json"

    monkeypatch.setattr(script, "BASELINE_PATH", missing_baseline)
    monkeypatch.setattr(
        script,
        "_run_mypy",
        lambda: (1, "src/automataii/presentation/qt/view.py:10: error: Bad thing  [misc]"),
    )
    monkeypatch.setattr(sys, "argv", ["check_mypy_baseline.py"])

    assert script.main() == 1
    assert not missing_baseline.exists()


def test_mypy_infrastructure_failure_does_not_pass_or_update(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    baseline_path = tmp_path / "baseline.json"
    monkeypatch.setattr(script, "BASELINE_PATH", baseline_path)
    monkeypatch.setattr(script, "_run_mypy", lambda: (2, "mypy: error: bad config"))

    monkeypatch.setattr(sys, "argv", ["check_mypy_baseline.py"])
    assert script.main() == 1
    assert not baseline_path.exists()

    monkeypatch.setattr(sys, "argv", ["check_mypy_baseline.py", "--update"])
    assert script.main() == 1
    assert not baseline_path.exists()


def test_source_line_is_part_of_signature(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path
    source_path = repo / "src" / "automataii" / "sample.py"
    source_path.parent.mkdir(parents=True)
    source_path.write_text("def old(): pass\n\ndef new(): pass\n")
    monkeypatch.setattr(script, "ROOT", repo)

    output = "\n".join(
        [
            "src/automataii/sample.py:1: error: Function is missing a type annotation  [no-untyped-def]",
            "src/automataii/sample.py:3: error: Function is missing a type annotation  [no-untyped-def]",
        ]
    )

    assert script._error_signatures(output) == [
        "src/automataii/sample.py: error: Function is missing a type annotation  [no-untyped-def] | source:def new(): pass",
        "src/automataii/sample.py: error: Function is missing a type annotation  [no-untyped-def] | source:def old(): pass",
    ]
