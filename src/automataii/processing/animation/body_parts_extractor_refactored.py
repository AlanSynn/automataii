"""
Refactored body parts extractor module.

This module maintains backward compatibility while delegating to the new modular structure.
"""

import argparse
from .parts_extraction import BodyPartsExtractor


# For backward compatibility - expose main classes
from .parts_extraction.segmentation import SkeletonSegmenter as FastSkeletonSegmenter


def main():
    """Main entry point for command-line usage."""
    parser = argparse.ArgumentParser(
        description="Extract character body parts using skeleton"
    )
    parser.add_argument("char_dir", help="Character directory path")
    parser.add_argument("--output", "-o", default=None, help="Output directory path")
    parser.add_argument(
        "--no-animation", action="store_true", help="Disable animation generation"
    )
    parser.add_argument("--frames", "-f", type=int, default=30, help="Animation frames")
    parser.add_argument("--fps", type=int, default=24, help="Animation FPS")
    
    args = parser.parse_args()
    
    extractor = BodyPartsExtractor(
        char_dir=args.char_dir,
        output_dir=args.output,
        generate_animations=not args.no_animation,
        num_frames=args.frames,
        fps=args.fps,
    )
    extractor.process()


if __name__ == "__main__":
    main()