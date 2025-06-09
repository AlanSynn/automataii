from ..managers.part_manager import PartManager


class ImageProcessingView(BaseView):
    def show_part_visuals(self, visible: bool):
        """Show or hide the character parts."""
        logging.info(f"ImageProcessingView: Setting parts visibility to {visible}")
        self.part_manager.show_parts(visible)

    def load_parts(self, parts_info: Dict[str, PartInfo]):
        """Loads character parts into the scene."""
        if not self.skeleton_item:
            logging.error("ImageProcessingView: Cannot load parts without a skeleton.")
            return
        logging.info(f"ImageProcessingView: Loading {len(parts_info)} parts via PartManager.")
        self.part_manager.load_parts(parts_info, self.skeleton_item)

    def set_edit_mode(self, enabled: bool):
        """Enable or disable skeleton editing mode."""
        if self.skeleton_item:
# ... existing code ...