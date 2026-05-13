from __future__ import annotations

import math

import numpy as np

from automataii.domain.generation.contour import AdvancedContourExtractor, ManufacturingContour
from automataii.domain.generation.layout import ScaleNormalizer


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
