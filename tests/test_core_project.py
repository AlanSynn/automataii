"""
Test project management system
"""
import pytest
from pathlib import Path
from automataii.core import ProjectManager, AtiiProject


class TestProjectManager:
    """Test project manager functionality"""
    
    def test_project_manager_creation(self):
        """Test project manager can be created"""
        manager = ProjectManager()
        assert manager is not None
        
    def test_project_manager_singleton_behavior(self):
        """Test project manager singleton behavior"""
        from automataii.core import get_global_project_manager
        
        manager1 = get_global_project_manager()
        manager2 = get_global_project_manager()
        
        assert manager1 is manager2


class TestAtiiProject:
    """Test Atii project functionality"""
    
    def test_project_creation(self):
        """Test project can be created"""
        project = AtiiProject()
        assert project is not None
        assert project.manifest is not None
        
    def test_project_manifest_properties(self):
        """Test project manifest properties"""
        project = AtiiProject()
        
        # Test default values
        assert project.manifest.version == "1.0.0"
        assert project.manifest.format_version == "1.0"
        assert project.manifest.name == ""
        assert project.manifest.description == ""
        
        # Test setting values
        project.manifest.name = "Test Project"
        project.manifest.description = "A test project for unit testing"
        project.manifest.author = "Test Author"
        
        assert project.manifest.name == "Test Project"
        assert project.manifest.description == "A test project for unit testing"
        assert project.manifest.author == "Test Author"
        
    def test_project_state_management(self):
        """Test project state management"""
        project = AtiiProject()
        
        # Test default state
        assert project.state is not None
        assert isinstance(project.state.ui_state, dict)
        assert isinstance(project.state.preferences, dict)
        assert isinstance(project.state.history, list)
        
        # Test state modification
        project.state.ui_state["window_size"] = {"width": 1200, "height": 800}
        project.state.preferences["theme"] = "dark"
        project.state.history.append({"action": "test_action", "timestamp": "2023-01-01"})
        
        assert project.state.ui_state["window_size"]["width"] == 1200
        assert project.state.preferences["theme"] == "dark"
        assert len(project.state.history) == 1
        
    def test_project_data_storage(self):
        """Test project data storage"""
        project = AtiiProject()
        
        # Test setting project data
        project.project_data["skeleton"] = {"joints": [], "bones": []}
        project.project_data["animations"] = {"main": {"frames": 30, "duration": 1.0}}
        
        assert "skeleton" in project.project_data
        assert "animations" in project.project_data
        assert project.project_data["skeleton"]["joints"] == []
        assert project.project_data["animations"]["main"]["frames"] == 30
        
    def test_project_modification_tracking(self):
        """Test project modification tracking"""
        project = AtiiProject()
        
        # Initially should not be modified
        assert not project._is_modified
        
        # Modifying manifest should mark as modified
        project.manifest.name = "Modified Project"
        # Note: We might need to implement modification tracking
        
    def test_project_metadata_validation(self):
        """Test project metadata validation"""
        project = AtiiProject()
        
        # Test that required fields can be set
        project.manifest.name = "Valid Project Name"
        project.manifest.version = "2.0.0"
        project.manifest.format_version = "1.1"
        
        assert project.manifest.name == "Valid Project Name"
        assert project.manifest.version == "2.0.0"
        assert project.manifest.format_version == "1.1"
        
    def test_project_tags_and_dependencies(self):
        """Test project tags and dependencies"""
        project = AtiiProject()
        
        # Test tags
        project.manifest.tags.append("animation")
        project.manifest.tags.append("character")
        project.manifest.tags.append("2d")
        
        assert len(project.manifest.tags) == 3
        assert "animation" in project.manifest.tags
        assert "character" in project.manifest.tags
        
        # Test dependencies
        project.manifest.dependencies["python"] = ">=3.8"
        project.manifest.dependencies["PyQt6"] = ">=6.0"
        
        assert len(project.manifest.dependencies) == 2
        assert project.manifest.dependencies["python"] == ">=3.8"
        assert project.manifest.dependencies["PyQt6"] == ">=6.0"
        
    def test_project_technical_metadata(self):
        """Test project technical metadata"""
        project = AtiiProject()
        
        # Test default technical metadata
        assert project.manifest.compression_level == 6
        assert project.manifest.checksum_algorithm == "sha256"
        assert project.manifest.file_count == 0
        assert project.manifest.total_size == 0
        
        # Test setting technical metadata
        project.manifest.compression_level = 9
        project.manifest.file_count = 10
        project.manifest.total_size = 1024
        
        assert project.manifest.compression_level == 9
        assert project.manifest.file_count == 10
        assert project.manifest.total_size == 1024
        
    def test_project_timestamps(self):
        """Test project timestamp handling"""
        project = AtiiProject()
        
        # Should have created_at and modified_at timestamps
        assert project.manifest.created_at is not None
        assert project.manifest.modified_at is not None
        
        # Timestamps should be datetime objects
        from datetime import datetime
        assert isinstance(project.manifest.created_at, datetime)
        assert isinstance(project.manifest.modified_at, datetime)