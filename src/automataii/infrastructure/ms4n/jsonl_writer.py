"""Deterministic JSONL writer for Lab/MS4N episodes."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from automataii.domain.ms4n import BreakdownRepairEpisode


def write_episodes_jsonl(episodes: Sequence[BreakdownRepairEpisode], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(episode.to_dict(), ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        for episode in episodes
    ]
    text = "\n".join(lines)
    if text:
        text += "\n"
    path.write_text(text, encoding="utf-8")
    return path
