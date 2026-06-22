#!/usr/bin/env python
"""Verification test for bend direction."""

import logging
import sys

# Set up detailed logging.
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s", stream=sys.stdout)

print("\n" + "=" * 80)
print("BEND DIRECTION VERIFICATION TEST")
print("=" * 80)
print("\nFix verification:")
print("- left_shoulder_7 -> left_elbow_8 (before: left_elbow_7)")
print("- right_shoulder_4 -> right_elbow_5 (before: right_elbow_4)")
print("- Find the real middle joint from the skeleton hierarchy")
print("\nTest sequence:")
print("1. Run: uv run python -m automataii")
print("2. Go to the Editor tab")
print("3. Click an elbow joint and confirm the color changes")
print("4. Click Play and run the animation")
print("\nExpected logs:")
print("- Click: 'Joint left_elbow_8 bend direction changed to -1.0'")
print("- Animation: 'IK: Using bend_direction -1.0 for middle joint left_elbow_8'")
print("\nImportant: the old 'left_elbow_7' error should not appear anymore.")
print("=" * 80)
