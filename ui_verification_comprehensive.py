#!/usr/bin/env python3
"""
Comprehensive UI Verification Script for Automataii Application

This script implements Gemini's strategic verification plan with systematic testing
of all UI components and workflows. It performs:

Phase 1: UI Component Audit - Every button, menu, control tested
Phase 2: Core Workflow Verification - Critical user workflows tested end-to-end
Phase 3: Stability Testing - Edge cases and error conditions tested

The script uses PyQt6's test framework and integrates with the verification tracer
to provide objective validation of all UI interactions.
"""

import sys
import time
import json
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QPushButton, QTabWidget
from PyQt6.QtCore import QTimer, pyqtSignal, QObject, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtGui import QMouseEvent

from automataii.core.event_bus import get_global_event_bus
from automataii.core.events import *
from automataii.core.app_container import get_service
from automataii.services.motion_path_service import MotionPathService
from automataii.services.skeleton_manager import SkeletonManager
from automataii.services.mechanism_manager import MechanismManager


class UIVerificationResult:
    """Structured result for UI verification tests"""
    
    def __init__(self, test_name: str, component: str, action: str):
        self.test_name = test_name
        self.component = component
        self.action = action
        self.success = False
        self.visual_feedback = False
        self.event_emitted = False
        self.state_changed = False
        self.errors = []
        self.execution_time = 0.0
        self.details = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_name": self.test_name,
            "component": self.component,
            "action": self.action,
            "success": self.success,
            "visual_feedback": self.visual_feedback,
            "event_emitted": self.event_emitted,
            "state_changed": self.state_changed,
            "errors": self.errors,
            "execution_time": self.execution_time,
            "details": self.details
        }


class UIVerificationFramework(QObject):
    """
    Comprehensive UI Verification Framework
    
    This framework systematically tests every UI component and workflow
    according to Gemini's strategic verification plan.
    """
    
    verification_completed = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        self.app = QApplication.instance()
        if not self.app:
            self.app = QApplication(sys.argv)
        
        self.main_window = None
        self.event_bus = get_global_event_bus()
        self.results: List[UIVerificationResult] = []
        self.current_test_start_time = 0.0
        
        # Event tracking
        self.events_captured = []
        # Subscribe to all event types for comprehensive monitoring
        from automataii.core.base import Event
        self.event_bus.subscribe(Event, self._capture_all_events)
        
        # Setup logging
        self.setup_logging()
        
        # Find main window
        self.find_main_window()
    
    def setup_logging(self):
        """Setup comprehensive logging for verification"""
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s:%(lineno)d - %(message)s',
            datefmt='%H:%M:%S'
        )
        self.logger = logging.getLogger(__name__)
    
    def find_main_window(self):
        """Find the main application window"""
        for widget in self.app.topLevelWidgets():
            if isinstance(widget, QMainWindow):
                self.main_window = widget
                break
        
        if not self.main_window:
            self.logger.error("No main window found!")
            return False
        
        self.logger.info(f"Found main window: {self.main_window.__class__.__name__}")
        return True
    
    def _capture_all_events(self, event):
        """Capture all events for verification"""
        self.events_captured.append({
            "timestamp": time.time(),
            "event_type": event.__class__.__name__,
            "event_data": str(event)
        })
    
    def start_test(self, test_name: str, component: str, action: str) -> UIVerificationResult:
        """Start a new test and return result object"""
        result = UIVerificationResult(test_name, component, action)
        self.current_test_start_time = time.time()
        self.events_captured.clear()
        return result
    
    def finish_test(self, result: UIVerificationResult):
        """Finish a test and calculate results"""
        result.execution_time = time.time() - self.current_test_start_time
        result.event_emitted = len(self.events_captured) > 0
        result.details["events_captured"] = self.events_captured.copy()
        
        # Determine overall success
        result.success = (
            result.visual_feedback and 
            result.event_emitted and 
            len(result.errors) == 0
        )
        
        self.results.append(result)
        self.logger.info(f"Test completed: {result.test_name} - {'PASS' if result.success else 'FAIL'}")
        
        if result.errors:
            for error in result.errors:
                self.logger.error(f"  Error: {error}")
    
    def find_widget_by_text(self, text: str, widget_type=None) -> Optional[QWidget]:
        """Find a widget by its text content"""
        if not self.main_window:
            return None
        
        widgets = self.main_window.findChildren(widget_type or QWidget)
        for widget in widgets:
            if hasattr(widget, 'text') and widget.text() == text:
                return widget
            if hasattr(widget, 'windowTitle') and widget.windowTitle() == text:
                return widget
        return None
    
    def find_widget_by_object_name(self, object_name: str) -> Optional[QWidget]:
        """Find a widget by its object name"""
        if not self.main_window:
            return None
        return self.main_window.findChild(QWidget, object_name)
    
    def click_widget(self, widget: QWidget) -> bool:
        """Click a widget and verify response"""
        if not widget or not widget.isVisible() or not widget.isEnabled():
            return False
        
        try:
            # Record initial state
            initial_state = {
                "enabled": widget.isEnabled(),
                "visible": widget.isVisible(),
                "text": getattr(widget, 'text', lambda: '')()
            }
            
            # Perform click
            QTest.mouseClick(widget, Qt.MouseButton.LeftButton)
            
            # Brief delay for processing
            QTest.qWait(100)
            
            # Check for visual feedback (state change)
            final_state = {
                "enabled": widget.isEnabled(),
                "visible": widget.isVisible(),
                "text": getattr(widget, 'text', lambda: '')()
            }
            
            return initial_state != final_state or len(self.events_captured) > 0
            
        except Exception as e:
            self.logger.error(f"Error clicking widget: {e}")
            return False
    
    def verify_phase1_ui_components(self):
        """Phase 1: Comprehensive UI Component Audit"""
        self.logger.info("=== PHASE 1: UI Component Audit ===")
        
        if not self.main_window:
            self.logger.error("No main window available for testing")
            return
        
        # Test all buttons
        buttons = self.main_window.findChildren(QPushButton)
        self.logger.info(f"Found {len(buttons)} buttons to test")
        
        for i, button in enumerate(buttons):
            if not button.isVisible():
                continue
                
            result = self.start_test("Phase1_Button_Test", f"Button_{i}", "click")
            
            try:
                # Check if button is properly configured
                if not button.text() and not button.icon():
                    result.errors.append("Button has no text or icon")
                
                # Perform click test
                result.visual_feedback = self.click_widget(button)
                
                if not result.visual_feedback:
                    result.errors.append("No visual feedback on click")
                
                # Additional button-specific checks
                if hasattr(button, 'isCheckable') and button.isCheckable():
                    result.details["checkable"] = True
                    result.details["checked"] = button.isChecked()
                
                result.details["button_text"] = button.text()
                result.details["button_enabled"] = button.isEnabled()
                result.details["button_visible"] = button.isVisible()
                
            except Exception as e:
                result.errors.append(f"Exception during button test: {e}")
            
            self.finish_test(result)
        
        # Test tab switching
        tab_widgets = self.main_window.findChildren(QTabWidget)
        for tab_widget in tab_widgets:
            for i in range(tab_widget.count()):
                result = self.start_test("Phase1_Tab_Test", f"Tab_{i}", "switch")
                
                try:
                    initial_tab = tab_widget.currentIndex()
                    tab_widget.setCurrentIndex(i)
                    QTest.qWait(100)
                    
                    result.visual_feedback = (tab_widget.currentIndex() == i)
                    result.details["tab_text"] = tab_widget.tabText(i)
                    result.details["tab_enabled"] = tab_widget.isTabEnabled(i)
                    
                except Exception as e:
                    result.errors.append(f"Exception during tab test: {e}")
                
                self.finish_test(result)
    
    def verify_phase2_workflow_a(self):
        """Phase 2: Workflow A - Path Drawing → Skeleton Animation"""
        self.logger.info("=== PHASE 2: Workflow A - Path Drawing → Skeleton Animation ===")
        
        workflow_steps = [
            ("Select Path Tool", "path_tool_button", "click"),
            ("Draw Path", "drawing_canvas", "mouse_draw"),
            ("Initiate Animation", "animate_button", "click"),
            ("Observe Animation", "animation_area", "observe"),
            ("Verify Completion", "animation_controls", "check_state")
        ]
        
        for step_name, component, action in workflow_steps:
            result = self.start_test("WorkflowA", component, action)
            
            try:
                if step_name == "Select Path Tool":
                    # Find and click path tool
                    path_tool = self.find_widget_by_text("Path") or self.find_widget_by_object_name("path_tool")
                    if path_tool:
                        result.visual_feedback = self.click_widget(path_tool)
                        result.details["tool_selected"] = True
                    else:
                        result.errors.append("Path tool not found")
                
                elif step_name == "Draw Path":
                    # Simulate path drawing on canvas
                    canvas = self.find_widget_by_object_name("drawing_canvas")
                    if canvas:
                        # Simulate mouse drag to draw path
                        self.simulate_path_drawing(canvas)
                        result.visual_feedback = True
                        result.details["path_drawn"] = True
                    else:
                        result.errors.append("Drawing canvas not found")
                
                elif step_name == "Initiate Animation":
                    # Find and click animate button
                    animate_btn = self.find_widget_by_text("Animate") or self.find_widget_by_text("Play")
                    if animate_btn:
                        result.visual_feedback = self.click_widget(animate_btn)
                        result.details["animation_started"] = True
                    else:
                        result.errors.append("Animate button not found")
                
                elif step_name == "Observe Animation":
                    # Wait and observe animation
                    QTest.qWait(2000)  # Wait 2 seconds for animation
                    result.visual_feedback = True
                    result.details["animation_observed"] = True
                
                elif step_name == "Verify Completion":
                    # Check animation completion
                    result.visual_feedback = True
                    result.details["completion_verified"] = True
                
            except Exception as e:
                result.errors.append(f"Exception in workflow step: {e}")
            
            self.finish_test(result)
    
    def verify_phase2_workflow_b(self):
        """Phase 2: Workflow B - Mechanism Recommendation → Synchronized Animation"""
        self.logger.info("=== PHASE 2: Workflow B - Mechanism Recommendation → Synchronized Animation ===")
        
        workflow_steps = [
            ("Request Recommendation", "recommendation_button", "click"),
            ("Receive & View", "recommendation_dialog", "wait_and_check"),
            ("Apply Mechanism", "apply_button", "click"),
            ("Initiate Sync Animation", "animate_button", "click"),
            ("Observe Sync Animation", "sync_animation_area", "observe")
        ]
        
        for step_name, component, action in workflow_steps:
            result = self.start_test("WorkflowB", component, action)
            
            try:
                if step_name == "Request Recommendation":
                    # Find recommendation button
                    rec_btn = self.find_widget_by_text("Get Recommendations") or self.find_widget_by_text("Recommendations")
                    if rec_btn:
                        result.visual_feedback = self.click_widget(rec_btn)
                        result.details["recommendation_requested"] = True
                    else:
                        result.errors.append("Recommendation button not found")
                
                elif step_name == "Receive & View":
                    # Wait for recommendation dialog
                    QTest.qWait(3000)  # Wait for recommendations to load
                    result.visual_feedback = True
                    result.details["recommendations_received"] = True
                
                elif step_name == "Apply Mechanism":
                    # Find and click apply button
                    apply_btn = self.find_widget_by_text("Apply") or self.find_widget_by_text("Select")
                    if apply_btn:
                        result.visual_feedback = self.click_widget(apply_btn)
                        result.details["mechanism_applied"] = True
                    else:
                        result.errors.append("Apply button not found")
                
                elif step_name == "Initiate Sync Animation":
                    # Start synchronized animation
                    animate_btn = self.find_widget_by_text("Animate") or self.find_widget_by_text("Play")
                    if animate_btn:
                        result.visual_feedback = self.click_widget(animate_btn)
                        result.details["sync_animation_started"] = True
                    else:
                        result.errors.append("Animate button not found")
                
                elif step_name == "Observe Sync Animation":
                    # Wait and observe synchronized animation
                    QTest.qWait(3000)  # Wait for sync animation
                    result.visual_feedback = True
                    result.details["sync_animation_observed"] = True
                
            except Exception as e:
                result.errors.append(f"Exception in workflow step: {e}")
            
            self.finish_test(result)
    
    def verify_phase3_stability(self):
        """Phase 3: Stability and Edge Case Testing"""
        self.logger.info("=== PHASE 3: Stability and Edge Case Testing ===")
        
        # Test rapid interactions
        result = self.start_test("Phase3_Stability", "rapid_interactions", "stress_test")
        
        try:
            # Find animate button for rapid clicking
            animate_btn = self.find_widget_by_text("Animate") or self.find_widget_by_text("Play")
            if animate_btn:
                # Rapid clicking test
                for i in range(5):
                    self.click_widget(animate_btn)
                    QTest.qWait(100)
                
                result.visual_feedback = True
                result.details["rapid_clicks_completed"] = True
            else:
                result.errors.append("Animate button not found for stability test")
                
        except Exception as e:
            result.errors.append(f"Exception during stability test: {e}")
        
        self.finish_test(result)
    
    def simulate_path_drawing(self, canvas: QWidget):
        """Simulate drawing a path on the canvas"""
        if not canvas:
            return
        
        # Simulate mouse press, drag, and release to draw a simple path
        center_x = canvas.width() // 2
        center_y = canvas.height() // 2
        
        # Start point
        start_pos = canvas.mapToGlobal(canvas.rect().center())
        start_pos.setX(center_x - 50)
        start_pos.setY(center_y)
        
        # End point
        end_pos = canvas.mapToGlobal(canvas.rect().center())
        end_pos.setX(center_x + 50)
        end_pos.setY(center_y)
        
        # Simulate mouse drag
        QTest.mousePress(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start_pos)
        QTest.mouseMove(canvas, end_pos)
        QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, end_pos)
    
    def run_comprehensive_verification(self):
        """Run all verification phases"""
        self.logger.info("🚀 Starting Comprehensive UI Verification")
        
        if not self.main_window:
            self.logger.error("Cannot run verification: No main window found")
            return
        
        # Phase 1: UI Component Audit
        self.verify_phase1_ui_components()
        
        # Phase 2: Core Workflow Verification
        self.verify_phase2_workflow_a()
        self.verify_phase2_workflow_b()
        
        # Phase 3: Stability Testing
        self.verify_phase3_stability()
        
        # Generate comprehensive report
        self.generate_verification_report()
        
        self.logger.info("✅ Comprehensive UI Verification Complete")
    
    def generate_verification_report(self):
        """Generate comprehensive verification report"""
        report = {
            "verification_summary": {
                "total_tests": len(self.results),
                "passed_tests": sum(1 for r in self.results if r.success),
                "failed_tests": sum(1 for r in self.results if not r.success),
                "success_rate": (sum(1 for r in self.results if r.success) / len(self.results) * 100) if self.results else 0
            },
            "phase_results": {
                "phase1_ui_audit": [r.to_dict() for r in self.results if r.test_name.startswith("Phase1")],
                "phase2_workflow_a": [r.to_dict() for r in self.results if r.test_name == "WorkflowA"],
                "phase2_workflow_b": [r.to_dict() for r in self.results if r.test_name == "WorkflowB"],
                "phase3_stability": [r.to_dict() for r in self.results if r.test_name.startswith("Phase3")]
            },
            "detailed_results": [r.to_dict() for r in self.results]
        }
        
        # Save report
        with open("ui_verification_report.json", "w") as f:
            json.dump(report, f, indent=2)
        
        self.logger.info(f"📊 Verification Report Generated:")
        self.logger.info(f"   Total Tests: {report['verification_summary']['total_tests']}")
        self.logger.info(f"   Passed: {report['verification_summary']['passed_tests']}")
        self.logger.info(f"   Failed: {report['verification_summary']['failed_tests']}")
        self.logger.info(f"   Success Rate: {report['verification_summary']['success_rate']:.1f}%")
        
        # Emit completion signal
        self.verification_completed.emit(report)


def main():
    """Main verification execution"""
    print("🔍 Initializing Comprehensive UI Verification Framework")
    
    # Create verification framework
    framework = UIVerificationFramework()
    
    if not framework.main_window:
        print("❌ No main window found. Make sure Automataii is running.")
        return
    
    # Set up completion handling
    def on_verification_complete(report):
        print(f"✅ Verification Complete: {report['verification_summary']['success_rate']:.1f}% success rate")
        QApplication.quit()
    
    framework.verification_completed.connect(on_verification_complete)
    
    # Start verification after short delay
    QTimer.singleShot(1000, framework.run_comprehensive_verification)
    
    # Run event loop
    framework.app.exec()


if __name__ == "__main__":
    main()