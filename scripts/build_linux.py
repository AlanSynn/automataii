#!/usr/bin/env python3
"""
Linux build script - AppImage generation with automatic update support
"""

import os
import sys
import shutil
import subprocess
import tempfile
import logging
from pathlib import Path
import requests
import stat

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LinuxBuilder:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.build_dir = project_root / "scripts" / "build"
        self.dist_dir = project_root / "dist"
        self.appimage_tool_url = "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
        
    def check_dependencies(self):
        """Check if required tools are installed"""
        required_tools = ['pyinstaller', 'wget', 'file']
        missing_tools = []
        
        for tool in required_tools:
            if shutil.which(tool) is None:
                missing_tools.append(tool)
        
        if missing_tools:
            logger.error(f"Missing required tools: {', '.join(missing_tools)}")
            if 'pyinstaller' in missing_tools:
                logger.info("Install PyInstaller: pip install pyinstaller")
            if 'wget' in missing_tools:
                logger.info("Install wget: sudo apt-get install wget or sudo yum install wget")
            return False
        
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
    
    def download_appimagetool(self):
        """Download AppImageTool"""
        appimagetool_path = self.build_dir / "appimagetool-x86_64.AppImage"
        
        if appimagetool_path.exists():
            logger.info("AppImageTool already downloaded.")
            return appimagetool_path
        
        logger.info("Downloading AppImageTool...")
        self.build_dir.mkdir(parents=True, exist_ok=True)
        
        response = requests.get(self.appimage_tool_url, stream=True)
        response.raise_for_status()
        
        with open(appimagetool_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # Make executable
        appimagetool_path.chmod(appimagetool_path.stat().st_mode | stat.S_IEXEC)
        logger.info(f"AppImageTool downloaded: {appimagetool_path}")
        
        return appimagetool_path
    
    def build_executable(self):
        """Build executable with PyInstaller"""
        logger.info("Building executable with PyInstaller...")
        
        spec_file = self.project_root / "automataii.spec"
        if not spec_file.exists():
            raise FileNotFoundError("automataii.spec file not found.")
        
        # Clean existing dist folder
        if self.dist_dir.exists():
            shutil.rmtree(self.dist_dir)
        
        # Run PyInstaller
        cmd = [sys.executable, '-m', 'PyInstaller', '--clean', str(spec_file)]
        subprocess.run(cmd, cwd=self.project_root, check=True)
        
        exe_dir = self.dist_dir / "Automataii"
        if not exe_dir.exists():
            raise FileNotFoundError("Built executable not found.")
        
        logger.info(f"Executable built successfully: {exe_dir}")
        return exe_dir
    
    def create_appdir(self, exe_dir: Path):
        """Create AppDir structure"""
        logger.info("Creating AppDir structure...")
        
        appdir_path = self.dist_dir / "Automataii.AppDir"
        
        # Remove existing AppDir
        if appdir_path.exists():
            shutil.rmtree(appdir_path)
        
        # Rename executable directory to AppDir
        shutil.move(str(exe_dir), str(appdir_path))
        
        # Create .desktop file
        desktop_content = """[Desktop Entry]
Name=Automataii
Exec=Automataii
Icon=automataii
Type=Application
Categories=Graphics;Development;
Comment=AI-powered character animation system
MimeType=image/png;image/jpeg;image/jpg;
StartupWMClass=Automataii
"""
        
        desktop_file = appdir_path / "automataii.desktop"
        with open(desktop_file, 'w') as f:
            f.write(desktop_content)
        
        # Create AppRun script
        apprun_content = """#!/bin/bash
cd "$(dirname "$0")"
exec ./Automataii "$@"
"""
        
        apprun_file = appdir_path / "AppRun"
        with open(apprun_file, 'w') as f:
            f.write(apprun_content)
        
        # Make executable
        apprun_file.chmod(apprun_file.stat().st_mode | stat.S_IEXEC)
        
        # Create icon file (default icon)
        icon_file = appdir_path / "automataii.png"
        self.create_default_icon(icon_file)
        
        logger.info(f"AppDir structure created: {appdir_path}")
        return appdir_path
    
    def create_default_icon(self, icon_path: Path):
        """Create default icon using PIL"""
        try:
            from PIL import Image, ImageDraw, ImageFont
            
            # Create 128x128 icon
            img = Image.new('RGBA', (128, 128), (70, 130, 180, 255))  # Steel Blue
            draw = ImageDraw.Draw(img)
            
            # Draw simple 'A' letter
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 80)
            except:
                font = ImageFont.load_default()
            
            # Calculate text size
            text = "A"
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            # Center text
            x = (128 - text_width) // 2
            y = (128 - text_height) // 2
            
            draw.text((x, y), text, fill=(255, 255, 255, 255), font=font)
            
            # Save as PNG
            img.save(icon_path, 'PNG')
            logger.info(f"Default icon created: {icon_path}")
            
        except ImportError:
            logger.warning("PIL not available, skipping default icon creation.")
            # Create minimal PNG file
            with open(icon_path, 'wb') as f:
                # Minimal PNG header
                f.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\xdac\xf8\x0f\x00\x00\x01\x00\x01\x00\x18\xdd\x8d\xb4\x00\x00\x00\x00IEND\xaeB`\x82')
    
    def create_appimage(self, appdir_path: Path, appimagetool_path: Path, update_info: str = None):
        """Create AppImage"""
        logger.info("Creating AppImage...")
        
        appimage_path = self.dist_dir / "Automataii-x86_64.AppImage"
        
        # Remove existing AppImage
        if appimage_path.exists():
            appimage_path.unlink()
        
        # Construct AppImageTool command
        cmd = [str(appimagetool_path), str(appdir_path)]
        
        # Add update information
        if update_info:
            cmd.extend(['-u', update_info])
        
        # Set environment variables (run without FUSE)
        env = os.environ.copy()
        env['ARCH'] = 'x86_64'
        
        # Create AppImage
        result = subprocess.run(cmd, cwd=self.dist_dir, env=env, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"AppImage creation failed: {result.stderr}")
            raise subprocess.CalledProcessError(result.returncode, cmd)
        
        # Find generated AppImage file
        for file in self.dist_dir.glob("Automataii-*.AppImage"):
            final_path = self.dist_dir / "Automataii-x86_64.AppImage"
            if file != final_path:
                shutil.move(str(file), str(final_path))
            appimage_path = final_path
            break
        
        if not appimage_path.exists():
            raise FileNotFoundError("Generated AppImage file not found.")
        
        # Make executable
        appimage_path.chmod(appimage_path.stat().st_mode | stat.S_IEXEC)
        
        logger.info(f"AppImage created: {appimage_path}")
        return appimage_path
    
    def build(self, update_url: str = None, create_zsync: bool = True):
        """Execute complete build process"""
        logger.info("=== Starting Linux build ===")
        
        # Check dependencies
        if not self.check_dependencies():
            return False
        
        try:
            # 1. Install Python dependencies
            self.install_python_dependencies()
            
            # 2. Download AppImageTool
            appimagetool_path = self.download_appimagetool()
            
            # 3. Build executable
            exe_dir = self.build_executable()
            
            # 4. Create AppDir structure
            appdir_path = self.create_appdir(exe_dir)
            
            # 5. Configure update information
            update_info = None
            if update_url:
                update_info = f"zsync|{update_url}/Automataii-latest-x86_64.AppImage.zsync"
            
            # 6. Create AppImage
            appimage_path = self.create_appimage(appdir_path, appimagetool_path, update_info)
            
            logger.info(f"Final distribution file: {appimage_path}")
            logger.info("=== Linux build complete ===")
            return True
            
        except Exception as e:
            logger.error(f"Build error: {e}")
            return False

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Build Automataii for Linux')
    parser.add_argument('--update-url', type=str, help='Automatic update server URL')
    parser.add_argument('--no-zsync', action='store_true', help='Skip zsync file creation')
    
    args = parser.parse_args()
    
    project_root = Path(__file__).parent.parent
    builder = LinuxBuilder(project_root)
    
    success = builder.build(
        update_url=args.update_url,
        create_zsync=not args.no_zsync
    )
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()