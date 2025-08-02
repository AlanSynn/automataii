#!/usr/bin/env python3
"""
Automated Trace Analyzer for Automataii UI Verification

This script continuously monitors the verification trace files and provides
real-time analysis of UI interactions, event patterns, and workflow completion.
It implements Gemini's strategic verification plan with automated analysis.
"""

import json
import time
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import re


@dataclass
class VerificationStep:
    """Represents a verification step with expected events and outcomes"""
    step_id: str
    description: str
    expected_events: List[str]
    expected_visual_feedback: bool
    completion_criteria: List[str]
    success: bool = False
    events_found: List[str] = None
    timestamp: Optional[datetime] = None
    details: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.events_found is None:
            self.events_found = []
        if self.details is None:
            self.details = {}


class AutomatedTraceAnalyzer:
    """
    Automated analyzer for UI verification traces
    
    Monitors trace files and provides real-time analysis of:
    - UI component interactions
    - Event emission patterns
    - Workflow completion status
    - Error detection and reporting
    """
    
    def __init__(self):
        self.trace_file = Path("workflow_trace.log")
        self.verification_file = Path("verification_trace.json")
        self.last_trace_position = 0
        self.last_verification_check = 0
        self.analysis_results = {
            "ui_components": {},
            "workflows": {},
            "events": {},
            "errors": [],
            "performance": {},
            "verification_status": "IN_PROGRESS"
        }
        
        # Define verification steps based on Gemini's strategic plan
        self.verification_steps = self._define_verification_steps()
        self.running = False
        self.analysis_thread = None
        
    def _define_verification_steps(self) -> Dict[str, VerificationStep]:
        """Define all verification steps based on Gemini's strategic plan"""
        return {
            # Phase 1: UI Component Audit
            "tab_navigation": VerificationStep(
                "tab_navigation",
                "Tab Navigation Testing",
                ["TabSwitchEvent", "TabActivatedEvent"],
                True,
                ["All tabs switch smoothly", "Content loads properly"]
            ),
            "button_responsiveness": VerificationStep(
                "button_responsiveness", 
                "Button Responsiveness Testing",
                ["ButtonClickedEvent", "ActionTriggeredEvent"],
                True,
                ["All buttons respond visually", "No crashes"]
            ),
            
            # Phase 2: Workflow A - Path Drawing → Skeleton Animation
            "path_tool_selection": VerificationStep(
                "path_tool_selection",
                "Select Path Tool",
                ["PathEditingModeActivated", "MotionPathStartedEvent"],
                True,
                ["Path tool is active", "Cursor changes"]
            ),
            "path_drawing": VerificationStep(
                "path_drawing",
                "Draw Path",
                ["MotionPathPointAddedEvent", "MotionPathCompletedEvent"],
                True,
                ["Path is drawn and visible", "Path data captured"]
            ),
            "animation_initiation": VerificationStep(
                "animation_initiation",
                "Initiate Animation",
                ["AnimationStartedEvent", "AnimationRunRequested"],
                True,
                ["Animation starts", "Controls respond"]
            ),
            "skeleton_animation": VerificationStep(
                "skeleton_animation",
                "Observe Skeleton Animation",
                ["SkeletonPoseUpdated", "AnimationTickEvent"],
                True,
                ["Skeleton follows path", "Smooth movement"]
            ),
            "animation_completion": VerificationStep(
                "animation_completion",
                "Verify Animation Completion",
                ["AnimationCompletedEvent", "AnimationStoppedEvent"],
                True,
                ["Animation completes", "Controls reset"]
            ),
            
            # Phase 2: Workflow B - Mechanism Recommendation → Synchronized Animation
            "mechanism_recommendation": VerificationStep(
                "mechanism_recommendation",
                "Request Mechanism Recommendation",
                ["MechanismRecommendationRequestedEvent", "RecommendationRequested"],
                True,
                ["Recommendation process starts", "Loading indication"]
            ),
            "recommendation_display": VerificationStep(
                "recommendation_display",
                "Receive & View Recommendations",
                ["RecommendationsReady", "RecommendationDialogShown"],
                True,
                ["Recommendations displayed", "Mechanisms visible"]
            ),
            "mechanism_application": VerificationStep(
                "mechanism_application",
                "Apply Mechanism",
                ["MechanismSelectedEvent", "MechanismAddedEvent"],
                True,
                ["Mechanism applied", "Visible in design"]
            ),
            "synchronized_animation": VerificationStep(
                "synchronized_animation",
                "Synchronized Animation",
                ["AnimationStartedEvent", "SkeletonPoseUpdated", "MechanismStateUpdated"],
                True,
                ["Both skeleton and mechanism animate", "Perfect synchronization"]
            ),
            
            # Phase 3: Stability Testing
            "rapid_interactions": VerificationStep(
                "rapid_interactions",
                "Rapid Interaction Testing",
                ["ErrorHandlingEvent", "GracefulRecoveryEvent"],
                True,
                ["No crashes", "Smooth handling"]
            ),
            "invalid_sequences": VerificationStep(
                "invalid_sequences",
                "Invalid Sequence Testing",
                ["ValidationErrorEvent", "UserFeedbackEvent"],
                True,
                ["Graceful error messages", "No crashes"]
            )
        }
    
    def start_monitoring(self):
        """Start continuous monitoring of trace files"""
        self.running = True
        self.analysis_thread = threading.Thread(target=self._monitoring_loop)
        self.analysis_thread.daemon = True
        self.analysis_thread.start()
        print("🔍 Automated Trace Analyzer Started - Monitoring verification...")
    
    def stop_monitoring(self):
        """Stop monitoring and generate final report"""
        self.running = False
        if self.analysis_thread:
            self.analysis_thread.join()
        print("📊 Monitoring stopped. Generating final report...")
        self.generate_final_report()
    
    def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                # Analyze workflow trace
                self._analyze_workflow_trace()
                
                # Analyze verification trace
                self._analyze_verification_trace()
                
                # Update verification status
                self._update_verification_status()
                
                # Generate real-time report
                self._generate_realtime_report()
                
                time.sleep(1)  # Check every second
                
            except Exception as e:
                print(f"❌ Error in monitoring loop: {e}")
                time.sleep(5)  # Wait longer on error
    
    def _analyze_workflow_trace(self):
        """Analyze workflow trace log for events and patterns"""
        if not self.trace_file.exists():
            return
        
        try:
            with open(self.trace_file, 'r') as f:
                f.seek(self.last_trace_position)
                new_lines = f.readlines()
                self.last_trace_position = f.tell()
            
            for line in new_lines:
                self._process_trace_line(line.strip())
                
        except Exception as e:
            print(f"❌ Error analyzing workflow trace: {e}")
    
    def _analyze_verification_trace(self):
        """Analyze verification trace JSON for detailed event data"""
        if not self.verification_file.exists():
            return
        
        try:
            with open(self.verification_file, 'r') as f:
                data = json.load(f)
            
            # Update analysis with verification data
            self.analysis_results["events"] = data.get("event_counts", {})
            self.analysis_results["performance"]["function_calls"] = data.get("function_call_count", 0)
            self.analysis_results["performance"]["signal_emissions"] = data.get("signal_emission_count", 0)
            
            # Analyze workflow states
            workflow_states = data.get("workflow_states", {})
            for workflow_name, state in workflow_states.items():
                if state.get("active", False):
                    self._update_workflow_status(workflow_name, state)
                    
        except Exception as e:
            print(f"❌ Error analyzing verification trace: {e}")
    
    def _process_trace_line(self, line: str):
        """Process a single trace line and extract events"""
        if not line:
            return
        
        # Extract timestamp, level, and message
        match = re.match(r'(\d{2}:\d{2}:\d{2}\.\d{3})\s+\[(\w+)\]\s+(.+)', line)
        if not match:
            return
        
        timestamp, level, message = match.groups()
        
        # Look for specific events and patterns
        self._detect_events_in_message(message, timestamp, level)
        
        # Check for errors
        if level in ["ERROR", "CRITICAL"]:
            self.analysis_results["errors"].append({
                "timestamp": timestamp,
                "level": level,
                "message": message
            })
    
    def _detect_events_in_message(self, message: str, timestamp: str, level: str):
        """Detect specific events in log messages"""
        # Event patterns to look for
        event_patterns = {
            "PathEditingModeActivated": r"path.*edit.*mode|path.*tool.*select",
            "MotionPathStartedEvent": r"motion.*path.*start|path.*draw.*start",
            "MotionPathPointAddedEvent": r"path.*point.*add|motion.*path.*point",
            "MotionPathCompletedEvent": r"path.*complet|motion.*path.*finish",
            "AnimationStartedEvent": r"animation.*start|animate.*begin",
            "AnimationTickEvent": r"animation.*tick|animate.*update",
            "SkeletonPoseUpdated": r"skeleton.*pose.*updat|pose.*chang",
            "AnimationCompletedEvent": r"animation.*complet|animate.*finish",
            "MechanismRecommendationRequestedEvent": r"mechanism.*recommend|recommend.*request",
            "RecommendationsReady": r"recommend.*ready|recommend.*receiv",
            "MechanismSelectedEvent": r"mechanism.*select|mechanism.*chose",
            "MechanismAddedEvent": r"mechanism.*add|mechanism.*appli",
            "MechanismStateUpdated": r"mechanism.*state.*updat|mechanism.*mov",
            "TabSwitchEvent": r"tab.*switch|tab.*chang",
            "ButtonClickedEvent": r"button.*click|button.*press",
            "ErrorHandlingEvent": r"error.*handl|exception.*catch",
            "ValidationErrorEvent": r"validation.*error|invalid.*input"
        }
        
        for event_type, pattern in event_patterns.items():
            if re.search(pattern, message, re.IGNORECASE):
                # Update event count
                if event_type not in self.analysis_results["events"]:
                    self.analysis_results["events"][event_type] = 0
                self.analysis_results["events"][event_type] += 1
                
                # Update verification steps
                self._update_verification_steps(event_type, timestamp, message)
    
    def _update_verification_steps(self, event_type: str, timestamp: str, message: str):
        """Update verification steps based on detected events"""
        for step_id, step in self.verification_steps.items():
            if event_type in step.expected_events:
                step.events_found.append(event_type)
                step.timestamp = timestamp
                step.details[event_type] = message
                
                # Check if step is complete
                if all(event in step.events_found for event in step.expected_events):
                    step.success = True
                    print(f"✅ Verification Step Complete: {step.description}")
    
    def _update_workflow_status(self, workflow_name: str, state: Dict):
        """Update workflow status based on verification trace"""
        if workflow_name not in self.analysis_results["workflows"]:
            self.analysis_results["workflows"][workflow_name] = {
                "active": False,
                "completed_steps": [],
                "total_steps": 0,
                "completion_rate": 0.0
            }
        
        self.analysis_results["workflows"][workflow_name].update(state)
    
    def _update_verification_status(self):
        """Update overall verification status"""
        completed_steps = sum(1 for step in self.verification_steps.values() if step.success)
        total_steps = len(self.verification_steps)
        completion_rate = (completed_steps / total_steps) * 100 if total_steps > 0 else 0
        
        self.analysis_results["verification_status"] = {
            "completed_steps": completed_steps,
            "total_steps": total_steps,
            "completion_rate": completion_rate,
            "status": "COMPLETED" if completion_rate >= 100 else "IN_PROGRESS"
        }
    
    def _generate_realtime_report(self):
        """Generate real-time verification report"""
        status = self.analysis_results["verification_status"]
        
        if isinstance(status, dict):
            completion_rate = status.get("completion_rate", 0)
            completed_steps = status.get("completed_steps", 0)
            total_steps = status.get("total_steps", 0)
            
            # Only print progress updates at significant milestones
            if completion_rate > 0 and completed_steps % 5 == 0:
                print(f"📊 Verification Progress: {completion_rate:.1f}% ({completed_steps}/{total_steps} steps)")
        
        # Save current analysis to file
        with open("realtime_verification_analysis.json", "w") as f:
            json.dump(self.analysis_results, f, indent=2, default=str)
    
    def generate_final_report(self):
        """Generate comprehensive final verification report"""
        print("\n" + "="*60)
        print("🎯 FINAL UI VERIFICATION REPORT")
        print("="*60)
        
        # Overall Status
        status = self.analysis_results["verification_status"]
        if isinstance(status, dict):
            print(f"📊 Overall Completion: {status.get('completion_rate', 0):.1f}%")
            print(f"✅ Completed Steps: {status.get('completed_steps', 0)}")
            print(f"📝 Total Steps: {status.get('total_steps', 0)}")
        
        # Phase Results
        print("\n📋 PHASE RESULTS:")
        
        # Phase 1: UI Component Audit
        phase1_steps = ["tab_navigation", "button_responsiveness"]
        phase1_success = sum(1 for step in phase1_steps if self.verification_steps[step].success)
        print(f"Phase 1 (UI Component Audit): {phase1_success}/{len(phase1_steps)} ✅")
        
        # Phase 2: Workflow Verification
        phase2_steps = ["path_tool_selection", "path_drawing", "animation_initiation", 
                       "skeleton_animation", "animation_completion", "mechanism_recommendation",
                       "recommendation_display", "mechanism_application", "synchronized_animation"]
        phase2_success = sum(1 for step in phase2_steps if self.verification_steps[step].success)
        print(f"Phase 2 (Workflow Verification): {phase2_success}/{len(phase2_steps)} ✅")
        
        # Phase 3: Stability Testing
        phase3_steps = ["rapid_interactions", "invalid_sequences"]
        phase3_success = sum(1 for step in phase3_steps if self.verification_steps[step].success)
        print(f"Phase 3 (Stability Testing): {phase3_success}/{len(phase3_steps)} ✅")
        
        # Event Analysis
        print("\n🔄 EVENT ANALYSIS:")
        total_events = sum(self.analysis_results["events"].values())
        print(f"Total Events Captured: {total_events}")
        
        for event_type, count in sorted(self.analysis_results["events"].items()):
            print(f"  {event_type}: {count}")
        
        # Error Analysis
        print("\n❌ ERROR ANALYSIS:")
        if self.analysis_results["errors"]:
            print(f"Total Errors: {len(self.analysis_results['errors'])}")
            for error in self.analysis_results["errors"][-5:]:  # Show last 5 errors
                print(f"  [{error['timestamp']}] {error['level']}: {error['message'][:100]}")
        else:
            print("No errors detected ✅")
        
        # Performance Analysis
        print("\n⚡ PERFORMANCE ANALYSIS:")
        perf = self.analysis_results["performance"]
        print(f"Function Calls: {perf.get('function_calls', 0)}")
        print(f"Signal Emissions: {perf.get('signal_emissions', 0)}")
        
        # Critical Success Criteria
        print("\n🎯 CRITICAL SUCCESS CRITERIA:")
        critical_checks = [
            ("Path Drawing Works", any(step.success for step in [self.verification_steps["path_drawing"]])),
            ("Skeleton Animation Works", any(step.success for step in [self.verification_steps["skeleton_animation"]])),
            ("Mechanism Recommendations Work", any(step.success for step in [self.verification_steps["mechanism_recommendation"]])),
            ("Synchronized Animation Works", any(step.success for step in [self.verification_steps["synchronized_animation"]])),
            ("No Critical Errors", len([e for e in self.analysis_results["errors"] if e["level"] == "CRITICAL"]) == 0),
            ("Button Responsiveness", self.verification_steps["button_responsiveness"].success),
            ("Tab Navigation", self.verification_steps["tab_navigation"].success),
            ("Stability Testing", any(step.success for step in [self.verification_steps["rapid_interactions"], self.verification_steps["invalid_sequences"]]))
        ]
        
        passed_criteria = sum(1 for _, passed in critical_checks if passed)
        total_criteria = len(critical_checks)
        
        for check_name, passed in critical_checks:
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"  {check_name}: {status}")
        
        # Final Assessment
        print("\n🏆 FINAL ASSESSMENT:")
        success_rate = (passed_criteria / total_criteria) * 100
        print(f"Success Rate: {success_rate:.1f}% ({passed_criteria}/{total_criteria})")
        
        if success_rate >= 87.5:  # 7/8 criteria
            print("🎉 RESULT: PRODUCTION READY ✅")
        elif success_rate >= 75:
            print("⚠️  RESULT: REQUIRES MINOR FIXES")
        else:
            print("❌ RESULT: REQUIRES MAJOR FIXES")
        
        # Save final report
        final_report = {
            "timestamp": datetime.now().isoformat(),
            "verification_status": self.analysis_results["verification_status"],
            "phase_results": {
                "phase1": {"passed": phase1_success, "total": len(phase1_steps)},
                "phase2": {"passed": phase2_success, "total": len(phase2_steps)},
                "phase3": {"passed": phase3_success, "total": len(phase3_steps)}
            },
            "event_analysis": self.analysis_results["events"],
            "error_analysis": self.analysis_results["errors"],
            "performance_analysis": self.analysis_results["performance"],
            "critical_success_criteria": {
                "passed": passed_criteria,
                "total": total_criteria,
                "success_rate": success_rate
            },
            "detailed_steps": {step_id: asdict(step) for step_id, step in self.verification_steps.items()}
        }
        
        with open("final_verification_report.json", "w") as f:
            json.dump(final_report, f, indent=2, default=str)
        
        print("\n📄 Final report saved to: final_verification_report.json")
        print("="*60)


def main():
    """Main entry point"""
    print("🚀 Starting Automated Trace Analyzer for UI Verification")
    print("This analyzer will monitor verification traces and provide real-time feedback")
    print("Press Ctrl+C to stop monitoring and generate final report")
    
    analyzer = AutomatedTraceAnalyzer()
    
    try:
        analyzer.start_monitoring()
        
        # Keep running until interrupted
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping analysis...")
        analyzer.stop_monitoring()
        print("📊 Analysis complete!")


if __name__ == "__main__":
    main()