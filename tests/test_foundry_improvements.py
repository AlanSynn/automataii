#!/usr/bin/env python3
"""
Test script to verify Mechanism Foundry improvements:
1. Parameter display with units
2. Info panel with current parameter values
3. All toolbar toggles work
"""

import sys

import pytest
from PyQt6.QtWidgets import QApplication

from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView

# Manual GUI verification; skip during automated pytest runs.
pytest.skip(
    "Manual foundry improvements test; skipping in automated pytest.", allow_module_level=True
)


def test_foundry_improvements():
    app = QApplication(sys.argv)

    view = MechanismFoundryView()
    view.setWindowTitle("Mechanism Foundry - Improvements Test")
    view.resize(1400, 800)
    view.show()

    print("=== Foundry View Improvements Test ===")
    print("\n✓ Toolbar exists with:")
    print(f"  - Play action: {view.play_action is not None}")
    print(f"  - Forces action: {view.forces_action is not None}")
    print(f"  - Velocity action: {view.velocity_action is not None}")
    print(f"  - Trail action: {view.trail_action is not None}")

    print("\n✓ Info panel exists:")
    print(f"  - Info text widget: {view.info_text is not None}")

    print("\n✓ Parameter sliders count:", len(view.parameter_sliders))
    print(
        "\n✓ Current mechanism:",
        view.current_mechanism.mechanism_type if view.current_mechanism else "None",
    )

    print("\n=== Manual Test Steps ===")
    print("1. Verify parameter labels show units (e.g., 'Ground Link (mm)')")
    print("2. Verify parameter values update with appropriate precision")
    print("3. Verify info panel shows current parameter values")
    print("4. Click Forces toggle - should hide/show force vectors")
    print("5. Change mechanism using dropdown - info panel should update")
    print("6. Adjust parameters - info panel should update in real-time")
    print("7. Test play/pause animation")

    sys.exit(app.exec())


if __name__ == "__main__":
    test_foundry_improvements()
