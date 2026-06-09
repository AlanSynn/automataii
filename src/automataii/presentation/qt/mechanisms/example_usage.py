"""
Example usage of the modular mechanism system.
Shows how to integrate with existing MechanismDesignTab.
"""

from PyQt6.QtWidgets import QGraphicsScene

from .adapters.mechanism_adapter import MechanismAdapter
from .interfaces.mechanism import MechanismParameters
from .registry import mechanism_registry


def example_create_mechanism():
    """Example: Create a new four-bar mechanism."""

    # Create mechanism parameters
    params = MechanismParameters(
        mechanism_type="four_bar",
        mechanism_id="mechanism_001",
        part_name="left_arm_lower",
        params={
            "anchor1": [0, 0],
            "anchor2": [100, 0],
            "l2": 40,  # Crank length
            "l3": 60,  # Coupler length
            "l4": 50,  # Rocker length
        },
    )

    # Create mechanism through registry
    mechanism = mechanism_registry.create_mechanism(params)

    if mechanism:
        # Validate parameters
        is_valid, msg = mechanism.validate_parameters()
        print(f"Mechanism valid: {is_valid} - {msg}")

        # Run simulation
        simulation = mechanism.simulate(num_frames=100)
        print(f"Simulation frames: {simulation.frames}")

        # Get key points
        key_points = mechanism.get_key_points()
        print(f"Key points: {key_points}")

    return mechanism


def example_create_editor():
    """Example: Create editor for mechanism."""

    # Create graphics scene
    scene = QGraphicsScene()

    # Create editor through registry
    editor = mechanism_registry.create_editor(
        mechanism_type="four_bar", mechanism_id="mechanism_001", scene=scene
    )

    if editor:
        # Create handles
        mechanism_data = {
            "params": {"anchor1": [0, 0], "anchor2": [100, 0], "l2": 40, "l3": 60, "l4": 50}
        }
        handles = editor.create_handles(mechanism_data)
        print(f"Created {len(handles)} handles")

        # Show handles for editing
        editor.show_handles()

    return editor


def example_export_blueprint():
    """Example: Export mechanism as blueprint."""

    # Get serializer from registry
    serializer = mechanism_registry.create_serializer("four_bar")

    if serializer:
        # Prepare mechanism data
        mechanism_data = {
            "parameters": {"anchor1": [0, 0], "anchor2": [100, 0], "l2": 40, "l3": 60, "l4": 50}
        }

        # Serialize to blueprint
        blueprint = serializer.serialize(mechanism_data)
        print(f"Blueprint type: {blueprint.mechanism_type}")
        print(f"Dimensions: {blueprint.dimensions}")

        # Export as SVG
        svg = serializer.export_to_svg(blueprint)
        print(f"SVG length: {len(svg)} characters")

        # Validate blueprint
        is_valid, msg = serializer.validate_blueprint(blueprint)
        print(f"Blueprint valid: {is_valid}")

    return blueprint


def example_adapter_usage():
    """Example: Use adapter for legacy compatibility."""

    adapter = MechanismAdapter()

    # Convert legacy mechanism data
    legacy_data = {
        "type": "4_bar_linkage",
        "id": "legacy_001",
        "part_name": "right_arm_lower",
        "params": {
            "ground_pivot_1": [0, 0],
            "ground_pivot_2": [100, 0],
            "L2": 40,
            "L3": 60,
            "L4": 50,
        },
    }

    # Create mechanism from legacy format
    mechanism = adapter.create_mechanism_from_legacy(legacy_data)

    if mechanism:
        print(f"Created mechanism from legacy: {mechanism.mechanism_type}")

        # Create editor
        scene = QGraphicsScene()
        adapter.create_editor_for_mechanism("legacy_001", scene)

        # Export blueprint
        adapter.export_mechanism_blueprint("legacy_001")

    return adapter


def integrate_with_mechanism_design_tab(tab):
    """
    Integration with existing MechanismDesignTab.

    Replace old system calls with new modular system:

    Old:
        self._create_4bar_linkage_handles(mechanism_id, layer_data)

    New:
        params = MechanismParameters.from_dict(layer_data)
        mechanism = mechanism_registry.create_mechanism(params)
        editor = mechanism_registry.create_editor(params.mechanism_type, mechanism_id, self.scene)
    """

    # Use adapter for gradual migration
    tab.mechanism_adapter = MechanismAdapter()

    # Replace mechanism creation
    def create_mechanism_new(mechanism_data):
        return tab.mechanism_adapter.create_mechanism_from_legacy(mechanism_data)

    # Replace editor creation
    def create_editor_new(mechanism_id):
        return tab.mechanism_adapter.create_editor_for_mechanism(mechanism_id, tab.mechanism_scene)

    # Replace blueprint export
    def export_blueprint_new(mechanism_id):
        return tab.mechanism_adapter.export_mechanism_blueprint(mechanism_id)

    # Monkey patch for testing (in production, properly refactor)
    tab.create_mechanism = create_mechanism_new
    tab.create_editor = create_editor_new
    tab.export_blueprint = export_blueprint_new

    print("Integration complete - using new modular system")


if __name__ == "__main__":
    # Run examples
    print("=== Mechanism Creation ===")
    example_create_mechanism()

    print("\n=== Editor Creation ===")
    example_create_editor()

    print("\n=== Blueprint Export ===")
    example_export_blueprint()

    print("\n=== Adapter Usage ===")
    example_adapter_usage()
