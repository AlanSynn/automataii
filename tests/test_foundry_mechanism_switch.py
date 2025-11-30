import sys
import pytest
from PyQt6.QtWidgets import QApplication
from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView

pytest.skip("Manual GUI exercise; skip during automated pytest runs.", allow_module_level=True)

app = QApplication(sys.argv)
view = MechanismFoundryView()
view.show()

print("\n=== Initial State ===")
print(
    f"Current mechanism: {view.current_mechanism.mechanism_type if view.current_mechanism else None}"
)
print(f"Current parameters: {view.current_parameters}")
print(f"Parameter sliders: {list(view.parameter_sliders.keys())}")

if view.mechanism_selector and view.mechanism_selector.count() > 1:
    print(f"\n=== Switching to mechanism index 1 ===")
    view.mechanism_selector.setCurrentIndex(1)

    print(
        f"New mechanism: {view.current_mechanism.mechanism_type if view.current_mechanism else None}"
    )
    print(f"New parameters: {view.current_parameters}")
    print(f"New parameter sliders: {list(view.parameter_sliders.keys())}")

    print(f"\n=== Switching back to mechanism index 0 ===")
    view.mechanism_selector.setCurrentIndex(0)

    print(
        f"Back to mechanism: {view.current_mechanism.mechanism_type if view.current_mechanism else None}"
    )
    print(f"Back to parameters: {view.current_parameters}")
    print(f"Back to parameter sliders: {list(view.parameter_sliders.keys())}")

print("\n=== Test Complete ===")
print("Close the window to exit.")

sys.exit(app.exec())
