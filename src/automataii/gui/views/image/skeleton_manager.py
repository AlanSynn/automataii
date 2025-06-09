"""Skeleton data management and visualization."""

import logging
from typing import Dict, List, Optional, Any
from PyQt6.QtWidgets import QGraphicsLineItem, QGraphicsEllipseItem, QGraphicsTextItem
from PyQt6.QtGui import QPen, QBrush, QColor
from PyQt6.QtCore import Qt, QPointF, QLineF


class SkeletonManager:
    """Manages skeleton data loading, visualization, and storage."""
    
    def __init__(self, view):
        self.view = view
        self.joints: Dict[str, Any] = {}  # Joint name to joint item
        self.joint_labels: Dict[str, QGraphicsTextItem] = {}
        self.lines: List[Any] = []  # List of skeleton line items
        self.original_skeleton_data: Optional[dict] = None
        self._skeleton_viz_items: List[Any] = []  # Temporary visualization items
    
    def load_skeleton(self, skeleton_data_dict: Optional[dict]) -> bool:
        """Loads skeleton data and prepares for visualization."""
        if not self.view.scene() or not hasattr(self.view, 'image_manager') or not self.view.image_manager.image_item:
            logging.error("Scene or image_item not available for skeleton loading.")
            return False
        
        # Handle None input gracefully
        if skeleton_data_dict is None:
            logging.info("SkeletonManager: load_skeleton called with None. Clearing skeleton.")
            self.clear_skeleton()
            self.original_skeleton_data = None
            self.view.scene().update()
            return True
        
        logging.info(
            f"SkeletonManager: load_skeleton called with keys: "
            f"{list(skeleton_data_dict.keys()) if skeleton_data_dict else 'None'}"
        )
        
        self.clear_skeleton()  # Clear previous skeleton
        self.original_skeleton_data = skeleton_data_dict  # Store the raw data
        
        char_cfg_skeleton_list = skeleton_data_dict.get("skeleton")
        if not isinstance(char_cfg_skeleton_list, list):
            logging.error(
                f"Skeleton data format error: 'skeleton' key not found or not a list. "
                f"Got: {type(char_cfg_skeleton_list)}"
            )
            self.original_skeleton_data = None
            return False
        
        # Visualize the skeleton after loading
        self.visualize_skeleton(skeleton_data_dict)
        
        logging.info(
            "SkeletonManager: Skeleton data processed and visualized. "
            "Interactive editing is disabled."
        )
        self.view.scene().update()
        return True
    
    def get_skeleton_data(self) -> Optional[dict]:
        """Returns the current skeleton data, preserving original format if possible."""
        if not self.joints:
            return None
        
        output_data = {}
        output_skeleton = None
        
        # Try to preserve original structure
        if self.original_skeleton_data:
            output_data = self.original_skeleton_data.copy()  # Preserve other keys
            original_structure = self.original_skeleton_data.get("skeleton")
            
            if isinstance(original_structure, list):
                output_skeleton = []
                original_map = {
                    j.get("name"): j for j in original_structure if j.get("name")
                }
                for name, skel_joint in self.joints.items():
                    # Update existing or add new
                    new_joint_data = original_map.get(name, {"name": name}).copy()
                    new_joint_data["loc"] = [
                        int(skel_joint.pos().x()),
                        int(skel_joint.pos().y()),
                    ]
                    # Preserve parent if it existed
                    if "parent" not in new_joint_data:
                        new_joint_data["parent"] = None
                    output_skeleton.append(new_joint_data)
            
            elif isinstance(original_structure, dict):
                output_skeleton = {}  # Keep dict structure
                for name, skel_joint in self.joints.items():
                    # Update existing or add new
                    new_joint_data = original_structure.get(name, {}).copy()
                    new_joint_data["x"] = int(skel_joint.pos().x())
                    new_joint_data["y"] = int(skel_joint.pos().y())
                    output_skeleton[name] = new_joint_data
                # Preserve bone_list if it exists
                if "bone_list" in self.original_skeleton_data:
                    output_data["bone_list"] = self.original_skeleton_data["bone_list"]
        
        # Fallback: create list format if no original data
        if output_skeleton is None:
            output_skeleton = []
            for name, skel_joint in self.joints.items():
                output_skeleton.append(
                    {
                        "name": name,
                        "loc": [int(skel_joint.pos().x()), int(skel_joint.pos().y())],
                        "parent": None,  # Cannot easily infer parent here
                    }
                )
        
        output_data["skeleton"] = output_skeleton
        return output_data
    
    def visualize_skeleton(self, skeleton_data: dict, joint_items: list = None):
        """Temporarily draws the skeleton structure on the scene."""
        self.clear_skeleton_visualization()  # Clear previous visualization
        
        if (
            not skeleton_data
            or "skeleton" not in skeleton_data
            or not isinstance(skeleton_data["skeleton"], list)
        ):
            logging.warning(
                "visualize_skeleton called with invalid or missing skeleton data."
            )
            return
        
        skeleton_list = skeleton_data["skeleton"]
        
        # Get bbox origin offset if available
        bbox_x = skeleton_data.get("bbox_origin_x", 0)
        bbox_y = skeleton_data.get("bbox_origin_y", 0)
        
        # Convert joint locations from cropped coordinates to scene coordinates
        joint_locations = {}
        for j in skeleton_list:
            if j.get("name") and j.get("loc") and len(j.get("loc")) >= 2:
                # Add bbox origin offset to convert from cropped to full image coordinates
                x = float(j["loc"][0]) + bbox_x
                y = float(j["loc"][1]) + bbox_y
                joint_locations[j["name"]] = QPointF(x, y)
        
        bone_pen = QPen(QColor("#FF5733"), 2, Qt.PenStyle.SolidLine)  # Bright orange
        joint_brush = QBrush(QColor("#FFC300"))  # Yellow for joints
        joint_pen = QPen(QColor("#C70039"), 1)  # Dark red outline
        joint_radius = 4
        
        # Draw bones
        for joint_info in skeleton_list:
            child_name = joint_info.get("name")
            parent_name = joint_info.get("parent")
            
            if (
                child_name in joint_locations
                and parent_name
                and parent_name in joint_locations
            ):
                p1 = joint_locations[parent_name]
                p2 = joint_locations[child_name]
                bone_line = QGraphicsLineItem(QLineF(p1, p2))
                bone_line.setPen(bone_pen)
                bone_line.setZValue(500)  # Draw on top
                self.view.scene().addItem(bone_line)
                self._skeleton_viz_items.append(bone_line)
        
        # Draw joints (circles)
        for name, loc in joint_locations.items():
            joint_circle = QGraphicsEllipseItem(
                loc.x() - joint_radius,
                loc.y() - joint_radius,
                joint_radius * 2,
                joint_radius * 2,
            )
            joint_circle.setBrush(joint_brush)
            joint_circle.setPen(joint_pen)
            joint_circle.setZValue(501)  # Draw on top of bones
            self.view.scene().addItem(joint_circle)
            self._skeleton_viz_items.append(joint_circle)
        
        logging.info(
            f"Visualizing skeleton with {len(joint_locations)} joints and associated bones."
        )
    
    def clear_skeleton_visualization(self):
        """Clears temporary skeleton visualization items."""
        for item in self._skeleton_viz_items:
            if item.scene():
                self.view.scene().removeItem(item)
        self._skeleton_viz_items.clear()
    
    def clear_skeleton(self):
        """Clears all skeleton-related items from the scene."""
        for joint in self.joints.values():
            if joint.scene():
                self.view.scene().removeItem(joint)
        self.joints.clear()
        
        for line in self.lines:
            if line.scene():
                self.view.scene().removeItem(line)
        self.lines.clear()
        
        self.clear_joint_labels()
        self.clear_skeleton_visualization()
    
    def clear_joint_labels(self):
        """Removes all joint label text items from the scene."""
        for label_item in self.joint_labels.values():
            if label_item.scene():
                self.view.scene().removeItem(label_item)
        self.joint_labels.clear()
    
    def show_skeleton_visuals(self, show: bool):
        """Shows or hides the skeleton joint and line visuals."""
        # Show/hide visualization items
        for item in self._skeleton_viz_items:
            item.setVisible(show)
        
        # Also show/hide any interactive items if they exist
        for joint_item in self.joints.values():
            joint_item.setVisible(show)
        for label_item in self.joint_labels.values():
            label_item.setVisible(show)
        for line_item in self.lines:
            line_item.setVisible(show)
        
        logging.debug(f"SkeletonManager: Skeleton visuals visibility set to {show}")
    
    def update_joint_label_position(self, joint_name: str):
        """Updates the position of a joint's label based on the joint's current position."""
        if joint_name in self.joints and joint_name in self.joint_labels:
            joint_item = self.joints[joint_name]
            label_item = self.joint_labels[joint_name]
            label_item.setPos(joint_item.pos() + QPointF(5, -10))
    
    def update_lines(self, joint_item):
        """Updates the lines connected to a moved joint."""
        # Placeholder - would update connected skeleton lines
        pass
    
    def get_lines_connected_to_joint(self, target_joint):
        """Returns a list of line items connected to the target joint."""
        # Placeholder - would return connected lines
        return []