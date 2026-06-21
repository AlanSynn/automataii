from __future__ import annotations

import json
import logging
import shutil
import time
import uuid
from pathlib import Path

from automataii.domain.animation.body_parts_extractor import BodyPartsExtractor
from automataii.domain.animation.image_to_annotations import image_to_annotations
from automataii.infrastructure.telemetry import telemetry_span
from automataii.utils.paths import resolve_path

logger = logging.getLogger("automataii.scenario.image_processing")

DEFAULT_IMAGE_CANDIDATES = (
    # PyInstaller stores root-level sample images at bundle_root/examples.
    "examples/girl.png",
    "examples/boy.png",
    # Development tree fallback.
    "src/examples/girl.png",
    "src/examples/boy.png",
    # Last-resort packaged resource that is always collected with resources/.
    "resources/examples/raw/placeholder.png",
)
GENERATED_TREE_MARKER = ".motionsmith-scenario-generated"


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
        annotations_output = _copy_tree(annotation_dir, output_dir / "annotations")

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
    _write_metrics(
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
    return Path(extractor.output_dir)


def _resolve_image(image_path: Path | None) -> Path:
    if image_path:
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {path}")
        return path.resolve()

    for candidate in DEFAULT_IMAGE_CANDIDATES:
        resolved = resolve_path(candidate)
        if resolved and resolved.exists():
            return Path(resolved)
    raise FileNotFoundError(
        f"No default image found. Checked: {', '.join(DEFAULT_IMAGE_CANDIDATES)}"
    )


def _copy_tree(src: Path, dst: Path) -> Path:
    """Copy a generated artifact tree without deleting unrelated user folders."""
    src = src.resolve()
    dst = dst.resolve()

    if src == dst:
        return dst

    target = dst
    if target.exists():
        marker_path = target / GENERATED_TREE_MARKER
        if (
            target.is_dir()
            and not target.is_symlink()
            and marker_path.is_file()
            and not marker_path.is_symlink()
        ):
            shutil.rmtree(target)
        else:
            target = _unique_sibling_path(dst)

    shutil.copytree(src, target, dirs_exist_ok=False)
    (target / GENERATED_TREE_MARKER).write_text("", encoding="utf-8")
    return target


def _unique_sibling_path(path: Path) -> Path:
    for _ in range(100):
        candidate = path.with_name(f"{path.name}-{uuid.uuid4().hex[:8]}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not allocate a unique output directory near {path}")


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
            "char_cfg": _artifact_path(
                annotation_dir, "char_cfg.yaml", annotation_info, "char_cfg_path"
            ),
            "texture": _artifact_path(
                annotation_dir, "texture.png", annotation_info, "texture_path"
            ),
            "mask": _artifact_path(annotation_dir, "mask.png", annotation_info, "mask_path"),
            "joint_overlay": _artifact_path(
                annotation_dir,
                "joint_overlay.png",
                annotation_info,
                "joint_overlay_path",
            ),
            "bounding_box": _artifact_path(
                annotation_dir,
                "bounding_box.yaml",
                annotation_info,
                "bounding_box_path",
            ),
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


def _artifact_path(
    annotation_dir: Path,
    filename: str,
    annotation_info: dict[str, str],
    fallback_key: str,
) -> str | None:
    copied_path = annotation_dir / filename
    if copied_path.exists():
        return str(copied_path.resolve())
    return annotation_info.get(fallback_key)


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
