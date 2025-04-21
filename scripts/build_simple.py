#!/usr/bin/env python3
"""
Simple build script for Automataii that works with uv
This script assumes all dependencies are already installed via uv
"""

import sys
import shutil
import subprocess
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SimpleBuilder:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.dist_dir = project_root / "dist"
        self.spec_file = project_root / "automataii.spec"
        
    def check_dependencies(self):
        """Check if required tools are available"""
        logger.info("Checking dependencies...")
        
        # Check PyInstaller
        try:
            subprocess.run([sys.executable, '-c', 'import PyInstaller'], check=True, capture_output=True)
            logger.info("✓ PyInstaller is available")
        except subprocess.CalledProcessError:
            logger.error("✗ PyInstaller not found. Install with: uv add pyinstaller")
            return False
        
        # Check platform-specific dependencies
        if sys.platform == "darwin":
            try:
                subprocess.run([sys.executable, '-c', 'import objc'], check=True, capture_output=True)
                logger.info("✓ PyObjC is available")
            except subprocess.CalledProcessError:
                logger.warning("⚠ PyObjC not found. Install with: uv add --optional build-macos")
        
        elif sys.platform == "win32":
            try:
                subprocess.run([sys.executable, '-c', 'import win32api'], check=True, capture_output=True)
                logger.info("✓ pywin32 is available")
            except subprocess.CalledProcessError:
                logger.warning("⚠ pywin32 not found. Install with: uv add --optional build-windows")
        
        return True
    
    def clean_build(self):
        """Clean previous build artifacts"""
        logger.info("Cleaning previous build artifacts...")
        
        # Clean dist and build directories but NOT the build scripts directory
        for path in [self.dist_dir, self.project_root / "build" / "temp"]:
            if path.exists():
                shutil.rmtree(path)
                logger.info(f"Removed {path}")
        
        # Clean PyInstaller build directory
        build_dir = self.project_root / "build"
        if build_dir.exists():
            for item in build_dir.iterdir():
                if item.name != "__pycache__" and item.suffix not in ['.py', '.md']:
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)
    
    def build_executable(self):
        """Build executable using PyInstaller"""
        logger.info("Building executable with PyInstaller...")
        
        if not self.spec_file.exists():
            logger.error(f"Spec file not found: {self.spec_file}")
            logger.info("Generate spec file first with: pyinstaller --name Automataii src/automataii/__main__.py")
            return False
        
        # Run PyInstaller
        cmd = [sys.executable, '-m', 'PyInstaller', '--clean', '--noconfirm', str(self.spec_file)]
        
        logger.info(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=self.project_root)
        
        if result.returncode != 0:
            logger.error("PyInstaller failed")
            return False
        
        # Check output
        if sys.platform == "darwin":
            output_path = self.dist_dir / "Automataii.app"
        elif sys.platform == "win32":
            output_path = self.dist_dir / "Automataii.exe"
        else:
            output_path = self.dist_dir / "Automataii"
        
        if output_path.exists():
            logger.info(f"✓ Build successful: {output_path}")
            return True
        else:
            logger.error(f"✗ Output not found: {output_path}")
            return False
    
    def build(self):
        """Execute build process"""
        logger.info("=== Starting Automataii Build ===")
        
        # Check dependencies
        if not self.check_dependencies():
            return False
        
        # Clean previous builds
        self.clean_build()
        
        # Build executable
        if not self.build_executable():
            return False
        
        logger.info("=== Build Complete ===")
        return True

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Simple build script for Automataii')
    parser.add_argument('--clean-only', action='store_true', help='Only clean build artifacts')
    
    args = parser.parse_args()
    
    project_root = Path(__file__).parent.parent
    builder = SimpleBuilder(project_root)
    
    if args.clean_only:
        builder.clean_build()
        return 0
    
    success = builder.build()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())