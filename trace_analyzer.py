#!/usr/bin/env python3
"""
ULTRATHINK Trace Analyzer
Analyzes captured verification traces to validate workflow execution and architecture integrity.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Tuple

class TraceAnalyzer:
    """
    Comprehensive trace analyzer for Automataii verification.
    
    Analyzes captured traces to validate:
    - Workflow execution completeness
    - Event-driven architecture integrity  
    - Performance characteristics
    - Error conditions and handling
    """
    
    def __init__(self, trace_file: str = "verification_trace.json"):
        self.trace_file = Path(trace_file)
        self.trace_data = {}
        self.analysis_results = {}
        
        # Load trace data
        if self.trace_file.exists():
            with open(self.trace_file) as f:
                self.trace_data = json.load(f)
        
        print(f"🔍 TraceAnalyzer initialized with {self.trace_file}")
    
    def analyze_comprehensive(self) -> Dict[str, Any]:
        """Perform comprehensive analysis of all workflows and architecture."""
        
        print("🧠 ULTRATHINK: Starting comprehensive trace analysis...")
        
        # Core analysis components
        self.analysis_results = {
            "timestamp": datetime.now().isoformat(),
            "workflow_analysis": self._analyze_workflows(),
            "event_bus_analysis": self._analyze_event_bus(),
            "performance_analysis": self._analyze_performance(),
            "architecture_integrity": self._analyze_architecture_integrity(),
            "error_analysis": self._analyze_errors(),
            "coverage_analysis": self._analyze_coverage(),
            "recommendations": self._generate_recommendations()
        }
        
        # Generate summary
        self.analysis_results["summary"] = self._generate_summary()
        
        # Save analysis results
        output_file = f"verification_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w') as f:
            json.dump(self.analysis_results, f, indent=2, default=str)
        
        print(f"📊 Analysis complete - Results saved to {output_file}")
        return self.analysis_results
    
    def _analyze_workflows(self) -> Dict[str, Any]:
        """Analyze the execution of all critical workflows."""
        
        workflows = {
            "path_drawing": {
                "expected_events": ["MotionPathStartedEvent", "MotionPathPointAddedEvent", "MotionPathCompletedEvent"],
                "expected_signals": ["motion_path_updated"],
                "min_duration_ms": 100,
                "max_duration_ms": 10000
            },
            "skeleton_animation": {
                "expected_events": ["AnimationStartedEvent", "PoseUpdatedEvent", "AnimationTickEvent"],
                "expected_signals": ["pose_updated", "animation_state_changed"],
                "min_duration_ms": 50,
                "max_duration_ms": 5000
            },
            "mechanism_recommendation": {
                "expected_events": ["MechanismRecommendationRequestedEvent", "MechanismSelectedEvent", "MechanismAddedEvent"],
                "expected_signals": ["mechanism_data_updated"],
                "min_duration_ms": 200,
                "max_duration_ms": 15000
            },
            "synchronized_animation": {
                "expected_events": ["AnimationStartedEvent", "PoseUpdatedEvent", "MechanismParameterChangedEvent"],
                "expected_signals": ["pose_updated", "mechanism_data_updated"],
                "min_duration_ms": 100,
                "max_duration_ms": 8000
            }
        }
        
        analysis = {}
        for workflow_name, criteria in workflows.items():
            analysis[workflow_name] = self._analyze_single_workflow(workflow_name, criteria)
        
        return analysis
    
    def _analyze_single_workflow(self, workflow_name: str, criteria: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a single workflow against its criteria."""
        
        # Get workflow data from trace
        workflow_data = self.trace_data.get("summary", {}).get("workflow_states", {}).get(workflow_name, {})
        steps = workflow_data.get("steps", [])
        
        # Check events
        events_found = self.trace_data.get("event_counts", {})
        signals_found = [s["signal"] for s in self.trace_data.get("signal_emissions", [])]
        
        # Analyze execution
        result = {
            "executed": len(steps) > 0,
            "step_count": len(steps),
            "events_analysis": {},
            "signals_analysis": {},
            "timing_analysis": {},
            "completeness_score": 0.0,
            "issues": []
        }
        
        # Event analysis
        for expected_event in criteria["expected_events"]:
            found_count = events_found.get(expected_event, 0)
            result["events_analysis"][expected_event] = {
                "found": found_count > 0,
                "count": found_count
            }
            if found_count == 0:
                result["issues"].append(f"Missing expected event: {expected_event}")
        
        # Signal analysis
        for expected_signal in criteria["expected_signals"]:
            found = expected_signal in signals_found
            result["signals_analysis"][expected_signal] = {"found": found}
            if not found:
                result["issues"].append(f"Missing expected signal: {expected_signal}")
        
        # Timing analysis
        if steps:
            durations = []
            for i in range(1, len(steps)):
                duration = (steps[i]["timestamp"] - steps[i-1]["timestamp"]) * 1000  # ms
                durations.append(duration)
            
            if durations:
                result["timing_analysis"] = {
                    "min_duration_ms": min(durations),
                    "max_duration_ms": max(durations),
                    "avg_duration_ms": sum(durations) / len(durations),
                    "within_expected_range": all(
                        criteria["min_duration_ms"] <= d <= criteria["max_duration_ms"] 
                        for d in durations
                    )
                }
        
        # Calculate completeness score
        events_score = sum(1 for e in criteria["expected_events"] if events_found.get(e, 0) > 0) / len(criteria["expected_events"])
        signals_score = sum(1 for s in criteria["expected_signals"] if s in signals_found) / len(criteria["expected_signals"])
        execution_score = 1.0 if len(steps) >= 3 else len(steps) / 3.0
        
        result["completeness_score"] = (events_score + signals_score + execution_score) / 3.0
        
        return result
    
    def _analyze_event_bus(self) -> Dict[str, Any]:
        """Analyze event bus architecture integrity."""
        
        event_counts = self.trace_data.get("event_counts", {})
        total_events = sum(event_counts.values())
        
        # Expected event types for full system operation
        expected_core_events = [
            "MotionPathCompletedEvent", "AnimationStartedEvent", "PoseUpdatedEvent",
            "MechanismSelectedEvent", "ProjectLoadedEvent"
        ]
        
        analysis = {
            "total_events_published": total_events,
            "unique_event_types": len(event_counts),
            "event_distribution": event_counts,
            "core_events_coverage": {},
            "bus_health_score": 0.0,
            "issues": []
        }
        
        # Check core event coverage
        found_core_events = 0
        for event_type in expected_core_events:
            found = event_type in event_counts
            analysis["core_events_coverage"][event_type] = found
            if found:
                found_core_events += 1
            else:
                analysis["issues"].append(f"Core event not published: {event_type}")
        
        # Calculate health score
        if total_events == 0:
            analysis["bus_health_score"] = 0.0
            analysis["issues"].append("No events published - event bus may not be operational")
        else:
            # Health based on event diversity and core coverage
            diversity_score = min(1.0, len(event_counts) / 10.0)  # Expect ~10 event types
            coverage_score = found_core_events / len(expected_core_events)
            volume_score = min(1.0, total_events / 20.0)  # Expect ~20 events for full test
            
            analysis["bus_health_score"] = (diversity_score + coverage_score + volume_score) / 3.0
        
        return analysis
    
    def _analyze_performance(self) -> Dict[str, Any]:
        """Analyze performance characteristics."""
        
        function_calls = self.trace_data.get("function_calls", [])
        signal_emissions = self.trace_data.get("signal_emissions", [])
        total_time = self.trace_data.get("summary", {}).get("total_time", 0)
        
        analysis = {
            "total_execution_time": total_time,
            "function_call_rate": len(function_calls) / max(total_time, 0.001),
            "signal_emission_rate": len(signal_emissions) / max(total_time, 0.001),
            "performance_score": 0.0,
            "bottlenecks": [],
            "issues": []
        }
        
        # Analyze function call timing
        if function_calls:
            call_intervals = []
            for i in range(1, len(function_calls)):
                interval = function_calls[i]["timestamp"] - function_calls[i-1]["timestamp"]
                call_intervals.append(interval)
            
            if call_intervals:
                avg_interval = sum(call_intervals) / len(call_intervals)
                max_interval = max(call_intervals)
                
                analysis["avg_call_interval"] = avg_interval
                analysis["max_call_interval"] = max_interval
                
                # Detect bottlenecks (intervals > 100ms)
                bottlenecks = [i for i, interval in enumerate(call_intervals) if interval > 0.1]
                if bottlenecks:
                    analysis["bottlenecks"] = bottlenecks[:5]  # Top 5
                    analysis["issues"].append(f"Performance bottlenecks detected: {len(bottlenecks)} slow operations")
        
        # Performance scoring
        if total_time < 1.0:
            time_score = 1.0  # Excellent response time
        elif total_time < 5.0:
            time_score = 0.8  # Good response time
        elif total_time < 10.0:
            time_score = 0.6  # Acceptable response time
        else:
            time_score = 0.3  # Slow response time
        
        activity_score = min(1.0, len(function_calls) / 50.0)  # Expect ~50 calls
        bottleneck_penalty = len(analysis.get("bottlenecks", [])) * 0.1
        
        analysis["performance_score"] = max(0.0, (time_score + activity_score) / 2.0 - bottleneck_penalty)
        
        return analysis
    
    def _analyze_architecture_integrity(self) -> Dict[str, Any]:
        """Analyze overall architecture integrity."""
        
        # Check DI container integrity
        function_calls = self.trace_data.get("function_calls", [])
        di_calls = [call for call in function_calls if "di.py" in call.get("function", "")]
        
        # Check event-driven patterns
        events = self.trace_data.get("event_counts", {})
        signals = self.trace_data.get("signal_emissions", [])
        
        analysis = {
            "di_container_active": len(di_calls) > 0,
            "event_driven_active": len(events) > 0,
            "signal_system_active": len(signals) > 0,
            "architecture_score": 0.0,
            "integration_health": {},
            "issues": []
        }
        
        # Integration health checks
        analysis["integration_health"] = {
            "event_bus_integration": len(events) > 0,
            "di_container_integration": len(di_calls) > 0,
            "signal_slot_integration": len(signals) > 0,
            "service_layer_integration": any("service" in call.get("function", "") for call in function_calls)
        }
        
        # Calculate architecture score
        active_systems = sum(analysis["integration_health"].values())
        total_systems = len(analysis["integration_health"])
        analysis["architecture_score"] = active_systems / total_systems if total_systems > 0 else 0.0
        
        # Generate issues
        for system, active in analysis["integration_health"].items():
            if not active:
                analysis["issues"].append(f"Architecture component not active: {system}")
        
        return analysis
    
    def _analyze_errors(self) -> Dict[str, Any]:
        """Analyze error conditions and handling."""
        
        function_calls = self.trace_data.get("function_calls", [])
        error_calls = [call for call in function_calls if "EXCEPTION" in str(call.get("result", ""))]
        
        analysis = {
            "total_errors": len(error_calls),
            "error_rate": len(error_calls) / max(len(function_calls), 1),
            "error_details": error_calls[:5],  # First 5 errors
            "error_handling_score": 0.0,
            "issues": []
        }
        
        # Score error handling
        if len(error_calls) == 0:
            analysis["error_handling_score"] = 1.0  # No errors is good
        elif analysis["error_rate"] < 0.05:
            analysis["error_handling_score"] = 0.8  # Low error rate is acceptable
        elif analysis["error_rate"] < 0.1:
            analysis["error_handling_score"] = 0.6  # Moderate error rate
        else:
            analysis["error_handling_score"] = 0.3  # High error rate is concerning
            analysis["issues"].append(f"High error rate detected: {analysis['error_rate']:.2%}")
        
        return analysis
    
    def _analyze_coverage(self) -> Dict[str, Any]:
        """Analyze verification coverage completeness."""
        
        workflow_states = self.trace_data.get("summary", {}).get("workflow_states", {})
        
        # Expected workflows
        expected_workflows = ["path_drawing", "skeleton_animation", "mechanism_recommendation"]
        
        analysis = {
            "total_workflows": len(expected_workflows),
            "executed_workflows": 0,
            "workflow_coverage": {},
            "coverage_score": 0.0,
            "missing_coverage": []
        }
        
        # Check workflow coverage
        for workflow in expected_workflows:
            executed = len(workflow_states.get(workflow, {}).get("steps", [])) > 0
            analysis["workflow_coverage"][workflow] = executed
            if executed:
                analysis["executed_workflows"] += 1
            else:
                analysis["missing_coverage"].append(workflow)
        
        # Calculate coverage score
        analysis["coverage_score"] = analysis["executed_workflows"] / analysis["total_workflows"]
        
        return analysis
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on analysis."""
        
        recommendations = []
        
        # Check workflow execution
        workflow_analysis = self.analysis_results.get("workflow_analysis", {})
        for workflow, data in workflow_analysis.items():
            if data.get("completeness_score", 0) < 0.8:
                recommendations.append(f"Improve {workflow} workflow - completeness score: {data.get('completeness_score', 0):.2f}")
        
        # Check event bus health
        event_bus_score = self.analysis_results.get("event_bus_analysis", {}).get("bus_health_score", 0)
        if event_bus_score < 0.7:
            recommendations.append(f"Event bus needs attention - health score: {event_bus_score:.2f}")
        
        # Check performance
        performance_score = self.analysis_results.get("performance_analysis", {}).get("performance_score", 0)
        if performance_score < 0.7:
            recommendations.append(f"Performance optimization needed - score: {performance_score:.2f}")
        
        # Check architecture integrity
        arch_score = self.analysis_results.get("architecture_integrity", {}).get("architecture_score", 0)
        if arch_score < 0.8:
            recommendations.append(f"Architecture integration issues - score: {arch_score:.2f}")
        
        return recommendations
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate overall verification summary."""
        
        # Collect key scores
        workflow_scores = [
            data.get("completeness_score", 0) 
            for data in self.analysis_results.get("workflow_analysis", {}).values()
        ]
        
        event_bus_score = self.analysis_results.get("event_bus_analysis", {}).get("bus_health_score", 0)
        performance_score = self.analysis_results.get("performance_analysis", {}).get("performance_score", 0)
        architecture_score = self.analysis_results.get("architecture_integrity", {}).get("architecture_score", 0)
        coverage_score = self.analysis_results.get("coverage_analysis", {}).get("coverage_score", 0)
        
        # Calculate overall score
        all_scores = workflow_scores + [event_bus_score, performance_score, architecture_score, coverage_score]
        overall_score = sum(all_scores) / len(all_scores) if all_scores else 0.0
        
        # Determine status
        if overall_score >= 0.9:
            status = "EXCELLENT"
            emoji = "🎉"
        elif overall_score >= 0.8:
            status = "GOOD"  
            emoji = "✅"
        elif overall_score >= 0.7:
            status = "ACCEPTABLE"
            emoji = "⚠️"
        elif overall_score >= 0.5:
            status = "NEEDS_IMPROVEMENT"
            emoji = "🔧"
        else:
            status = "CRITICAL"
            emoji = "❌"
        
        return {
            "overall_score": overall_score,
            "status": status,
            "emoji": emoji,
            "workflow_average": sum(workflow_scores) / len(workflow_scores) if workflow_scores else 0.0,
            "component_scores": {
                "workflows": sum(workflow_scores) / len(workflow_scores) if workflow_scores else 0.0,
                "event_bus": event_bus_score,
                "performance": performance_score,
                "architecture": architecture_score,
                "coverage": coverage_score
            },
            "total_issues": sum(
                len(component.get("issues", [])) 
                for component in self.analysis_results.values() 
                if isinstance(component, dict)
            ),
            "total_recommendations": len(self.analysis_results.get("recommendations", []))
        }
    
    def print_summary_report(self):
        """Print a comprehensive summary report."""
        
        if not self.analysis_results:
            print("❌ No analysis results available. Run analyze_comprehensive() first.")
            return
        
        summary = self.analysis_results["summary"]
        
        print("\n" + "="*80)
        print("🧠 ULTRATHINK COMPREHENSIVE VERIFICATION ANALYSIS")
        print("="*80)
        
        print(f"\n{summary['emoji']} OVERALL STATUS: {summary['status']}")
        print(f"📊 Overall Score: {summary['overall_score']:.3f}")
        print(f"🚨 Total Issues: {summary['total_issues']}")
        print(f"💡 Recommendations: {summary['total_recommendations']}")
        
        print(f"\n📈 Component Scores:")
        for component, score in summary["component_scores"].items():
            print(f"  {component}: {score:.3f}")
        
        # Show critical issues
        if summary["total_issues"] > 0:
            print(f"\n🚨 Critical Issues Found:")
            for component_name, component_data in self.analysis_results.items():
                if isinstance(component_data, dict) and "issues" in component_data:
                    for issue in component_data["issues"][:3]:  # Top 3 per component
                        print(f"    ❌ [{component_name}] {issue}")
        
        # Show recommendations
        recommendations = self.analysis_results.get("recommendations", [])
        if recommendations:
            print(f"\n💡 Top Recommendations:")
            for rec in recommendations[:5]:  # Top 5
                print(f"    💡 {rec}")
        
        print(f"\n🎯 Verification Summary:")
        coverage = self.analysis_results.get("coverage_analysis", {})
        print(f"  Workflows Executed: {coverage.get('executed_workflows', 0)}/{coverage.get('total_workflows', 0)}")
        print(f"  Coverage Score: {coverage.get('coverage_score', 0):.3f}")
        
        event_bus = self.analysis_results.get("event_bus_analysis", {})
        print(f"  Events Published: {event_bus.get('total_events_published', 0)}")
        print(f"  Event Types: {event_bus.get('unique_event_types', 0)}")
        
        performance = self.analysis_results.get("performance_analysis", {})
        print(f"  Total Execution Time: {performance.get('total_execution_time', 0):.3f}s")
        print(f"  Function Calls: {len(self.trace_data.get('function_calls', []))}")
        
        print("="*80)


def main():
    """Main analysis execution."""
    analyzer = TraceAnalyzer()
    results = analyzer.analyze_comprehensive()
    analyzer.print_summary_report()
    
    return results


if __name__ == "__main__":
    main()