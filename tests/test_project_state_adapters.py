"""
Tests for Project State Adapters.

Verifies data transformations and signal handling.
"""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from automataii.application.project import (
    JointData,
    MechanismData,
    PartData,
    PathData,
    Point,
    ProjectStateManager,
    SkeletonData,
)
from automataii.application.project.adapters import (
    EditorTabAdapter,
    ImageProcessingTabAdapter,
    MechanismDesignTabAdapter,
)


class TestImageProcessingTabAdapter:
    """Tests for ImageProcessingTabAdapter."""

    @pytest.fixture
    def state_manager(self):
        """Create mock state manager."""
        manager = MagicMock(spec=ProjectStateManager)
        manager.skeleton_changed = MagicMock()
        manager.skeleton_changed.connect = MagicMock()
        manager.skeleton_changed.disconnect = MagicMock()
        return manager

    @pytest.fixture
    def mock_tab(self):
        """Create mock ImageProcessingTab."""
        tab = MagicMock()
        tab.parts_generated = MagicMock()
        tab.parts_generated.connect = MagicMock()
        tab.parts_generated.disconnect = MagicMock()
        tab.skeleton_updated = MagicMock()
        tab.skeleton_updated.connect = MagicMock()
        tab.skeleton_updated.disconnect = MagicMock()
        return tab

    @pytest.fixture
    def adapter(self, state_manager):
        """Create adapter with mocked state manager."""
        return ImageProcessingTabAdapter(state_manager)

    def test_attach_connects_signals(self, adapter, mock_tab):
        """Test that attach() connects to tab signals."""
        adapter.attach(mock_tab)

        assert adapter.is_connected
        assert adapter.tab == mock_tab
        mock_tab.parts_generated.connect.assert_called_once()
        mock_tab.skeleton_updated.connect.assert_called_once()
        adapter.state_manager.skeleton_changed.connect.assert_called_once()

    def test_detach_disconnects_signals(self, adapter, mock_tab):
        """Test that detach() disconnects from tab signals."""
        adapter.attach(mock_tab)
        adapter.detach()

        assert not adapter.is_connected
        assert adapter.tab is None

    def test_transform_skeleton_data(self, adapter):
        """Test skeleton data transformation."""
        raw_skeleton = {
            "skeleton": [
                {"name": "root", "loc": [100, 200], "parent": None},
                {"name": "hip", "loc": [100, 250], "parent": "root"},
                {"name": "left_leg", "loc": [80, 300], "parent": "hip", "bend_direction": -1.0},
            ]
        }

        result = adapter._transform_skeleton_data(raw_skeleton)

        assert result is not None
        assert isinstance(result, SkeletonData)
        assert len(result.joints) == 3
        assert result.root_joint == "root"

        # Check joint positions
        assert result.joints["root"].position.x == 100
        assert result.joints["root"].position.y == 200
        assert result.joints["root"].parent is None

        # Check bones
        assert len(result.bones) == 2

        # Check bend direction preserved
        assert result.joints["left_leg"].bend_direction == -1.0

    def test_transform_skeleton_data_empty(self, adapter):
        """Test empty skeleton returns None."""
        result = adapter._transform_skeleton_data({})
        assert result is None

        result = adapter._transform_skeleton_data({"skeleton": []})
        assert result is None

    def test_transform_parts_info(self, adapter):
        """Test parts info transformation."""
        parts_info = {
            "parts": {
                "head": {
                    "image_path": "head.png",
                    "mask_path": "head_mask.png",
                    "roi": [50, 30, 100, 120],
                    "z_value": 5,
                },
                "body": {
                    "image_path": "body.png",
                    "roi": [40, 150, 120, 200],
                },
            },
            "joint_map": {
                "head": "neck",
                "body": "hip",
            },
        }

        result = adapter._transform_parts_info(parts_info, "/output")

        assert len(result) == 2
        assert "head" in result
        assert "body" in result

        # Check head part
        head = result["head"]
        assert head.name == "head"
        assert head.texture_path.endswith("head.png")
        assert head.anchor_joint == "neck"
        assert head.transform.x == 50
        assert head.transform.y == 30
        assert head.z_index == 5

        # Check body part (no mask_path specified, should use default)
        body = result["body"]
        assert body.name == "body"
        assert body.anchor_joint == "hip"

    def test_transform_parts_info_character_schema(self, adapter, tmp_path):
        """Test nested character.parts schema from generated parts_info.json."""
        image_file = tmp_path / "head.png"
        image_file.write_bytes(b"png")

        parts_info = {
            "character": {
                "parts": {
                    "head": {
                        "image_path": "head.png",
                        "roi": [10, 20, 30, 40],
                        "anchor_joint_id": "neck",
                        "z_value": 3.0,
                        "fill_color": "rgba(255,0,0,0.5)",
                    },
                },
            },
        }

        result = adapter._transform_parts_info(parts_info, str(tmp_path))

        assert "head" in result
        head = result["head"]
        assert Path(head.texture_path).is_absolute()
        assert Path(head.texture_path).exists()
        assert head.anchor_joint == "neck"
        assert head.roi == (10.0, 20.0, 30.0, 40.0)
        assert head.z_index == 3

    def test_on_skeleton_updated_calls_state_manager(self, adapter, mock_tab, state_manager):
        """Test skeleton update flows to state manager."""
        adapter.attach(mock_tab)

        skeleton_data = {
            "skeleton": [
                {"name": "root", "loc": [100, 200], "parent": None},
            ]
        }

        adapter._on_skeleton_updated(skeleton_data)

        state_manager.load_skeleton.assert_called_once()
        call_args = state_manager.load_skeleton.call_args[0]
        assert isinstance(call_args[0], SkeletonData)

    def test_parts_generated_defers_to_mainwindow_pipeline(
        self, state_manager, mock_tab, tmp_path
    ):
        """Adapter should not double-load parts when MainWindow pipeline is active."""
        adapter = ImageProcessingTabAdapter(state_manager, prefer_main_window_pipeline=True)
        adapter.attach(mock_tab)

        payload_path = tmp_path / "parts_info.json"
        payload_path.write_text(
            '{"parts": {"head": {"image_path": "head.png", "roi": [0, 0, 10, 10]}}}',
            encoding="utf-8",
        )

        adapter._on_parts_generated({"char_cfg_path": str(tmp_path / "char_cfg.yaml")}, str(tmp_path))

        state_manager.load_parts.assert_not_called()

    def test_skeleton_updated_defers_to_mainwindow_pipeline(self, state_manager, mock_tab):
        """Adapter should not double-load skeleton when MainWindow pipeline is active."""
        adapter = ImageProcessingTabAdapter(state_manager, prefer_main_window_pipeline=True)
        adapter.attach(mock_tab)

        adapter._on_skeleton_updated(
            {
                "skeleton": [
                    {"name": "root", "loc": [0, 0], "parent": None},
                    {"name": "neck", "loc": [0, -10], "parent": "root"},
                ]
            }
        )

        state_manager.load_skeleton.assert_not_called()

    def test_state_skeleton_change_updates_tab(self, adapter, mock_tab, state_manager):
        """Test state manager skeleton change updates tab."""
        adapter.attach(mock_tab)

        skeleton = SkeletonData(
            joints={"root": JointData(id="root", position=Point(x=100, y=200))},
            bones=(),
            root_joint="root",
        )

        adapter._on_state_skeleton_changed(skeleton)

        mock_tab.on_skeleton_updated_externally.assert_called_once()
        call_args = mock_tab.on_skeleton_updated_externally.call_args[0]
        assert call_args[0] is not None
        assert "joints" in call_args[0]
        assert call_args[0]["joints"]["root"]["name"] == "root"


class TestProjectStateManagerIntegration:
    """Integration tests for ProjectStateManager."""

    def test_state_manager_initialization(self):
        """Test state manager initializes correctly."""
        # This will fail if PyQt6 is not properly set up
        try:
            import sys

            from PyQt6.QtWidgets import QApplication

            # Create QApplication if not exists
            _ = QApplication.instance() or QApplication(sys.argv)

            manager = ProjectStateManager()
            assert manager.state is not None
            assert not manager.is_dirty
            assert not manager.can_undo
            assert not manager.can_redo

        except ImportError:
            pytest.skip("PyQt6 not available for integration tests")

    def test_load_parts_updates_state(self):
        """Test load_parts updates state and emits signals."""
        try:
            import sys

            from PyQt6.QtWidgets import QApplication

            _ = QApplication.instance() or QApplication(sys.argv)

            manager = ProjectStateManager()

            # Create signal spy
            signal_received = []
            manager.parts_changed.connect(lambda x: signal_received.append(x))

            # Load parts
            parts = {
                "head": PartData(
                    name="head",
                    texture_path="head.png",
                    mask_path="head_mask.png",
                    anchor_joint="neck",
                ),
            }
            manager.load_parts(parts)

            # Verify state updated
            assert manager.state.has_parts()
            assert "head" in manager.state.parts
            assert manager.is_dirty
            assert manager.can_undo

            # Verify signal emitted
            assert len(signal_received) == 1

        except ImportError:
            pytest.skip("PyQt6 not available for integration tests")

    def test_undo_redo(self):
        """Test undo/redo functionality."""
        try:
            import sys

            from PyQt6.QtWidgets import QApplication

            _ = QApplication.instance() or QApplication(sys.argv)

            manager = ProjectStateManager()

            # Initial state
            assert not manager.can_undo

            # Add parts
            parts = {
                "head": PartData(
                    name="head",
                    texture_path="head.png",
                    mask_path="head_mask.png",
                    anchor_joint="neck",
                ),
            }
            manager.load_parts(parts)
            assert manager.state.has_parts()
            assert manager.can_undo

            # Undo
            manager.undo()
            assert not manager.state.has_parts()
            assert manager.can_redo

            # Redo
            manager.redo()
            assert manager.state.has_parts()

        except ImportError:
            pytest.skip("PyQt6 not available for integration tests")


class TestEditorTabAdapter:
    """Tests for EditorTabAdapter."""

    @pytest.fixture
    def state_manager(self):
        """Create mock state manager."""
        manager = MagicMock(spec=ProjectStateManager)
        manager.parts_changed = MagicMock()
        manager.parts_changed.connect = MagicMock()
        manager.parts_changed.disconnect = MagicMock()
        manager.skeleton_changed = MagicMock()
        manager.skeleton_changed.connect = MagicMock()
        manager.skeleton_changed.disconnect = MagicMock()
        manager.paths_changed = MagicMock()
        manager.paths_changed.connect = MagicMock()
        manager.paths_changed.disconnect = MagicMock()
        manager.begin_batch = MagicMock()
        manager.end_batch = MagicMock()
        return manager

    @pytest.fixture
    def mock_tab(self):
        """Create mock EditorTab."""
        tab = MagicMock()
        tab.path_data_changed = MagicMock()
        tab.path_data_changed.connect = MagicMock()
        tab.path_data_changed.disconnect = MagicMock()
        tab.motion_path_updated = MagicMock()
        tab.motion_path_updated.connect = MagicMock()
        tab.motion_path_updated.disconnect = MagicMock()
        return tab

    @pytest.fixture
    def adapter(self, state_manager):
        """Create adapter with mocked state manager."""
        return EditorTabAdapter(state_manager)

    def test_attach_connects_signals(self, adapter, mock_tab):
        """Test that attach() connects to tab signals."""
        adapter.attach(mock_tab)

        assert adapter.is_connected
        assert adapter.tab == mock_tab
        mock_tab.path_data_changed.connect.assert_called_once()
        mock_tab.motion_path_updated.connect.assert_called_once()

    def test_transform_qpath_to_pathdata(self, adapter):
        """Test QPainterPath to PathData transformation."""
        try:
            from PyQt6.QtGui import QPainterPath

            # Create a simple path
            qpath = QPainterPath()
            qpath.moveTo(0, 0)
            qpath.lineTo(100, 0)
            qpath.lineTo(100, 100)
            qpath.lineTo(0, 100)

            result = adapter._transform_qpath_to_pathdata("test_part", qpath)

            assert result is not None
            assert result.part_name == "test_part"
            assert len(result.points) == 4
            assert result.points[0].x == 0
            assert result.points[0].y == 0
            assert result.points[1].x == 100
            assert result.enabled

        except ImportError:
            pytest.skip("PyQt6 not available")

    def test_transform_qpath_empty(self, adapter):
        """Test empty path returns None."""
        try:
            from PyQt6.QtGui import QPainterPath

            qpath = QPainterPath()
            result = adapter._transform_qpath_to_pathdata("test", qpath)
            assert result is None

        except ImportError:
            pytest.skip("PyQt6 not available")

    def test_transform_pathdata_to_qpath(self, adapter):
        """Test PathData to QPainterPath transformation."""
        try:
            path_data = PathData(
                part_name="test",
                points=(
                    Point(x=0, y=0),
                    Point(x=100, y=0),
                    Point(x=100, y=100),
                ),
                is_closed=False,
            )

            result = adapter._transform_pathdata_to_qpath(path_data)

            assert not result.isEmpty()
            assert result.elementCount() == 3

        except ImportError:
            pytest.skip("PyQt6 not available")

    def test_state_parts_change_updates_tab(self, adapter, mock_tab, state_manager):
        """Test state manager parts change updates tab."""
        adapter.attach(mock_tab)

        parts = {
            "head": PartData(
                name="head",
                texture_path="head.png",
                mask_path="head_mask.png",
                anchor_joint="neck",
            ),
        }

        adapter._on_state_parts_changed(parts)

        mock_tab.set_parts_data.assert_called_once()

    def test_state_skeleton_change_updates_tab(self, adapter, mock_tab, state_manager):
        """Test state manager skeleton change updates tab."""
        adapter.attach(mock_tab)

        skeleton = SkeletonData(
            joints={
                "root": JointData(id="root", position=Point(x=100, y=200), name="root"),
                "hip_1": JointData(
                    id="hip_1",
                    position=Point(x=100, y=240),
                    name="hip",
                    parent="root",
                ),
            },
            bones=(),
            root_joint="root",
        )

        adapter._on_state_skeleton_changed(skeleton)

        mock_tab.on_skeleton_updated.assert_called_once()
        mock_tab.cache_initial_skeleton.assert_called_once()
        skeleton_dict = mock_tab.cache_initial_skeleton.call_args[0][0]
        assert skeleton_dict["joints"]["root"]["name"] == "root"
        assert skeleton_dict["joints"]["hip_1"]["parent_id"] == "root"
        assert skeleton_dict["joint_map"]["hip"] == "hip_1"
        assert skeleton_dict["hierarchy"]["root"] == ["hip_1"]
        assert "root" in skeleton_dict["root_joint_ids"]


class TestMechanismDesignTabAdapter:
    """Tests for MechanismDesignTabAdapter."""

    @pytest.fixture
    def state_manager(self):
        """Create mock state manager."""

        manager = MagicMock(spec=ProjectStateManager)
        manager.parts_changed = MagicMock()
        manager.parts_changed.connect = MagicMock()
        manager.parts_changed.disconnect = MagicMock()
        manager.skeleton_changed = MagicMock()
        manager.skeleton_changed.connect = MagicMock()
        manager.skeleton_changed.disconnect = MagicMock()
        manager.paths_changed = MagicMock()
        manager.paths_changed.connect = MagicMock()
        manager.paths_changed.disconnect = MagicMock()
        manager.mechanisms_changed = MagicMock()
        manager.mechanisms_changed.connect = MagicMock()
        manager.mechanisms_changed.disconnect = MagicMock()

        # Mock state object
        mock_state = MagicMock()
        mock_state.get_mechanism.return_value = None
        manager.state = mock_state

        return manager

    @pytest.fixture
    def mock_tab(self):
        """Create mock MechanismDesignTab."""
        tab = MagicMock()
        tab.mechanism_parameters_changed = MagicMock()
        tab.mechanism_parameters_changed.connect = MagicMock()
        tab.mechanism_parameters_changed.disconnect = MagicMock()
        tab.mechanism_path_generated = MagicMock()
        tab.mechanism_path_generated.connect = MagicMock()
        tab.mechanism_path_generated.disconnect = MagicMock()
        return tab

    @pytest.fixture
    def adapter(self, state_manager):
        """Create adapter with mocked state manager."""
        return MechanismDesignTabAdapter(state_manager)

    def test_attach_connects_signals(self, adapter, mock_tab):
        """Test that attach() connects to tab signals."""
        adapter.attach(mock_tab)

        assert adapter.is_connected
        assert adapter.tab == mock_tab
        mock_tab.mechanism_parameters_changed.connect.assert_called_once()
        mock_tab.mechanism_path_generated.connect.assert_called_once()

    def test_state_parts_change_updates_tab(self, adapter, mock_tab, state_manager):
        """Test state manager parts change updates tab."""
        adapter.attach(mock_tab)

        parts = {
            "head": PartData(
                name="head",
                texture_path="head.png",
                mask_path="head_mask.png",
                anchor_joint="neck",
            ),
        }

        adapter._on_state_parts_changed(parts)

        mock_tab.set_parts_data.assert_called_once()

    def test_state_paths_change_updates_tab(self, adapter, mock_tab, state_manager):
        """Test state manager paths change updates tab."""
        adapter.attach(mock_tab)

        paths = {
            "head": PathData(
                part_name="head",
                points=(Point(x=0, y=0), Point(x=100, y=100)),
                enabled=True,
            ),
        }

        adapter._on_state_paths_changed(paths)

        mock_tab.set_path_data_from_editor.assert_called_once()

    def test_state_skeleton_change_updates_tab(self, adapter, mock_tab, state_manager):
        """Test state manager skeleton change updates tab."""
        adapter.attach(mock_tab)

        skeleton = SkeletonData(
            joints={
                "root": JointData(id="root", position=Point(x=100, y=200), name="root"),
                "neck_3": JointData(
                    id="neck_3",
                    position=Point(x=100, y=180),
                    name="neck",
                    parent="root",
                ),
            },
            bones=(),
            root_joint="root",
        )

        adapter._on_state_skeleton_changed(skeleton)

        mock_tab.on_skeleton_updated.assert_called_once()
        mock_tab.cache_initial_skeleton.assert_called_once()
        skeleton_dict = mock_tab.cache_initial_skeleton.call_args[0][0]
        assert skeleton_dict["joints"]["root"]["name"] == "root"
        assert skeleton_dict["joint_map"]["neck"] == "neck_3"
        assert skeleton_dict["hierarchy"]["root"] == ["neck_3"]
        assert skeleton_dict["joints"]["neck_3"]["parent_id"] == "root"

    def test_joint_data_to_dict_includes_name_for_ik_compat(self):
        joint = JointData(id="hip_1", position=Point(x=10, y=20))

        serialized = joint.to_dict()

        assert serialized["id"] == "hip_1"
        assert serialized["name"] == "hip_1"

    def test_joint_data_from_dict_accepts_parent_id_alias(self):
        parsed = JointData.from_dict(
            {
                "id": "neck_3",
                "name": "neck",
                "position": [10.0, 20.0],
                "parent_id": "root_0",
            }
        )

        assert parsed.parent == "root_0"

    def test_add_mechanism_for_part(self, adapter, state_manager):
        """Test adding a mechanism for a part."""
        mechanism_id = adapter.add_mechanism_for_part(
            part_name="arm",
            mechanism_type="4_bar_linkage",
            params={"link_length": 100},
        )

        assert mechanism_id is not None
        assert "arm" in mechanism_id
        assert "4_bar_linkage" in mechanism_id
        state_manager.add_mechanism.assert_called_once()

    def test_transform_pathdata_to_qpath(self, adapter):
        """Test PathData to QPainterPath transformation."""
        try:
            path_data = PathData(
                part_name="test",
                points=(
                    Point(x=0, y=0),
                    Point(x=100, y=0),
                    Point(x=100, y=100),
                ),
                is_closed=False,
            )

            result = adapter._transform_pathdata_to_qpath(path_data)

            assert not result.isEmpty()
            assert result.elementCount() == 3

        except ImportError:
            pytest.skip("PyQt6 not available")

    def test_transform_mechanism_to_layer_data_restores_generated_path(self, adapter):
        mech_data = MechanismData(
            id="mech_1",
            part_name="arm",
            type="4_bar_linkage",
            params={"l1": 120.0},
            layer_data={
                "source": "foundry",
                "generated_path_data": {
                    "points": [[10.0, 20.0], [30.0, 40.0], [50.0, 45.0]],
                    "is_closed": False,
                },
            },
            enabled=True,
        )

        layer_data = adapter._transform_mechanism_to_layer_data(mech_data)

        assert layer_data["id"] == "mech_1"
        assert layer_data["source"] == "foundry"
        assert "generated_path_data" not in layer_data
        assert "generated_path" in layer_data
        assert layer_data["generated_path"].isEmpty() is False
        assert layer_data["generated_path"].elementCount() == 3
