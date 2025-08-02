"""
Domain-UI Integration Bridge

Provides integration between domain layer components and PyQt6 UI layer.
This maintains clean architecture separation while enabling UI connectivity.

Architecture:
- Domain layer: Pure business logic, no UI dependencies
- UI layer: PyQt6 components with domain integration
- Bridge layer: Connects domain callbacks to PyQt6 signals
"""

from PyQt6.QtCore import QObject, QPointF, pyqtSignal

from automataii.domain.kinematics.core.base_component import KinematicsComponent


class DomainUIBridge(QObject):
    """
    Bridges domain layer components to PyQt6 UI layer.

    Converts domain callbacks to PyQt6 signals and provides
    coordinate system conversions between domain and UI.
    """

    # Signals for UI integration
    error_occurred = pyqtSignal(str)  # Error message
    state_changed = pyqtSignal(dict)  # State data
    target_updated = pyqtSignal(str, float, float)  # effector_id, x, y

    def __init__(self, parent=None):
        super().__init__(parent)
        self._connected_components: dict[str, KinematicsComponent] = {}

    def connect_component(self, component: KinematicsComponent, component_id: str) -> None:
        """
        Connect a domain component to the UI bridge.

        Args:
            component: Domain layer kinematics component
            component_id: Unique identifier for the component
        """
        self._connected_components[component_id] = component

        # Set up callbacks to convert to PyQt6 signals
        component.set_error_callback(lambda msg: self.error_occurred.emit(msg))
        component.set_state_change_callback(lambda state: self.state_changed.emit(state))

    def disconnect_component(self, component_id: str) -> None:
        """Disconnect a component from the UI bridge."""
        if component_id in self._connected_components:
            component = self._connected_components[component_id]
            component.set_error_callback(None)
            component.set_state_change_callback(None)
            del self._connected_components[component_id]

    def get_component(self, component_id: str) -> KinematicsComponent | None:
        """Get a connected component by ID."""
        return self._connected_components.get(component_id)

    @staticmethod
    def tuple_to_qpointf(point: tuple[float, float]) -> QPointF:
        """Convert domain (x, y) tuple to PyQt6 QPointF."""
        return QPointF(point[0], point[1])

    @staticmethod
    def qpointf_to_tuple(point: QPointF) -> tuple[float, float]:
        """Convert PyQt6 QPointF to domain (x, y) tuple."""
        return (float(point.x()), float(point.y()))

    @staticmethod
    def targets_to_qpoints(targets: dict[str, tuple[float, float]]) -> dict[str, QPointF]:
        """Convert domain targets dict to PyQt6 QPointF dict."""
        return {
            effector_id: DomainUIBridge.tuple_to_qpointf(target)
            for effector_id, target in targets.items()
        }

    @staticmethod
    def qpoints_to_targets(qpoints: dict[str, QPointF]) -> dict[str, tuple[float, float]]:
        """Convert PyQt6 QPointF dict to domain targets dict."""
        return {
            effector_id: DomainUIBridge.qpointf_to_tuple(qpoint)
            for effector_id, qpoint in qpoints.items()
        }


class MechanismTargetBridge(QObject):
    """
    Bridges mechanism targets between domain and UI layers.

    Provides the MechanismTargetProvider protocol implementation
    that connects to UI mechanism tabs.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mechanism_tab = None

    def set_mechanism_tab(self, mechanism_tab) -> None:
        """Set the mechanism tab to get targets from."""
        self._mechanism_tab = mechanism_tab

    def get_mechanism_targets(self, progress: float) -> dict[str, tuple[float, float]]:
        """
        Implementation of MechanismTargetProvider protocol.

        Args:
            progress: Animation progress from 0.0 to 1.0

        Returns:
            Dictionary mapping effector IDs to target positions as (x, y) tuples
        """
        if not self._mechanism_tab:
            return {}

        # Get QPointF targets from mechanism tab
        qpoint_targets = self._mechanism_tab.get_mechanism_targets(progress)

        # Convert to domain tuples
        return DomainUIBridge.qpoints_to_targets(qpoint_targets)


class UIIntegrationManager:
    """
    Manages UI integration for the entire application.

    Provides centralized management of domain-UI bridges and
    coordinate system conversions.
    """

    def __init__(self):
        self.main_bridge = DomainUIBridge()
        self.target_bridge = MechanismTargetBridge()
        self._component_bridges: dict[str, DomainUIBridge] = {}

    def create_component_bridge(self, component_id: str) -> DomainUIBridge:
        """Create a new UI bridge for a specific component."""
        bridge = DomainUIBridge()
        self._component_bridges[component_id] = bridge
        return bridge

    def get_component_bridge(self, component_id: str) -> DomainUIBridge | None:
        """Get the UI bridge for a specific component."""
        return self._component_bridges.get(component_id)

    def remove_component_bridge(self, component_id: str) -> None:
        """Remove a component bridge."""
        if component_id in self._component_bridges:
            del self._component_bridges[component_id]

    def connect_mechanism_tab(self, mechanism_tab) -> None:
        """Connect a mechanism tab for target provision."""
        self.target_bridge.set_mechanism_tab(mechanism_tab)

    def shutdown(self) -> None:
        """Clean shutdown of all bridges."""
        for bridge in self._component_bridges.values():
            # Disconnect all components
            for component_id in list(bridge._connected_components.keys()):
                bridge.disconnect_component(component_id)

        self._component_bridges.clear()
