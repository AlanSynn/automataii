"""
.atii project file format implementation.
"""

import json
import zipfile
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from datetime import datetime
import logging

from automataii.core.serialization.base import Serializable
from automataii.core.events import EventBus, get_global_event_bus
from automataii.core.events.base import ProjectLoaded, ProjectSaved


@dataclass
class ProjectManifest(Serializable):
    """Project manifest containing metadata and version info."""
    
    version: str = "1.0.0"
    format_version: str = "1.0"
    name: str = ""
    description: str = ""
    author: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    modified_at: datetime = field(default_factory=datetime.now)
    dependencies: Dict[str, str] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    thumbnail: Optional[str] = None  # Path to thumbnail image
    
    # Technical metadata
    compression_level: int = 6
    checksum_algorithm: str = "sha256"
    file_count: int = 0
    total_size: int = 0


@dataclass
class ProjectState(Serializable):
    """Application state that should be preserved with the project."""
    
    ui_state: Dict[str, Any] = field(default_factory=dict)
    preferences: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict[str, Any]] = field(default_factory=list)
    bookmarks: List[str] = field(default_factory=list)
    recent_files: List[str] = field(default_factory=list)


class AtiiProject:
    """
    Manages .atii project files using ZIP-based container format.
    
    Structure:
    ├── manifest.json           # Project metadata
    ├── project.json           # Core project data
    ├── state/                 # Application state
    │   ├── ui_state.json     # Window layouts, panel positions
    │   ├── preferences.json   # User preferences
    │   └── history.json      # Undo/redo history
    ├── assets/               # Images, textures, models
    ├── animations/           # Animation data
    ├── mechanisms/           # Mechanism definitions
    └── cache/               # Optional cached data
    """
    
    def __init__(self, file_path: Optional[Union[str, Path]] = None):
        self.file_path = Path(file_path) if file_path else None
        self.manifest = ProjectManifest()
        self.project_data: Dict[str, Any] = {}
        self.state = ProjectState()
        self._assets: Dict[str, bytes] = {}
        self._is_modified = False
        self._logger = logging.getLogger(__name__)
        self._event_bus: EventBus = get_global_event_bus()
        
        if self.file_path and self.file_path.exists():
            self.load()
    
    @property
    def is_modified(self) -> bool:
        """Check if project has unsaved changes."""
        return self._is_modified
    
    @property
    def name(self) -> str:
        """Get project name."""
        return self.manifest.name
    
    @name.setter
    def name(self, value: str) -> None:
        """Set project name."""
        self.manifest.name = value
        self._mark_modified()
    
    def load(self, file_path: Optional[Union[str, Path]] = None) -> None:
        """
        Load project from .atii file.
        
        Args:
            file_path: Path to .atii file (optional if already set)
        """
        if file_path:
            self.file_path = Path(file_path)
        
        if not self.file_path or not self.file_path.exists():
            raise FileNotFoundError(f"Project file not found: {self.file_path}")
        
        try:
            with zipfile.ZipFile(self.file_path, 'r') as archive:
                # Load manifest
                if 'manifest.json' in archive.namelist():
                    manifest_data = json.loads(archive.read('manifest.json').decode('utf-8'))
                    self.manifest = ProjectManifest.from_dict(manifest_data)
                
                # Load project data
                if 'project.json' in archive.namelist():
                    self.project_data = json.loads(archive.read('project.json').decode('utf-8'))
                
                # Load state
                self._load_state_from_archive(archive)
                
                # Load assets
                self._load_assets_from_archive(archive)
            
            self._is_modified = False
            self._logger.info(f"Loaded project: {self.manifest.name}")
            
            # Fire event
            event = ProjectLoaded(
                aggregate_id=str(self.file_path),
                project_path=str(self.file_path),
                project_name=self.manifest.name
            )
            self._event_bus.publish(event)
            
        except Exception as e:
            self._logger.error(f"Failed to load project: {e}")
            raise
    
    def save(self, file_path: Optional[Union[str, Path]] = None) -> None:
        """
        Save project to .atii file.
        
        Args:
            file_path: Path to save to (optional if already set)
        """
        if file_path:
            self.file_path = Path(file_path)
        
        if not self.file_path:
            raise ValueError("No file path specified for saving")
        
        # Ensure parent directory exists
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Update manifest
        self.manifest.modified_at = datetime.now()
        
        try:
            # Use temporary file for atomic save
            temp_path = self.file_path.with_suffix('.tmp')
            
            with zipfile.ZipFile(temp_path, 'w', zipfile.ZIP_DEFLATED, 
                               compresslevel=self.manifest.compression_level) as archive:
                
                # Save manifest
                manifest_json = json.dumps(self.manifest.to_dict(), indent=2)
                archive.writestr('manifest.json', manifest_json)
                
                # Save project data
                project_json = json.dumps(self.project_data, indent=2)
                archive.writestr('project.json', project_json)
                
                # Save state
                self._save_state_to_archive(archive)
                
                # Save assets
                self._save_assets_to_archive(archive)
            
            # Atomic rename
            temp_path.replace(self.file_path)
            
            self._is_modified = False
            self._logger.info(f"Saved project: {self.manifest.name}")
            
            # Fire event
            event = ProjectSaved(
                aggregate_id=str(self.file_path),
                project_path=str(self.file_path),
                save_time=0.0  # TODO: measure actual save time
            )
            self._event_bus.publish(event)
            
        except Exception as e:
            self._logger.error(f"Failed to save project: {e}")
            # Clean up temp file
            if temp_path.exists():
                temp_path.unlink()
            raise
    
    def _load_state_from_archive(self, archive: zipfile.ZipFile) -> None:
        """Load state data from archive."""
        state_files = {
            'ui_state': 'state/ui_state.json',
            'preferences': 'state/preferences.json', 
            'history': 'state/history.json'
        }
        
        for attr, path in state_files.items():
            if path in archive.namelist():
                data = json.loads(archive.read(path).decode('utf-8'))
                setattr(self.state, attr, data)
    
    def _save_state_to_archive(self, archive: zipfile.ZipFile) -> None:
        """Save state data to archive."""
        state_data = {
            'state/ui_state.json': self.state.ui_state,
            'state/preferences.json': self.state.preferences,
            'state/history.json': self.state.history
        }
        
        for path, data in state_data.items():
            json_str = json.dumps(data, indent=2)
            archive.writestr(path, json_str)
    
    def _load_assets_from_archive(self, archive: zipfile.ZipFile) -> None:
        """Load binary assets from archive."""
        for file_info in archive.infolist():
            if file_info.filename.startswith('assets/'):
                self._assets[file_info.filename] = archive.read(file_info.filename)
    
    def _save_assets_to_archive(self, archive: zipfile.ZipFile) -> None:
        """Save binary assets to archive."""
        for asset_path, asset_data in self._assets.items():
            archive.writestr(asset_path, asset_data)
    
    def add_asset(self, name: str, data: bytes, category: str = "images") -> str:
        """
        Add binary asset to project.
        
        Args:
            name: Asset name/filename
            data: Binary data
            category: Asset category (images, textures, models, etc.)
            
        Returns:
            Asset path within project
        """
        asset_path = f"assets/{category}/{name}"
        self._assets[asset_path] = data
        self._mark_modified()
        return asset_path
    
    def get_asset(self, path: str) -> Optional[bytes]:
        """Get binary asset by path."""
        return self._assets.get(path)
    
    def remove_asset(self, path: str) -> bool:
        """Remove asset by path."""
        if path in self._assets:
            del self._assets[path]
            self._mark_modified()
            return True
        return False
    
    def list_assets(self, category: Optional[str] = None) -> List[str]:
        """List all asset paths, optionally filtered by category."""
        if category:
            prefix = f"assets/{category}/"
            return [path for path in self._assets.keys() if path.startswith(prefix)]
        return list(self._assets.keys())
    
    def set_project_data(self, key: str, value: Any) -> None:
        """Set project data value."""
        self.project_data[key] = value
        self._mark_modified()
    
    def get_project_data(self, key: str, default: Any = None) -> Any:
        """Get project data value."""
        return self.project_data.get(key, default)
    
    def _mark_modified(self) -> None:
        """Mark project as modified."""
        self._is_modified = True
    
    def get_info(self) -> Dict[str, Any]:
        """Get project information."""
        return {
            'name': self.manifest.name,
            'description': self.manifest.description,
            'author': self.manifest.author,
            'version': self.manifest.version,
            'created_at': self.manifest.created_at,
            'modified_at': self.manifest.modified_at,
            'file_path': str(self.file_path) if self.file_path else None,
            'is_modified': self._is_modified,
            'asset_count': len(self._assets),
            'tags': self.manifest.tags
        }
    
    def validate(self) -> List[str]:
        """
        Validate project integrity.
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Check required fields
        if not self.manifest.name:
            errors.append("Project name is required")
        
        if not self.manifest.version:
            errors.append("Project version is required")
        
        # Validate project data structure
        try:
            json.dumps(self.project_data)
        except (TypeError, ValueError) as e:
            errors.append(f"Invalid project data: {e}")
        
        return errors
    
    def create_backup(self, backup_dir: Optional[Union[str, Path]] = None) -> Path:
        """
        Create backup of current project.
        
        Args:
            backup_dir: Directory to save backup (default: same as project)
            
        Returns:
            Path to backup file
        """
        if not self.file_path:
            raise ValueError("Cannot backup unsaved project")
        
        backup_dir = Path(backup_dir) if backup_dir else self.file_path.parent
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{self.file_path.stem}_backup_{timestamp}.atii"
        backup_path = backup_dir / backup_name
        
        # Copy current file
        if self.file_path.exists():
            import shutil
            shutil.copy2(self.file_path, backup_path)
            self._logger.info(f"Created backup: {backup_path}")
        
        return backup_path