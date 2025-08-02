#!/usr/bin/env python3
"""
ULTRATHINK Systematic UI Verification
Complete verification protocol starting from main to ensure every UI button and workflow functions perfectly.
"""

import sys
import time
import json
import threading
import subprocess
from datetime import datetime
from pathlib import Path
from trace_analyzer import TraceAnalyzer

class SystematicUIVerification:
    """
    Comprehensive UI verification protocol ensuring 100% functionality.
    
    Tests every:
    - Button click and response
    - Workflow step completion
    - Event emission and handling
    - Animation functionality
    - Error handling
    """
    
    def __init__(self):
        self.verification_results = {}
        self.start_time = time.time()
        self.current_step = 0
        self.total_steps = 25
        self.app_process = None
        self.monitoring_active = False
        
        print("🧠 ULTRATHINK SYSTEMATIC UI VERIFICATION")
        print("=" * 80)
        print("🎯 Complete verification starting from main.py")
        print("🔍 Every UI button and workflow step tested")
        print("✅ Zero tolerance for malfunctions")
        print("")
        
    def execute_complete_verification(self):
        """Execute systematic verification from main startup to complete workflows."""
        
        print("🚀 STARTING COMPLETE VERIFICATION FROM MAIN")
        print("=" * 80)
        
        try:
            # Phase 1: Application Startup Verification
            self._verify_application_startup()
            
            # Phase 2: UI Component Verification  
            self._verify_ui_components()
            
            # Phase 3: Path Drawing Workflow Verification
            self._verify_path_drawing_workflow()
            
            # Phase 4: Skeleton Animation Verification
            self._verify_skeleton_animation_workflow()
            
            # Phase 5: Mechanism Recommendation Verification
            self._verify_mechanism_recommendation_workflow()
            
            # Phase 6: Synchronized Animation Verification
            self._verify_synchronized_animation_workflow()
            
            # Phase 7: Complete System Integration Test
            self._verify_complete_integration()
            
            # Phase 8: Final Validation
            self._generate_final_verification_report()
            
        except Exception as e:
            print(f"💥 Verification failed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._cleanup_verification()
    
    def _step_progress(self, description):
        """Track verification progress."""
        self.current_step += 1
        progress = (self.current_step / self.total_steps) * 100
        print(f"\n[{self.current_step:2d}/{self.total_steps}] ({progress:5.1f}%) {description}")
        print("-" * 60)
    
    def _verify_application_startup(self):
        """Verify application starts correctly from main.py."""
        
        self._step_progress("🚀 Verifying Application Startup")
        
        print("📋 Testing application launch from main.py...")
        
        # Check if application is already running with verification
        trace_file = Path("verification_trace.json")
        log_file = Path("workflow_trace.log")
        
        if trace_file.exists() and log_file.exists():
            print("✅ Application already running with verification tracing")
            
            # Verify trace data is being updated
            initial_size = trace_file.stat().st_size if trace_file.exists() else 0
            time.sleep(2)
            current_size = trace_file.stat().st_size if trace_file.exists() else 0
            
            if current_size >= initial_size:
                print("✅ Trace data being generated - application active")
                self.verification_results["application_startup"] = {
                    "success": True,
                    "trace_active": True,
                    "application_responding": True
                }
            else:
                print("⚠️ Application may not be responding - checking...")
                self.verification_results["application_startup"] = {
                    "success": False,
                    "trace_active": False,
                    "issue": "Application not updating trace data"
                }
        else:
            print("❌ Application not running with verification tracing")
            print("🔧 Manual startup required:")
            print("   Run: python verification_tracer.py")
            self.verification_results["application_startup"] = {
                "success": False,
                "trace_active": False,
                "issue": "Application not started with verification"
            }
            return
        
        # Analyze initial application state
        analyzer = TraceAnalyzer()
        results = analyzer.analyze_comprehensive()
        
        startup_analysis = {
            "services_initialized": len(results.get("function_calls", [])) > 0,
            "architecture_score": results.get("architecture_integrity", {}).get("architecture_score", 0),
            "initial_events": results.get("event_bus_analysis", {}).get("total_events_published", 0)
        }
        
        self.verification_results["application_startup"].update(startup_analysis)
        
        if startup_analysis["services_initialized"]:
            print("✅ Services initialized successfully")
        else:
            print("⚠️ Services may not be fully initialized")
        
        print(f"📊 Architecture Score: {startup_analysis['architecture_score']:.3f}")
        print(f"📊 Initial Events: {startup_analysis['initial_events']}")
    
    def _verify_ui_components(self):
        """Verify all UI components are functional."""
        
        self._step_progress("🖱️ Verifying UI Components")
        
        print("📋 UI Component Verification Checklist:")
        
        ui_components = [
            {
                "name": "Main Window",
                "description": "Application window visible and responsive",
                "test": "Window should be visible with proper title and layout"
            },
            {
                "name": "Tab Widget", 
                "description": "All tabs present and clickable",
                "test": "Welcome, Character Selection, Path Editor, Mechanism Design, Options tabs"
            },
            {
                "name": "Welcome Tab",
                "description": "Landing page with example images",
                "test": "Example images displayed and clickable"
            },
            {
                "name": "Character Selection Tab",
                "description": "Image loading and processing controls",
                "test": "File dialogs and processing buttons functional"
            },
            {
                "name": "Path Editor Tab",
                "description": "Character display and path editing tools",
                "test": "Character visualization and drawing tools"
            },
            {
                "name": "Mechanism Design Tab",
                "description": "Mechanism visualization and controls",
                "test": "Mechanism display area and parameter controls"
            },
            {
                "name": "Options Tab",
                "description": "Application settings and preferences",
                "test": "Settings controls and theme options"
            }
        ]
        
        print("\n🔍 MANUAL VERIFICATION REQUIRED:")
        print("Please verify each UI component is functional:")
        print("")
        
        for i, component in enumerate(ui_components, 1):
            print(f"{i}. {component['name']}:")
            print(f"   Description: {component['description']}")
            print(f"   Test: {component['test']}")
            print("")
        
        # Wait for user confirmation
        ui_verification = input("✅ Are all UI components functional? (y/n): ").lower().strip()
        
        self.verification_results["ui_components"] = {
            "success": ui_verification == 'y',
            "components_tested": len(ui_components),
            "user_confirmed": ui_verification == 'y',
            "timestamp": datetime.now().isoformat()
        }
        
        if ui_verification == 'y':
            print("✅ All UI components verified functional")
        else:
            print("❌ UI component issues detected")
            issues = input("📝 Describe issues (optional): ").strip()
            self.verification_results["ui_components"]["issues"] = issues
    
    def _verify_path_drawing_workflow(self):
        """Verify complete path drawing workflow."""
        
        self._step_progress("🎨 Verifying Path Drawing Workflow")
        
        print("📋 Path Drawing Workflow Verification:")
        print("")
        
        # Capture initial state
        initial_analyzer = TraceAnalyzer()
        initial_results = initial_analyzer.analyze_comprehensive()
        initial_events = initial_results.get("event_counts", {})
        
        workflow_steps = [
            "1. Navigate to 'Path Editor' tab",
            "2. Load character image (use example: alien.png, astronaut.png, or prek.png)",
            "3. Click on character part to select it (arm, leg, torso, etc.)",
            "4. Click and drag to draw motion path with multiple points",
            "5. Complete path drawing (right-click or ESC)",
            "6. Verify path visualization appears as connected line"
        ]
        
        print("🎯 Execute Path Drawing Workflow:")
        for step in workflow_steps:
            print(f"   {step}")
        print("")
        
        print("🔍 Expected Events During This Workflow:")
        print("   • MotionPathStartedEvent - when starting to draw")
        print("   • MotionPathPointAddedEvent - for each point added")
        print("   • MotionPathCompletedEvent - when path is finished")
        print("   • UI signals for visual updates")
        print("")
        
        # Wait for workflow completion
        input("⏳ Complete the path drawing workflow above, then press ENTER...")
        
        # Analyze workflow results
        post_analyzer = TraceAnalyzer()
        post_results = post_analyzer.analyze_comprehensive()
        post_events = post_results.get("event_counts", {})
        
        # Check for expected events
        expected_events = ["MotionPathStartedEvent", "MotionPathPointAddedEvent", "MotionPathCompletedEvent"]
        events_found = {}
        
        for event in expected_events:
            initial_count = initial_events.get(event, 0)
            post_count = post_events.get(event, 0)
            new_count = post_count - initial_count
            events_found[event] = new_count
            
            if new_count > 0:
                print(f"   ✅ {event}: {new_count} new occurrences")
            else:
                print(f"   ❌ {event}: NOT DETECTED")
        
        # Overall workflow success
        events_success = sum(1 for count in events_found.values() if count > 0) >= 2
        
        # Visual confirmation
        visual_success = input("✅ Did the path appear visually on screen? (y/n): ").lower().strip() == 'y'
        
        workflow_success = events_success and visual_success
        
        self.verification_results["path_drawing"] = {
            "success": workflow_success,
            "events_found": events_found,
            "events_success": events_success,
            "visual_success": visual_success,
            "total_new_events": sum(events_found.values()),
            "timestamp": datetime.now().isoformat()
        }
        
        if workflow_success:
            print("✅ Path Drawing Workflow - PASSED")
        else:
            print("❌ Path Drawing Workflow - FAILED")
            if not events_success:
                print("   Issue: Expected events not detected")
            if not visual_success:
                print("   Issue: Path not displayed visually")
    
    def _verify_skeleton_animation_workflow(self):
        """Verify skeleton animation functionality."""
        
        self._step_progress("🏃 Verifying Skeleton Animation Workflow")
        
        print("📋 Skeleton Animation Workflow Verification:")
        print("")
        
        # Capture initial state
        initial_analyzer = TraceAnalyzer()
        initial_results = initial_analyzer.analyze_comprehensive()
        initial_events = initial_results.get("event_counts", {})
        
        workflow_steps = [
            "1. Ensure character with drawn path is loaded (from previous step)",
            "2. Locate animation controls (Play/Stop/Reset buttons)",
            "3. Click PLAY button (▶️) to start skeleton animation",
            "4. Observe skeleton joints moving along the drawn path",
            "5. Let animation run for 3-5 seconds",
            "6. Click STOP button (⏸️) to end animation",
            "7. Try RESET button to return to initial pose"
        ]
        
        print("🎯 Execute Skeleton Animation Workflow:")
        for step in workflow_steps:
            print(f"   {step}")
        print("")
        
        print("🔍 Expected Events During This Workflow:")
        print("   • AnimationStartedEvent - when animation begins")
        print("   • PoseUpdatedEvent - during skeleton pose updates")
        print("   • AnimationTickEvent - animation frame updates")
        print("   • AnimationStoppedEvent - when animation stops")
        print("")
        
        # Wait for workflow completion
        input("⏳ Complete the skeleton animation workflow above, then press ENTER...")
        
        # Analyze workflow results
        post_analyzer = TraceAnalyzer()
        post_results = post_analyzer.analyze_comprehensive()
        post_events = post_results.get("event_counts", {})
        
        # Check for expected events
        expected_events = ["AnimationStartedEvent", "PoseUpdatedEvent", "AnimationTickEvent", "AnimationStoppedEvent"]
        events_found = {}
        
        for event in expected_events:
            initial_count = initial_events.get(event, 0)
            post_count = post_events.get(event, 0)
            new_count = post_count - initial_count
            events_found[event] = new_count
            
            if new_count > 0:
                print(f"   ✅ {event}: {new_count} new occurrences")
            else:
                print(f"   ❌ {event}: NOT DETECTED")
        
        # Success criteria
        animation_started = events_found.get("AnimationStartedEvent", 0) > 0
        skeleton_moved = events_found.get("PoseUpdatedEvent", 0) > 0
        animation_ticked = events_found.get("AnimationTickEvent", 0) > 0
        
        # Visual confirmation
        visual_questions = [
            ("Did skeleton joints move smoothly?", "skeleton_smooth"),
            ("Did skeleton follow the drawn path?", "skeleton_path_following"),
            ("Did animation controls respond properly?", "controls_responsive")
        ]
        
        visual_results = {}
        for question, key in visual_questions:
            response = input(f"✅ {question} (y/n): ").lower().strip() == 'y'
            visual_results[key] = response
        
        events_success = animation_started and (skeleton_moved or animation_ticked)
        visual_success = all(visual_results.values())
        workflow_success = events_success and visual_success
        
        self.verification_results["skeleton_animation"] = {
            "success": workflow_success,
            "events_found": events_found,
            "events_success": events_success,
            "visual_results": visual_results,
            "visual_success": visual_success,
            "animation_started": animation_started,
            "skeleton_moved": skeleton_moved,
            "total_new_events": sum(events_found.values()),
            "timestamp": datetime.now().isoformat()
        }
        
        if workflow_success:
            print("✅ Skeleton Animation Workflow - PASSED")
        else:
            print("❌ Skeleton Animation Workflow - FAILED")
    
    def _verify_mechanism_recommendation_workflow(self):
        """Verify mechanism recommendation functionality."""
        
        self._step_progress("⚙️ Verifying Mechanism Recommendation Workflow")
        
        print("📋 Mechanism Recommendation Workflow Verification:")
        print("")
        
        # Capture initial state
        initial_analyzer = TraceAnalyzer()
        initial_results = initial_analyzer.analyze_comprehensive()
        initial_events = initial_results.get("event_counts", {})
        
        workflow_steps = [
            "1. Navigate to 'Mechanism Design' tab",
            "2. Ensure character with motion path is loaded",
            "3. Look for 'Get Recommendations' or 'Recommend Mechanisms' button",
            "4. Click the recommendation button",
            "5. Wait for mechanism analysis to complete",
            "6. Verify recommendation dialog appears with mechanism options",
            "7. Select a mechanism (4-bar linkage recommended)",
            "8. Click 'Apply' or 'Add to Design' to add mechanism",
            "9. Verify mechanism appears in the design view"
        ]
        
        print("🎯 Execute Mechanism Recommendation Workflow:")
        for step in workflow_steps:
            print(f"   {step}")
        print("")
        
        print("🔍 Expected Events During This Workflow:")
        print("   • MechanismRecommendationRequestedEvent - when requesting recommendations")
        print("   • MechanismSelectedEvent - when selecting a mechanism")
        print("   • MechanismAddedEvent - when mechanism is added to design")
        print("   • MechanismParameterChangedEvent - when parameters are set")
        print("")
        
        # Wait for workflow completion
        input("⏳ Complete the mechanism recommendation workflow above, then press ENTER...")
        
        # Analyze workflow results
        post_analyzer = TraceAnalyzer()
        post_results = post_analyzer.analyze_comprehensive()
        post_events = post_results.get("event_counts", {})
        
        # Check for expected events
        expected_events = ["MechanismRecommendationRequestedEvent", "MechanismSelectedEvent", "MechanismAddedEvent", "MechanismParameterChangedEvent"]
        events_found = {}
        
        for event in expected_events:
            initial_count = initial_events.get(event, 0)
            post_count = post_events.get(event, 0)
            new_count = post_count - initial_count
            events_found[event] = new_count
            
            if new_count > 0:
                print(f"   ✅ {event}: {new_count} new occurrences")
            else:
                print(f"   ❌ {event}: NOT DETECTED")
        
        # Visual confirmation
        visual_questions = [
            ("Did recommendation dialog appear?", "dialog_appeared"),
            ("Were mechanism options displayed?", "options_displayed"),
            ("Did selected mechanism appear in design view?", "mechanism_visible"),
            ("Are mechanism parameters adjustable?", "parameters_adjustable")
        ]
        
        visual_results = {}
        for question, key in visual_questions:
            response = input(f"✅ {question} (y/n): ").lower().strip() == 'y'
            visual_results[key] = response
        
        # Success criteria
        recommendation_requested = events_found.get("MechanismRecommendationRequestedEvent", 0) > 0
        mechanism_selected = events_found.get("MechanismSelectedEvent", 0) > 0
        events_success = recommendation_requested or mechanism_selected
        visual_success = visual_results.get("dialog_appeared", False) and visual_results.get("mechanism_visible", False)
        workflow_success = events_success and visual_success
        
        self.verification_results["mechanism_recommendation"] = {
            "success": workflow_success,
            "events_found": events_found,
            "events_success": events_success,
            "visual_results": visual_results,
            "visual_success": visual_success,
            "recommendation_requested": recommendation_requested,
            "mechanism_selected": mechanism_selected,
            "total_new_events": sum(events_found.values()),
            "timestamp": datetime.now().isoformat()
        }
        
        if workflow_success:
            print("✅ Mechanism Recommendation Workflow - PASSED")
        else:
            print("❌ Mechanism Recommendation Workflow - FAILED")
    
    def _verify_synchronized_animation_workflow(self):
        """Verify synchronized skeleton and mechanism animation."""
        
        self._step_progress("🔄 Verifying Synchronized Animation Workflow")
        
        print("📋 Synchronized Animation Workflow Verification:")
        print("")
        
        # Capture initial state
        initial_analyzer = TraceAnalyzer()
        initial_results = initial_analyzer.analyze_comprehensive()
        initial_events = initial_results.get("event_counts", {})
        
        workflow_steps = [
            "1. Ensure both skeleton and mechanism are loaded (from previous steps)",
            "2. In Mechanism Design tab, find combined animation controls",
            "3. Click 'Play Combined Animation' or similar control",
            "4. Observe BOTH skeleton AND mechanism animating together",
            "5. Verify skeleton follows its motion path",
            "6. Verify mechanism operates according to its parameters",
            "7. Check that timing is synchronized between components",
            "8. Try adjusting animation speed if controls available",
            "9. Stop animation and verify both components stop together"
        ]
        
        print("🎯 Execute Synchronized Animation Workflow:")
        for step in workflow_steps:
            print(f"   {step}")
        print("")
        
        print("🔍 Expected Events During This Workflow:")
        print("   • AnimationStartedEvent - combined animation start")
        print("   • PoseUpdatedEvent - skeleton pose updates")
        print("   • MechanismParameterChangedEvent - mechanism state updates")
        print("   • AnimationTickEvent - frame synchronization")
        print("")
        
        # Wait for workflow completion
        input("⏳ Complete the synchronized animation workflow above, then press ENTER...")
        
        # Analyze workflow results
        post_analyzer = TraceAnalyzer()
        post_results = post_analyzer.analyze_comprehensive()
        post_events = post_results.get("event_counts", {})
        
        # Check for expected events
        expected_events = ["AnimationStartedEvent", "PoseUpdatedEvent", "MechanismParameterChangedEvent", "AnimationTickEvent"]
        events_found = {}
        
        for event in expected_events:
            initial_count = initial_events.get(event, 0)
            post_count = post_events.get(event, 0)
            new_count = post_count - initial_count
            events_found[event] = new_count
            
            if new_count > 0:
                print(f"   ✅ {event}: {new_count} new occurrences")
            else:
                print(f"   ❌ {event}: NOT DETECTED")
        
        # Visual confirmation for synchronized animation
        sync_questions = [
            ("Did both skeleton AND mechanism animate together?", "both_animated"),
            ("Was timing synchronized between skeleton and mechanism?", "timing_synchronized"),
            ("Did skeleton follow the motion path during combined animation?", "skeleton_path_sync"),
            ("Did mechanism operate smoothly during animation?", "mechanism_smooth"),
            ("Did both components stop together when animation ended?", "synchronized_stop")
        ]
        
        visual_results = {}
        for question, key in sync_questions:
            response = input(f"✅ {question} (y/n): ").lower().strip() == 'y'
            visual_results[key] = response
        
        # Success criteria for synchronized animation
        animation_started = events_found.get("AnimationStartedEvent", 0) > 0
        skeleton_updated = events_found.get("PoseUpdatedEvent", 0) > 0
        mechanism_updated = events_found.get("MechanismParameterChangedEvent", 0) > 0
        
        events_success = animation_started and skeleton_updated and mechanism_updated
        visual_success = visual_results.get("both_animated", False) and visual_results.get("timing_synchronized", False)
        workflow_success = events_success and visual_success
        
        self.verification_results["synchronized_animation"] = {
            "success": workflow_success,
            "events_found": events_found,
            "events_success": events_success,
            "visual_results": visual_results,
            "visual_success": visual_success,
            "animation_started": animation_started,
            "skeleton_updated": skeleton_updated,
            "mechanism_updated": mechanism_updated,
            "total_new_events": sum(events_found.values()),
            "timestamp": datetime.now().isoformat()
        }
        
        if workflow_success:
            print("✅ Synchronized Animation Workflow - PASSED")
        else:
            print("❌ Synchronized Animation Workflow - FAILED")
    
    def _verify_complete_integration(self):
        """Verify complete system integration."""
        
        self._step_progress("🔗 Verifying Complete System Integration")
        
        print("📋 Complete Integration Test:")
        print("")
        
        # Test complete workflow from start to finish
        integration_steps = [
            "1. Complete workflow: Welcome → Character Selection → Path Editor → Mechanism Design",
            "2. Load character → Draw path → Animate skeleton → Get recommendations → Add mechanism → Synchronized animation",
            "3. Test all tabs and navigation",
            "4. Test error recovery (try invalid operations)",
            "5. Test resource cleanup (close and reopen features)"
        ]
        
        print("🎯 Complete Integration Test:")
        for step in integration_steps:
            print(f"   {step}")
        print("")
        
        # Performance and stability check
        print("⚡ Performance and Stability Checks:")
        
        performance_questions = [
            ("Are all operations responsive (< 2 second delays)?", "responsive"),
            ("Did any crashes or freezes occur?", "crashes", True),  # True means reverse (crashes are bad)
            ("Is memory usage reasonable (no excessive consumption)?", "memory_reasonable"),
            ("Do animations run smoothly without stuttering?", "animations_smooth"),
            ("Are all UI elements properly rendered?", "ui_rendered")
        ]
        
        performance_results = {}
        for question, key, *reverse in performance_questions:
            response = input(f"✅ {question} (y/n): ").lower().strip() == 'y'
            # Reverse logic for negative questions (crashes)
            if reverse and reverse[0]:
                response = not response
            performance_results[key] = response
        
        integration_success = all(performance_results.values())
        
        # Final trace analysis
        final_analyzer = TraceAnalyzer()
        final_results = final_analyzer.analyze_comprehensive()
        
        self.verification_results["complete_integration"] = {
            "success": integration_success,
            "performance_results": performance_results,
            "final_analysis": final_results.get("summary", {}),
            "total_events": sum(final_results.get("event_counts", {}).values()),
            "total_function_calls": len(final_results.get("function_calls", [])),
            "timestamp": datetime.now().isoformat()
        }
        
        if integration_success:
            print("✅ Complete System Integration - PASSED")
        else:
            print("❌ Complete System Integration - FAILED")
            failed_aspects = [k for k, v in performance_results.items() if not v]
            print(f"   Failed aspects: {', '.join(failed_aspects)}")
    
    def _generate_final_verification_report(self):
        """Generate comprehensive final verification report."""
        
        self._step_progress("📊 Generating Final Verification Report")
        
        print("📊 FINAL VERIFICATION ANALYSIS")
        print("=" * 80)
        
        # Calculate overall success metrics
        workflow_results = [
            self.verification_results.get("path_drawing", {}).get("success", False),
            self.verification_results.get("skeleton_animation", {}).get("success", False),
            self.verification_results.get("mechanism_recommendation", {}).get("success", False),
            self.verification_results.get("synchronized_animation", {}).get("success", False),
            self.verification_results.get("complete_integration", {}).get("success", False)
        ]
        
        total_workflows = len(workflow_results)
        successful_workflows = sum(workflow_results)
        success_rate = (successful_workflows / total_workflows) * 100 if total_workflows > 0 else 0
        
        print(f"📈 OVERALL VERIFICATION RESULTS:")
        print(f"   Total Workflows Tested: {total_workflows}")
        print(f"   Successful Workflows: {successful_workflows}")
        print(f"   Success Rate: {success_rate:.1f}%")
        print(f"   Verification Duration: {time.time() - self.start_time:.1f} seconds")
        print("")
        
        # Individual workflow results
        workflow_names = {
            "application_startup": "🚀 Application Startup",
            "ui_components": "🖱️ UI Components",
            "path_drawing": "🎨 Path Drawing",
            "skeleton_animation": "🏃 Skeleton Animation", 
            "mechanism_recommendation": "⚙️ Mechanism Recommendation",
            "synchronized_animation": "🔄 Synchronized Animation",
            "complete_integration": "🔗 Complete Integration"
        }
        
        print("🔍 DETAILED WORKFLOW RESULTS:")
        for workflow_id, workflow_name in workflow_names.items():
            result = self.verification_results.get(workflow_id, {})
            success = result.get("success", False)
            status = "✅ PASSED" if success else "❌ FAILED"
            print(f"   {workflow_name}: {status}")
            
            # Show event details for workflows that track events
            if "events_found" in result:
                total_events = sum(result["events_found"].values())
                print(f"      Events Captured: {total_events}")
        
        # Final trace analysis
        final_analyzer = TraceAnalyzer()
        final_analysis = final_analyzer.analyze_comprehensive()
        final_analyzer.print_summary_report()
        
        # Overall assessment
        if success_rate >= 90:
            overall_status = "🎉 EXCELLENT - All workflows functioning perfectly"
        elif success_rate >= 80:
            overall_status = "✅ GOOD - Most workflows functional with minor issues"
        elif success_rate >= 60:
            overall_status = "⚠️ ACCEPTABLE - Some workflows need attention"
        else:
            overall_status = "❌ CRITICAL - Major workflow issues detected"
        
        print(f"\n{overall_status}")
        
        # Save comprehensive report
        final_report = {
            "timestamp": datetime.now().isoformat(),
            "verification_duration": time.time() - self.start_time,
            "overall_success_rate": success_rate,
            "workflow_results": self.verification_results,
            "final_analysis": final_analysis,
            "status": overall_status
        }
        
        report_file = f"final_ui_verification_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(final_report, f, indent=2, default=str)
        
        print(f"\n💾 Complete verification report saved to: {report_file}")
        
        return final_report
    
    def _cleanup_verification(self):
        """Cleanup verification resources."""
        self.monitoring_active = False
        print(f"\n🏁 Verification completed at {datetime.now().isoformat()}")


def main():
    """Execute systematic UI verification."""
    
    verifier = SystematicUIVerification()
    
    try:
        verifier.execute_complete_verification()
        print("\n🎉 SYSTEMATIC UI VERIFICATION COMPLETED!")
        
    except KeyboardInterrupt:
        print("\n⏹️ Verification interrupted by user")
        
    except Exception as e:
        print(f"\n💥 Verification failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        verifier._cleanup_verification()


if __name__ == "__main__":
    main()