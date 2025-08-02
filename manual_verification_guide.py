#!/usr/bin/env python3
"""
Manual Verification Guide with Trace Analysis
Provides step-by-step instructions and real-time trace analysis
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
import threading
import queue

class VerificationMonitor:
    """Real-time monitoring of verification traces"""
    
    def __init__(self):
        self.trace_file = Path("workflow_trace.log")
        self.json_file = Path("verification_trace.json")
        self.event_queue = queue.Queue()
        self.monitoring = False
        self.workflow_status = {
            "path_drawing": {"active": False, "events": []},
            "skeleton_animation": {"active": False, "events": []},
            "mechanism_recommendation": {"active": False, "events": []},
            "synchronized_animation": {"active": False, "events": []}
        }
    
    def start_monitoring(self):
        """Start monitoring trace files in background thread"""
        self.monitoring = True
        monitor_thread = threading.Thread(target=self._monitor_traces)
        monitor_thread.daemon = True
        monitor_thread.start()
        print("[MONITOR] Started trace monitoring")
    
    def stop_monitoring(self):
        """Stop monitoring"""
        self.monitoring = False
        print("[MONITOR] Stopped trace monitoring")
    
    def _monitor_traces(self):
        """Monitor trace files for changes"""
        last_size = 0
        
        while self.monitoring:
            try:
                # Check trace file for new entries
                if self.trace_file.exists():
                    current_size = self.trace_file.stat().st_size
                    if current_size > last_size:
                        with open(self.trace_file, 'r') as f:
                            f.seek(last_size)
                            new_lines = f.readlines()
                            for line in new_lines:
                                self._process_trace_line(line)
                        last_size = current_size
                
                # Check JSON file for structured data
                if self.json_file.exists():
                    with open(self.json_file, 'r') as f:
                        data = json.load(f)
                        self._process_json_data(data)
                
            except Exception as e:
                print(f"[MONITOR ERROR] {e}")
            
            time.sleep(0.5)  # Check every 500ms
    
    def _process_trace_line(self, line: str):
        """Process a single trace line"""
        # Look for key patterns
        if "Event:" in line:
            if "MotionPathCompletedEvent" in line:
                self.workflow_status["path_drawing"]["events"].append({
                    "time": datetime.now().isoformat(),
                    "event": "MotionPathCompletedEvent",
                    "line": line.strip()
                })
                print(f"\n[DETECTED] Path Drawing Event!")
            
            elif "SkeletonAnimationRequestedEvent" in line or "SkeletonUpdatedEvent" in line:
                self.workflow_status["skeleton_animation"]["events"].append({
                    "time": datetime.now().isoformat(),
                    "event": line.strip(),
                    "line": line.strip()
                })
                print(f"\n[DETECTED] Skeleton Animation Event!")
            
            elif "MechanismRecommendationRequestedEvent" in line or "MechanismSelectedEvent" in line:
                self.workflow_status["mechanism_recommendation"]["events"].append({
                    "time": datetime.now().isoformat(),
                    "event": line.strip(),
                    "line": line.strip()
                })
                print(f"\n[DETECTED] Mechanism Recommendation Event!")
            
            elif "SynchronizedAnimationRequestedEvent" in line or "AnimationFrameEvent" in line:
                self.workflow_status["synchronized_animation"]["events"].append({
                    "time": datetime.now().isoformat(),
                    "event": line.strip(),
                    "line": line.strip()
                })
                print(f"\n[DETECTED] Synchronized Animation Event!")
    
    def _process_json_data(self, data: Dict):
        """Process structured JSON trace data"""
        # Extract event counts and workflow states
        if "summary" in data and "workflow_states" in data["summary"]:
            for workflow, state in data["summary"]["workflow_states"].items():
                if state.get("active"):
                    self.workflow_status[workflow]["active"] = True
    
    def print_workflow_guide(self, workflow_name: str):
        """Print step-by-step guide for a workflow"""
        guides = {
            "path_drawing": """
PATH DRAWING WORKFLOW VERIFICATION
==================================

STEPS TO EXECUTE:
1. Launch the Automataii application (if not already running)
   $ uv run automataii

2. Navigate to the EDITOR tab

3. Select the "Draw Path" tool from the toolbar
   - Look for a pencil/path icon
   - Or use the menu: Tools → Draw Path

4. On the canvas, perform these actions:
   a) Click and hold the left mouse button at position (100, 100)
   b) Drag to create a curved path to position (300, 300)
   c) Release the mouse button

5. EDGE CASES TO TEST:
   - Single click without dragging
   - Very complex/long path
   - Path that goes outside canvas bounds
   - Press ESC while drawing

EXPECTED EVENTS:
- mousePress event at start
- Multiple mouseMove events during drag
- mouseRelease event at end
- MotionPathCompletedEvent published
- ProjectDataManager receives and stores path

VERIFICATION POINTS:
✓ Path appears on canvas
✓ Event shows in trace log
✓ Path data persisted to project state
""",

            "skeleton_animation": """
SKELETON ANIMATION WORKFLOW VERIFICATION
========================================

STEPS TO EXECUTE:
1. Ensure you're in the EDITOR tab

2. Load or create a skeleton:
   - File → Open Project (with skeleton)
   - OR use the skeleton creation tool

3. Set up a target point:
   - Click to place a target on the canvas
   - OR load a project with existing targets

4. Select the skeleton by clicking on it

5. Click the "Animate" button in the toolbar
   - Look for play/animation icon
   - OR use menu: Animation → Start

6. EDGE CASES TO TEST:
   - Unreachable target (far from skeleton)
   - No skeleton selected
   - Rapid animation clicks
   - Skeleton with joint constraints

EXPECTED EVENTS:
- SkeletonAnimationRequestedEvent on button click
- IK solver function calls in kinematics module
- SkeletonUpdatedEvent with new joint positions
- Renderer update calls

VERIFICATION POINTS:
✓ Skeleton moves smoothly to target
✓ IK solver completes < 16ms
✓ Visual updates match calculated positions
✓ No errors for unreachable targets
""",

            "mechanism_recommendation": """
MECHANISM RECOMMENDATION WORKFLOW VERIFICATION
==============================================

STEPS TO EXECUTE:
1. Navigate to MECHANISM DESIGN tab

2. Ensure you have a motion path:
   - Draw one using the path tool
   - OR load a project with existing path

3. Select the motion path on canvas

4. Click "Recommend Mechanism" button
   - Look for lightbulb/suggestion icon
   - OR use menu: Mechanisms → Get Recommendations

5. In the recommendation dialog:
   - Review suggested mechanisms
   - Select one mechanism
   - Click "Place" or "OK"

6. EDGE CASES TO TEST:
   - Path that no mechanism can replicate
   - Very simple straight-line path
   - Complex multi-curve path
   - Cancel dialog without selection

EXPECTED EVENTS:
- MechanismRecommendationRequestedEvent
- Database query with path data
- List of recommendations returned
- MechanismSelectedEvent on selection
- MechanismAddedEvent after placement

VERIFICATION POINTS:
✓ Recommendation dialog shows options
✓ Selected mechanism appears on canvas
✓ Mechanism data added to project state
✓ Appropriate message for infeasible paths
""",

            "synchronized_animation": """
SYNCHRONIZED ANIMATION WORKFLOW VERIFICATION
============================================

STEPS TO EXECUTE:
1. Set up a scene with both skeleton AND mechanism:
   - Load a project with both
   - OR create skeleton + place mechanism

2. Link skeleton to mechanism (if required):
   - Select both components
   - Use "Link" tool or menu option

3. Click the global "Play" button
   - Look for main play/animate all icon
   - OR use menu: Animation → Play All

4. During animation:
   - Observe synchronized movement
   - Try pause/resume buttons
   - Drag timeline scrubber

5. EDGE CASES TO TEST:
   - Unlinked skeleton and mechanism
   - Different animation speeds
   - Pause mid-animation
   - Scrub timeline backwards

EXPECTED EVENTS:
- SynchronizedAnimationRequestedEvent
- Stream of AnimationFrameEvent(time=t)
- Parallel SkeletonUpdatedEvent(time=t)
- Parallel MechanismStateUpdatedEvent(time=t)
- Synchronized renderer updates

VERIFICATION POINTS:
✓ Skeleton and mechanism move together
✓ Frame timestamps match exactly
✓ Smooth playback at target FPS
✓ Pause/resume works correctly
✓ Timeline scrubbing updates both
"""
        }
        
        print(guides.get(workflow_name, "Unknown workflow"))
    
    def analyze_workflow(self, workflow_name: str):
        """Analyze captured events for a workflow"""
        workflow_data = self.workflow_status.get(workflow_name)
        if not workflow_data:
            print(f"[ERROR] Unknown workflow: {workflow_name}")
            return
        
        print(f"\n{'='*60}")
        print(f"WORKFLOW ANALYSIS: {workflow_name.upper()}")
        print(f"{'='*60}")
        
        events = workflow_data.get("events", [])
        if not events:
            print("No events captured for this workflow yet.")
            return
        
        print(f"Total Events Captured: {len(events)}")
        print("\nEvent Timeline:")
        for i, event in enumerate(events):
            print(f"  {i+1}. [{event['time']}] {event['event']}")
        
        # Workflow-specific analysis
        if workflow_name == "path_drawing":
            motion_events = [e for e in events if "MotionPathCompleted" in e["event"]]
            print(f"\nMotion Path Events: {len(motion_events)}")
            if motion_events:
                print("✓ Path drawing workflow completed successfully")
            else:
                print("✗ No MotionPathCompletedEvent detected")
        
        elif workflow_name == "skeleton_animation":
            request_events = [e for e in events if "AnimationRequested" in e["event"]]
            update_events = [e for e in events if "Updated" in e["event"]]
            print(f"\nAnimation Requests: {len(request_events)}")
            print(f"Skeleton Updates: {len(update_events)}")
            if request_events and update_events:
                print("✓ Skeleton animation workflow completed successfully")
            else:
                print("✗ Missing animation request or update events")
        
        elif workflow_name == "mechanism_recommendation":
            request_events = [e for e in events if "RecommendationRequested" in e["event"]]
            selected_events = [e for e in events if "Selected" in e["event"]]
            print(f"\nRecommendation Requests: {len(request_events)}")
            print(f"Mechanism Selections: {len(selected_events)}")
            if request_events and selected_events:
                print("✓ Mechanism recommendation workflow completed successfully")
            else:
                print("✗ Missing recommendation or selection events")
        
        elif workflow_name == "synchronized_animation":
            frame_events = [e for e in events if "AnimationFrame" in e["event"]]
            print(f"\nAnimation Frames: {len(frame_events)}")
            if frame_events:
                print("✓ Synchronized animation initiated")
                # Check for synchronization
                # Would need to parse timestamps from event data
            else:
                print("✗ No animation frame events detected")


def main():
    """Interactive verification guide"""
    monitor = VerificationMonitor()
    
    print("""
AUTOMATAII MANUAL VERIFICATION GUIDE
====================================

This guide will help you verify the 4 critical workflows:
1. Path Drawing
2. Skeleton Animation  
3. Mechanism Recommendation
4. Synchronized Animation

The monitor will track events in real-time as you perform actions.
""")
    
    monitor.start_monitoring()
    
    while True:
        print("\n" + "="*60)
        print("VERIFICATION MENU")
        print("="*60)
        print("1. Path Drawing Workflow")
        print("2. Skeleton Animation Workflow")
        print("3. Mechanism Recommendation Workflow")
        print("4. Synchronized Animation Workflow")
        print("")
        print("5. Analyze Path Drawing Results")
        print("6. Analyze Skeleton Animation Results")
        print("7. Analyze Mechanism Recommendation Results")
        print("8. Analyze Synchronized Animation Results")
        print("")
        print("9. Show All Captured Events")
        print("0. Exit")
        
        choice = input("\nSelect option (0-9): ").strip()
        
        if choice == "0":
            break
        elif choice == "1":
            monitor.print_workflow_guide("path_drawing")
        elif choice == "2":
            monitor.print_workflow_guide("skeleton_animation")
        elif choice == "3":
            monitor.print_workflow_guide("mechanism_recommendation")
        elif choice == "4":
            monitor.print_workflow_guide("synchronized_animation")
        elif choice == "5":
            monitor.analyze_workflow("path_drawing")
        elif choice == "6":
            monitor.analyze_workflow("skeleton_animation")
        elif choice == "7":
            monitor.analyze_workflow("mechanism_recommendation")
        elif choice == "8":
            monitor.analyze_workflow("synchronized_animation")
        elif choice == "9":
            print("\nALL CAPTURED EVENTS:")
            for workflow, data in monitor.workflow_status.items():
                if data["events"]:
                    print(f"\n{workflow.upper()}:")
                    for event in data["events"]:
                        print(f"  - {event}")
        else:
            print("Invalid option")
        
        input("\nPress Enter to continue...")
    
    monitor.stop_monitoring()
    print("\nVerification guide closed.")


if __name__ == "__main__":
    main()