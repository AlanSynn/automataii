from __future__ import annotations

import math
import re
from pathlib import Path

import cv2
import numpy as np

from automataii.domain.generation.contour import AdvancedContourExtractor, ManufacturingContour
from automataii.domain.generation.layout import ScaleNormalizer
from automataii.infrastructure.generation.processors.png_blueprint import PNGBlueprintProcessor
from automataii.infrastructure.generation.svg.optimizer import BlueprintLayoutOptimizer


def _sample_contour() -> ManufacturingContour:
    points = np.array([[[0, 0]], [[10, 0]], [[10, 10]], [[0, 10]]], dtype=np.int32)
    return ManufacturingContour(points, points, "M 0 0 L 10 10 Z")


def test_contour_extractor_normalizes_constructor_and_bad_path() -> None:
    extractor = AdvancedContourExtractor(tolerance=math.nan, min_area=-5.0)

    assert extractor.tolerance == 2.0
    assert extractor.min_area == 100.0
    assert extractor.extract_manufacturing_contours(None) == []  # type: ignore[arg-type]


def test_alpha_and_preprocess_masks_sanitize_nonfinite_arrays() -> None:
    extractor = AdvancedContourExtractor()

    assert extractor._extract_alpha_mask(np.array([])) is None

    image = np.array([[[0.0, math.nan, math.inf, math.inf]]], dtype=float)
    mask = extractor._extract_alpha_mask(image)
    assert mask is not None
    assert mask.dtype == np.uint8
    assert mask[0, 0] == 255

    processed = extractor._preprocess_mask(np.array([[math.nan, math.inf]], dtype=float))
    assert processed.dtype == np.uint8
    assert processed.shape[0] >= 1

    assert extractor._extract_alpha_mask(np.array([["bad"]], dtype=object)).sum() == 0
    assert extractor._preprocess_mask(np.array(5.0)).shape == (1, 1)


def test_contour_to_svg_path_filters_malformed_and_nonfinite_points() -> None:
    extractor = AdvancedContourExtractor()
    contour = np.array([[[0.0, 0.0]], [[math.nan, 1.0]], [[2.0, 2.0]]])

    assert extractor._contour_to_svg_path(contour) == "M 0.00 0.00 L 2.00 2.00 Z"
    assert extractor._contour_to_svg_path(np.array([1.0, 2.0, 3.0])) == ""
    assert extractor._contour_to_svg_path(np.array(1.0)) == ""


def test_manufacturing_contour_filters_nonfinite_geometry_for_serialization() -> None:
    contour = ManufacturingContour(
        np.array([[[0.0, 0.0]], [[math.nan, 1.0]], [[10.0, 0.0]], [[10.0, 10.0]]]),
        np.array([1.0, 2.0, 3.0]),
        "M 0 0",
    )
    contour.area = math.nan
    contour.perimeter = math.inf

    payload = contour.to_dict()

    assert len(contour.contour) == 3
    assert contour.simplified_contour.size == 0
    assert payload["area"] == 0.0
    assert payload["perimeter"] == 0.0
    assert payload["bounding_rect"] == [0, 0, 11, 11]


def test_apply_offset_to_path_handles_exponents_and_bad_tokens() -> None:
    extractor = AdvancedContourExtractor()

    shifted = extractor.apply_offset_to_path("M 1e1 -2.5 L 0 0 C bad", math.nan, 2.0)

    assert shifted == "M 10.00 -0.50 L 0.00 2.00 C bad"
    assert extractor.apply_offset_to_path("M 1.2.3 4", 1.0, 1.0) == "M 1.2.3 4"
    assert extractor.apply_offset_to_path(None, 1.0, 1.0) == ""  # type: ignore[arg-type]


def test_scale_normalizer_handles_bad_scale_inputs_and_svg_tokens() -> None:
    normalizer = ScaleNormalizer(target_character_height_mm=math.nan)

    assert normalizer.target_height_mm == 300.0
    assert normalizer.calculate_scale_factor(math.inf) == 0.36
    assert normalizer.calculate_scale_factor(0.0) == 0.36
    assert normalizer._scale_svg_path("M 1e1 -2.5 L bad 4 L 2 3", math.nan) == (
        "M 10.00 -2.50 L bad 4 L 2.00 3.00"
    )


def test_normalize_contour_keeps_scaled_properties_finite() -> None:
    contour = _sample_contour()
    contour.area = math.nan
    contour.perimeter = math.inf
    contour.bounding_rect = (0, 0, 10, 10)

    scaled = ScaleNormalizer().normalize_contour(contour, math.nan)

    assert scaled.bounding_rect == (0, 0, 10, 10)
    assert scaled.area == 0.0
    assert scaled.perimeter == 0.0
    assert scaled.svg_path == "M 0.00 0.00 L 10.00 10.00 Z"


class _BlueprintPartInfo:
    def __init__(self, *, name: str, image_path: str, roi: list[float]) -> None:
        self.name = name
        self.image_path = image_path
        self.roi = roi
        self.x = roi[0]
        self.y = roi[1]
        self.local_pivot_offset = [roi[2] / 2.0, roi[3] / 2.0]


class _BlueprintPartItem:
    def __init__(self, part_info: _BlueprintPartInfo) -> None:
        self.part_info = part_info


class _PixmapBlueprintPartItem(_BlueprintPartItem):
    def __init__(self, part_info: _BlueprintPartInfo, pixmap: object) -> None:
        super().__init__(part_info)
        self.part_pixmap = pixmap


def test_character_part_blueprint_texture_keeps_editor_canvas_alignment(tmp_path: Path) -> None:
    """Transparent margins must not be squeezed into the cut contour bounds.

    Editor parts are shown as an alpha-masked pixmap on a full cropped canvas.
    The cut sheet may crop the red cut outline to the contour bbox, but the
    embedded texture has to stay translated from the full editor canvas;
    otherwise the visible body component no longer matches the editor shape.
    """
    image_path = tmp_path / "offset_triangle.png"
    bgra = np.zeros((160, 200, 4), dtype=np.uint8)
    triangle = np.array([[[70, 40], [150, 64], [92, 130]]], dtype=np.int32)
    cv2.fillPoly(bgra, triangle, color=(60, 120, 220, 255))
    assert cv2.imwrite(str(image_path), bgra)

    part_item = _BlueprintPartItem(
        _BlueprintPartInfo(
            name="offset_triangle",
            image_path=str(image_path),
            roi=[0.0, 0.0, 200.0, 160.0],
        )
    )

    layout_items, _width, _height = BlueprintLayoutOptimizer().optimize_blueprint_layout(
        [part_item], {}, unit_system="imperial"
    )

    assert len(layout_items) == 1
    item = layout_items[0]
    image_match = re.search(
        r'<image\b[^>]*\sx="(?P<x>-?\d+(?:\.\d+)?)"[^>]*\sy="(?P<y>-?\d+(?:\.\d+)?)"'
        r'[^>]*\swidth="(?P<width>\d+(?:\.\d+)?)"[^>]*\sheight="(?P<height>\d+(?:\.\d+)?)"',
        item.svg_content,
    )
    assert image_match is not None
    assert float(image_match.group("x")) < 0.0
    assert float(image_match.group("y")) < 0.0
    assert float(image_match.group("width")) > item.bounds.width
    assert float(image_match.group("height")) > item.bounds.height
    assert "clip-path" in item.svg_content
    assert "cutting-path" in item.svg_content


def test_character_part_contour_prefers_current_editor_pixmap(tmp_path: Path) -> None:
    from PyQt6.QtGui import QImage, QPixmap
    from PyQt6.QtWidgets import QApplication

    _app = QApplication.instance() or QApplication([])
    disk_path = tmp_path / "stale_rect.png"
    stale = np.zeros((80, 80, 4), dtype=np.uint8)
    stale[5:75, 5:75, :] = (20, 20, 20, 255)
    assert cv2.imwrite(str(disk_path), stale)

    rgba = np.zeros((80, 80, 4), dtype=np.uint8)
    triangle = np.array([[[30, 18], [64, 62], [16, 70]]], dtype=np.int32)
    cv2.fillPoly(rgba, triangle, color=(240, 120, 80, 255))
    image = QImage(rgba.data, 80, 80, 80 * 4, QImage.Format.Format_RGBA8888).copy()
    item = _PixmapBlueprintPartItem(
        _BlueprintPartInfo(
            name="editor_triangle",
            image_path=str(disk_path),
            roi=[0.0, 0.0, 80.0, 80.0],
        ),
        QPixmap.fromImage(image),
    )

    contour = PNGBlueprintProcessor().process_part_png(item)

    assert contour is not None
    assert getattr(contour, "coordinate_space", None) == "displayed_roi"
    assert getattr(contour, "source_image_data_uri", "").startswith("data:image/png;base64,")
    # The stale disk rectangle would start near x=5; the editor triangle starts
    # much farther right, proving the visible pixmap won.
    assert contour.bounding_rect[0] > 10
