"""
Golden Master Tests for Domain State Classes.

These tests capture the expected behavior of domain state classes
to ensure refactoring doesn't change their semantics.
"""

from automataii.domain.mechanisms.core.state import (
    ForceType,
    ForceVector,
    MechanismState,
    RenderConfig,
    SafetyLevel,
    SafetyStatus,
)


class TestForceVectorGoldenMaster:
    """Golden master tests for ForceVector."""

    def test_force_vector_defaults(self, golden_master):
        """Capture default color assignments for each force type."""
        force_defaults = {}

        for force_type in ForceType:
            force = ForceVector(
                position=(0.0, 0.0),
                magnitude=100.0,
                angle=0.0,
                force_type=force_type,
            )
            force_defaults[force_type.value] = {
                "color": force.color,
                "label": force.label,
            }

        snapshot = golden_master("force_vector_defaults")
        snapshot.assert_matches(
            force_defaults,
            message="ForceVector default colors for each force type",
        )

    def test_force_vector_components(self, golden_master):
        """Capture force component calculations at various angles."""
        component_results = {}

        test_angles = [0, 30, 45, 60, 90, 120, 135, 150, 180, 225, 270, 315]

        for angle in test_angles:
            force = ForceVector(
                position=(0.0, 0.0),
                magnitude=100.0,
                angle=float(angle),
                force_type=ForceType.APPLIED,
            )
            fx, fy = force.to_components()
            component_results[str(angle)] = {
                "fx": round(fx, 6),
                "fy": round(fy, 6),
            }

        snapshot = golden_master("force_vector_components")
        snapshot.assert_matches(
            component_results,
            message="Force components at various angles",
        )


class TestMechanismStateGoldenMaster:
    """Golden master tests for MechanismState."""

    def test_mechanism_state_defaults(self, golden_master):
        """Capture default values for MechanismState."""
        state = MechanismState(
            positions={"joint_A": (0.0, 0.0), "joint_B": (100.0, 50.0)},
        )

        snapshot = golden_master("mechanism_state_defaults")
        snapshot.assert_matches(
            {
                "positions": state.positions,
                "velocities": state.velocities,
                "forces": state.forces,
                "safety_level": state.safety_status.level.value,
                "safety_message": state.safety_status.message,
                "metadata": state.metadata,
            },
            message="MechanismState default values",
        )

    def test_mechanism_state_with_forces(self, golden_master):
        """Capture MechanismState with forces."""
        force1 = ForceVector(
            position=(50.0, 25.0),
            magnitude=150.0,
            angle=45.0,
            force_type=ForceType.APPLIED,
        )
        force2 = ForceVector(
            position=(100.0, 50.0),
            magnitude=75.0,
            angle=180.0,
            force_type=ForceType.REACTION,
        )

        state = MechanismState(
            positions={"joint_A": (0.0, 0.0), "joint_B": (100.0, 50.0)},
            velocities={"joint_A": (0.0, 0.0), "joint_B": (10.0, 5.0)},
            forces={"input_force": force1, "output_force": force2},
            safety_status=SafetyStatus(level=SafetyLevel.WARNING, message="High stress detected"),
            metadata={"simulation_time": 1.5},
        )

        # Serialize forces for comparison
        forces_data = {}
        if state.forces:
            for name, force in state.forces.items():
                fx, fy = force.to_components()
                forces_data[name] = {
                    "position": force.position,
                    "magnitude": force.magnitude,
                    "angle": force.angle,
                    "type": force.force_type.value,
                    "components": (round(fx, 6), round(fy, 6)),
                }

        snapshot = golden_master("mechanism_state_with_forces")
        snapshot.assert_matches(
            {
                "positions": state.positions,
                "velocities": state.velocities,
                "forces": forces_data,
                "safety_level": state.safety_status.level.value,
                "safety_message": state.safety_status.message,
                "metadata": state.metadata,
            },
            message="MechanismState with forces",
        )


class TestRenderConfigGoldenMaster:
    """Golden master tests for RenderConfig."""

    def test_render_config_defaults(self, golden_master):
        """Capture default RenderConfig values."""
        config = RenderConfig()

        snapshot = golden_master("render_config_defaults")
        snapshot.assert_matches(
            {
                "show_forces": config.show_forces,
                "show_safety_zones": config.show_safety_zones,
                "show_labels": config.show_labels,
                "show_trails": config.show_trails,
                "color_scheme": config.color_scheme,
                "scale": config.scale,
            },
            message="RenderConfig default values",
        )


class TestSafetyStatusGoldenMaster:
    """Golden master tests for SafetyStatus."""

    def test_safety_levels(self, golden_master):
        """Capture all safety levels and their values."""
        levels = {}
        for level in SafetyLevel:
            status = SafetyStatus(level=level, message=f"Test {level.value}")
            levels[level.value] = {
                "message": status.message,
                "details": status.details,
            }

        snapshot = golden_master("safety_levels")
        snapshot.assert_matches(
            levels,
            message="Safety levels and their representations",
        )
