#!/usr/bin/env python

import sys
from pathlib import Path

import cv2

# Add the src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from automataii.domain.animation.body_parts_extractor import BodyPartsExtractor
from automataii.domain.animation.image_to_annotations import image_to_annotations


def test_elephant_image():
    """Test the elephant image texture extraction"""

    # Process the elephant image
    img_path = "image_123650291.JPG"

    print(f"Testing texture extraction for: {img_path}")

    # Step 1: Generate annotations
    print("Step 1: Generating annotations...")
    results = image_to_annotations(img_path)

    if results:
        print(f"Annotations created in: {results['output_dir']}")

        # Step 2: Extract body parts
        print("Step 2: Extracting body parts...")
        extractor = BodyPartsExtractor(
            char_dir=results["output_dir"],
            output_dir=Path(results["output_dir"]) / "body_parts",
            generate_animations=False,
        )
        extractor.process()

        print(f"Body parts extracted to: {Path(results['output_dir']) / 'body_parts'}")

        # Check the results
        output_dir = Path(results["output_dir"]) / "body_parts"
        if output_dir.exists():
            parts_found = list(output_dir.glob("*.png"))
            print(f"\nFound {len(parts_found)} body part images:")
            for part in parts_found:
                print(f"  - {part.name}")

            # Check if textures have content
            for part_path in parts_found[:3]:  # Check first 3 parts
                img = cv2.imread(str(part_path), cv2.IMREAD_UNCHANGED)
                if img is not None:
                    h, w = img.shape[:2]
                    channels = img.shape[2] if len(img.shape) == 3 else 1
                    alpha_mean = 0
                    if channels == 4:
                        alpha_mean = img[:, :, 3].mean()
                    print(
                        f"  {part_path.name}: {w}x{h}, {channels} channels, alpha mean: {alpha_mean:.1f}"
                    )
    else:
        print("Failed to generate annotations")


if __name__ == "__main__":
    test_elephant_image()
