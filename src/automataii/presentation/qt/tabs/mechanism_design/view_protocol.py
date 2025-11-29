"""
View Protocol for MechanismDesignTab.

Defines the minimal interface that the View (Tab) must provide to the Presenter.
This enables true MVP separation and makes the Tab a "Passive View".

Architecture: MVP - Passive View Pattern
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from PyQt6.QtCore import QPointF
    from PyQt6.QtGui import QPainterPath
    from PyQt6.QtWidgets import QGraphicsItem, QGraphicsScene


@runtime_checkable
class MechanismDesignView(Protocol):
    """
    Protocol defining what the View must provide to the Presenter.

    The View (Tab) is responsible for:
    - Owning Qt widgets and scene
    - Rendering visual items
    - Capturing user input and forwarding to Presenter
    - Updating UI based on Presenter signals

    The View must NOT contain business logic.
    """

    # === SCENE ACCESS ===

    @property
    def mechanism_scene(self) -> "QGraphicsScene":
        """The graphics scene for mechanism visualization."""
        ...

    @property
    def mechanism_view(self) -> Any:
        """The graphics view widget."""
        ...

    # === UI UPDATE METHODS ===

    def update_ui_state(self, has_paths: bool, has_mechanisms: bool, animation_running: bool) -> None:
        """Update UI button states based on current state."""
        ...

    def update_mechanism_list(self, items: list[dict]) -> None:
        """Update the mechanism layers list widget."""
        ...

    def show_message(self, title: str, message: str, level: str = "info") -> None:
        """Show a message to the user (info, warning, error)."""
        ...

    # === VISUAL RENDERING ===

    def add_visual_items_to_scene(self, items: list["QGraphicsItem"]) -> None:
        """Add visual items to the scene."""
        ...

    def remove_visual_items_from_scene(self, items: list["QGraphicsItem"]) -> None:
        """Remove visual items from the scene."""
        ...

    def update_scene(self) -> None:
        """Force scene update/repaint."""
        ...

    # === VISUAL FACTORY ACCESS ===

    def create_mechanism_visuals(
        self, mechanism_type: str, data: dict, transform_func: Any
    ) -> list["QGraphicsItem"]:
        """Create visual items for a mechanism type."""
        ...

    # === SKELETON VISUALIZATION ===

    def update_skeleton_visualization(self, skeleton_data: dict) -> None:
        """Update skeleton joint/bone visualization."""
        ...

    def clear_skeleton_visualization(self) -> None:
        """Clear skeleton visual items."""
        ...

    # === PART ITEM ACCESS ===

    def get_part_item(self, part_name: str) -> Any | None:
        """Get the CharacterPartItem for a part name."""
        ...

    def set_part_position(self, part_name: str, position: "QPointF") -> None:
        """Set position of a part item."""
        ...

    # === ANIMATION TIMER ===

    def start_animation_timer(self, interval_ms: int) -> None:
        """Start the animation timer."""
        ...

    def stop_animation_timer(self) -> None:
        """Stop the animation timer."""
        ...

    def is_animation_timer_active(self) -> bool:
        """Check if animation timer is running."""
        ...


@runtime_checkable
class MechanismDesignPresenterProtocol(Protocol):
    """
    Protocol defining what the Presenter must provide.

    The Presenter is responsible for:
    - All business logic
    - State management
    - Coordinating services
    - Telling the View what to display
    """

    # === LIFECYCLE ===

    def activate(self) -> None:
        """Called when tab becomes active."""
        ...

    def deactivate(self) -> None:
        """Called when tab becomes inactive."""
        ...

    # === USER ACTIONS ===

    def on_start_animation(self) -> None:
        """Handle start animation request."""
        ...

    def on_stop_animation(self) -> None:
        """Handle stop animation request."""
        ...

    def on_reset_animation(self) -> None:
        """Handle reset animation request."""
        ...

    def on_layer_selected(self, layer_id: str | None) -> None:
        """Handle layer selection change."""
        ...

    def on_layer_toggled(self, layer_id: str, enabled: bool) -> None:
        """Handle layer enable/disable toggle."""
        ...

    def on_get_recommendations(self) -> None:
        """Handle recommendation request."""
        ...

    def on_export_blueprint(self) -> None:
        """Handle blueprint export request."""
        ...

    # === DATA INPUT ===

    def set_path_data(self, path_data: dict[str, "QPainterPath"]) -> None:
        """Receive path data from editor."""
        ...

    def set_parts_data(self, parts_data: dict[str, Any]) -> None:
        """Receive parts data from editor."""
        ...

    def set_skeleton_data(self, skeleton_data: dict | None) -> None:
        """Receive skeleton data."""
        ...

    # === MECHANISM GENERATION ===

    def generate_mechanism_from_candidate(self, candidate_data: dict) -> None:
        """Generate mechanism from recommendation candidate."""
        ...
