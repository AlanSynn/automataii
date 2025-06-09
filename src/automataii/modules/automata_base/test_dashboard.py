#!/usr/bin/env python3
"""
Test Dashboard for Automata Base System

Interactive dashboard for running and viewing test results with real-time updates,
coverage visualization, and detailed test history.
"""

import sys
import os
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import threading

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTableWidget, QTableWidgetItem, QTabWidget,
    QTextEdit, QProgressBar, QLabel, QComboBox, QCheckBox,
    QSplitter, QTreeWidget, QTreeWidgetItem, QGroupBox,
    QGridLayout, QFrame
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QSize
from PyQt6.QtGui import QFont, QColor, QPalette, QIcon, QPainter, QPixmap
from PyQt6.QtCharts import QChart, QChartView, QPieSeries, QBarSeries, QBarSet, QValueAxis, QBarCategoryAxis


class TestExecutor(QThread):
    """Background thread for running tests."""
    
    progress = pyqtSignal(int)
    test_update = pyqtSignal(str, str, bool)  # test_name, status, passed
    log_output = pyqtSignal(str)
    finished_tests = pyqtSignal(dict)  # results
    
    def __init__(self, test_type: str = "all"):
        super().__init__()
        self.test_type = test_type
        self.process = None
        
    def run(self):
        """Execute tests based on type."""
        start_time = time.time()
        results = {
            'start_time': datetime.now().isoformat(),
            'test_type': self.test_type,
            'tests': {},
            'summary': {}
        }
        
        try:
            if self.test_type == "e2e":
                self._run_e2e_tests(results)
            elif self.test_type == "unit":
                self._run_unit_tests(results)
            elif self.test_type == "gui":
                self._run_gui_tests(results)
            else:  # all
                self._run_all_tests(results)
                
        except Exception as e:
            self.log_output.emit(f"Error: {str(e)}")
            
        results['duration'] = time.time() - start_time
        results['summary'] = self._calculate_summary(results['tests'])
        
        self.finished_tests.emit(results)
        
    def _run_e2e_tests(self, results: dict):
        """Run end-to-end tests."""
        self.log_output.emit("🔄 Running E2E tests...")
        
        e2e_files = [
            "test_e2e_base_workflow.py",
            "test_e2e_canvas_operations.py",
            "test_e2e_mechanism_integration.py",
            "test_e2e_export_functionality.py"
        ]
        
        total_tests = len(e2e_files) * 8  # Approximate
        current = 0
        
        for test_file in e2e_files:
            self.log_output.emit(f"\n📋 Running {test_file}")
            
            cmd = [sys.executable, "-m", "pytest", f"tests/e2e/{test_file}", 
                   "-v", "--tb=short", "--json-report", "--json-report-file=test_report.json"]
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, 
                                     stderr=subprocess.STDOUT, text=True)
            
            for line in process.stdout:
                self.log_output.emit(line.strip())
                
                # Parse test results from output
                if "PASSED" in line:
                    test_name = line.split()[0]
                    self.test_update.emit(test_name, "PASSED", True)
                    current += 1
                elif "FAILED" in line:
                    test_name = line.split()[0]
                    self.test_update.emit(test_name, "FAILED", False)
                    current += 1
                    
                self.progress.emit(int((current / total_tests) * 100))
                
            process.wait()
            
            # Load results from JSON if available
            try:
                with open("test_report.json", "r") as f:
                    report = json.load(f)
                    for test in report.get('tests', []):
                        results['tests'][test['nodeid']] = {
                            'outcome': test['outcome'],
                            'duration': test.get('duration', 0),
                            'error': test.get('call', {}).get('longrepr', '')
                        }
            except:
                pass
                
    def _run_unit_tests(self, results: dict):
        """Run unit tests."""
        self.log_output.emit("🔄 Running unit tests...")
        
        cmd = [sys.executable, "-m", "pytest", "tests/", 
               "-k", "not e2e and not gui", "-v"]
        
        self._run_pytest_command(cmd, results)
        
    def _run_gui_tests(self, results: dict):
        """Run GUI-specific tests."""
        self.log_output.emit("🔄 Running GUI tests...")
        
        cmd = [sys.executable, "tests/run_gui_tests.py", "-v"]
        
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True)
        
        for line in process.stdout:
            self.log_output.emit(line.strip())
            
    def _run_all_tests(self, results: dict):
        """Run all test types."""
        self._run_unit_tests(results)
        self._run_gui_tests(results) 
        self._run_e2e_tests(results)
        
    def _run_pytest_command(self, cmd: list, results: dict):
        """Run a pytest command and parse results."""
        process = subprocess.Popen(cmd + ["--json-report", "--json-report-file=test_report.json"],
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        
        for line in process.stdout:
            self.log_output.emit(line.strip())
            
        process.wait()
        
        # Parse JSON report
        try:
            with open("test_report.json", "r") as f:
                report = json.load(f)
                for test in report.get('tests', []):
                    results['tests'][test['nodeid']] = {
                        'outcome': test['outcome'],
                        'duration': test.get('duration', 0)
                    }
        except:
            pass
            
    def _calculate_summary(self, tests: dict) -> dict:
        """Calculate test summary statistics."""
        total = len(tests)
        passed = sum(1 for t in tests.values() if t.get('outcome') == 'passed')
        failed = sum(1 for t in tests.values() if t.get('outcome') == 'failed')
        skipped = sum(1 for t in tests.values() if t.get('outcome') == 'skipped')
        
        return {
            'total': total,
            'passed': passed,
            'failed': failed,
            'skipped': skipped,
            'pass_rate': (passed / total * 100) if total > 0 else 0
        }


class TestDashboard(QMainWindow):
    """Main dashboard window."""
    
    def __init__(self):
        super().__init__()
        self.test_executor = None
        self.test_history = []
        self.current_results = None
        
        self.setup_ui()
        self.load_test_history()
        
    def setup_ui(self):
        """Setup the user interface."""
        self.setWindowTitle("Automata Base System - Test Dashboard")
        self.setGeometry(100, 100, 1400, 900)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        
        # Main layout
        layout = QVBoxLayout(central)
        
        # Header
        header = self._create_header()
        layout.addWidget(header)
        
        # Main content tabs
        self.tabs = QTabWidget()
        
        # Overview tab
        self.overview_tab = self._create_overview_tab()
        self.tabs.addTab(self.overview_tab, "📊 Overview")
        
        # Test results tab
        self.results_tab = self._create_results_tab()
        self.tabs.addTab(self.results_tab, "📋 Test Results")
        
        # Coverage tab
        self.coverage_tab = self._create_coverage_tab()
        self.tabs.addTab(self.coverage_tab, "📈 Coverage")
        
        # History tab
        self.history_tab = self._create_history_tab()
        self.tabs.addTab(self.history_tab, "📜 History")
        
        layout.addWidget(self.tabs)
        
        # Status bar
        self.status_label = QLabel("Ready")
        self.statusBar().addPermanentWidget(self.status_label)
        
        # Apply styling
        self._apply_styling()
        
    def _create_header(self) -> QWidget:
        """Create header with controls."""
        header = QFrame()
        header.setFrameStyle(QFrame.Shape.Box)
        layout = QHBoxLayout(header)
        
        # Title
        title = QLabel("🧪 Test Dashboard")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        layout.addWidget(title)
        
        layout.addStretch()
        
        # Test type selector
        layout.addWidget(QLabel("Test Type:"))
        self.test_type_combo = QComboBox()
        self.test_type_combo.addItems(["All Tests", "E2E Tests", "Unit Tests", "GUI Tests"])
        layout.addWidget(self.test_type_combo)
        
        # Run button
        self.run_button = QPushButton("▶️ Run Tests")
        self.run_button.clicked.connect(self.run_tests)
        self.run_button.setMinimumSize(120, 35)
        layout.addWidget(self.run_button)
        
        # Stop button
        self.stop_button = QPushButton("⏹️ Stop")
        self.stop_button.clicked.connect(self.stop_tests)
        self.stop_button.setEnabled(False)
        layout.addWidget(self.stop_button)
        
        return header
        
    def _create_overview_tab(self) -> QWidget:
        """Create overview tab with charts."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Summary cards
        cards_layout = QHBoxLayout()
        
        self.total_card = self._create_summary_card("Total Tests", "0", "#2196F3")
        self.passed_card = self._create_summary_card("Passed", "0", "#4CAF50")
        self.failed_card = self._create_summary_card("Failed", "0", "#F44336")
        self.coverage_card = self._create_summary_card("Coverage", "0%", "#FF9800")
        
        cards_layout.addWidget(self.total_card)
        cards_layout.addWidget(self.passed_card)
        cards_layout.addWidget(self.failed_card)
        cards_layout.addWidget(self.coverage_card)
        
        layout.addLayout(cards_layout)
        
        # Charts
        charts_layout = QHBoxLayout()
        
        # Pie chart for test results
        self.results_chart = self._create_results_chart()
        charts_layout.addWidget(self.results_chart)
        
        # Bar chart for test duration
        self.duration_chart = self._create_duration_chart()
        charts_layout.addWidget(self.duration_chart)
        
        layout.addLayout(charts_layout)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setMinimumHeight(25)
        layout.addWidget(self.progress_bar)
        
        return widget
        
    def _create_summary_card(self, title: str, value: str, color: str) -> QFrame:
        """Create a summary card widget."""
        card = QFrame()
        card.setFrameStyle(QFrame.Shape.Box)
        card.setStyleSheet(f"""
            QFrame {{
                border: 2px solid {color};
                border-radius: 10px;
                background-color: {color}20;
                padding: 10px;
            }}
        """)
        
        layout = QVBoxLayout(card)
        
        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setFont(QFont("Arial", 12))
        layout.addWidget(title_label)
        
        value_label = QLabel(value)
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_label.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        value_label.setStyleSheet(f"color: {color};")
        layout.addWidget(value_label)
        
        # Store value label for updates
        card.value_label = value_label
        
        return card
        
    def _create_results_chart(self) -> QChartView:
        """Create pie chart for test results."""
        series = QPieSeries()
        series.append("Passed", 0)
        series.append("Failed", 0)
        series.append("Skipped", 0)
        
        # Colors
        colors = [QColor("#4CAF50"), QColor("#F44336"), QColor("#FFC107")]
        for i, slice in enumerate(series.slices()):
            slice.setBrush(colors[i])
            slice.setLabelVisible(True)
            
        chart = QChart()
        chart.addSeries(series)
        chart.setTitle("Test Results Distribution")
        chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        
        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Store series for updates
        chart_view.series = series
        
        return chart_view
        
    def _create_duration_chart(self) -> QChartView:
        """Create bar chart for test durations."""
        series = QBarSeries()
        
        chart = QChart()
        chart.addSeries(series)
        chart.setTitle("Test Execution Time")
        chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        
        # Axes
        axis_x = QBarCategoryAxis()
        axis_y = QValueAxis()
        axis_y.setTitleText("Duration (seconds)")
        
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        
        series.attachAxis(axis_x)
        series.attachAxis(axis_y)
        
        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Store for updates
        chart_view.series = series
        chart_view.axis_x = axis_x
        chart_view.axis_y = axis_y
        
        return chart_view
        
    def _create_results_tab(self) -> QWidget:
        """Create test results tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Results table
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels(["Test Name", "Status", "Duration", "Error"])
        self.results_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.results_table)
        
        # Log output
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(200)
        self.log_output.setFont(QFont("Consolas", 9))
        layout.addWidget(self.log_output)
        
        return widget
        
    def _create_coverage_tab(self) -> QWidget:
        """Create coverage tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Coverage summary
        summary_group = QGroupBox("Coverage Summary")
        summary_layout = QGridLayout(summary_group)
        
        self.coverage_labels = {}
        metrics = ["Lines", "Branches", "Functions", "Classes"]
        for i, metric in enumerate(metrics):
            label = QLabel(f"{metric}:")
            value = QLabel("0%")
            value.setFont(QFont("Arial", 14, QFont.Weight.Bold))
            summary_layout.addWidget(label, i, 0)
            summary_layout.addWidget(value, i, 1)
            self.coverage_labels[metric.lower()] = value
            
        layout.addWidget(summary_group)
        
        # File coverage tree
        self.coverage_tree = QTreeWidget()
        self.coverage_tree.setHeaderLabels(["File", "Coverage", "Lines", "Missing"])
        layout.addWidget(self.coverage_tree)
        
        return widget
        
    def _create_history_tab(self) -> QWidget:
        """Create history tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # History table
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(5)
        self.history_table.setHorizontalHeaderLabels(["Date", "Type", "Total", "Passed", "Duration"])
        layout.addWidget(self.history_table)
        
        # Clear history button
        clear_button = QPushButton("Clear History")
        clear_button.clicked.connect(self.clear_history)
        layout.addWidget(clear_button)
        
        return widget
        
    def _apply_styling(self):
        """Apply custom styling to the dashboard."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QPushButton {
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:enabled {
                background-color: #2196F3;
                color: white;
            }
            QPushButton:hover:enabled {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
            QTabWidget::pane {
                border: 1px solid #ddd;
                background-color: white;
            }
            QTableWidget {
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            QTextEdit {
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: #f9f9f9;
            }
        """)
        
    def run_tests(self):
        """Start running tests."""
        if self.test_executor and self.test_executor.isRunning():
            return
            
        # Clear previous results
        self.log_output.clear()
        self.results_table.setRowCount(0)
        self.progress_bar.setValue(0)
        
        # Update UI state
        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_label.setText("Running tests...")
        
        # Get test type
        test_type_map = {
            "All Tests": "all",
            "E2E Tests": "e2e",
            "Unit Tests": "unit",
            "GUI Tests": "gui"
        }
        test_type = test_type_map[self.test_type_combo.currentText()]
        
        # Create and start executor
        self.test_executor = TestExecutor(test_type)
        self.test_executor.progress.connect(self.progress_bar.setValue)
        self.test_executor.test_update.connect(self.update_test_result)
        self.test_executor.log_output.connect(self.append_log)
        self.test_executor.finished_tests.connect(self.on_tests_finished)
        
        self.test_executor.start()
        
    def stop_tests(self):
        """Stop running tests."""
        if self.test_executor:
            self.test_executor.terminate()
            self.test_executor.wait()
            
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText("Tests stopped")
        
    def update_test_result(self, test_name: str, status: str, passed: bool):
        """Update test result in table."""
        row = self.results_table.rowCount()
        self.results_table.insertRow(row)
        
        # Test name
        self.results_table.setItem(row, 0, QTableWidgetItem(test_name))
        
        # Status with color
        status_item = QTableWidgetItem(status)
        if passed:
            status_item.setForeground(QColor("#4CAF50"))
        else:
            status_item.setForeground(QColor("#F44336"))
        self.results_table.setItem(row, 1, status_item)
        
    def append_log(self, message: str):
        """Append message to log output."""
        self.log_output.append(message)
        
    def on_tests_finished(self, results: dict):
        """Handle test completion."""
        self.current_results = results
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        
        # Update summary
        summary = results.get('summary', {})
        self.total_card.value_label.setText(str(summary.get('total', 0)))
        self.passed_card.value_label.setText(str(summary.get('passed', 0)))
        self.failed_card.value_label.setText(str(summary.get('failed', 0)))
        
        # Update charts
        self.update_charts(results)
        
        # Add to history
        self.add_to_history(results)
        
        # Update status
        pass_rate = summary.get('pass_rate', 0)
        self.status_label.setText(f"Tests completed - Pass rate: {pass_rate:.1f}%")
        
    def update_charts(self, results: dict):
        """Update dashboard charts."""
        summary = results.get('summary', {})
        
        # Update pie chart
        self.results_chart.series.clear()
        self.results_chart.series.append("Passed", summary.get('passed', 0))
        self.results_chart.series.append("Failed", summary.get('failed', 0))
        self.results_chart.series.append("Skipped", summary.get('skipped', 0))
        
        colors = [QColor("#4CAF50"), QColor("#F44336"), QColor("#FFC107")]
        for i, slice in enumerate(self.results_chart.series.slices()):
            slice.setBrush(colors[i])
            slice.setLabelVisible(True)
            
        # Update duration chart
        self.duration_chart.series.clear()
        
        # Group tests by category
        categories = {}
        for test_name, test_data in results.get('tests', {}).items():
            category = test_name.split('::')[0].split('/')[-1]
            if category not in categories:
                categories[category] = []
            categories[category].append(test_data.get('duration', 0))
            
        # Create bar sets
        if categories:
            bar_set = QBarSet("Duration")
            category_names = []
            
            for category, durations in categories.items():
                avg_duration = sum(durations) / len(durations) if durations else 0
                bar_set.append(avg_duration)
                category_names.append(category)
                
            self.duration_chart.series.append(bar_set)
            self.duration_chart.axis_x.clear()
            self.duration_chart.axis_x.append(category_names)
            
    def add_to_history(self, results: dict):
        """Add test run to history."""
        self.test_history.append(results)
        
        # Update history table
        row = self.history_table.rowCount()
        self.history_table.insertRow(row)
        
        summary = results.get('summary', {})
        self.history_table.setItem(row, 0, QTableWidgetItem(results.get('start_time', '')))
        self.history_table.setItem(row, 1, QTableWidgetItem(results.get('test_type', '')))
        self.history_table.setItem(row, 2, QTableWidgetItem(str(summary.get('total', 0))))
        self.history_table.setItem(row, 3, QTableWidgetItem(str(summary.get('passed', 0))))
        self.history_table.setItem(row, 4, QTableWidgetItem(f"{results.get('duration', 0):.1f}s"))
        
        # Save history
        self.save_test_history()
        
    def load_test_history(self):
        """Load test history from file."""
        history_file = Path("test_history.json")
        if history_file.exists():
            try:
                with open(history_file, 'r') as f:
                    self.test_history = json.load(f)
                    
                # Populate history table
                for result in self.test_history:
                    self.add_to_history(result)
            except:
                self.test_history = []
                
    def save_test_history(self):
        """Save test history to file."""
        with open("test_history.json", 'w') as f:
            json.dump(self.test_history[-50:], f, indent=2)  # Keep last 50 runs
            
    def clear_history(self):
        """Clear test history."""
        self.test_history.clear()
        self.history_table.setRowCount(0)
        self.save_test_history()


def main():
    """Main entry point."""
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle("Fusion")
    
    dashboard = TestDashboard()
    dashboard.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()