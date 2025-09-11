#!/usr/bin/env python3
"""
Windows build script with WinSparkle auto-update support
"""

import os
import sys
import shutil
import subprocess
import tempfile
import logging
from pathlib import Path
import requests
import zipfile

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WindowsBuilder:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.build_dir = project_root / "scripts" / "build"
        self.dist_dir = project_root / "dist"
        self.winsparkle_version = "0.8.0"
        self.winsparkle_url = f"https://github.com/vslavik/winsparkle/releases/download/v{self.winsparkle_version}/WinSparkle-{self.winsparkle_version}.zip"
        self.nsis_installer = True
        
    def check_dependencies(self):
        """Check if required tools are installed"""
        required_tools = ['pyinstaller']
        optional_tools = ['makensis']  # NSIS for installer creation
        missing_tools = []
        
        for tool in required_tools:
            if shutil.which(tool) is None:
                missing_tools.append(tool)
        
        if missing_tools:
            logger.error(f"Missing required tools: {', '.join(missing_tools)}")
            if 'pyinstaller' in missing_tools:
                logger.info("Install PyInstaller: pip install pyinstaller")
            return False
        
        # Check for NSIS (optional)
        if shutil.which('makensis') is None:
            logger.warning("NSIS not found. Installer creation will be skipped.")
            logger.info("Download NSIS from: https://nsis.sourceforge.io/Download")
            self.nsis_installer = False
        
        return True
    
    def install_python_dependencies(self):
        """Install Python build dependencies"""
        logger.info("Checking Python dependencies...")
        
        # Check if PyInstaller is available
        try:
            subprocess.run([sys.executable, '-c', 'import PyInstaller'], check=True, capture_output=True)
            logger.info("PyInstaller is already available")
        except subprocess.CalledProcessError:
            logger.info("Installing PyInstaller...")
            subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyinstaller'], check=True)
        
        # Check Windows-specific dependencies
        try:
            subprocess.run([sys.executable, '-c', 'import win32api'], check=True, capture_output=True)
            logger.info("pywin32 is already available")
        except subprocess.CalledProcessError:
            logger.info("Installing pywin32...")
            subprocess.run([sys.executable, '-m', 'pip', 'install', 'pywin32'], check=True)
    
    def download_winsparkle(self):
        """Download WinSparkle library"""
        winsparkle_dir = self.build_dir / "WinSparkle"
        
        if winsparkle_dir.exists():
            logger.info("WinSparkle already downloaded.")
            return winsparkle_dir
        
        logger.info(f"Downloading WinSparkle {self.winsparkle_version}...")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            zip_path = temp_path / "winsparkle.zip"
            
            # Download WinSparkle
            response = requests.get(self.winsparkle_url, stream=True)
            response.raise_for_status()
            
            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Extract ZIP
            logger.info("Extracting WinSparkle...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_path)
            
            # Find extracted directory
            extracted_dirs = [d for d in temp_path.iterdir() if d.is_dir() and d.name.startswith('WinSparkle')]
            if not extracted_dirs:
                raise FileNotFoundError("WinSparkle directory not found in extracted files.")
            
            # Copy to build directory
            self.build_dir.mkdir(parents=True, exist_ok=True)
            shutil.copytree(extracted_dirs[0], winsparkle_dir)
            logger.info(f"WinSparkle installed at: {winsparkle_dir}")
        
        return winsparkle_dir
    
    def build_executable(self):
        """Build executable with PyInstaller"""
        logger.info("Building executable with PyInstaller...")
        
        spec_file = self.project_root / "packaging" / "pyinstaller" / "automataii.spec"
        if not spec_file.exists():
            raise FileNotFoundError(f"Spec file not found: {spec_file}")
        
        # Clean existing dist folder
        if self.dist_dir.exists():
            shutil.rmtree(self.dist_dir)
        
        # Run PyInstaller
        cmd = [sys.executable, '-m', 'PyInstaller', '--clean', str(spec_file)]
        subprocess.run(cmd, cwd=self.project_root, check=True)
        
        exe_path = self.dist_dir / "Automataii.exe"
        if not exe_path.exists():
            raise FileNotFoundError("Built executable not found.")
        
        logger.info(f"Executable built successfully: {exe_path}")
        return exe_path
    
    def build(self, create_installer: bool = True):
        """Execute complete build process"""
        logger.info("=== Starting Windows build ===")
        
        # Check dependencies
        if not self.check_dependencies():
            return False
        
        try:
            # 1. Install Python dependencies
            self.install_python_dependencies()
            
            # 2. Download WinSparkle
            self.download_winsparkle()
            
            # 3. Build executable
            exe_path = self.build_executable()
            
            logger.info(f"Final distribution file: {exe_path}")
            logger.info("=== Windows build complete ===")
            return True
            
        except Exception as e:
            logger.error(f"Build error: {e}")
            return False

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Build Automataii for Windows')
    parser.add_argument('--no-installer', action='store_true', help='Skip installer creation')
    
    args = parser.parse_args()
    
    project_root = Path(__file__).parent.parent
    builder = WindowsBuilder(project_root)
    
    success = builder.build(create_installer=not args.no_installer)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
