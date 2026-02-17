from __future__ import annotations

import cv2
import numpy as np

from automataii.domain.animation.body_parts_extractor import BodyPartsExtractor
from automataii.domain.animation.part_definitions import BODY_PARTS


def _empty_masks(shape: tuple[int, int]) -> dict[str, np.ndarray]:
    return {name: np.zeros(shape, dtype=np.uint8) for name in BODY_PARTS}


def test_synthesize_missing_limb_masks_creates_upper_arms() -> None:
    extractor = BodyPartsExtractor(char_dir=".", output_dir=".")
    extractor.mask = np.zeros((200, 200), dtype=np.uint8)
    cv2.rectangle(extractor.mask, (40, 30), (160, 190), 255, thickness=-1)
    extractor.texture_relative_joint_map = {
        # compact joints near torso (typical collapse case)
        "left_shoulder": (115, 95),
        "left_elbow": (120, 102),
        "left_hand": (124, 112),
        "right_shoulder": (85, 95),
        "right_elbow": (80, 102),
        "right_hand": (76, 112),
        "left_hip": (110, 130),
        "left_knee": (112, 150),
        "left_foot": (114, 170),
        "right_hip": (90, 130),
        "right_knee": (88, 150),
        "right_foot": (86, 170),
    }

    masks = _empty_masks(extractor.mask.shape)
    filled = extractor._synthesize_missing_limb_masks(masks)

    assert np.count_nonzero(filled["left_arm_upper"]) > 0
    assert np.count_nonzero(filled["right_arm_upper"]) > 0
    assert np.count_nonzero(filled["left_leg_upper"]) > 0
    assert np.count_nonzero(filled["right_leg_upper"]) > 0


def test_synthesize_missing_limb_masks_preserves_existing_mask() -> None:
    extractor = BodyPartsExtractor(char_dir=".", output_dir=".")
    extractor.mask = np.zeros((120, 120), dtype=np.uint8)
    cv2.rectangle(extractor.mask, (20, 20), (100, 110), 255, thickness=-1)
    extractor.texture_relative_joint_map = {
        "left_shoulder": (70, 50),
        "left_elbow": (80, 58),
        "left_hand": (90, 65),
    }

    masks = _empty_masks(extractor.mask.shape)
    cv2.rectangle(masks["left_arm_upper"], (62, 45), (72, 60), 255, thickness=-1)
    before = int(np.count_nonzero(masks["left_arm_upper"]))

    filled = extractor._synthesize_missing_limb_masks(masks)
    after = int(np.count_nonzero(filled["left_arm_upper"]))

    assert after >= before
