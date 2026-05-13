from __future__ import annotations

import math

from automataii.application.editor.motion_paths import MotionPathRepository


def test_motion_path_repository_filters_bad_points_and_names() -> None:
    repo = MotionPathRepository()
    seen: list[dict] = []
    repo.subscribe(lambda snapshot: seen.append(snapshot))

    repo.replace(
        {
            "hand": [(0, 0), (math.nan, 1), (2, math.inf), (3, 4)],
            "": [(9, 9)],
            "bad": [(math.nan, math.nan)],
        }
    )

    assert repo.snapshot() == {"hand": ((0.0, 0.0), (3.0, 4.0))}
    assert seen[-1] == {"hand": ((0.0, 0.0), (3.0, 4.0))}


def test_motion_path_repository_ignores_empty_part_name_on_upsert() -> None:
    repo = MotionPathRepository()
    repo.upsert("", [(1, 2)])
    assert repo.snapshot() == {}
