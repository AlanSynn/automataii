#!/usr/bin/env python3
"""
Execute Comprehensive Verification of Automataii
This script coordinates the verification process
"""

import subprocess
import sys
import time
import json
from pathlib import Path
from datetime import datetime
import threading
import queue

class VerificationExecutor:
    """Coordinates the verification execution"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.trace_log = self.project_root / "workflow_trace.log"
        self.json_trace = self.project_root / "verification_trace.json"
        self.app_process = None
        self.tracer_process = None
        self.monitor_queue = queue.Queue()
        self.monitoring = True
        
    def start_verification(self):
        """Start the verification process"""
        print("""
╔══════════════════════════════════════════════════════════════╗
║          AUTOMATAII VERIFICATION EXECUTION                    ║
╚══════════════════════════════════════════════════════════════╝

This will:
1. Clean existing trace files
2. Start the verification tracer
3. Launch Automataii application
4. Guide you through manual verification steps
5. Analyze results in real-time
""")
        
        # Clean trace files
        self._clean_traces()
        
        # Start verification tracer
        print("\n[1/3] Starting verification tracer...")
        self._start_tracer()
        
        # Start Automataii application
        print("\n[2/3] Launching Automataii application...")
        self._start_application()
        
        # Start trace monitoring
        print("\n[3/3] Starting trace monitoring...")
        monitor_thread = threading.Thread(target=self._monitor_traces)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        # Wait for app to initialize
        print("\nWaiting for application to initialize...")
        time.sleep(3)
        
        # Run verification workflows
        self._run_verification_workflows()
        
    def _clean_traces(self):
        """Clean existing trace files"""
        for file in [self.trace_log, self.json_trace]:
            if file.exists():
                file.unlink()
                print(f"  Cleaned: {file.name}")
    
    def _start_tracer(self):
        """Start the verification tracer"""
        tracer_script = self.project_root / "verification_tracer.py"
        if not tracer_script.exists():
            print("[ERROR] verification_tracer.py not found!")
            return False
        
        # Start tracer in background
        self.tracer_process = subprocess.Popen(
            [sys.executable, str(tracer_script)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(self.project_root)
        )
        
        # Give it time to initialize
        time.sleep(1)
        
        if self.tracer_process.poll() is None:
            print("  ✓ Verification tracer started (PID: {})".format(self.tracer_process.pid))
            return True
        else:
            print("  ✗ Failed to start verification tracer")
            return False
    
    def _start_application(self):
        """Start the Automataii application"""
        # Try to launch with uv
        try:
            self.app_process = subprocess.Popen(
                ["uv", "run", "automataii"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(self.project_root)
            )
            
            # Give it time to start
            time.sleep(2)
            
            if self.app_process.poll() is None:
                print("  ✓ Automataii started (PID: {})".format(self.app_process.pid))
                return True
            else:
                print("  ✗ Failed to start Automataii")
                return False
                
        except FileNotFoundError:
            print("  ✗ 'uv' command not found. Please ensure uv is installed.")
            return False
    
    def _monitor_traces(self):
        """Monitor trace files for updates"""
        last_log_size = 0
        last_json_mtime = 0
        
        while self.monitoring:
            try:
                # Monitor log file
                if self.trace_log.exists():
                    current_size = self.trace_log.stat().st_size
                    if current_size > last_log_size:
                        with open(self.trace_log, 'r') as f:
                            f.seek(last_log_size)
                            new_lines = f.readlines()
                            for line in new_lines:
                                if any(keyword in line for keyword in 
                                      ["Event:", "ERROR:", "WARNING:", "WORKFLOW:"]):
                                    self.monitor_queue.put(("log", line.strip()))
                        last_log_size = current_size
                
                # Monitor JSON file
                if self.json_trace.exists():
                    current_mtime = self.json_trace.stat().st_mtime
                    if current_mtime > last_json_mtime:
                        self.monitor_queue.put(("json", "JSON trace updated"))
                        last_json_mtime = current_mtime
                
            except Exception as e:
                print(f"[MONITOR ERROR] {e}")
            
            time.sleep(0.5)
    
    def _run_verification_workflows(self):
        """Guide through verification workflows"""
        workflows = [
            ("Path Drawing", self._verify_path_drawing),
            ("Skeleton Animation", self._verify_skeleton_animation),
            ("Mechanism Recommendation", self._verify_mechanism_recommendation),
            ("Synchronized Animation", self._verify_synchronized_animation)
        ]
        
        print("\n" + "="*60)
        print("STARTING WORKFLOW VERIFICATION")
        print("="*60)
        
        for workflow_name, workflow_func in workflows:
            print(f"\n\n{'='*60}")
            print(f"WORKFLOW: {workflow_name}")
            print(f"{'='*60}")
            
            # Clear monitor queue
            while not self.monitor_queue.empty():
                self.monitor_queue.get()
            
            # Run workflow
            workflow_func()
            
            # Show captured events
            print("\n[CAPTURED EVENTS]")
            event_count = 0
            timeout = time.time() + 2  # Wait 2 seconds for events
            
            while time.time() < timeout:
                try:
                    event_type, event_data = self.monitor_queue.get(timeout=0.1)
                    if event_type == "log":
                        print(f"  {event_data}")
                        event_count += 1
                except queue.Empty:
                    pass
            
            if event_count == 0:
                print("  No events captured - verification may have failed")
            
            # Analyze after each workflow
            print("\n[ANALYZING WORKFLOW]")
            self._run_analysis(workflow_name)
            
            input("\nPress Enter to continue to next workflow...")
        
        # Final analysis
        print("\n\n" + "="*60)
        print("FINAL VERIFICATION ANALYSIS")
        print("="*60)
        self._run_full_analysis()
    
    def _verify_path_drawing(self):
        """Path drawing workflow verification"""
        print("""
INSTRUCTIONS:
1. The Automataii application should be open
2. Click on the "Editor" tab if not already there
3. Select the "Draw Path" tool (pencil icon or Tools → Draw Path)
4. On the canvas:
   - Click and hold at position (100, 100)
   - Drag to create a curved path to (300, 300)
   - Release the mouse button

EXPECTED BEHAVIOR:
- Path should appear on canvas
- MotionPathCompletedEvent should be published
- Path data should be saved to project state

Press Enter when ready to start...""")
        input()
        
        print("\nPerform the path drawing now...")
        print("Monitoring for events...")
    
    def _verify_skeleton_animation(self):
        """Skeleton animation workflow verification"""
        print("""
INSTRUCTIONS:
1. Ensure you're in the "Editor" tab
2. Load a project with a skeleton (File → Open)
   OR create a new skeleton
3. Place a target point on the canvas
4. Select the skeleton
5. Click the "Animate" button

EXPECTED BEHAVIOR:
- Skeleton should move smoothly to target
- IK solver should calculate joint positions
- Visual updates should occur in real-time

Press Enter when ready to start...""")
        input()
        
        print("\nPerform the skeleton animation now...")
        print("Monitoring for events...")
    
    def _verify_mechanism_recommendation(self):
        """Mechanism recommendation workflow verification"""
        print("""
INSTRUCTIONS:
1. Navigate to "Mechanism Design" tab
2. Ensure you have a motion path drawn
3. Select the motion path
4. Click "Recommend Mechanism" button
5. Select a mechanism from the dialog
6. Click "Place" or "OK"

EXPECTED BEHAVIOR:
- Recommendation dialog shows options
- Selected mechanism appears on canvas
- Mechanism is added to project state

Press Enter when ready to start...""")
        input()
        
        print("\nPerform the mechanism recommendation now...")
        print("Monitoring for events...")
    
    def _verify_synchronized_animation(self):
        """Synchronized animation workflow verification"""
        print("""
INSTRUCTIONS:
1. Set up a scene with both skeleton AND mechanism
2. Link them if required (select both → "Link" tool)
3. Click the global "Play" button
4. Try pause/resume during playback
5. Drag the timeline scrubber

EXPECTED BEHAVIOR:
- Skeleton and mechanism move together
- Smooth synchronized animation
- Pause/resume works correctly
- Timeline scrubbing updates both

Press Enter when ready to start...""")
        input()
        
        print("\nPerform the synchronized animation now...")
        print("Monitoring for events...")
    
    def _run_analysis(self, workflow_name: str):
        """Run analysis for a specific workflow"""
        try:
            # Run trace analyzer
            result = subprocess.run(
                [sys.executable, "trace_analyzer.py"],
                capture_output=True,
                text=True,
                cwd=str(self.project_root)
            )
            
            # Extract relevant section
            output_lines = result.stdout.split('\n')
            in_workflow = False
            
            for line in output_lines:
                if f"[ANALYZING] {workflow_name.upper()}" in line:
                    in_workflow = True
                elif "[ANALYZING]" in line and in_workflow:
                    break
                elif in_workflow and line.strip():
                    print(line)
                    
        except Exception as e:
            print(f"[ANALYSIS ERROR] {e}")
    
    def _run_full_analysis(self):
        """Run complete trace analysis"""
        try:
            result = subprocess.run(
                [sys.executable, "trace_analyzer.py"],
                capture_output=True,
                text=True,
                cwd=str(self.project_root)
            )
            
            print(result.stdout)
            
        except Exception as e:
            print(f"[ANALYSIS ERROR] {e}")
    
    def cleanup(self):
        """Clean up processes"""
        self.monitoring = False
        
        if self.app_process:
            print("\nTerminating Automataii...")
            self.app_process.terminate()
            self.app_process.wait(timeout=5)
        
        if self.tracer_process:
            print("Terminating verification tracer...")
            self.tracer_process.terminate()
            self.tracer_process.wait(timeout=5)
        
        print("\nVerification execution complete.")


def main():
    """Main execution"""
    executor = VerificationExecutor()
    
    try:
        executor.start_verification()
    except KeyboardInterrupt:
        print("\n\nVerification interrupted by user.")
    except Exception as e:
        print(f"\n\nERROR: {e}")
    finally:
        executor.cleanup()


if __name__ == "__main__":
    main()