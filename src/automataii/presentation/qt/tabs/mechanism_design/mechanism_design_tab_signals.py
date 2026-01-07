"""
Signal Connection Manager for MechanismDesignTab.

Manages all signal/slot connections in a centralized, organized manner.
Provides clear separation between UI event handling and business logic.

ULTRATHINK Architecture: Centralized signal management for maintainability.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from automataii.presentation.qt.tabs.mechanism_design.tab import MechanismDesignTab


class MechanismDesignTabSignals:
    """
    Manages signal/slot connections for MechanismDesignTab.

    Responsibilities:
    - Centralized signal connection management
    - Organized connection by functional area
    - Easy connection/disconnection for testing
    - Clear documentation of signal flow

    Does NOT handle:
    - Business logic implementation
    - Event processing logic
    - Widget creation
    - UI state management
    """

    def __init__(self, widgets: dict):
        """
        Initialize the signal manager.

        Args:
            widgets: Dictionary of UI widgets to connect signals for
        """
        self.widgets = widgets
        self._connections = []  # Track connections for cleanup

    def connect_all_signals(self, tab: 'MechanismDesignTab') -> None:
        """
        Connect all signals for the mechanism design tab.

        Args:
            tab: The MechanismDesignTab instance to connect signals to
        """
        self._connect_mechanism_generation_signals(tab)
        self._connect_animation_signals(tab)
        self._connect_view_control_signals(tab)
        self._connect_blueprint_signals(tab)
        self._connect_list_signals(tab)
        self._connect_parametric_signals(tab)
        self._connect_external_signals(tab)

    def disconnect_all_signals(self) -> None:
        """Disconnect all managed signals."""
        for connection in self._connections:
            try:
                connection.disconnect()
            except (RuntimeError, TypeError):
                # Signal already disconnected or object deleted
                pass
        self._connections.clear()

    def _connect_mechanism_generation_signals(self, tab: 'MechanismDesignTab') -> None:
        """Connect mechanism generation related signals."""
        recommendation_btn = self.widgets.get('recommendation_btn')
        if recommendation_btn and hasattr(tab, '_on_get_recommendations'):
            connection = recommendation_btn.clicked.connect(tab._on_get_recommendations)
            self._connections.append(connection)

        assign_character_btn = self.widgets.get('assign_character_btn')
        if assign_character_btn and hasattr(tab, '_on_assign_character'):
            connection = assign_character_btn.clicked.connect(tab._on_assign_character)
            self._connections.append(connection)

    def _connect_animation_signals(self, tab: 'MechanismDesignTab') -> None:
        """Connect animation control signals."""
        import logging
        play_btn = self.widgets.get('play_btn')
        stop_btn = self.widgets.get('stop_btn')
        reset_btn = self.widgets.get('reset_btn')

        if play_btn and hasattr(tab, '_on_start_animation'):
            logging.info(f"[SIGNAL] Connecting play_btn to tab._on_start_animation, tab_id={id(tab)}")
            connection = play_btn.clicked.connect(tab._on_start_animation)
            self._connections.append(connection)

        if stop_btn and hasattr(tab, '_on_stop_animation'):
            connection = stop_btn.clicked.connect(tab._on_stop_animation)
            self._connections.append(connection)

        if reset_btn and hasattr(tab, '_on_reset_animation'):
            connection = reset_btn.clicked.connect(tab._on_reset_animation)
            self._connections.append(connection)

    def _connect_view_control_signals(self, tab: 'MechanismDesignTab') -> None:
        """Connect view control signals."""
        zoom_in_btn = self.widgets.get('zoom_in_btn')
        zoom_out_btn = self.widgets.get('zoom_out_btn')
        zoom_fit_btn = self.widgets.get('zoom_fit_btn')
        center_character_btn = self.widgets.get('center_character_btn')

        if zoom_in_btn and hasattr(tab, 'mechanism_view'):
            connection = zoom_in_btn.clicked.connect(lambda: tab.mechanism_view.zoom(1))
            self._connections.append(connection)

        if zoom_out_btn and hasattr(tab, 'mechanism_view'):
            connection = zoom_out_btn.clicked.connect(lambda: tab.mechanism_view.zoom(-1))
            self._connections.append(connection)

        if zoom_fit_btn and hasattr(tab, 'mechanism_view'):
            connection = zoom_fit_btn.clicked.connect(tab.mechanism_view.zoom_to_fit)
            self._connections.append(connection)

        if center_character_btn and hasattr(tab, 'center_on_character'):
            connection = center_character_btn.clicked.connect(tab.center_on_character)
            self._connections.append(connection)

    def _connect_blueprint_signals(self, tab: 'MechanismDesignTab') -> None:
        """Connect blueprint export signals."""
        blueprint_btn = self.widgets.get('blueprint_btn')
        if blueprint_btn and hasattr(tab, '_on_export_blueprint'):
            connection = blueprint_btn.clicked.connect(tab._on_export_blueprint)
            self._connections.append(connection)

    def _connect_list_signals(self, tab: 'MechanismDesignTab') -> None:
        """Connect list widget signals."""
        mechanism_layers_list = self.widgets.get('mechanism_layers_list')
        if mechanism_layers_list:
            if hasattr(tab, '_on_layer_selection_changed'):
                connection = mechanism_layers_list.itemSelectionChanged.connect(
                    tab._on_layer_selection_changed
                )
                self._connections.append(connection)

            if hasattr(tab, '_on_layer_item_clicked'):
                connection = mechanism_layers_list.itemClicked.connect(tab._on_layer_item_clicked)
                self._connections.append(connection)

    def _connect_parametric_signals(self, tab: 'MechanismDesignTab') -> None:
        """Connect parametric editing signals."""
        parametric_edit_btn = self.widgets.get('parametric_edit_btn')

        if parametric_edit_btn and hasattr(tab, 'toggle_parametric_mode'):
            connection = parametric_edit_btn.clicked.connect(
                lambda: tab.toggle_parametric_mode()
            )
            self._connections.append(connection)


    def _connect_external_signals(self, tab: 'MechanismDesignTab') -> None:
        """Connect external system signals."""
        # Connect EditorView's joint_bend_direction_changed signal
        if (hasattr(tab, 'mechanism_view') and
            hasattr(tab.mechanism_view, 'joint_bend_direction_changed') and
            hasattr(tab, '_handle_joint_bend_direction_changed')):
            connection = tab.mechanism_view.joint_bend_direction_changed.connect(
                tab._handle_joint_bend_direction_changed
            )
            self._connections.append(connection)

    def get_connection_count(self) -> int:
        """Get the number of active connections."""
        return len(self._connections)

    def is_connected(self, widget_name: str, signal_name: str) -> bool:
        """
        Check if a specific widget signal is connected.

        Args:
            widget_name: Name of the widget
            signal_name: Name of the signal

        Returns:
            True if signal is connected
        """
        widget = self.widgets.get(widget_name)
        if not widget:
            return False

        signal = getattr(widget, signal_name, None)
        if not signal:
            return False

        # Check if signal has any connections
        try:
            # This is a PyQt6-specific way to check connections
            return signal.receivers() > 0
        except AttributeError:
            return False
