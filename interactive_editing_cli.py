#!/usr/bin/env python3
"""
Interactive Body Parts Editing CLI
Command-line interface for precise body part boundary definition
"""

import os
import sys
import argparse
from pathlib import Path

# Add source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from automataii.animate.interactive_body_editor import run_interactive_editing


def main():
    parser = argparse.ArgumentParser(
        description='Interactive Body Parts Editor - Define precise boundaries for body part segmentation'
    )
    
    parser.add_argument(
        'image', 
        help='Path to the character image (PNG/JPG)'
    )
    
    parser.add_argument(
        '--editing', 
        action='store_true', 
        help='Start interactive editing mode'
    )
    
    parser.add_argument(
        '--skeleton', 
        help='Path to skeleton configuration file (char_cfg.yaml or skeleton.json). If not provided, will look in image directory'
    )
    
    parser.add_argument(
        '--output', 
        help='Output directory for results (default: image_directory/interactive_output)'
    )
    
    args = parser.parse_args()
    
    # Validate image file
    if not os.path.exists(args.image):
        print(f"Error: Image file not found: {args.image}")
        sys.exit(1)
    
    # Check if editing mode is requested
    if not args.editing:
        print("Interactive Body Parts Editor")
        print("=" * 40)
        print()
        print("This tool allows you to precisely define body part boundaries by clicking on the image.")
        print()
        print("Usage:")
        print(f"  {sys.argv[0]} <image_path> --editing [--skeleton <skeleton_file>]")
        print()
        print("Example:")
        print(f"  {sys.argv[0]} Robot.png --editing")
        print()
        print("Features:")
        print("- Interactive boundary definition by clicking")
        print("- Real-time preview of segmentation")
        print("- Save/load boundary configurations")
        print("- Joint-based skeleton integration")
        print("- Export final segmentation masks")
        print()
        print("Add --editing flag to start interactive mode")
        return
    
    print("🤖 Interactive Body Parts Editor")
    print("=" * 50)
    print(f"Image: {args.image}")
    print(f"Skeleton: {args.skeleton or 'Auto-detect'}")
    print()
    print("Starting interactive editing session...")
    print()
    
    try:
        run_interactive_editing(args.image, args.skeleton)
        print("✅ Interactive editing session completed!")
        
    except KeyboardInterrupt:
        print("\n⏹️  Interactive editing cancelled by user")
        
    except Exception as e:
        print(f"❌ Error during interactive editing: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()