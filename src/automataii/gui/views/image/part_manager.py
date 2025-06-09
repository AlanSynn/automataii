"""Character parts management for the image view."""

import logging
from typing import Dict, Optional
from PyQt6.QtCore import QPointF
from pathlib import Path

from ....core.models.mechanism import PartInfo
from ...graphics_items.part_item import CharacterPartItem


class PartManager:
    """Manages character parts loading and display."""

    def __init__(self, view, project_dir: Path):
        self.view = view
        self.project_dir = project_dir
        self.part_items: Dict[str, CharacterPartItem] = {}
        self.joint_to_part_map: Dict[str, CharacterPartItem] = {}
        self.skeleton_to_part_map: Dict[str, str] = {}

    def clear_character_parts(self):
        """Removes all CharacterPartItem instances from the scene."""
        logging.debug(
            f"PartManager: Clearing {len(self.part_items)} character part items."
        )
        for part_item in self.part_items.values():
            if part_item.scene() == self.view.scene():
                self.view.scene().removeItem(part_item)
        self.part_items.clear()
        self.joint_to_part_map.clear()

    def load_character_parts(
        self,
        parts_data: Dict[str, PartInfo],
        skeleton_to_part_map: Dict[str, str],
        effective_bbox_offset: QPointF,
    ):
        """Loads and displays CharacterPartItems based on parts_data."""
        self.clear_character_parts()  # Clear existing parts first

        if not self.view.scene():
            logging.error(
                "PartManager: Scene not available to load character parts."
            )
            return

        if not parts_data:
            logging.warning(
                "PartManager: No parts_data provided to load_character_parts."
            )
            return

        logging.info(f"PartManager: Loading {len(parts_data)} character parts.")

        self.skeleton_to_part_map = skeleton_to_part_map  # Store the map

        for part_name, part_info_obj in parts_data.items():
            if not isinstance(part_info_obj, PartInfo):
                logging.warning(
                    f"PartManager: Item '{part_name}' in parts_data is not a PartInfo object. Skipping."
                )
                continue

            try:
                # Create the CharacterPartItem
                part_item = CharacterPartItem(part_info_obj, self.project_dir)

                # Default position is (0,0)
                item_x = 0.0
                item_y = 0.0

                if part_info_obj.roi and len(part_info_obj.roi) == 4:
                    # If ROI exists, position based on ROI
                    item_x += part_info_obj.roi[0]
                    item_y += part_info_obj.roi[1]
                    logging.debug(
                        f"PartManager: Positioning '{part_name}' using ROI "
                        f"({part_info_obj.roi[0]}, {part_info_obj.roi[1]}). "
                        f"Pos: ({item_x}, {item_y})"
                    )
                else:
                    logging.debug(
                        f"PartManager: Positioning '{part_name}' at texture origin (0,0) "
                        "due to no ROI."
                    )

                part_item.setPos(item_x, item_y)
                part_item.setZValue(10)  # Parts above image, below skeleton visuals
                part_item.setVisible(False)  # Initially hidden

                self.view.scene().addItem(part_item)
                self.part_items[part_name] = part_item

                # Map controlling skeleton joint to this part item
                for skel_joint_name, controlled_part_name in skeleton_to_part_map.items():
                    if controlled_part_name == part_name:
                        self.joint_to_part_map[skel_joint_name] = part_item
                        logging.debug(
                            f"PartManager: Mapped skeleton joint '{skel_joint_name}' "
                            f"to control part '{part_name}'."
                        )
                        break

            except Exception as e:
                logging.error(
                    f"PartManager: Error creating/loading CharacterPartItem "
                    f"for '{part_name}': {e}"
                )

        logging.info(
            f"PartManager: Loaded {len(self.part_items)} part items. "
            f"Mapped {len(self.joint_to_part_map)} joints to parts."
        )

    def show_part_visuals(self, show: bool):
        """Shows or hides the CharacterPartItem visuals."""
        for part_item in self.part_items.values():
            part_item.setVisible(show)
        logging.debug(
            f"PartManager: Character part visuals visibility set to {show}"
        )
        # When showing parts, typically hide the base image texture
        if hasattr(self.view, 'image_manager') and self.view.image_manager.image_item:
            self.view.image_manager.image_item.setVisible(not show)

    def update_linked_part_position(
        self, joint_name: str, new_joint_scene_pos: QPointF
    ):
        """Moves the CharacterPartItem linked to the given joint name."""
        part_name_to_move = self.skeleton_to_part_map.get(joint_name)

        if part_name_to_move and part_name_to_move in self.part_items:
            part_item = self.part_items[part_name_to_move]

            # Get the vector from part_item's origin to its anchor_offset
            anchor_vector_in_scene = part_item.transform().map(
                part_item.anchor_offset
            ) - part_item.transform().map(QPointF(0, 0))

            # The new position of the part's origin
            new_part_origin_scene_pos = new_joint_scene_pos - anchor_vector_in_scene
            part_item.setPos(new_part_origin_scene_pos)

            logging.debug(
                f"Moved part '{part_name_to_move}' to scene pos {part_item.pos()} "
                f"to align its anchor with joint '{joint_name}' at {new_joint_scene_pos}"
            )
        else:
            logging.debug(
                f"No part found or mapped to move for joint '{joint_name}'. "
                f"Searched for part: {part_name_to_move}"
            )