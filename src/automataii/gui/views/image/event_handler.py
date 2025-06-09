"""Event handling for the image view."""

import logging
from typing import Optional
from PyQt6.QtCore import QEvent, QPointF
from PyQt6.QtWidgets import QGraphicsView


class EventHandler:
    """Handles mouse and drag events for the image view."""
    
    def __init__(self, view: QGraphicsView):
        self.view = view
        self.dragged_joint_item = None
        self.drag_start_pos: Optional[QPointF] = None
        self.drag_start_pos_offset: Optional[QPointF] = None
    
    def handle_mouse_press(self, event: QEvent, pos) -> bool:
        """Handle mouse press events. Returns True if event was consumed."""
        # Check if the click is on a joint
        item = self.view.itemAt(pos)
        
        # Currently joints are not interactive (SkeletonJoint removed)
        # This is a placeholder for future interactive elements
        
        # Clear guides if clicking on background
        if hasattr(self.view, 'guide_renderer'):
            self.view.guide_renderer.update_and_draw_cut_guides(None)
        
        return False  # Let the view handle panning
    
    def handle_mouse_move(self, event: QEvent) -> bool:
        """Handle mouse move events. Returns True if event was consumed."""
        if self.dragged_joint_item and self.drag_start_pos:
            current_scene_pos = self.view.mapToScene(event.pos())
            
            # Move the joint to the current mouse position
            self.dragged_joint_item.setPos(
                current_scene_pos + self.drag_start_pos_offset
            )
            
            # Update connected elements
            if hasattr(self.view, 'skeleton_manager'):
                self.view.skeleton_manager.update_lines(self.dragged_joint_item)
                
                # Update label position if joint has a name attribute
                if hasattr(self.dragged_joint_item, 'name'):
                    self.view.skeleton_manager.update_joint_label_position(
                        self.dragged_joint_item.name
                    )
            
            # Update linked parts
            if hasattr(self.view, 'part_manager') and hasattr(self.dragged_joint_item, 'name'):
                self.view.part_manager.update_linked_part_position(
                    self.dragged_joint_item.name,
                    self.dragged_joint_item.scenePos()
                )
            
            # Update guides
            if hasattr(self.view, 'guide_renderer'):
                self.view.guide_renderer.update_and_draw_cut_guides(
                    self.dragged_joint_item
                )
            
            return True  # Consume event
        
        return False
    
    def handle_mouse_release(self, event: QEvent) -> bool:
        """Handle mouse release events. Returns True if event was consumed."""
        if self.dragged_joint_item:
            # Reset state
            self.dragged_joint_item = None
            self.drag_start_pos = None
            self.drag_start_pos_offset = None
            return True
        
        return False
    
    def clear_drag_state(self):
        """Clear any active drag state."""
        self.dragged_joint_item = None
        self.drag_start_pos = None
        self.drag_start_pos_offset = None