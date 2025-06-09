#!/usr/bin/env python3
"""
Visual Test Runner for Automata Base System

This script runs GUI tests in a visual mode where you can see the widgets
being tested. Useful for debugging and understanding test behavior.
"""

import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QSplitter, QTreeWidget, QTreeWidgetItem,
    QLabel, QProgressBar, QCheckBox, QSpinBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor, QPalette, QTextCursor
import unittest
import time
from typing import Dict, List, Optional

# Add module to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tests.gui_test_utils import QtTestCase


class TestRunnerThread(QThread):
    """Thread for running tests without blocking GUI."""
    
    test_started = pyqtSignal(str)  # Test name
    test_finished = pyqtSignal(str, bool, str)  # Test name, success, message
    suite_started = pyqtSignal(str)  # Suite name
    suite_finished = pyqtSignal(str, int, int)  # Suite name, passed, total
    all_finished = pyqtSignal()
    log_message = pyqtSignal(str, str)  # Message, level (info/error/success)
    
    def __init__(self, test_modules: List[str], delay: int = 0):
        super().__init__()
        self.test_modules = test_modules
        self.delay = delay  # Delay between tests in ms
        self.should_stop = False
        
    def run(self):
        """Run all tests."""
        for module_name in self.test_modules:
            if self.should_stop:
                break
                
            self.suite_started.emit(module_name)
            
            try:
                # Import test module
                module = __import__(f"tests.{module_name}", fromlist=[''])
                
                # Find test classes
                test_classes = []
                for name in dir(module):
                    obj = getattr(module, name)
                    if (isinstance(obj, type) and 
                        issubclass(obj, unittest.TestCase) and
                        obj != unittest.TestCase):
                        test_classes.append(obj)
                        
                passed = 0
                total = 0
                
                for test_class in test_classes:
                    if self.should_stop:
                        break
                        
                    # Get test methods
                    test_methods = [m for m in dir(test_class) 
                                   if m.startswith('test_')]
                    
                    for method_name in test_methods:
                        if self.should_stop:
                            break
                            
                        total += 1
                        test_name = f"{test_class.__name__}.{method_name}"
                        self.test_started.emit(test_name)
                        
                        # Add delay for visual effect
                        if self.delay > 0:
                            self.msleep(self.delay)
                        
                        # Run test
                        try:
                            # Create test instance with custom app
                            app = QApplication.instance()
                            test = test_class(method_name)
                            
                            # Setup if needed
                            if hasattr(test, 'setUp'):
                                test.setUp()
                                
                            # Run test method
                            getattr(test, method_name)()
                            
                            # Teardown
                            if hasattr(test, 'tearDown'):
                                test.tearDown()
                                
                            self.test_finished.emit(test_name, True, "Passed")
                            passed += 1
                            
                        except Exception as e:
                            self.test_finished.emit(test_name, False, str(e))
                            self.log_message.emit(f"❌ {test_name}: {str(e)}", "error")
                            
                self.suite_finished.emit(module_name, passed, total)
                
            except Exception as e:
                self.log_message.emit(f"Failed to load module {module_name}: {e}", "error")
                self.suite_finished.emit(module_name, 0, 0)
                
        self.all_finished.emit()
        
    def stop(self):
        """Stop test execution."""
        self.should_stop = True


class VisualTestRunner(QMainWindow):
    """Visual test runner with live widget display."""
    
    def __init__(self):
        super().__init__()
        self.test_thread = None
        self.current_widget = None
        self.test_results = {}
        
        self.setup_ui()
        self.setup_style()
        
    def setup_ui(self):
        """Setup the user interface."""
        self.setWindowTitle("Automata Base System - Visual Test Runner")
        self.setGeometry(100, 100, 1200, 800)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        
        # Main layout
        layout = QVBoxLayout(central)
        
        # Header
        header_layout = QHBoxLayout()
        
        title = QLabel("🧪 Visual Test Runner")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Controls
        self.delay_spinner = QSpinBox()
        self.delay_spinner.setRange(0, 2000)
        self.delay_spinner.setValue(500)
        self.delay_spinner.setSuffix(" ms")
        header_layout.addWidget(QLabel("Delay:"))
        header_layout.addWidget(self.delay_spinner)
        
        self.visual_checkbox = QCheckBox("Show Widgets")
        self.visual_checkbox.setChecked(True)
        header_layout.addWidget(self.visual_checkbox)
        
        self.run_button = QPushButton("▶️ Run Tests")
        self.run_button.clicked.connect(self.run_tests)
        header_layout.addWidget(self.run_button)
        
        self.stop_button = QPushButton("⏹️ Stop")
        self.stop_button.clicked.connect(self.stop_tests)
        self.stop_button.setEnabled(False)
        header_layout.addWidget(self.stop_button)
        
        layout.addLayout(header_layout)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)
        
        # Main content splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel - Test tree
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        left_layout.addWidget(QLabel("Test Results:"))
        
        self.test_tree = QTreeWidget()
        self.test_tree.setHeaderLabels(["Test", "Status"])
        self.test_tree.setColumnWidth(0, 300)
        left_layout.addWidget(self.test_tree)
        
        splitter.addWidget(left_panel)
        
        # Middle panel - Widget display
        middle_panel = QWidget()
        middle_layout = QVBoxLayout(middle_panel)
        
        middle_layout.addWidget(QLabel("Widget Under Test:"))
        
        self.widget_container = QWidget()
        self.widget_container.setMinimumSize(400, 400)
        self.widget_container.setStyleSheet("""
            QWidget {
                background-color: #f0f0f0;
                border: 2px dashed #ccc;
                border-radius: 5px;
            }
        """)
        
        widget_layout = QVBoxLayout(self.widget_container)
        self.widget_label = QLabel("No widget being tested")
        self.widget_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        widget_layout.addWidget(self.widget_label)
        
        middle_layout.addWidget(self.widget_container)
        
        splitter.addWidget(middle_panel)
        
        # Right panel - Log output
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        right_layout.addWidget(QLabel("Test Output:"))
        
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont("Consolas", 9))
        right_layout.addWidget(self.log_output)
        
        splitter.addWidget(right_panel)
        
        # Set splitter sizes
        splitter.setSizes([300, 400, 500])
        
        layout.addWidget(splitter)
        
        # Status bar
        self.statusBar().showMessage("Ready to run tests")
        
    def setup_style(self):
        """Setup application style."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QPushButton {
                padding: 5px 15px;
                border-radius: 3px;
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
            QTreeWidget {
                border: 1px solid #ddd;
                border-radius: 3px;
            }
            QTextEdit {
                border: 1px solid #ddd;
                border-radius: 3px;
                background-color: #ffffff;
            }
        """)
        
    def run_tests(self):
        """Start running tests."""
        # Clear previous results
        self.test_tree.clear()
        self.log_output.clear()
        self.test_results.clear()
        self.progress_bar.setValue(0)
        
        # Disable run button
        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        
        # Get test modules
        test_modules = [
            "test_gui_base_selection",
            "test_gui_preview",
            "test_gui_integration"
        ]
        
        # Create and start test thread
        self.test_thread = TestRunnerThread(
            test_modules,
            self.delay_spinner.value()
        )
        
        # Connect signals
        self.test_thread.test_started.connect(self.on_test_started)
        self.test_thread.test_finished.connect(self.on_test_finished)
        self.test_thread.suite_started.connect(self.on_suite_started)
        self.test_thread.suite_finished.connect(self.on_suite_finished)
        self.test_thread.all_finished.connect(self.on_all_finished)
        self.test_thread.log_message.connect(self.log_message)
        
        # Start thread
        self.test_thread.start()
        
        self.log_message("🚀 Starting test run...", "info")
        
    def stop_tests(self):
        """Stop running tests."""
        if self.test_thread:
            self.test_thread.stop()
            self.test_thread.wait()
            
        self.on_all_finished()
        
    def on_test_started(self, test_name: str):
        """Handle test start."""
        self.statusBar().showMessage(f"Running: {test_name}")
        self.log_message(f"▶️  {test_name}", "info")
        
        # Show widget if visual mode
        if self.visual_checkbox.isChecked():
            self.show_test_widget(test_name)
            
    def on_test_finished(self, test_name: str, success: bool, message: str):
        """Handle test completion."""
        # Update tree
        suite_name = test_name.split('.')[0]
        
        # Find or create suite item
        suite_item = None
        for i in range(self.test_tree.topLevelItemCount()):
            item = self.test_tree.topLevelItem(i)
            if item.text(0) == suite_name:
                suite_item = item
                break
                
        if not suite_item:
            suite_item = QTreeWidgetItem([suite_name, ""])
            self.test_tree.addTopLevelItem(suite_item)
            
        # Add test item
        test_item = QTreeWidgetItem([test_name.split('.')[1], 
                                    "✅ Pass" if success else "❌ Fail"])
        
        if not success:
            test_item.setToolTip(1, message)
            test_item.setForeground(1, QColor("red"))
        else:
            test_item.setForeground(1, QColor("green"))
            
        suite_item.addChild(test_item)
        suite_item.setExpanded(True)
        
        # Update progress
        total_tests = sum(len(v) for v in self.test_results.values()) + 1
        self.progress_bar.setValue(int((total_tests / 30) * 100))  # Approximate
        
        # Store result
        if suite_name not in self.test_results:
            self.test_results[suite_name] = []
        self.test_results[suite_name].append((test_name, success))
        
    def on_suite_started(self, suite_name: str):
        """Handle suite start."""
        self.log_message(f"\n📋 {suite_name}", "info")
        
    def on_suite_finished(self, suite_name: str, passed: int, total: int):
        """Handle suite completion."""
        # Update suite item
        for i in range(self.test_tree.topLevelItemCount()):
            item = self.test_tree.topLevelItem(i)
            if item.text(0) == suite_name:
                item.setText(1, f"{passed}/{total}")
                if passed == total:
                    item.setForeground(1, QColor("green"))
                else:
                    item.setForeground(1, QColor("red"))
                break
                
    def on_all_finished(self):
        """Handle all tests completed."""
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        
        # Calculate totals
        total = sum(len(v) for v in self.test_results.values())
        passed = sum(1 for v in self.test_results.values() 
                    for _, success in v if success)
        
        self.statusBar().showMessage(
            f"✅ Completed: {passed}/{total} tests passed"
        )
        
        self.log_message(f"\n🏁 Test run completed: {passed}/{total} passed", 
                        "success" if passed == total else "error")
        
        # Clear widget display
        if self.current_widget:
            self.current_widget.deleteLater()
            self.current_widget = None
        self.widget_label.show()
        
    def show_test_widget(self, test_name: str):
        """Show the widget being tested."""
        # Clear previous widget
        if self.current_widget:
            self.current_widget.deleteLater()
            
        self.widget_label.hide()
        
        # Create appropriate widget based on test
        if "BaseSelectionWidget" in test_name:
            from ui.base_selection_widget import BaseSelectionWidget
            self.current_widget = BaseSelectionWidget()
        elif "BasePreviewWidget" in test_name:
            from ui.base_preview_widget import BasePreviewWidget
            self.current_widget = BasePreviewWidget()
        else:
            # For integration tests, show both widgets
            from ui.base_selection_widget import BaseSelectionWidget
            from ui.base_preview_widget import BasePreviewWidget
            
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.addWidget(BaseSelectionWidget())
            layout.addWidget(BasePreviewWidget())
            self.current_widget = container
            
        # Add to container
        if self.current_widget:
            layout = self.widget_container.layout()
            layout.addWidget(self.current_widget)
            
    def log_message(self, message: str, level: str = "info"):
        """Add message to log output."""
        cursor = self.log_output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        # Set color based on level
        if level == "error":
            color = "red"
        elif level == "success":
            color = "green"
        else:
            color = "black"
            
        cursor.insertHtml(f'<span style="color: {color}">{message}</span><br>')
        
        # Auto scroll
        self.log_output.setTextCursor(cursor)
        

def main():
    """Main entry point."""
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle("Fusion")
    
    runner = VisualTestRunner()
    runner.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()