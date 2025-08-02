#!/usr/bin/env python3
"""
ULTRATHINK Interactive Verification Guide
Provides step-by-step guidance for comprehensive workflow verification with real-time monitoring.
"""

import time
import json
import sys
from pathlib import Path
from datetime import datetime
from trace_analyzer import TraceAnalyzer

class InteractiveVerificationGuide:
    """
    Interactive guide for comprehensive verification of all Automataii workflows.
    
    Provides real-time monitoring and step-by-step instructions for:
    1. Path Drawing Workflow
    2. Skeleton Animation Workflow  
    3. Mechanism Recommendation Workflow
    4. Synchronized Animation Workflow
    """
    
    def __init__(self):
        self.analyzer = TraceAnalyzer()
        self.start_time = time.time()
        self.workflow_results = {}
        
        print("🧠 ULTRATHINK Interactive Verification Guide")
        print("=" * 60)
        print("📋 Comprehensive end-to-end verification of Automataii workflows")
        print("🔍 Real-time monitoring and analysis enabled")
        print("")
    
    def run_comprehensive_verification(self):
        """Execute comprehensive verification of all workflows."""
        
        print("🚀 Starting comprehensive ULTRATHINK verification...")
        print("")
        
        # Initial status check
        self._display_current_status()
        
        # Workflow verification sequence
        workflows = [
            ("path_drawing", "🎨 Path Drawing Workflow", self._verify_path_drawing),
            ("skeleton_animation", "🏃 Skeleton Animation Workflow", self._verify_skeleton_animation),
            ("mechanism_recommendation", "⚙️ Mechanism Recommendation Workflow", self._verify_mechanism_recommendation),
            ("synchronized_animation", "🔄 Synchronized Animation Workflow", self._verify_synchronized_animation)
        ]
        
        for workflow_id, workflow_name, verify_func in workflows:
            print(f"\n{'='*60}")
            print(f"{workflow_name}")
            print("=" * 60)
            
            try:
                result = verify_func()
                self.workflow_results[workflow_id] = result
                
                if result["success"]:
                    print(f"✅ {workflow_name} - PASSED")
                else:
                    print(f"❌ {workflow_name} - FAILED")
                    print(f"   Issues: {', '.join(result.get('issues', []))}")
                
            except KeyboardInterrupt:
                print(f"\n⏹️ Verification interrupted during {workflow_name}")
                break
            except Exception as e:
                print(f"💥 Error during {workflow_name}: {e}")
                self.workflow_results[workflow_id] = {"success": False, "error": str(e)}
        
        # Final analysis
        self._generate_final_report()
    
    def _display_current_status(self):
        """Display current application and trace status."""
        
        print("📊 Current Application Status:")
        
        # Analyze current trace
        self.analyzer.analyze_comprehensive()
        results = self.analyzer.analysis_results
        
        if results:
            summary = results["summary"]
            print(f"   Overall Score: {summary['overall_score']:.3f}")
            print(f"   Status: {summary['status']}")
            print(f"   Events Published: {results['event_bus_analysis']['total_events_published']}")
            print(f"   Function Calls: {len(self.analyzer.trace_data.get('function_calls', []))}")
        else:
            print("   No trace data available yet")
        
        print("")
        input("🔥 Press ENTER when the Automataii application window is visible and ready...")
        print("")
    
    def _verify_path_drawing(self):
        """Verify path drawing workflow."""
        
        print("🎨 Testing Path Drawing Workflow")
        print("=" * 40)
        
        instructions = [
            "1. Navigate to the 'Path Editor' tab",
            "2. Load a character image (use one of the example images if needed)",
            "3. Click on a character part (like an arm or leg) to select it",
            "4. Draw a motion path by clicking and dragging to create multiple points",
            "5. Complete the path by right-clicking or pressing ESC",
            "6. Verify the path appears as a line connecting the points"
        ]
        
        print("📋 Step-by-step instructions:")
        for instruction in instructions:
            print(f"   {instruction}")
        
        print("\n🔍 Expected Events to Monitor:")
        print("   • MotionPathStartedEvent - when you start drawing")
        print("   • MotionPathPointAddedEvent - for each point added")
        print("   • MotionPathCompletedEvent - when path is finished")
        print("")
        
        # Wait for user to complete workflow
        input("⏳ Complete the path drawing workflow, then press ENTER to analyze...")
        
        # Analyze results
        return self._analyze_workflow_execution(
            "path_drawing",
            expected_events=["MotionPathStartedEvent", "MotionPathPointAddedEvent", "MotionPathCompletedEvent"],
            expected_signals=["motion_path_updated"],
            min_events=3
        )
    
    def _verify_skeleton_animation(self):
        """Verify skeleton animation workflow."""
        
        print("🏃 Testing Skeleton Animation Workflow")
        print("=" * 40)
        
        instructions = [
            "1. Ensure a character with skeleton is loaded (from previous step)",
            "2. Navigate to 'Path Editor' tab if not already there",
            "3. Click the 'Play Animation' button (▶️) in the animation controls",
            "4. Observe the skeleton animating according to the drawn path",
            "5. You should see smooth movement of skeleton joints",
            "6. Click 'Stop' button (⏸️) to end animation",
            "7. Try 'Reset' button to return to initial pose"
        ]
        
        print("📋 Step-by-step instructions:")
        for instruction in instructions:
            print(f"   {instruction}")
        
        print("\n🔍 Expected Events to Monitor:")
        print("   • AnimationStartedEvent - when animation begins")
        print("   • PoseUpdatedEvent - during skeleton updates")
        print("   • AnimationTickEvent - animation frame updates")
        print("   • AnimationStoppedEvent - when animation stops")
        print("")
        
        input("⏳ Complete the skeleton animation workflow, then press ENTER to analyze...")
        
        return self._analyze_workflow_execution(
            "skeleton_animation",
            expected_events=["AnimationStartedEvent", "PoseUpdatedEvent", "AnimationTickEvent"],
            expected_signals=["pose_updated", "animation_state_changed"],
            min_events=5  # Should have multiple animation ticks
        )
    
    def _verify_mechanism_recommendation(self):
        """Verify mechanism recommendation workflow."""
        
        print("⚙️ Testing Mechanism Recommendation Workflow")
        print("=" * 40)
        
        instructions = [
            "1. Navigate to the 'Mechanism Design' tab",
            "2. Ensure you have a character with a drawn motion path",
            "3. Click 'Get Recommendations' or similar button for mechanism suggestions",
            "4. Wait for the system to analyze the motion path",
            "5. A dialog should appear with mechanism recommendations",
            "6. Select one of the recommended mechanisms (e.g., 4-bar linkage)",
            "7. Click 'Apply' or 'Add to Design'",
            "8. Verify the mechanism appears in the design view",
            "9. Try adjusting mechanism parameters using handles or sliders"
        ]
        
        print("📋 Step-by-step instructions:")
        for instruction in instructions:
            print(f"   {instruction}")
        
        print("\n🔍 Expected Events to Monitor:")
        print("   • MechanismRecommendationRequestedEvent - when requesting recommendations")
        print("   • MechanismSelectedEvent - when selecting a mechanism")
        print("   • MechanismAddedEvent - when mechanism is added to design")
        print("   • MechanismParameterChangedEvent - when adjusting parameters")
        print("")
        
        input("⏳ Complete the mechanism recommendation workflow, then press ENTER to analyze...")
        
        return self._analyze_workflow_execution(
            "mechanism_recommendation",
            expected_events=["MechanismRecommendationRequestedEvent", "MechanismSelectedEvent", "MechanismAddedEvent"],
            expected_signals=["mechanism_data_updated"],
            min_events=3
        )
    
    def _verify_synchronized_animation(self):
        """Verify synchronized skeleton + mechanism animation."""
        
        print("🔄 Testing Synchronized Animation Workflow")
        print("=" * 40)
        
        instructions = [
            "1. Ensure you have both a skeleton and mechanism from previous steps",
            "2. In the 'Mechanism Design' tab, look for animation controls",
            "3. Click 'Play Combined Animation' or similar control",
            "4. Observe BOTH the skeleton AND mechanism animating together",
            "5. Verify the skeleton follows its motion path",
            "6. Verify the mechanism operates according to its parameters",
            "7. Check that timing is synchronized between skeleton and mechanism",
            "8. Try adjusting animation speed if controls are available",
            "9. Stop and restart animation to test controls"
        ]
        
        print("📋 Step-by-step instructions:")
        for instruction in instructions:
            print(f"   {instruction}")
        
        print("\n🔍 Expected Events to Monitor:")
        print("   • AnimationStartedEvent - animation start")
        print("   • PoseUpdatedEvent - skeleton pose updates") 
        print("   • MechanismParameterChangedEvent - mechanism state updates")
        print("   • AnimationTickEvent - frame synchronization")
        print("")
        
        input("⏳ Complete the synchronized animation workflow, then press ENTER to analyze...")
        
        return self._analyze_workflow_execution(
            "synchronized_animation",
            expected_events=["AnimationStartedEvent", "PoseUpdatedEvent", "MechanismParameterChangedEvent"],
            expected_signals=["pose_updated", "mechanism_data_updated"],
            min_events=6  # Should have multiple coordinated updates
        )
    
    def _analyze_workflow_execution(self, workflow_name, expected_events, expected_signals, min_events=1):
        """Analyze workflow execution results."""
        
        print(f"\n🔍 Analyzing {workflow_name} execution...")
        
        # Get fresh analysis
        self.analyzer = TraceAnalyzer()  # Reload trace data
        self.analyzer.analyze_comprehensive()
        results = self.analyzer.analysis_results
        
        # Extract workflow-specific data
        workflow_data = results.get("workflow_analysis", {}).get(workflow_name, {})
        event_counts = results.get("event_counts", {})
        
        analysis = {
            "success": False,
            "events_found": {},
            "signals_found": [],
            "total_events": sum(event_counts.values()),
            "issues": [],
            "recommendations": []
        }
        
        # Check expected events
        events_found = 0
        for event in expected_events:
            count = event_counts.get(event, 0)
            analysis["events_found"][event] = count
            if count > 0:
                events_found += 1
                print(f"   ✅ {event}: {count} occurrences")
            else:
                print(f"   ❌ {event}: NOT FOUND")
                analysis["issues"].append(f"Missing event: {event}")
        
        # Check signals
        all_signals = [s["signal"] for s in self.analyzer.trace_data.get("signal_emissions", [])]
        for signal in expected_signals:
            if signal in all_signals:
                print(f"   ✅ Signal {signal}: FOUND")
                analysis["signals_found"].append(signal)
            else:
                print(f"   ❌ Signal {signal}: NOT FOUND")
                analysis["issues"].append(f"Missing signal: {signal}")
        
        # Overall success criteria
        events_success = events_found >= len(expected_events) * 0.7  # 70% of expected events
        signals_success = len(analysis["signals_found"]) >= len(expected_signals) * 0.5  # 50% of expected signals
        volume_success = analysis["total_events"] >= min_events
        
        analysis["success"] = events_success and signals_success and volume_success
        
        # Performance metrics
        if workflow_data:
            completeness = workflow_data.get("completeness_score", 0)
            print(f"   📊 Completeness Score: {completeness:.3f}")
            
            if completeness < 0.7:
                analysis["recommendations"].append(f"Improve workflow completeness (current: {completeness:.3f})")
        
        print(f"   📈 Events Found: {events_found}/{len(expected_events)}")
        print(f"   📈 Signals Found: {len(analysis['signals_found'])}/{len(expected_signals)}")
        print(f"   📈 Total Events: {analysis['total_events']}")
        
        return analysis
    
    def _generate_final_report(self):
        """Generate comprehensive final verification report."""
        
        print("\n" + "="*80)
        print("🧠 ULTRATHINK FINAL VERIFICATION REPORT")
        print("="*80)
        
        # Overall statistics
        total_workflows = len(self.workflow_results)
        successful_workflows = sum(1 for r in self.workflow_results.values() if r.get("success", False))
        
        print(f"\n📊 VERIFICATION SUMMARY:")
        print(f"   Total Workflows Tested: {total_workflows}")
        print(f"   Successful Workflows: {successful_workflows}")
        print(f"   Success Rate: {successful_workflows/total_workflows*100:.1f}%" if total_workflows > 0 else "N/A")
        print(f"   Total Verification Time: {time.time() - self.start_time:.1f} seconds")
        
        # Individual workflow results
        print(f"\n🔍 WORKFLOW RESULTS:")
        for workflow_id, result in self.workflow_results.items():
            status = "✅ PASSED" if result.get("success", False) else "❌ FAILED"
            print(f"   {workflow_id}: {status}")
            
            if not result.get("success", False):
                issues = result.get("issues", [])
                for issue in issues[:3]:  # Show top 3 issues
                    print(f"      • {issue}")
        
        # Final trace analysis
        print(f"\n📈 FINAL TRACE ANALYSIS:")
        self.analyzer.analyze_comprehensive()
        final_results = self.analyzer.analysis_results
        
        if final_results:
            summary = final_results["summary"]
            print(f"   Overall Score: {summary['overall_score']:.3f}")
            print(f"   Status: {summary['status']}")
            print(f"   Events Published: {final_results['event_bus_analysis']['total_events_published']}")
            print(f"   Function Calls: {len(self.analyzer.trace_data.get('function_calls', []))}")
            print(f"   Signal Emissions: {len(self.analyzer.trace_data.get('signal_emissions', []))}")
        
        # Recommendations
        if final_results and final_results.get("recommendations"):
            print(f"\n💡 RECOMMENDATIONS:")
            for rec in final_results["recommendations"]:
                print(f"   • {rec}")
        
        # Overall assessment
        if successful_workflows >= total_workflows * 0.8:
            print(f"\n🎉 VERIFICATION SUCCESSFUL!")
            print(f"   The Automataii application demonstrates excellent workflow integrity.")
        elif successful_workflows >= total_workflows * 0.6:
            print(f"\n✅ VERIFICATION MOSTLY SUCCESSFUL!")
            print(f"   Most workflows are functional with some areas for improvement.")
        else:
            print(f"\n⚠️ VERIFICATION NEEDS ATTENTION!")
            print(f"   Several workflows require fixes before production readiness.")
        
        # Save final report
        report_file = f"final_verification_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "verification_duration": time.time() - self.start_time,
            "workflow_results": self.workflow_results,
            "final_analysis": final_results,
            "summary": {
                "total_workflows": total_workflows,
                "successful_workflows": successful_workflows,
                "success_rate": successful_workflows/total_workflows if total_workflows > 0 else 0,
                "overall_score": final_results["summary"]["overall_score"] if final_results else 0
            }
        }
        
        with open(report_file, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)
        
        print(f"\n💾 Final report saved to: {report_file}")
        print("="*80)


def main():
    """Main verification execution."""
    
    guide = InteractiveVerificationGuide()
    
    try:
        guide.run_comprehensive_verification()
    except KeyboardInterrupt:
        print("\n⏹️ Verification interrupted by user")
    except Exception as e:
        print(f"\n💥 Verification failed: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n🏁 ULTRATHINK verification completed!")


if __name__ == "__main__":
    main()