import sys

from PyQt6.QtWidgets import QApplication

from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView

if __name__ == "__main__":
    app = QApplication(sys.argv)

    view = MechanismFoundryView()
    view.setWindowTitle("Enhanced Info Panel Test")
    view.resize(1400, 900)
    view.show()

    print("✓ Enhanced info panel test started")
    print("✓ Check the right-side info panel for rich educational content")
    print("✓ Switch between mechanisms to see different content")

    sys.exit(app.exec())
