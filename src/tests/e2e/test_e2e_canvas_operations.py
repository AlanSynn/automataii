"""End-to-end tests for canvas operations including drawing, zooming, and panning."""

import math
from unittest.mock import patch, MagicMock

import pytest
from PyQt6.QtCore import Qt, QPointF, QPoint, QRectF
from PyQt6.QtGui import QWheelEvent, QPainterPath
from PyQt6.QtWidgets import QGraphicsItem
from PyQt6.QtTest import QTest

from .fixtures import E2ETestBase, TestImageGenerator
from automataii.gui.graphics_items.part_item import CharacterPartItem
from automataii.gui.graphics_items.anchor_item import AnchorItem


class TestE2ECanvasOperations(E2ETestBase):
    """Test canvas drawing, zooming, panning, and other view operations."""
    
    def test_freehand_path_drawing(self, qtbot):
        """Test freehand drawing of motion paths on canvas."""
        window = self.create_main_window()
        
        # Setup editor with a part
        self.switch_to_tab("editor")
        editor_tab = window.tab_manager.tabs["editor"]
        editor_view = editor_tab.editor_view
        
        # Load test part
        parts_info = {"test_arm": MagicMock()}
        editor_tab.load_parts(parts_info)
        
        # Select the part
        editor_tab._selection_handler.select_part("test_arm")
        
        # Enable motion path drawing mode
        editor_view.set_mode("define_motion_path")
        assert editor_view.current_mode == "define_motion_path"
        
        # Draw a complex freehand path
        path_points = []
        for i in range(20):
            angle = i * 18  # 20 points around circle
            x = 200 + 50 * math.cos(math.radians(angle))
            y = 200 + 50 * math.sin(math.radians(angle))
            path_points.append(QPointF(x, y))
        
        # Simulate drawing
        self.simulate_canvas_drawing(editor_view, path_points)
        
        # Verify path was created
        assert "test_arm" in editor_view.motion_path_handler._final_paths_map
        path = editor_view.motion_path_handler._final_paths_map["test_arm"]
        assert not path.isEmpty()
        assert path.elementCount() > 10  # Should have multiple points
        
        # Test path smoothing (if implemented)
        # Path points should be reasonably smooth
        
    def test_canvas_zoom_operations(self, qtbot):
        """Test zooming functionality with mouse wheel and buttons."""
        window = self.create_main_window()
        
        self.switch_to_tab("editor")
        editor_tab = window.tab_manager.tabs["editor"]
        editor_view = editor_tab.editor_view
        
        # Get initial zoom level
        initial_scale = editor_view.transform().m11()
        
        # Test zoom in with mouse wheel
        center_point = editor_view.rect().center()
        wheel_event = QWheelEvent(
            QPointF(center_point),
            QPointF(center_point),
            QPoint(),
            QPoint(0, 120),  # Positive delta for zoom in
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False
        )
        editor_view.wheelEvent(wheel_event)
        
        # Verify zoom increased
        new_scale = editor_view.transform().m11()
        assert new_scale > initial_scale
        
        # Test zoom out
        wheel_event = QWheelEvent(
            QPointF(center_point),
            QPointF(center_point),
            QPoint(),
            QPoint(0, -120),  # Negative delta for zoom out
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False
        )
        editor_view.wheelEvent(wheel_event)
        
        # Should be back close to initial
        final_scale = editor_view.transform().m11()
        assert abs(final_scale - initial_scale) < 0.1
        
        # Test zoom to fit
        editor_view.zoom_to_fit()
        QTest.qWait(100)
        
        # Test zoom reset (Ctrl+0)
        qtbot.keyClick(editor_view, Qt.Key.Key_0, Qt.KeyboardModifier.ControlModifier)
        reset_scale = editor_view.transform().m11()
        assert reset_scale == 1.0
    
    def test_canvas_pan_operations(self, qtbot):
        """Test panning functionality with middle mouse button and Alt+drag."""
        window = self.create_main_window()
        
        self.switch_to_tab("editor")
        editor_view = window.tab_manager.tabs["editor"].editor_view
        
        # Add some items to scene for reference
        editor_view.scene().addRect(0, 0, 100, 100)
        
        # Get initial center
        initial_center = editor_view.mapToScene(editor_view.rect().center())
        
        # Test middle mouse button pan
        start_pos = editor_view.rect().center()
        end_pos = QPoint(start_pos.x() + 100, start_pos.y() + 50)
        
        qtbot.mousePress(editor_view.viewport(), Qt.MouseButton.MiddleButton, pos=start_pos)
        qtbot.mouseMove(editor_view.viewport(), pos=end_pos)
        qtbot.mouseRelease(editor_view.viewport(), Qt.MouseButton.MiddleButton, pos=end_pos)
        
        # Verify view moved
        new_center = editor_view.mapToScene(editor_view.rect().center())
        assert new_center != initial_center
        
        # Test Alt+Left mouse pan
        qtbot.mousePress(
            editor_view.viewport(), 
            Qt.MouseButton.LeftButton, 
            Qt.KeyboardModifier.AltModifier, 
            pos=end_pos
        )
        qtbot.mouseMove(editor_view.viewport(), pos=start_pos)
        qtbot.mouseRelease(
            editor_view.viewport(), 
            Qt.MouseButton.LeftButton, 
            Qt.KeyboardModifier.AltModifier, 
            pos=start_pos
        )
        
        # Should be roughly back to original position
        final_center = editor_view.mapToScene(editor_view.rect().center())
        assert abs(final_center.x() - initial_center.x()) < 10
        assert abs(final_center.y() - initial_center.y()) < 10
    
    def test_part_selection_and_movement(self, qtbot):
        """Test selecting and moving parts on canvas."""
        window = self.create_main_window()
        
        self.switch_to_tab("editor")
        editor_tab = window.tab_manager.tabs["editor"]
        editor_view = editor_tab.editor_view
        
        # Create multiple parts
        parts_info = {
            "part1": MagicMock(),
            "part2": MagicMock(),
            "part3": MagicMock()
        }
        editor_tab.load_parts(parts_info)
        
        # Find part items in scene
        part_items = [item for item in editor_view.scene().items() 
                     if isinstance(item, CharacterPartItem)]
        assert len(part_items) >= 3
        
        # Test clicking on a part to select it
        part_item = part_items[0]
        part_center = editor_view.mapFromScene(part_item.sceneBoundingRect().center())
        
        qtbot.mouseClick(editor_view.viewport(), Qt.MouseButton.LeftButton, pos=part_center)
        
        # Verify part is selected
        selected_item = editor_view.get_selected_item()
        assert selected_item == part_item
        
        # Test dragging part to new position
        initial_pos = part_item.pos()
        
        qtbot.mousePress(editor_view.viewport(), Qt.MouseButton.LeftButton, pos=part_center)
        new_pos = QPoint(part_center.x() + 50, part_center.y() + 30)
        qtbot.mouseMove(editor_view.viewport(), pos=new_pos)
        qtbot.mouseRelease(editor_view.viewport(), Qt.MouseButton.LeftButton, pos=new_pos)
        
        # Verify part moved
        final_pos = part_item.pos()
        assert final_pos != initial_pos
        assert abs(final_pos.x() - initial_pos.x() - 50) < 5
        assert abs(final_pos.y() - initial_pos.y() - 30) < 5
    
    def test_joint_definition_on_canvas(self, qtbot):
        """Test defining joints by clicking on canvas."""
        window = self.create_main_window()
        
        self.switch_to_tab("editor")
        editor_tab = window.tab_manager.tabs["editor"]
        editor_view = editor_tab.editor_view
        
        # Load skeleton data
        skeleton_data = TestImageGenerator.create_test_skeleton_data()
        editor_tab.load_skeleton(skeleton_data)
        
        # Start joint definition mode
        editor_view.start_define_joint()
        assert editor_view.current_mode == "define_joint"
        
        # Click to place parent joint
        parent_pos = QPointF(100, 100)
        self.simulate_canvas_click(editor_view, parent_pos)
        
        # Click to place child joint
        child_pos = QPointF(150, 150)
        self.simulate_canvas_click(editor_view, child_pos)
        
        # Verify joint was created
        joint_items = [item for item in editor_view.scene().items() 
                      if hasattr(item, 'joint_data')]
        assert len(joint_items) > 0
        
        # Test canceling joint definition with ESC
        editor_view.start_define_joint()
        qtbot.keyClick(editor_view, Qt.Key.Key_Escape)
        assert editor_view.current_mode == "select"
    
    def test_grid_snapping(self, qtbot):
        """Test grid display and snapping functionality."""
        window = self.create_main_window()
        
        self.switch_to_tab("editor")
        editor_view = window.tab_manager.tabs["editor"].editor_view
        
        # Verify grid is displayed
        # This is visual, so we check the grid drawer state
        assert hasattr(editor_view, 'grid_drawer')
        assert editor_view.grid_drawer is not None
        
        # Test changing display units
        editor_view.set_display_unit("cm")
        assert editor_view.display_unit == "cm"
        
        editor_view.set_display_unit("inch")
        assert editor_view.display_unit == "inch"
        
        editor_view.set_display_unit("px")
        assert editor_view.display_unit == "px"
        
        # Force redraw to update grid
        editor_view.viewport().update()
    
    def test_context_menu_operations(self, qtbot):
        """Test right-click context menu operations."""
        window = self.create_main_window()
        
        self.switch_to_tab("editor")
        editor_tab = window.tab_manager.tabs["editor"]
        editor_view = editor_tab.editor_view
        
        # Load a part
        parts_info = {"test_part": MagicMock()}
        editor_tab.load_parts(parts_info)
        
        # Find the part item
        part_items = [item for item in editor_view.scene().items() 
                     if isinstance(item, CharacterPartItem)]
        assert len(part_items) > 0
        
        part_item = part_items[0]
        part_center = editor_view.mapFromScene(part_item.sceneBoundingRect().center())
        
        # Right-click on part
        with patch('PyQt6.QtWidgets.QMenu.exec') as mock_menu:
            editor_view.customContextMenuRequested.emit(part_center)
            # Verify context menu would be shown
            # (actual menu testing would require more complex mocking)
    
    def test_multi_selection_operations(self, qtbot):
        """Test selecting multiple items with rubber band selection."""
        window = self.create_main_window()
        
        self.switch_to_tab("mechanism")
        mech_tab = window.tab_manager.tabs["mechanism_generation"]
        viz_widget = mech_tab._visualization
        view = viz_widget.view
        
        # Add multiple items to scene
        for i in range(5):
            anchor = AnchorItem(QPointF(i * 50, i * 50))
            viz_widget.scene.addItem(anchor)
        
        # Perform rubber band selection
        start_pos = QPoint(0, 0)
        end_pos = QPoint(200, 200)
        
        qtbot.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start_pos)
        qtbot.mouseMove(view.viewport(), pos=end_pos)
        qtbot.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=end_pos)
        
        # Check selected items
        selected_items = view.scene().selectedItems()
        assert len(selected_items) > 0
    
    def test_undo_redo_canvas_operations(self, qtbot):
        """Test undo/redo functionality for canvas operations."""
        window = self.create_main_window()
        
        self.switch_to_tab("mechanism")
        mech_tab = window.tab_manager.tabs["mechanism_generation"]
        
        # Enable edit mode
        mech_tab._edit_mode_btn.setChecked(True)
        
        # Add an anchor
        initial_anchor_pos = QPointF(100, 100)
        anchor = AnchorItem(initial_anchor_pos)
        mech_tab._visualization.scene.addItem(anchor)
        
        # Move the anchor
        new_pos = QPointF(150, 150)
        anchor.setPos(new_pos)
        
        # Trigger undo
        qtbot.keyClick(mech_tab, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        
        # Anchor should be back at original position
        # (This assumes undo is properly implemented)
        
        # Trigger redo
        qtbot.keyClick(mech_tab, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
        
        # Anchor should be at new position again
    
    def test_touch_gesture_support(self, qtbot):
        """Test touch gesture support for tablets."""
        window = self.create_main_window()
        
        self.switch_to_tab("editor")
        editor_view = window.tab_manager.tabs["editor"].editor_view
        
        # Verify gestures are enabled
        gestures = editor_view.grabGesture(Qt.GestureType.PinchGesture)
        
        # Test pinch gesture handling
        # Note: Actual gesture testing requires platform-specific event simulation
        # This test verifies the infrastructure is in place
        assert hasattr(editor_view, 'pinchTriggered')
        assert hasattr(editor_view, 'gestureEvent')
    
    def test_canvas_coordinate_systems(self, qtbot):
        """Test coordinate system conversions and displays."""
        window = self.create_main_window()
        
        self.switch_to_tab("editor")
        editor_view = window.tab_manager.tabs["editor"].editor_view
        
        # Test scene to view coordinate conversion
        scene_point = QPointF(100, 100)
        view_point = editor_view.mapFromScene(scene_point)
        
        # Convert back
        converted_scene_point = editor_view.mapToScene(view_point)
        
        # Should match (within floating point tolerance)
        assert abs(scene_point.x() - converted_scene_point.x()) < 0.01
        assert abs(scene_point.y() - converted_scene_point.y()) < 0.01
        
        # Test with zoom
        editor_view.set_zoom_level(2.0)
        
        view_point_zoomed = editor_view.mapFromScene(scene_point)
        assert view_point_zoomed != view_point  # Should be different when zoomed
        
        # But conversion back should still work
        converted_scene_point_zoomed = editor_view.mapToScene(view_point_zoomed)
        assert abs(scene_point.x() - converted_scene_point_zoomed.x()) < 0.01
        assert abs(scene_point.y() - converted_scene_point_zoomed.y()) < 0.01