"""
Manual test for Path Preview Overlay functionality
Run this to visually verify hover-to-show-path works correctly.

Instructions:
1. Run: uv run python test_path_preview_manual.py
2. Navigate to Mechanism Foundry tab
3. Hover mouse over mechanism points (coupler, output for fourbar)
4. Verify cyan dashed path appears with markers and arrows
5. Verify path auto-fades after 2 seconds
6. Toggle "Path Preview" toolbar button to enable/disable
"""

import sys

from PyQt6.QtWidgets import QApplication


def main():
    print("=" * 60)
    print("PATH PREVIEW MANUAL TEST")
    print("=" * 60)
    print()
    print("Test Steps:")
    print("1. Click 'Mechanism Foundry' tab")
    print("2. Hover over mechanism points (e.g., coupler, output)")
    print("3. Verify cyan dashed path appears")
    print("4. Verify path has markers (small circles)")
    print("5. Verify path has direction arrows")
    print("6. Wait 2 seconds - path should auto-fade")
    print("7. Toggle 'Path Preview' toolbar button")
    print("8. Verify hover no longer shows paths when disabled")
    print()
    print("Expected Behavior:")
    print("  - Hover distance threshold: 20 pixels")
    print("  - Path color: Cyan (0, 206, 209)")
    print("  - Path style: Dashed line")
    print("  - Auto-fade delay: 2 seconds")
    print("  - Z-levels: path(100), markers(101), arrows(102)")
    print()
    print("=" * 60)
    print()

    from automataii.presentation.qt.main_window import AutomataDesigner

    app = QApplication(sys.argv)
    window = AutomataDesigner(debug_mode=False, editing_mode=False)
    window.show()

    tab_widget = window.tab_widget
    for i in range(tab_widget.count()):
        if "Mechanism Foundry" in tab_widget.tabText(i):
            tab_widget.setCurrentIndex(i)
            print(f"✓ Switched to Mechanism Foundry tab (index {i})")
            break

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
