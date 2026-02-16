"""Matching/fallback helpers for mechanism-to-character rebinding."""
from __future__ import annotations

from typing import Any


def normalize_token(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def resolve_target_part_name(
    mechanism_id: str,
    layer_data: dict[str, Any],
    parts_data: dict[str, Any],
) -> str:
    explicit_part = str(layer_data.get("part_name") or "").strip()
    if explicit_part in parts_data:
        return explicit_part

    normalized_to_part: dict[str, str] = {}
    for part_name in parts_data:
        norm = normalize_token(str(part_name))
        if norm and norm not in normalized_to_part:
            normalized_to_part[norm] = str(part_name)

    candidates: list[str] = []
    for key in ("part_name", "name", "label", "target_part", "mechanism_name"):
        value = layer_data.get(key)
        if isinstance(value, str) and value.strip():
            candidates.append(value.strip())
    if mechanism_id:
        candidates.append(str(mechanism_id))

    for candidate in candidates:
        norm_candidate = normalize_token(candidate)
        if not norm_candidate:
            continue
        direct = normalized_to_part.get(norm_candidate)
        if direct:
            return direct

    best_match: tuple[int, str] | None = None
    norm_candidates = [normalize_token(c) for c in candidates if c]
    for norm_part, part_name in normalized_to_part.items():
        if not norm_part:
            continue
        for norm_candidate in norm_candidates:
            if not norm_candidate:
                continue
            if norm_part in norm_candidate or norm_candidate in norm_part:
                score = len(norm_part)
                if best_match is None or score > best_match[0]:
                    best_match = (score, part_name)
    if best_match:
        return best_match[1]

    if "torso" in parts_data:
        return "torso"
    return str(next(iter(parts_data.keys())))


def resolve_part_scene_fallback(part_info: Any) -> tuple[float, float]:
    roi = getattr(part_info, "roi", None)
    if isinstance(roi, list | tuple) and len(roi) >= 4:
        try:
            x, y, w, h = float(roi[0]), float(roi[1]), float(roi[2]), float(roi[3])
            return (x + (w * 0.5), y + (h * 0.5))
        except (TypeError, ValueError):
            pass

    return (
        float(getattr(part_info, "x", 400.0)),
        float(getattr(part_info, "y", 300.0)),
    )
