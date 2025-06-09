"""Test script for the refactored recommendation dialog."""

if __name__ == "__main__":
    import sys
    import logging
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QPainterPath
    
    from dialog import MechanismRecommendationDialog

    logging.basicConfig(level=logging.DEBUG)

    app = QApplication(sys.argv)

    # Create a dummy user motion path
    user_path = QPainterPath()
    user_path.moveTo(10, 10)
    user_path.lineTo(50, 80)
    user_path.quadTo(100, 100, 150, 50)
    
    # Dummy file path (would be real path in actual usage)
    dummy_filepath = "generated_mechanism_paths.json"

    # Test the dialog
    selected_mechanism = MechanismRecommendationDialog.get_recommendation(
        user_path, dummy_filepath, parent=None
    )
    
    if selected_mechanism:
        print(f"Mechanism selected: {selected_mechanism.get('name')}")
    else:
        print("Dialog cancelled or no mechanism selected.")

    sys.exit(app.exec())