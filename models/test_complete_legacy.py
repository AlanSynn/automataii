#!/usr/bin/env python
"""
Complete Legacy API + ONNX Test
Tests: Legacy PyTorch -> ONNX inference -> Comparison
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path

def run_command(cmd, description):
    """Run command and handle errors"""
    print(f"\n🔄 {description}")
    print(f"Command: {cmd}")

    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {description} - SUCCESS")
            if result.stdout:
                print("Output:", result.stdout[-500:])  # Last 500 chars
        else:
            print(f"❌ {description} - FAILED")
            print("Error:", result.stderr)
            return False
    except Exception as e:
        print(f"❌ {description} - EXCEPTION: {e}")
        return False

    return True

def main():
    parser = argparse.ArgumentParser(description='Complete Legacy API + ONNX Test')
    parser.add_argument('--image', default='astronaut.png', help='Test image')
    parser.add_argument('--det-config', default='./archives/detector_mar_content/config.py')
    parser.add_argument('--det-checkpoint', default='./archives/detector_mar_content/latest.pth')
    parser.add_argument('--pose-config', default='./archives/pose_mar_content/config.py')
    parser.add_argument('--pose-checkpoint', default='./archives/pose_mar_content/best_AP_epoch_72.pth')

    args = parser.parse_args()

    print("🧪 Complete Legacy API + ONNX Test")
    print("=" * 50)

    success_count = 0
    total_tests = 0

    # Step 1: Test Legacy PyTorch API
    total_tests += 1
    legacy_cmd = f"python process_legacy_api.py --image {args.image} --det-config {args.det_config} --det-checkpoint {args.det_checkpoint} --pose-config {args.pose_config} --pose-checkpoint {args.pose_checkpoint}"
    if run_command(legacy_cmd, "Legacy PyTorch API Test"):
        success_count += 1

    # Step 2: Test ONNX inference (using existing ONNX models)
    total_tests += 1
    onnx_test_cmd = f"python test_onnx_inference.py --image {args.image} --detector-onnx ./exports/detector_backbone.onnx --pose-onnx ./exports/pose_model.onnx"
    if run_command(onnx_test_cmd, "ONNX Inference Test"):
        success_count += 1

    # Summary
    print("\n" + "=" * 50)
    print(f"📊 Test Summary: {success_count}/{total_tests} tests passed")

    if success_count == total_tests:
        print("🎉 All tests passed! Both Legacy API and ONNX are working!")
    else:
        print("⚠️ Some tests failed. Check the logs above.")

    # Check if files exist
    print("\n📁 Generated Files:")
    files_to_check = [
        f'./results/{Path(args.image).stem}_legacy/',
        './results/astronaut/',
        './exports/detector_backbone.onnx',
        './exports/pose_model.onnx'
    ]

    for file_path in files_to_check:
        if os.path.exists(file_path):
            if os.path.isdir(file_path):
                file_count = len(os.listdir(file_path))
                print(f"  ✅ {file_path} ({file_count} files)")
            else:
                size_mb = os.path.getsize(file_path) / (1024*1024)
                print(f"  ✅ {file_path} ({size_mb:.1f} MB)")
        else:
            print(f"  ❌ {file_path} (missing)")

if __name__ == '__main__':
    main()