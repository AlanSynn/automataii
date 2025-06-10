from PyQt6.QtWidgets import QWidget, QLabel

class EditorTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QLabel("Hello from Editor Tab")
        self.setLayout(self.layout)