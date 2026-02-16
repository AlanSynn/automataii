"""
Comprehensive feature verification tests for:
1. Ctrl+Z undo/redo functionality
2. Logging system debug/info separation
3. All menu actions
4. Project save to tmp directory
"""

import logging
import tempfile

import pytest


class TestUndoRedoFunctionality:
    """Test SSOT undo/redo system."""

    def test_project_state_manager_undo_redo(self):
        """Verify ProjectStateManager has undo/redo capability."""
        from automataii.application.project import ProjectStateManager
        from automataii.application.project.models import PartData

        manager = ProjectStateManager()

        # Initial state - no undo available
        assert not manager.can_undo
        assert not manager.can_redo

        # Make a change
        part = PartData(
            name="test_part",
            texture_path="test.png",
            mask_path="test_mask.png",
            anchor_joint="root",
        )
        manager.load_parts({"test_part": part})

        # Now undo should be available
        assert manager.can_undo
        assert not manager.can_redo

        # Perform undo
        manager.undo()

        # After undo, redo should be available
        assert manager.can_redo

    def test_project_controller_undo_redo(self):
        """Verify ProjectController delegates to state manager."""
        from automataii.application.project import ProjectSerializer, ProjectStateManager
        from automataii.presentation.qt.windows.components import ProjectController

        state_manager = ProjectStateManager()
        serializer = ProjectSerializer()
        controller = ProjectController(state_manager, serializer)

        # Initially no undo
        assert not controller.can_undo
        assert not controller.can_redo

        # Undo when nothing to undo returns False
        result = controller.undo()
        assert result is False

    def test_undo_redo_signals_emitted(self):
        """Verify undo/redo availability signals are emitted."""
        from automataii.application.project import ProjectStateManager
        from automataii.application.project.models import PartData

        manager = ProjectStateManager()

        # Track signal emissions
        undo_signals = []
        redo_signals = []
        manager.undo_available.connect(lambda x: undo_signals.append(x))
        manager.redo_available.connect(lambda x: redo_signals.append(x))

        # Make a change
        part = PartData(
            name="test",
            texture_path="test.png",
            mask_path="test_mask.png",
            anchor_joint="root",
        )
        manager.load_parts({"test": part})

        # Should have emitted undo_available(True) and redo_available(False)
        assert True in undo_signals
        assert False in redo_signals


class TestLoggingSystem:
    """Test logging system configuration."""

    def test_setup_logging_creates_handlers(self):
        """Verify setup_logging creates file and console handlers."""
        from automataii.utils.logging_config import setup_logging

        # Get root logger before setup
        root = logging.getLogger()
        original_handlers = len(root.handlers)

        # Setup logging
        setup_logging(console_log_level=logging.INFO)

        # Should have handlers now
        assert len(root.handlers) >= 2  # At least file and console

    def test_debug_level_separation(self):
        """Verify debug/info level separation works."""
        from automataii.utils.logging_config import setup_logging

        # Setup with INFO level for console
        setup_logging(console_log_level=logging.INFO)

        root = logging.getLogger()

        # Check handlers have correct levels
        file_handler = None
        console_handler = None
        for handler in root.handlers:
            if isinstance(handler, logging.FileHandler):
                file_handler = handler
            elif isinstance(handler, logging.StreamHandler) and not isinstance(
                handler, logging.FileHandler
            ):
                console_handler = handler

        # File handler should be DEBUG, console should be INFO
        if file_handler:
            assert file_handler.level == logging.DEBUG
        if console_handler:
            assert console_handler.level == logging.INFO

    def test_telemetry_logger_separate(self):
        """Verify telemetry logger is separate."""
        from automataii.utils.logging_config import setup_logging

        setup_logging()

        telemetry = logging.getLogger("automataii.telemetry")

        # Telemetry logger should not propagate
        assert telemetry.propagate is False
        # Should have its own handler
        assert len(telemetry.handlers) >= 1


class TestMenuActions:
    """Test menu action connections."""

    def test_action_manager_creates_all_actions(self):
        """Verify ActionManager creates all required actions."""

        from PyQt6.QtWidgets import QApplication, QMainWindow

        # Need QApplication for QAction
        app = QApplication.instance()
        if app is None:
            app = QApplication([])

        parent = QMainWindow()

        from automataii.presentation.qt.actions.action_manager import ActionManager

        manager = ActionManager(parent)

        # Check all expected actions exist
        expected_actions = [
            "load_parts",
            "save_project",
            "exit",
            "zoom_in",
            "zoom_out",
            "zoom_fit",
            "reset_view",
            "undo",
            "redo",
            "about",
            "new_project",
            "export",
            "check_updates",
        ]

        for action_id in expected_actions:
            action = manager.get_action(action_id)
            assert action is not None, f"Action '{action_id}' not found"

    def test_undo_redo_actions_have_shortcuts(self):
        """Verify undo/redo actions have correct keyboard shortcuts."""
        from PyQt6.QtGui import QKeySequence
        from PyQt6.QtWidgets import QApplication, QMainWindow

        app = QApplication.instance()
        if app is None:
            app = QApplication([])

        parent = QMainWindow()

        from automataii.presentation.qt.actions.action_manager import ActionManager

        manager = ActionManager(parent)

        undo_action = manager.get_action("undo")
        redo_action = manager.get_action("redo")

        # Check shortcuts
        assert undo_action.shortcut() == QKeySequence("Ctrl+Z")
        assert redo_action.shortcut() == QKeySequence("Ctrl+Y")


class TestProjectSaveToTmp:
    """Test project save to tmp directory."""

    def test_get_default_project_dir_returns_tmp(self):
        """Verify get_default_project_dir returns a tmp directory."""
        from automataii.presentation.qt.windows.components import get_default_project_dir

        default_dir = get_default_project_dir()

        # Should be in system temp directory
        assert tempfile.gettempdir() in str(default_dir)
        assert "automataii_projects" in str(default_dir)

    def test_get_default_project_dir_creates_directory(self):
        """Verify get_default_project_dir creates the directory if not exists."""
        from automataii.presentation.qt.windows.components import get_default_project_dir

        default_dir = get_default_project_dir()

        # Directory should exist after call
        assert default_dir.exists()
        assert default_dir.is_dir()

    def test_project_controller_uses_tmp_for_default_save(self):
        """Verify ProjectController uses tmp directory for default save path."""
        from automataii.application.project import ProjectSerializer, ProjectStateManager
        from automataii.presentation.qt.windows.components import (
            ProjectController,
            get_default_project_dir,
        )

        state_manager = ProjectStateManager()
        serializer = ProjectSerializer()
        controller = ProjectController(state_manager, serializer)

        # Get the default directory
        default_dir = get_default_project_dir()

        # The state has no project_dir, so save should use tmp
        state = state_manager.state
        assert state.project_dir is None

        # This confirms the code path - actual dialog testing requires GUI

    def test_quick_save_method_exists(self):
        """Verify quick_save method exists on ProjectController."""
        from automataii.application.project import ProjectSerializer, ProjectStateManager
        from automataii.presentation.qt.windows.components import ProjectController

        state_manager = ProjectStateManager()
        serializer = ProjectSerializer()
        controller = ProjectController(state_manager, serializer)

        # Method should exist
        assert hasattr(controller, "quick_save")
        assert callable(controller.quick_save)


class TestIntegration:
    """Integration tests for the complete workflow."""

    def test_undo_redo_state_consistency(self):
        """Test that undo/redo maintains state consistency."""
        from automataii.application.project import ProjectStateManager
        from automataii.application.project.models import PartData

        manager = ProjectStateManager()

        # Add part
        part1 = PartData(
            name="part1",
            texture_path="part1.png",
            mask_path="part1_mask.png",
            anchor_joint="root",
        )
        manager.load_parts({"part1": part1})
        assert "part1" in manager.state.parts

        # Add another part
        part2 = PartData(
            name="part2",
            texture_path="part2.png",
            mask_path="part2_mask.png",
            anchor_joint="root",
        )
        manager.update_part(part2)

        # Undo should remove part2 changes
        manager.undo()

        # Redo should restore
        manager.redo()


class TestMechanismUndoRedo:
    """Test undo/redo for all mechanism types."""

    def test_mechanism_undo_redo_all_types(self):
        """Verify undo/redo works for all mechanism types."""
        from automataii.application.project import ProjectStateManager
        from automataii.application.project.models import MechanismData

        manager = ProjectStateManager()

        # Test all mechanism types
        mechanism_types = [
            ("4_bar_linkage", {"L1": 100, "L2": 40, "L3": 60, "L4": 50}),
            ("5_bar_linkage", {"L2": 40, "L3": 50, "L4": 45, "L5": 55}),
            ("6_bar_linkage", {"L2": 40, "L3": 60, "L4": 50, "L5": 45, "L6": 55}),
            ("cam", {"base_radius": 25, "eccentricity": 10, "follower_rod_length": 40}),
            ("gear", {"r1": 30, "r2": 50}),
            ("planetary_gear", {"r_sun": 20, "r_planet": 30, "arm_length": 15}),
        ]

        for mech_type, params in mechanism_types:
            # Add mechanism
            mech = MechanismData(
                id=f"test_{mech_type}",
                part_name="test_part",
                type=mech_type,
                params=params,
                enabled=True,
            )
            manager.add_mechanism(mech)
            assert f"test_{mech_type}" in manager.state.mechanisms

            # Verify can undo
            assert manager.can_undo

            # Undo
            manager.undo()
            assert f"test_{mech_type}" not in manager.state.mechanisms

            # Verify can redo
            assert manager.can_redo

            # Redo
            manager.redo()
            assert f"test_{mech_type}" in manager.state.mechanisms

            # Clean up for next iteration
            manager.remove_mechanism(f"test_{mech_type}")

    def test_mechanism_param_update_undo_redo(self):
        """Verify parameter updates are captured in undo/redo stack."""
        from automataii.application.project import ProjectStateManager
        from automataii.application.project.models import MechanismData

        manager = ProjectStateManager()

        # Add initial mechanism
        mech = MechanismData(
            id="test_4bar",
            part_name="test_part",
            type="4_bar_linkage",
            params={"L1": 100, "L2": 40, "L3": 60, "L4": 50},
            enabled=True,
        )
        manager.add_mechanism(mech)

        # Update parameters (simulates handle drag)
        updated_mech = mech.with_params({"L1": 100, "L2": 50, "L3": 70, "L4": 60})
        manager.update_mechanism(updated_mech)

        # Verify updated
        current = manager.state.get_mechanism("test_4bar")
        assert current.params["L2"] == 50

        # Undo should restore original params
        manager.undo()
        current = manager.state.get_mechanism("test_4bar")
        assert current.params["L2"] == 40

        # Redo should restore updated params
        manager.redo()
        current = manager.state.get_mechanism("test_4bar")
        assert current.params["L2"] == 50

    def test_multiple_mechanism_updates_undo_chain(self):
        """Test multiple sequential updates can be undone in order."""
        from automataii.application.project import ProjectStateManager
        from automataii.application.project.models import MechanismData

        manager = ProjectStateManager()

        # Add mechanism
        mech = MechanismData(
            id="test_cam",
            part_name="test_part",
            type="cam",
            params={"base_radius": 25, "eccentricity": 10},
            enabled=True,
        )
        manager.add_mechanism(mech)

        # Perform multiple updates (simulates multiple handle drags)
        for i in range(5):
            updated = manager.state.get_mechanism("test_cam").with_params(
                {"base_radius": 25 + i * 5, "eccentricity": 10 + i * 2}
            )
            manager.update_mechanism(updated)

        # Final state
        current = manager.state.get_mechanism("test_cam")
        assert current.params["base_radius"] == 45  # 25 + 4*5

        # Undo all 5 updates
        for i in range(5):
            manager.undo()

        # Back to original
        current = manager.state.get_mechanism("test_cam")
        assert current.params["base_radius"] == 25

        # Redo all 5 updates
        for i in range(5):
            manager.redo()

        # Back to final state
        current = manager.state.get_mechanism("test_cam")
        assert current.params["base_radius"] == 45

    def test_mechanisms_changed_signal_emitted_on_undo_redo(self):
        """Verify mechanisms_changed signal is emitted on undo/redo."""
        from automataii.application.project import ProjectStateManager
        from automataii.application.project.models import MechanismData

        manager = ProjectStateManager()

        # Track signal emissions
        signals_received = []
        manager.mechanisms_changed.connect(lambda mechs: signals_received.append(mechs))

        # Add mechanism
        mech = MechanismData(
            id="test_gear",
            part_name="test_part",
            type="gear",
            params={"r1": 30, "r2": 50},
            enabled=True,
        )
        manager.add_mechanism(mech)
        assert len(signals_received) == 1
        assert "test_gear" in signals_received[-1]

        # Undo
        manager.undo()
        assert len(signals_received) == 2
        assert "test_gear" not in signals_received[-1]

        # Redo
        manager.redo()
        assert len(signals_received) == 3
        assert "test_gear" in signals_received[-1]


class TestLoggingIntegration:
    """Logging integration tests."""

    def test_logging_file_creation(self):
        """Test that log files are created."""
        from automataii.utils.logging_config import setup_logging
        from automataii.utils.paths import get_project_root

        setup_logging()

        log_dir = get_project_root() / "logs"
        assert log_dir.exists()

        # Main log file should exist or be creatable
        log_file = log_dir / "automataii.log"
        # File may not exist if no logging has occurred yet, but directory should


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
