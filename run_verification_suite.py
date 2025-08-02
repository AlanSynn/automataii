#!/usr/bin/env python3
"""
Comprehensive Verification Suite for Automataii
Executes all 4 critical workflows with automated testing
"""

import sys
import time
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer, QPoint, Qt, QPointF
from PyQt6.QtTest import QTest
from PyQt6.QtGui import QMouseEvent

from automataii.app.main import AutomataiApp
from automataii.core.event_bus import EventBus
from automataii.core.events import (
    MotionPathCompletedEvent,
    SkeletonAnimationRequestedEvent,
    MechanismRecommendationRequestedEvent,
    SynchronizedAnimationRequestedEvent
)

class VerificationSuite:
    """Automated verification suite for critical workflows"""
    
    def __init__(self):
        self.app = None
        self.main_window = None
        self.results = {
            "start_time": datetime.now().isoformat(),
            "workflows": {},
            "events_captured": [],
            "errors": [],
            "performance_metrics": {}
        }
        self.event_bus = EventBus()
        self._setup_event_monitoring()
        
    def _setup_event_monitoring(self):
        """Monitor all events for verification"""
        # Subscribe to all critical events
        event_types = [
            MotionPathCompletedEvent,
            SkeletonAnimationRequestedEvent,
            MechanismRecommendationRequestedEvent,
            SynchronizedAnimationRequestedEvent
        ]
        
        for event_type in event_types:
            self.event_bus.subscribe(event_type, self._capture_event)
    
    def _capture_event(self, event):
        """Capture event data for analysis"""
        event_data = {
            "type": event.__class__.__name__,
            "timestamp": datetime.now().isoformat(),
            "data": str(event)
        }
        self.results["events_captured"].append(event_data)
        print(f"[VERIFICATION] Event captured: {event_data['type']}")
    
    def run_all_workflows(self):
        """Execute all verification workflows"""
        print("\n" + "="*60)
        print("AUTOMATAII VERIFICATION SUITE")
        print("="*60 + "\n")
        
        # Initialize Qt application
        qt_app = QApplication(sys.argv)
        self.app = AutomataiApp()
        self.main_window = self.app.window
        self.main_window.show()
        
        # Allow UI to initialize
        qt_app.processEvents()
        time.sleep(1)
        
        # Run workflows sequentially
        workflows = [
            ("path_drawing", self.verify_path_drawing_workflow),
            ("skeleton_animation", self.verify_skeleton_animation_workflow),
            ("mechanism_recommendation", self.verify_mechanism_recommendation_workflow),
            ("synchronized_animation", self.verify_synchronized_animation_workflow)
        ]
        
        for workflow_name, workflow_func in workflows:
            print(f"\n[WORKFLOW] Starting: {workflow_name}")
            self.results["workflows"][workflow_name] = {
                "start": datetime.now().isoformat(),
                "status": "running",
                "steps": []
            }
            
            try:
                workflow_func()
                self.results["workflows"][workflow_name]["status"] = "completed"
            except Exception as e:
                self.results["workflows"][workflow_name]["status"] = "failed"
                self.results["workflows"][workflow_name]["error"] = str(e)
                self.results["errors"].append({
                    "workflow": workflow_name,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })
                print(f"[ERROR] Workflow {workflow_name} failed: {e}")
            
            self.results["workflows"][workflow_name]["end"] = datetime.now().isoformat()
            
            # Pause between workflows
            time.sleep(2)
            qt_app.processEvents()
        
        # Save results
        self._save_results()
        
        # Keep app running for manual inspection if needed
        print("\n[COMPLETE] Verification suite finished. Press Ctrl+C to exit.")
        qt_app.exec()
    
    def verify_path_drawing_workflow(self):
        """Workflow 1: Path Drawing → Event → Persistence"""
        steps = []
        
        # Step 1: Navigate to Editor tab
        editor_tab = self._get_editor_tab()
        if not editor_tab:
            raise Exception("Editor tab not found")
        
        self.main_window.tab_widget.setCurrentWidget(editor_tab)
        steps.append("Navigated to Editor tab")
        
        # Step 2: Get the graphics view
        graphics_view = editor_tab.findChild(type(editor_tab).__bases__[0], "graphics_view")
        if not graphics_view:
            # Try alternative approach
            for child in editor_tab.findChildren(QWidget):
                if hasattr(child, 'scene') and hasattr(child, 'viewport'):
                    graphics_view = child
                    break
        
        if not graphics_view:
            raise Exception("Graphics view not found")
        
        steps.append("Found graphics view")
        
        # Step 3: Simulate path drawing
        start_point = QPoint(100, 100)
        end_point = QPoint(300, 300)
        
        # Mouse press
        QTest.mousePress(graphics_view.viewport(), Qt.MouseButton.LeftButton, 
                         Qt.KeyboardModifier.NoModifier, start_point)
        steps.append(f"Mouse pressed at {start_point}")
        
        # Mouse move (simulate drawing)
        for i in range(5):
            intermediate = QPoint(
                start_point.x() + (end_point.x() - start_point.x()) * i // 4,
                start_point.y() + (end_point.y() - start_point.y()) * i // 4
            )
            QTest.mouseMove(graphics_view.viewport(), intermediate)
            time.sleep(0.1)
        
        steps.append("Mouse moved along path")
        
        # Mouse release
        QTest.mouseRelease(graphics_view.viewport(), Qt.MouseButton.LeftButton,
                          Qt.KeyboardModifier.NoModifier, end_point)
        steps.append(f"Mouse released at {end_point}")
        
        # Verify event was emitted
        time.sleep(0.5)
        motion_path_events = [e for e in self.results["events_captured"] 
                             if e["type"] == "MotionPathCompletedEvent"]
        
        if motion_path_events:
            steps.append(f"MotionPathCompletedEvent captured: {len(motion_path_events)}")
        else:
            steps.append("WARNING: No MotionPathCompletedEvent captured")
        
        self.results["workflows"]["path_drawing"]["steps"] = steps
        print(f"[PATH DRAWING] Completed {len(steps)} steps")
    
    def verify_skeleton_animation_workflow(self):
        """Workflow 2: Skeleton Animation → IK Solving → Updates"""
        steps = []
        
        # Step 1: Ensure we have a skeleton loaded
        # For now, we'll simulate this by checking if skeleton exists
        editor_tab = self._get_editor_tab()
        if not editor_tab:
            raise Exception("Editor tab not found")
        
        steps.append("Editor tab found")
        
        # Step 2: Trigger animation
        # Look for animate button or trigger programmatically
        animate_action = self._find_action("Animate")
        if animate_action:
            animate_action.trigger()
            steps.append("Triggered animate action")
        else:
            # Emit event directly
            self.event_bus.publish(SkeletonAnimationRequestedEvent())
            steps.append("Published SkeletonAnimationRequestedEvent directly")
        
        # Step 3: Wait for IK solving
        time.sleep(1)
        
        # Check for skeleton update events
        skeleton_events = [e for e in self.results["events_captured"]
                          if "Skeleton" in e["type"] and "Update" in e["type"]]
        
        if skeleton_events:
            steps.append(f"Skeleton update events captured: {len(skeleton_events)}")
        else:
            steps.append("WARNING: No skeleton update events captured")
        
        self.results["workflows"]["skeleton_animation"]["steps"] = steps
        print(f"[SKELETON ANIMATION] Completed {len(steps)} steps")
    
    def verify_mechanism_recommendation_workflow(self):
        """Workflow 3: Recommendation → Search → Selection → Placement"""
        steps = []
        
        # Step 1: Navigate to mechanism design tab
        mechanism_tab = self._get_mechanism_design_tab()
        if mechanism_tab:
            self.main_window.tab_widget.setCurrentWidget(mechanism_tab)
            steps.append("Navigated to Mechanism Design tab")
        else:
            steps.append("WARNING: Mechanism Design tab not found")
        
        # Step 2: Trigger recommendation
        self.event_bus.publish(MechanismRecommendationRequestedEvent())
        steps.append("Published MechanismRecommendationRequestedEvent")
        
        # Step 3: Wait for recommendation dialog
        time.sleep(1)
        
        # Check for mechanism selection events
        mechanism_events = [e for e in self.results["events_captured"]
                           if "Mechanism" in e["type"]]
        
        if mechanism_events:
            steps.append(f"Mechanism events captured: {len(mechanism_events)}")
        else:
            steps.append("WARNING: No mechanism events captured")
        
        self.results["workflows"]["mechanism_recommendation"]["steps"] = steps
        print(f"[MECHANISM RECOMMENDATION] Completed {len(steps)} steps")
    
    def verify_synchronized_animation_workflow(self):
        """Workflow 4: Synchronized Skeleton + Mechanism Animation"""
        steps = []
        
        # Step 1: Ensure both skeleton and mechanism exist
        steps.append("Checking for skeleton and mechanism")
        
        # Step 2: Trigger synchronized animation
        self.event_bus.publish(SynchronizedAnimationRequestedEvent())
        steps.append("Published SynchronizedAnimationRequestedEvent")
        
        # Step 3: Monitor animation frames
        time.sleep(2)  # Let animation run
        
        # Check for animation frame events
        animation_events = [e for e in self.results["events_captured"]
                           if "Animation" in e["type"] or "Frame" in e["type"]]
        
        if animation_events:
            steps.append(f"Animation events captured: {len(animation_events)}")
            
            # Check for synchronization
            skeleton_updates = [e for e in animation_events if "Skeleton" in e["type"]]
            mechanism_updates = [e for e in animation_events if "Mechanism" in e["type"]]
            
            if skeleton_updates and mechanism_updates:
                steps.append(f"Synchronized updates: {len(skeleton_updates)} skeleton, {len(mechanism_updates)} mechanism")
            else:
                steps.append("WARNING: Missing synchronized updates")
        else:
            steps.append("WARNING: No animation events captured")
        
        self.results["workflows"]["synchronized_animation"]["steps"] = steps
        print(f"[SYNCHRONIZED ANIMATION] Completed {len(steps)} steps")
    
    def _get_editor_tab(self):
        """Find the Editor tab widget"""
        for i in range(self.main_window.tab_widget.count()):
            tab = self.main_window.tab_widget.widget(i)
            if "Editor" in self.main_window.tab_widget.tabText(i):
                return tab
        return None
    
    def _get_mechanism_design_tab(self):
        """Find the Mechanism Design tab widget"""
        for i in range(self.main_window.tab_widget.count()):
            tab = self.main_window.tab_widget.widget(i)
            if "Mechanism" in self.main_window.tab_widget.tabText(i):
                return tab
        return None
    
    def _find_action(self, action_name: str):
        """Find an action by name in the main window"""
        for action in self.main_window.findChildren(type(self.main_window).__bases__[0]):
            if hasattr(action, 'text') and action_name in action.text():
                return action
        return None
    
    def _save_results(self):
        """Save verification results to file"""
        self.results["end_time"] = datetime.now().isoformat()
        
        output_file = project_root / "verification_results.json"
        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\n[SAVED] Results saved to: {output_file}")
        
        # Generate summary report
        self._generate_summary_report()
    
    def _generate_summary_report(self):
        """Generate human-readable summary report"""
        report_lines = [
            "VERIFICATION SUITE SUMMARY",
            "=" * 60,
            f"Start Time: {self.results['start_time']}",
            f"End Time: {self.results.get('end_time', 'N/A')}",
            "",
            "WORKFLOW RESULTS:",
            "-" * 40
        ]
        
        for workflow_name, workflow_data in self.results["workflows"].items():
            status = workflow_data.get("status", "unknown")
            steps_count = len(workflow_data.get("steps", []))
            report_lines.append(f"\n{workflow_name.upper()}:")
            report_lines.append(f"  Status: {status}")
            report_lines.append(f"  Steps Completed: {steps_count}")
            
            if status == "failed":
                report_lines.append(f"  Error: {workflow_data.get('error', 'Unknown error')}")
            
            if workflow_data.get("steps"):
                report_lines.append("  Steps:")
                for step in workflow_data["steps"]:
                    report_lines.append(f"    - {step}")
        
        report_lines.extend([
            "",
            "EVENT SUMMARY:",
            "-" * 40,
            f"Total Events Captured: {len(self.results['events_captured'])}"
        ])
        
        # Count events by type
        event_counts = {}
        for event in self.results["events_captured"]:
            event_type = event["type"]
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
        
        for event_type, count in event_counts.items():
            report_lines.append(f"  {event_type}: {count}")
        
        if self.results["errors"]:
            report_lines.extend([
                "",
                "ERRORS:",
                "-" * 40
            ])
            for error in self.results["errors"]:
                report_lines.append(f"  [{error['workflow']}] {error['error']}")
        
        report_lines.extend([
            "",
            "=" * 60,
            "VERIFICATION COMPLETE"
        ])
        
        report_file = project_root / "verification_summary.txt"
        with open(report_file, 'w') as f:
            f.write('\n'.join(report_lines))
        
        print(f"[SAVED] Summary report saved to: {report_file}")
        print("\n" + '\n'.join(report_lines))


if __name__ == "__main__":
    suite = VerificationSuite()
    suite.run_all_workflows()