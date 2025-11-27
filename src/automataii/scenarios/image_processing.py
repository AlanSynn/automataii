from __future__ import annotations

import json
import logging
import shutil
import time
from pathlib import Path
from typing import Iterable, Optional

from automataii.domain.animation.body_parts_extractor import BodyPartsExtractor
from automataii.domain.animation.image_to_annotations import image_to_annotations
from automataii.core.telemetry import telemetry_span
from automataii.utils.paths import resolve_path

logger = logging.getLogger("automataii.scenario.image_processing")

DEFAULT_IMAGE_CANDIDATES = (
    "data/characters/astronaut.png",
    "src/examples/girl.png",
    "src/examples/boy.png",
)


def run_image_processing_scenario(
    output_dir: Path,
    *,
    image_path: Path | None = None,
    detector_model: Path | None = None,
    pose_model: Path | None = None,
) -> Path:
    """
    Execute the image-processing automation scenario.

    Steps:
        1. Run ONNX-based detection/pose pipeline (`image_to_annotations`).
        2. Run `BodyPartsExtractor` to produce segmented parts + metadata.
        3. Emit manifest + metrics artifacts and telemetry spans.
    """
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    image_path = _resolve_image(image_path)
    logger.info("Image-processing scenario starting with image=%s", image_path)

    start_time = time.perf_counter()

    with telemetry_span(
        "scenario.image_processing",
        image=image_path.name,
        detector=str(detector_model) if detector_model else None,
        pose=str(pose_model) if pose_model else None,
    ) as span:
        annotation = image_to_annotations(
            str(image_path),
            detector_onnx=str(detector_model) if detector_model else None,
            pose_onnx=str(pose_model) if pose_model else None,
        )
        if not annotation:
            raise RuntimeError("image_to_annotations returned no results")

        annotation_dir = Path(annotation["output_dir"]).resolve()
        annotations_output = output_dir / "annotations"
        _copy_tree(annotation_dir, annotations_output)

        extractor = BodyPartsExtractor(
            char_dir=str(annotations_output),
            output_dir=str(output_dir / "parts"),
        )
        extractor.process()

        parts_info_path = extractor.output_dir / "parts_info.json"
        part_count = 0
        if parts_info_path.exists():
            parts_data = json.loads(parts_info_path.read_text(encoding="utf-8"))
            part_count = len(parts_data.get("character", {}).get("parts", {}))
        else:
            logger.warning("parts_info.json not found at %s", parts_info_path)

        span.set(
            annotation_dir=str(annotations_output),
            parts_dir=str(extractor.output_dir),
            part_count=part_count,
        )

        manifest_path = _write_manifest(
            output_dir=output_dir,
            image=image_path,
            annotation_dir=annotations_output,
            annotation_info=annotation,
            parts_dir=extractor.output_dir,
            parts_info_path=parts_info_path,
            part_count=part_count,
        )

    duration_ms = round((time.perf_counter() - start_time) * 1000, 3)
    metrics_path = _write_metrics(
        output_dir=output_dir,
        duration_ms=duration_ms,
        part_count=part_count,
        image=image_path,
        manifest_path=manifest_path,
        parts_info_path=parts_info_path,
    )

    logger.info(
        "Image-processing scenario completed in %.2f ms; parts=%d; artifacts=%s",
        duration_ms,
        part_count,
        output_dir,
    )
    return extractor.output_dir


def _resolve_image(image_path: Optional[Path]) -> Path:
    if image_path:
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {path}")
        return path.resolve()

    for candidate in DEFAULT_IMAGE_CANDIDATES:
        resolved = resolve_path(candidate)
        if resolved and resolved.exists():
            return resolved
    raise FileNotFoundError(
        f"No default image found. Checked: {', '.join(DEFAULT_IMAGE_CANDIDATES)}"
    )


def _copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, dirs_exist_ok=True)


def _write_manifest(
    *,
    output_dir: Path,
    image: Path,
    annotation_dir: Path,
    annotation_info: dict[str, str],
    parts_dir: Path,
    parts_info_path: Path,
    part_count: int,
) -> Path:
    manifest = {
        "image": str(image.resolve()),
        "annotation": {
            "dir": str(annotation_dir.resolve()),
            "char_cfg": annotation_info.get("char_cfg_path"),
            "texture": annotation_info.get("texture_path"),
            "mask": annotation_info.get("mask_path"),
            "joint_overlay": annotation_info.get("joint_overlay_path"),
            "bounding_box": annotation_info.get("bounding_box_path"),
        },
        "parts": {
            "dir": str(parts_dir.resolve()),
            "parts_info": str(parts_info_path.resolve()),
            "part_count": part_count,
        },
    }
    manifest_path = output_dir / "image_processing_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def _write_metrics(
    *,
    output_dir: Path,
    duration_ms: float,
    part_count: int,
    image: Path,
    manifest_path: Path,
    parts_info_path: Path,
) -> Path:
    metrics = {
        "duration_ms": duration_ms,
        "part_count": part_count,
        "image": str(image.name),
        "manifest": str(manifest_path.resolve()),
        "parts_info": str(parts_info_path.resolve()),
    }
    metrics_path = output_dir / "image_processing_metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    return metrics_path
