"""
OS-level file association handler for .atii project files.
"""

import os
import sys
import platform
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List
import logging
import mimetypes
from PIL import Image, ImageDraw, ImageFont
import io
from datetime import datetime

from automataii.core.container import Injectable
from .project_format import AtiiProject


class FileIntegration(Injectable):
    """
    Handles OS-specific file integration for .atii project files.
    
    Features:
    - MIME type registration
    - File association registration
    - Thumbnail generation
    - Quick Look support (macOS)
    - Context menu integration
    - Drag and drop support
    """
    
    def __init__(self):
        self._logger = logging.getLogger(__name__)
        self._system = platform.system().lower()
        self._mime_type = "application/x-automataii-project"
        self._file_extension = ".atii"
        
        # Initialize MIME type
        mimetypes.add_type(self._mime_type, self._file_extension)
    
    def register_file_associations(self, app_path: Optional[Path] = None) -> bool:
        """
        Register .atii file associations with the OS.
        
        Args:
            app_path: Path to application executable
            
        Returns:
            True if registration successful
        """
        if not app_path:
            app_path = Path(sys.executable)
        
        try:
            if self._system == "windows":
                return self._register_windows_associations(app_path)
            elif self._system == "darwin":
                return self._register_macos_associations(app_path)
            elif self._system == "linux":
                return self._register_linux_associations(app_path)
            else:
                self._logger.warning(f"Unsupported system: {self._system}")
                return False
                
        except Exception as e:
            self._logger.error(f"Failed to register file associations: {e}", exc_info=True)
            return False
    
    def _register_windows_associations(self, app_path: Path) -> bool:
        """Register file associations on Windows."""
        import winreg
        
        try:
            # Register file extension
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, 
                                 rf"Software\Classes\{self._file_extension}") as key:
                winreg.SetValue(key, None, winreg.REG_SZ, "AutomataiProject")
            
            # Register application
            prog_id = "AutomataiProject"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, 
                                 rf"Software\Classes\{prog_id}") as key:
                winreg.SetValue(key, None, winreg.REG_SZ, "Automataii Project")
                
                # Set icon
                with winreg.CreateKey(key, "DefaultIcon") as icon_key:
                    icon_path = self._get_icon_path()
                    winreg.SetValue(icon_key, None, winreg.REG_SZ, str(icon_path))
                
                # Set open command
                with winreg.CreateKey(key, r"shell\open\command") as cmd_key:
                    command = f'"{app_path}" "%1"'
                    winreg.SetValue(cmd_key, None, winreg.REG_SZ, command)
            
            # Notify shell of changes
            import ctypes
            ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
            
            self._logger.info("Windows file associations registered")
            return True
            
        except Exception as e:
            self._logger.error(f"Windows registration failed: {e}")
            return False
    
    def _register_macos_associations(self, app_path: Path) -> bool:
        """Register file associations on macOS."""
        try:
            # Create .app bundle info if needed
            app_bundle = self._find_or_create_app_bundle(app_path)
            if not app_bundle:
                return False
            
            # Update Info.plist
            plist_path = app_bundle / "Contents" / "Info.plist"
            if not plist_path.exists():
                self._create_info_plist(plist_path)
            
            # Register with Launch Services
            result = subprocess.run([
                "/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister",
                "-f", str(app_bundle)
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                self._logger.info("macOS file associations registered")
                return True
            else:
                self._logger.error(f"lsregister failed: {result.stderr}")
                return False
                
        except Exception as e:
            self._logger.error(f"macOS registration failed: {e}")
            return False
    
    def _register_linux_associations(self, app_path: Path) -> bool:
        """Register file associations on Linux."""
        try:
            # Create .desktop file
            desktop_file = self._create_desktop_file(app_path)
            if not desktop_file:
                return False
            
            # Update MIME database
            self._create_mime_xml()
            
            # Update desktop database
            subprocess.run(["update-desktop-database", 
                          str(Path.home() / ".local" / "share" / "applications")],
                         capture_output=True)
            
            subprocess.run(["update-mime-database", 
                          str(Path.home() / ".local" / "share" / "mime")],
                         capture_output=True)
            
            self._logger.info("Linux file associations registered")
            return True
            
        except Exception as e:
            self._logger.error(f"Linux registration failed: {e}")
            return False
    
    def generate_thumbnail(self, project_path: Path, size: tuple = (256, 256)) -> Optional[bytes]:
        """
        Generate thumbnail for project file.
        
        Args:
            project_path: Path to .atii project
            size: Thumbnail size (width, height)
            
        Returns:
            PNG thumbnail data or None if failed
        """
        try:
            # Load project to get thumbnail data
            project = AtiiProject(project_path)
            project.load()
            
            # Check if project has embedded thumbnail
            if project.manifest.thumbnail:
                thumbnail_data = project.get_asset(project.manifest.thumbnail)
                if thumbnail_data:
                    return self._resize_image(thumbnail_data, size)
            
            # Generate default thumbnail
            return self._generate_default_thumbnail(project, size)
            
        except Exception as e:
            self._logger.error(f"Failed to generate thumbnail: {e}")
            return None
    
    def _resize_image(self, image_data: bytes, size: tuple) -> bytes:
        """Resize image data to thumbnail size."""
        with Image.open(io.BytesIO(image_data)) as img:
            img.thumbnail(size, Image.Resampling.LANCZOS)
            
            # Convert to RGB if necessary
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Save as PNG
            output = io.BytesIO()
            img.save(output, format='PNG')
            return output.getvalue()
    
    def _generate_default_thumbnail(self, project: AtiiProject, size: tuple) -> bytes:
        """Generate default thumbnail for project."""
        width, height = size
        
        # Create image with gradient background
        img = Image.new('RGB', (width, height), color='#f0f0f0')
        draw = ImageDraw.Draw(img)
        
        # Draw gradient background
        for y in range(height):
            color = int(240 - (y / height) * 40)
            draw.line([(0, y), (width, y)], fill=(color, color, color + 10))
        
        # Draw project icon/logo
        icon_size = min(width, height) // 3
        icon_x = (width - icon_size) // 2
        icon_y = (height - icon_size) // 3
        
        # Simple geometric shape as project icon
        draw.ellipse([
            icon_x, icon_y,
            icon_x + icon_size, icon_y + icon_size
        ], fill='#4a90e2', outline='#2e5c8a', width=3)
        
        # Add project name
        try:
            # Try to load a font
            font = ImageFont.truetype("arial.ttf", 16)
        except:
            font = ImageFont.load_default()
        
        text = project.name or "Automataii Project"
        text_bbox = draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        
        text_x = (width - text_width) // 2
        text_y = icon_y + icon_size + 20
        
        # Draw text with shadow
        draw.text((text_x + 1, text_y + 1), text, fill='#888888', font=font)
        draw.text((text_x, text_y), text, fill='#333333', font=font)
        
        # Add file type indicator
        type_text = ".atii"
        type_bbox = draw.textbbox((0, 0), type_text, font=font)
        type_width = type_bbox[2] - type_bbox[0]
        
        draw.text((width - type_width - 10, height - 25), type_text, 
                 fill='#666666', font=font)
        
        # Save as PNG
        output = io.BytesIO()
        img.save(output, format='PNG')
        return output.getvalue()
    
    def create_quick_look_plugin(self) -> bool:
        """
        Create Quick Look plugin for macOS (placeholder implementation).
        
        Returns:
            True if plugin created successfully
        """
        if self._system != "darwin":
            return False
        
        # This would involve creating a proper Quick Look plugin bundle
        # For now, just return False as this is a complex implementation
        self._logger.info("Quick Look plugin creation not implemented")
        return False
    
    def handle_drag_drop(self, file_paths: List[Path]) -> List[Path]:
        """
        Handle drag and drop of files onto application.
        
        Args:
            file_paths: List of dropped file paths
            
        Returns:
            List of valid .atii project files
        """
        valid_projects = []
        
        for path in file_paths:
            if path.suffix.lower() == self._file_extension:
                try:
                    # Validate project file
                    project = AtiiProject(path)
                    project.load()
                    valid_projects.append(path)
                except Exception as e:
                    self._logger.warning(f"Invalid project file {path}: {e}")
        
        return valid_projects
    
    def get_file_info(self, project_path: Path) -> Dict[str, Any]:
        """
        Get file information for project.
        
        Args:
            project_path: Path to project file
            
        Returns:
            Dictionary with file information
        """
        try:
            project = AtiiProject(project_path)
            project.load()
            
            stat = project_path.stat()
            
            return {
                'name': project.name,
                'description': project.manifest.description,
                'author': project.manifest.author,
                'version': project.manifest.version,
                'created': project.manifest.created_at,
                'modified': project.manifest.modified_at,
                'file_size': stat.st_size,
                'file_modified': datetime.fromtimestamp(stat.st_mtime),
                'asset_count': len(project.list_assets()),
                'tags': project.manifest.tags
            }
            
        except Exception as e:
            self._logger.error(f"Failed to get file info: {e}")
            return {
                'name': project_path.stem,
                'error': str(e)
            }
    
    def _get_icon_path(self) -> Path:
        """Get path to application icon."""
        # Return path to icon file (implementation depends on packaging)
        return Path(__file__).parent.parent.parent / "resources" / "icon.ico"
    
    def _find_or_create_app_bundle(self, app_path: Path) -> Optional[Path]:
        """Find or create macOS app bundle."""
        # Look for existing .app bundle
        current = app_path
        while current.parent != current:
            if current.suffix == '.app':
                return current
            current = current.parent
        
        # Create minimal app bundle structure
        bundle_name = "Automataii.app"
        bundle_path = app_path.parent / bundle_name
        
        try:
            contents_dir = bundle_path / "Contents"
            macos_dir = contents_dir / "MacOS"
            resources_dir = contents_dir / "Resources"
            
            contents_dir.mkdir(parents=True, exist_ok=True)
            macos_dir.mkdir(exist_ok=True)
            resources_dir.mkdir(exist_ok=True)
            
            return bundle_path
            
        except Exception as e:
            self._logger.error(f"Failed to create app bundle: {e}")
            return None
    
    def _create_info_plist(self, plist_path: Path) -> None:
        """Create Info.plist for macOS app bundle."""
        plist_content = f'''
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleIdentifier</key>
    <string>com.automataii.app</string>
    <key>CFBundleName</key>
    <string>Automataii</string>
    <key>CFBundleDisplayName</key>
    <string>Automataii</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleExecutable</key>
    <string>automataii</string>
    <key>CFBundleDocumentTypes</key>
    <array>
        <dict>
            <key>CFBundleTypeExtensions</key>
            <array>
                <string>atii</string>
            </array>
            <key>CFBundleTypeIconFile</key>
            <string>project_icon</string>
            <key>CFBundleTypeName</key>
            <string>Automataii Project</string>
            <key>CFBundleTypeRole</key>
            <string>Editor</string>
            <key>LSHandlerRank</key>
            <string>Owner</string>
        </dict>
    </array>
</dict>
</plist>
'''
        
        plist_path.parent.mkdir(parents=True, exist_ok=True)
        with open(plist_path, 'w') as f:
            f.write(plist_content)
    
    def _create_desktop_file(self, app_path: Path) -> Optional[Path]:
        """Create .desktop file for Linux."""
        desktop_dir = Path.home() / ".local" / "share" / "applications"
        desktop_dir.mkdir(parents=True, exist_ok=True)
        
        desktop_file = desktop_dir / "automataii.desktop"
        
        desktop_content = f'''
[Desktop Entry]
Name=Automataii
Comment=Automataii Project Editor
Exec={app_path} %f
Icon=automataii
Terminal=false
Type=Application
Categories=Graphics;Engineering;
MimeType={self._mime_type};
'''
        
        try:
            with open(desktop_file, 'w') as f:
                f.write(desktop_content)
            
            # Make executable
            desktop_file.chmod(0o755)
            return desktop_file
            
        except Exception as e:
            self._logger.error(f"Failed to create desktop file: {e}")
            return None
    
    def _create_mime_xml(self) -> None:
        """Create MIME type XML for Linux."""
        mime_dir = Path.home() / ".local" / "share" / "mime" / "packages"
        mime_dir.mkdir(parents=True, exist_ok=True)
        
        mime_file = mime_dir / "automataii.xml"
        
        mime_content = f'''
<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
    <mime-type type="{self._mime_type}">
        <comment>Automataii Project</comment>
        <glob pattern="*{self._file_extension}"/>
        <magic priority="50">
            <match type="string" offset="0" value="PK"/>
        </magic>
    </mime-type>
</mime-info>
'''
        
        try:
            with open(mime_file, 'w') as f:
                f.write(mime_content)
        except Exception as e:
            self._logger.error(f"Failed to create MIME XML: {e}")


# Global file integration instance
_global_file_integration: Optional[FileIntegration] = None


def get_global_file_integration() -> FileIntegration:
    """Get the global file integration handler."""
    global _global_file_integration
    if _global_file_integration is None:
        _global_file_integration = FileIntegration()
    return _global_file_integration