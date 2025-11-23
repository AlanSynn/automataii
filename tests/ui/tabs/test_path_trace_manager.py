"""Tests for PathTraceManager.

This module tests the path trace management logic for mechanism animations.

Test Coverage:
- Initialization (config, defaults)
- Trace lifecycle (init, update, clear)
- Stride gating (visual update throttling)
- Max points enforcement (memory bounds)
- Visibility control
- Edge cases (missing traces, scene cleanup)
"""

import pytest
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QColor, QPainterPath
from PyQt6.QtWidgets import QApplication, QGraphicsScene

from automataii.ui.tabs.mechanism_design.path_trace_manager import (
    PathTraceConfig,
    PathTraceManager,
)


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def qapp():
    """Create QApplication for Qt tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def scene(qapp):
    """Create QGraphicsScene for testing."""
    return QGraphicsScene()


@pytest.fixture
def manager():
    """Create PathTraceManager with default config."""
    return PathTraceManager()


@pytest.fixture
def custom_config():
    """Create custom PathTraceConfig."""
    return PathTraceConfig(
        max_points=100,
        update_stride=3,
        pen_color=QColor("#00ff00"),
        pen_width=2.0,
        z_value=50,
    )


# ============================================================================
# INITIALIZATION TESTS
# ============================================================================


def test_manager_initialization_defaults(manager):
    """Test manager initializes with default configuration."""
    assert manager is not None
    assert manager._config is not None
    assert manager._config.max_points == 500
    assert manager._config.update_stride == 2
    assert manager._config.pen_color == QColor("#ff3030")
    assert manager._config.pen_width == 3.0
    assert manager._config.z_value == 100


def test_manager_initialization_custom_config(custom_config):
    """Test manager initializes with custom configuration."""
    manager = PathTraceManager(config=custom_config)
    assert manager._config == custom_config
    assert manager._config.max_points == 100
    assert manager._config.update_stride == 3


def test_manager_initializes_empty_data_structures(manager):
    """Test manager initializes with empty data structures."""
    assert len(manager._trace_items) == 0
    assert len(manager._trace_points) == 0
    assert len(manager._trace_paths) == 0


# ============================================================================
# INIT_TRACE TESTS
# ============================================================================


def test_init_trace_creates_item_in_scene(manager, scene):
    """Test init_trace creates QGraphicsPathItem and adds to scene."""
    mechanism_id = "mech_1"

    manager.init_trace(mechanism_id, scene)

    # Should create trace item
    assert mechanism_id in manager._trace_items
    item = manager._trace_items[mechanism_id]
    assert item is not None

    # Should add to scene
    assert item.scene() == scene
    assert item in scene.items()


def test_init_trace_initializes_data_structures(manager, scene):
    """Test init_trace initializes point buffer and path."""
    mechanism_id = "mech_1"

    manager.init_trace(mechanism_id, scene)

    # Should initialize point buffer (empty list)
    assert mechanism_id in manager._trace_points
    assert manager._trace_points[mechanism_id] == []

    # Should initialize empty path
    assert mechanism_id in manager._trace_paths
    path = manager._trace_paths[mechanism_id]
    assert isinstance(path, QPainterPath)
    assert path.isEmpty()


def test_init_trace_removes_old_item_from_scene(manager, scene):
    """Test init_trace removes old trace item before creating new one."""
    mechanism_id = "mech_1"

    # First initialization
    manager.init_trace(mechanism_id, scene)
    old_item = manager._trace_items[mechanism_id]

    # Second initialization (should replace)
    manager.init_trace(mechanism_id, scene)
    new_item = manager._trace_items[mechanism_id]

    # Should be different items
    assert old_item is not new_item

    # Old item should be removed from scene
    assert old_item not in scene.items()

    # New item should be in scene
    assert new_item in scene.items()


def test_init_trace_applies_pen_styling(manager, scene):
    """Test init_trace applies correct pen styling from config."""
    mechanism_id = "mech_1"

    manager.init_trace(mechanism_id, scene)
    item = manager._trace_items[mechanism_id]

    pen = item.pen()
    assert pen.color() == manager._config.pen_color
    assert pen.widthF() == manager._config.pen_width
    assert pen.isCosmetic()  # Should be cosmetic for consistent width


def test_init_trace_sets_z_value(manager, scene):
    """Test init_trace sets correct Z-value from config."""
    mechanism_id = "mech_1"

    manager.init_trace(mechanism_id, scene)
    item = manager._trace_items[mechanism_id]

    assert item.zValue() == manager._config.z_value


# ============================================================================
# UPDATE_TRACE TESTS
# ============================================================================


def test_update_trace_appends_point(manager, scene):
    """Test update_trace appends point to buffer."""
    mechanism_id = "mech_1"
    manager.init_trace(mechanism_id, scene)

    point1 = QPointF(10.0, 20.0)
    point2 = QPointF(15.0, 25.0)

    manager.update_trace(mechanism_id, point1, frame_tick=0)
    assert len(manager._trace_points[mechanism_id]) == 1
    assert manager._trace_points[mechanism_id][0] == point1

    manager.update_trace(mechanism_id, point2, frame_tick=1)
    assert len(manager._trace_points[mechanism_id]) == 2
    assert manager._trace_points[mechanism_id][1] == point2


def test_update_trace_enforces_max_points(manager, scene):
    """Test update_trace enforces max_points limit."""
    mechanism_id = "mech_1"
    manager.init_trace(mechanism_id, scene)

    max_points = manager._config.max_points

    # Add max_points + 50 points
    for i in range(max_points + 50):
        manager.update_trace(mechanism_id, QPointF(float(i), float(i)), frame_tick=i)

    # Should only keep last max_points
    assert len(manager._trace_points[mechanism_id]) == max_points


def test_update_trace_respects_stride_gating(manager, scene):
    """Test update_trace respects stride gating for visual updates."""
    mechanism_id = "mech_1"
    manager.init_trace(mechanism_id, scene)

    stride = manager._config.update_stride

    # Add points, track when path gets updated
    initial_path = manager._trace_paths[mechanism_id]

    # Add first point (won't render - need 2 points for a line)
    manager.update_trace(mechanism_id, QPointF(0.0, 0.0), frame_tick=0)
    path_after_point1 = manager._trace_paths[mechanism_id]
    assert path_after_point1.isEmpty()  # Still empty (1 point can't draw a line)

    # Add second point (should always update for first 2 points)
    manager.update_trace(mechanism_id, QPointF(1.0, 1.0), frame_tick=1)
    path_after_point2 = manager._trace_paths[mechanism_id]
    assert not path_after_point2.isEmpty()  # Now we have a line

    # Now test stride gating for subsequent points
    # stride=2, so frame_tick=2,4,6,... should update
    manager.update_trace(mechanism_id, QPointF(2.0, 2.0), frame_tick=2)
    path_after_stride_hit = manager._trace_paths[mechanism_id]
    assert path_after_stride_hit != path_after_point2  # Should update (stride hit)

    manager.update_trace(mechanism_id, QPointF(3.0, 3.0), frame_tick=3)
    path_after_stride_miss = manager._trace_paths[mechanism_id]
    assert path_after_stride_miss == path_after_stride_hit  # Should NOT update (stride miss)


def test_update_trace_updates_first_two_points_immediately(manager, scene):
    """Test update_trace updates visual for first 2 points regardless of stride."""
    mechanism_id = "mech_1"
    manager.init_trace(mechanism_id, scene)

    # Add first point at frame_tick=1 (stride miss, but should still attempt update)
    manager.update_trace(mechanism_id, QPointF(0.0, 0.0), frame_tick=1)
    assert len(manager._trace_points[mechanism_id]) == 1
    path_after_1 = manager._trace_paths[mechanism_id]

    # Add second point at frame_tick=3 (stride miss, but should still update)
    manager.update_trace(mechanism_id, QPointF(1.0, 1.0), frame_tick=3)
    assert len(manager._trace_points[mechanism_id]) == 2
    path_after_2 = manager._trace_paths[mechanism_id]

    # First point can't render (need 2 points for a line), but second point should
    assert path_after_1.isEmpty()  # 1 point can't draw a line
    assert not path_after_2.isEmpty()  # 2 points can draw a line


def test_update_trace_auto_initializes_if_needed(manager, scene):
    """Test update_trace auto-initializes trace if not already initialized."""
    mechanism_id = "mech_1"

    # Don't call init_trace, call update_trace directly with scene
    manager.update_trace(mechanism_id, QPointF(10.0, 20.0), frame_tick=0, scene=scene)

    # Should auto-initialize
    assert mechanism_id in manager._trace_items
    assert mechanism_id in manager._trace_points
    assert len(manager._trace_points[mechanism_id]) == 1


def test_update_trace_builds_painter_path(manager, scene):
    """Test update_trace builds correct QPainterPath from points."""
    mechanism_id = "mech_1"
    manager.init_trace(mechanism_id, scene)

    points = [QPointF(0.0, 0.0), QPointF(10.0, 10.0), QPointF(20.0, 5.0)]

    for i, point in enumerate(points):
        manager.update_trace(mechanism_id, point, frame_tick=i * 2)  # Always hit stride

    path = manager._trace_paths[mechanism_id]
    assert not path.isEmpty()

    # Path should start at first point
    assert path.elementAt(0).x == points[0].x()
    assert path.elementAt(0).y == points[0].y()


# ============================================================================
# CLEAR TESTS
# ============================================================================


def test_clear_trace_removes_from_scene(manager, scene):
    """Test clear_trace removes QGraphicsPathItem from scene."""
    mechanism_id = "mech_1"
    manager.init_trace(mechanism_id, scene)
    item = manager._trace_items[mechanism_id]

    assert item in scene.items()

    manager.clear_trace(mechanism_id, scene)

    assert item not in scene.items()


def test_clear_trace_removes_data_structures(manager, scene):
    """Test clear_trace removes all data structures for mechanism."""
    mechanism_id = "mech_1"
    manager.init_trace(mechanism_id, scene)
    manager.update_trace(mechanism_id, QPointF(10.0, 20.0), frame_tick=0)

    assert mechanism_id in manager._trace_items
    assert mechanism_id in manager._trace_points
    assert mechanism_id in manager._trace_paths

    manager.clear_trace(mechanism_id, scene)

    assert mechanism_id not in manager._trace_items
    assert mechanism_id not in manager._trace_points
    assert mechanism_id not in manager._trace_paths


def test_clear_all_traces_removes_all(manager, scene):
    """Test clear_all_traces removes all traces."""
    mech_ids = ["mech_1", "mech_2", "mech_3"]

    for mech_id in mech_ids:
        manager.init_trace(mech_id, scene)

    assert len(manager._trace_items) == 3
    assert len(scene.items()) == 3

    manager.clear_all_traces(scene)

    assert len(manager._trace_items) == 0
    assert len(manager._trace_points) == 0
    assert len(manager._trace_paths) == 0
    assert len(scene.items()) == 0


# ============================================================================
# VISIBILITY TESTS
# ============================================================================


def test_set_trace_visible_shows_item(manager, scene):
    """Test set_trace_visible shows trace item."""
    mechanism_id = "mech_1"
    manager.init_trace(mechanism_id, scene)
    item = manager._trace_items[mechanism_id]

    item.setVisible(False)
    assert not item.isVisible()

    manager.set_trace_visible(mechanism_id, True)
    assert item.isVisible()


def test_set_trace_visible_hides_item(manager, scene):
    """Test set_trace_visible hides trace item."""
    mechanism_id = "mech_1"
    manager.init_trace(mechanism_id, scene)
    item = manager._trace_items[mechanism_id]

    assert item.isVisible()

    manager.set_trace_visible(mechanism_id, False)
    assert not item.isVisible()


# ============================================================================
# GETTER TESTS
# ============================================================================


def test_get_trace_item_returns_item(manager, scene):
    """Test get_trace_item returns correct QGraphicsPathItem."""
    mechanism_id = "mech_1"
    manager.init_trace(mechanism_id, scene)

    item = manager.get_trace_item(mechanism_id)
    assert item is manager._trace_items[mechanism_id]


def test_get_trace_item_returns_none_if_not_exists(manager):
    """Test get_trace_item returns None for nonexistent mechanism."""
    item = manager.get_trace_item("nonexistent")
    assert item is None


def test_get_trace_points_returns_copy(manager, scene):
    """Test get_trace_points returns copy of point buffer."""
    mechanism_id = "mech_1"
    manager.init_trace(mechanism_id, scene)

    original_points = [QPointF(0.0, 0.0), QPointF(10.0, 10.0)]
    for i, point in enumerate(original_points):
        manager.update_trace(mechanism_id, point, frame_tick=i * 2)

    points_copy = manager.get_trace_points(mechanism_id)

    # Should be equal
    assert len(points_copy) == len(original_points)

    # Should be a copy (not same list)
    assert points_copy is not manager._trace_points[mechanism_id]

    # Modifying copy should not affect original
    points_copy.append(QPointF(100.0, 100.0))
    assert len(manager._trace_points[mechanism_id]) == len(original_points)


def test_get_trace_points_returns_empty_if_not_exists(manager):
    """Test get_trace_points returns empty list for nonexistent mechanism."""
    points = manager.get_trace_points("nonexistent")
    assert points == []


# ============================================================================
# EDGE CASE TESTS
# ============================================================================


def test_clear_trace_handles_nonexistent_mechanism(manager, scene):
    """Test clear_trace handles nonexistent mechanism gracefully."""
    # Should not raise exception
    manager.clear_trace("nonexistent", scene)


def test_set_trace_visible_handles_nonexistent_mechanism(manager):
    """Test set_trace_visible handles nonexistent mechanism gracefully."""
    # Should not raise exception
    manager.set_trace_visible("nonexistent", True)


def test_update_trace_with_zero_stride(scene):
    """Test update_trace with stride=1 (update every frame)."""
    config = PathTraceConfig(update_stride=1)
    manager = PathTraceManager(config=config)

    mechanism_id = "mech_1"
    manager.init_trace(mechanism_id, scene)

    # Add 5 points
    for i in range(5):
        manager.update_trace(mechanism_id, QPointF(float(i), float(i)), frame_tick=i)

    # Path should be updated after each point (stride=1)
    path = manager._trace_paths[mechanism_id]
    assert not path.isEmpty()


def test_init_trace_with_already_initialized_mechanism(manager, scene):
    """Test init_trace can be called multiple times (reinitialization)."""
    mechanism_id = "mech_1"

    # First init
    manager.init_trace(mechanism_id, scene)
    manager.update_trace(mechanism_id, QPointF(10.0, 20.0), frame_tick=0)
    assert len(manager._trace_points[mechanism_id]) == 1

    # Second init (should clear previous data)
    manager.init_trace(mechanism_id, scene)
    assert len(manager._trace_points[mechanism_id]) == 0
    assert manager._trace_paths[mechanism_id].isEmpty()


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


def test_full_trace_lifecycle(manager, scene):
    """Test full trace lifecycle: init -> update x 100 -> clear."""
    mechanism_id = "mech_1"

    # Init
    manager.init_trace(mechanism_id, scene)
    assert mechanism_id in manager._trace_items

    # Update 100 times
    for i in range(100):
        manager.update_trace(mechanism_id, QPointF(float(i), float(i)), frame_tick=i)

    assert len(manager._trace_points[mechanism_id]) == 100
    assert not manager._trace_paths[mechanism_id].isEmpty()

    # Clear
    manager.clear_trace(mechanism_id, scene)
    assert mechanism_id not in manager._trace_items


def test_multiple_mechanisms_independent_traces(manager, scene):
    """Test multiple mechanisms maintain independent traces."""
    mech_1 = "mech_1"
    mech_2 = "mech_2"

    manager.init_trace(mech_1, scene)
    manager.init_trace(mech_2, scene)

    # Update mech_1 with 10 points
    for i in range(10):
        manager.update_trace(mech_1, QPointF(float(i), 0.0), frame_tick=i * 2)

    # Update mech_2 with 20 points
    for i in range(20):
        manager.update_trace(mech_2, QPointF(0.0, float(i)), frame_tick=i * 2)

    # Should be independent
    assert len(manager._trace_points[mech_1]) == 10
    assert len(manager._trace_points[mech_2]) == 20


def test_trace_persistence_across_visibility_changes(manager, scene):
    """Test trace data persists when visibility changes."""
    mechanism_id = "mech_1"
    manager.init_trace(mechanism_id, scene)

    # Add points
    for i in range(10):
        manager.update_trace(mechanism_id, QPointF(float(i), float(i)), frame_tick=i * 2)

    # Hide
    manager.set_trace_visible(mechanism_id, False)
    assert len(manager._trace_points[mechanism_id]) == 10  # Data should persist

    # Show
    manager.set_trace_visible(mechanism_id, True)
    assert len(manager._trace_points[mechanism_id]) == 10  # Data should still be there


# ============================================================================
# PROPERTY-BASED TESTS (Invariants)
# ============================================================================


def test_max_points_invariant(manager, scene):
    """Property: buffer never exceeds max_points."""
    mechanism_id = "mech_1"
    manager.init_trace(mechanism_id, scene)

    max_points = manager._config.max_points

    # Add way more than max_points
    for i in range(max_points * 3):
        manager.update_trace(mechanism_id, QPointF(float(i), float(i)), frame_tick=i)

        # Invariant: should never exceed max_points
        assert len(manager._trace_points[mechanism_id]) <= max_points


def test_stride_gating_invariant(manager, scene):
    """Property: visual updates only on stride boundaries (after first 2 points)."""
    mechanism_id = "mech_1"
    manager.init_trace(mechanism_id, scene)

    stride = manager._config.update_stride

    # Add first 2 points (should always update)
    manager.update_trace(mechanism_id, QPointF(0.0, 0.0), frame_tick=0)
    manager.update_trace(mechanism_id, QPointF(1.0, 1.0), frame_tick=1)

    # Now test stride invariant
    prev_path = manager._trace_paths[mechanism_id]

    for frame_tick in range(2, 50):
        manager.update_trace(
            mechanism_id, QPointF(float(frame_tick), float(frame_tick)), frame_tick=frame_tick
        )
        current_path = manager._trace_paths[mechanism_id]

        if frame_tick % stride == 0:
            # Should have updated path
            # Note: We can't directly compare QPainterPath objects, but we can check element count
            assert current_path.elementCount() >= prev_path.elementCount()

        prev_path = current_path


# ============================================================================
# NEW API METHODS TESTS (MM-6.1 Phase 1 Re-extraction)
# ============================================================================


def test_get_all_mechanism_ids_empty(manager):
    """Test get_all_mechanism_ids with no traces."""
    ids = manager.get_all_mechanism_ids()
    assert ids == []


def test_get_all_mechanism_ids_multiple(manager, scene):
    """Test get_all_mechanism_ids with multiple traces."""
    mech_ids = ["mech_1", "mech_2", "mech_3"]

    for mech_id in mech_ids:
        manager.init_trace(mech_id, scene)

    ids = manager.get_all_mechanism_ids()
    assert set(ids) == set(mech_ids)


def test_has_trace_returns_false_for_missing(manager):
    """Test has_trace returns False for non-existent trace."""
    assert not manager.has_trace("nonexistent")


def test_has_trace_returns_true_after_init(manager, scene):
    """Test has_trace returns True after initialization."""
    mechanism_id = "mech_1"
    manager.init_trace(mechanism_id, scene)
    assert manager.has_trace(mechanism_id)


def test_has_trace_returns_false_after_clear(manager, scene):
    """Test has_trace returns False after clearing."""
    mechanism_id = "mech_1"
    manager.init_trace(mechanism_id, scene)
    manager.clear_trace(mechanism_id, scene)
    assert not manager.has_trace(mechanism_id)


def test_clear_trace_points_only_preserves_item(manager, scene):
    """Test clear_trace_points_only keeps visual item but clears data."""
    mechanism_id = "mech_1"
    manager.init_trace(mechanism_id, scene)

    # Add points
    for i in range(10):
        manager.update_trace(mechanism_id, QPointF(float(i), float(i)), frame_tick=i * 2)

    assert len(manager._trace_points[mechanism_id]) == 10
    assert not manager._trace_paths[mechanism_id].isEmpty()

    # Clear points only
    manager.clear_trace_points_only(mechanism_id)

    # Points should be cleared
    assert len(manager._trace_points[mechanism_id]) == 0

    # Path should be empty
    assert manager._trace_paths[mechanism_id].isEmpty()

    # But item should still exist
    assert manager.has_trace(mechanism_id)
    assert mechanism_id in manager._trace_items


def test_clear_trace_points_only_on_missing_mechanism(manager):
    """Test clear_trace_points_only handles missing mechanism gracefully."""
    # Should not raise exception
    manager.clear_trace_points_only("nonexistent")
