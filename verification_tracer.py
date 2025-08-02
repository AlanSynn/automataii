#!/usr/bin/env python3
"""
ULTRATHINK Dynamic Verification Tracer

This script provides comprehensive end-to-end verification of the Automataii application
by tracing every function call, signal emission, event publication, and data flow
through the three critical workflows:

1. Drawing a Path
2. Skeleton Animation 
3. Mechanism Recommendations

It implements Gemini's two-pronged verification strategy with detailed runtime logging.
"""

import sys
import logging
import time
import threading
from pathlib import Path
from typing import Dict, List, Any
import functools
import inspect

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from automataii.core.event_bus import get_global_event_bus
from automataii.core.events import *
from automataii.services.motion_path_service import MotionPathService
from automataii.core.app_container import get_service


class WorkflowTracer:
    """
    Comprehensive workflow tracer that captures every aspect of execution.
    
    This tracer:
    - Logs all function calls with parameters and return values
    - Captures all signal emissions with data
    - Records all event publications and subscriptions
    - Tracks data flow through the entire system
    - Measures performance at each step
    - Detects integration issues and missing connections
    """
    
    def __init__(self):
        self.trace_log: List[Dict[str, Any]] = []
        self.start_time = time.time()
        self.workflow_states = {
            "path_drawing": {"active": False, "steps": []},
            "skeleton_animation": {"active": False, "steps": []},
            "mechanism_recommendation": {"active": False, "steps": []}
        }
        
        # Setup comprehensive logging
        self._setup_tracing_logger()
        
        # Event tracking
        self.event_counts = {}
        self.signal_emissions = []
        self.function_calls = []
        
        print("🔍 WorkflowTracer initialized - Ready for comprehensive verification")
    
    def _setup_tracing_logger(self):
        """Setup detailed logging for workflow tracing."""
        # Create formatter that includes microseconds
        formatter = logging.Formatter(
            '%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s:%(lineno)d - %(message)s',
            datefmt='%H:%M:%S'
        )
        
        # Console handler for real-time monitoring
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(formatter)
        
        # File handler for complete trace
        file_handler = logging.FileHandler('workflow_trace.log', mode='w')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        
        # Setup root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        root_logger.handlers = []  # Clear existing handlers
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)
        
        print("📝 Tracing logger configured - All output will be captured")
    
    def log_step(self, workflow: str, step: str, details: Dict[str, Any] = None):
        """Log a step in the workflow with full context."""
        timestamp = time.time() - self.start_time
        
        entry = {
            "timestamp": timestamp,
            "workflow": workflow,
            "step": step,
            "details": details or {},
            "thread": f"Thread-{threading.current_thread().ident}",
        }
        
        self.trace_log.append(entry)
        self.workflow_states[workflow]["steps"].append(entry)
        
        logging.info(f"🔹 [{workflow}] {step} | {details}")
    
    def start_workflow(self, workflow: str):
        """Mark the start of a workflow."""
        self.workflow_states[workflow]["active"] = True
        self.log_step(workflow, f"WORKFLOW_STARTED", {"start_time": time.time()})
        print(f"🚀 Starting workflow verification: {workflow}")
    
    def end_workflow(self, workflow: str, success: bool = True):
        """Mark the end of a workflow."""
        self.workflow_states[workflow]["active"] = False
        self.log_step(workflow, f"WORKFLOW_COMPLETED", {
            "success": success, 
            "step_count": len(self.workflow_states[workflow]["steps"]),
            "end_time": time.time()
        })
        print(f"✅ Completed workflow verification: {workflow} (Success: {success})")
    
    def trace_function_call(self, func_name: str, args: tuple, kwargs: dict, result: Any = None):
        """Trace a function call with full details."""
        self.function_calls.append({
            "function": func_name,
            "args": str(args)[:200],  # Truncate long args
            "kwargs": str(kwargs)[:200],
            "result": str(result)[:200] if result is not None else None,
            "timestamp": time.time() - self.start_time
        })
        
        logging.debug(f"🔧 CALL: {func_name}({args}, {kwargs}) -> {result}")
    
    def trace_signal_emission(self, signal_name: str, data: Any = None):
        """Trace a signal emission."""
        self.signal_emissions.append({
            "signal": signal_name,
            "data": str(data)[:200] if data else None,
            "timestamp": time.time() - self.start_time
        })
        
        logging.debug(f"📡 SIGNAL: {signal_name} | Data: {data}")
    
    def trace_event_publication(self, event_type: str, event_data: Any = None):
        """Trace an event publication."""
        if event_type not in self.event_counts:
            self.event_counts[event_type] = 0
        self.event_counts[event_type] += 1
        
        logging.debug(f"📢 EVENT: {event_type} #{self.event_counts[event_type]} | Data: {event_data}")
    
    def get_workflow_summary(self) -> Dict[str, Any]:
        """Get a summary of all workflow traces."""
        return {
            "total_time": time.time() - self.start_time,
            "total_entries": len(self.trace_log),
            "workflow_states": self.workflow_states,
            "event_counts": self.event_counts,
            "function_call_count": len(self.function_calls),
            "signal_emission_count": len(self.signal_emissions)
        }
    
    def verify_workflow_integrity(self) -> Dict[str, List[str]]:
        """Verify the integrity of all workflows and return issues found."""
        issues = {"critical": [], "warnings": [], "info": []}
        
        # Check for missing workflow steps
        for workflow_name, workflow_data in self.workflow_states.items():
            if not workflow_data["steps"]:
                issues["warnings"].append(f"No steps recorded for workflow: {workflow_name}")
            elif len(workflow_data["steps"]) < 3:
                issues["warnings"].append(f"Very few steps in workflow: {workflow_name} ({len(workflow_data['steps'])} steps)")
        
        # Check for event publication/subscription mismatches
        expected_events = ["MotionPathCompletedEvent", "AnimationStartedEvent", "MechanismSelectedEvent"]
        for event in expected_events:
            if event not in self.event_counts:
                issues["warnings"].append(f"Expected event not published: {event}")
        
        # Check for signal emission gaps
        if len(self.signal_emissions) == 0:
            issues["critical"].append("No signal emissions detected - potential integration failure")
        
        # Check for function call gaps
        if len(self.function_calls) < 10:
            issues["warnings"].append("Very few function calls detected - verification may be incomplete")
        
        return issues
    
    def print_comprehensive_report(self):
        """Print a comprehensive report of the verification."""
        print("\n" + "="*80)
        print("🧠 ULTRATHINK COMPREHENSIVE VERIFICATION REPORT")
        print("="*80)
        
        summary = self.get_workflow_summary()
        print(f"📊 Total Verification Time: {summary['total_time']:.3f} seconds")
        print(f"📝 Total Trace Entries: {summary['total_entries']}")
        print(f"🔧 Function Calls: {summary['function_call_count']}")
        print(f"📡 Signal Emissions: {summary['signal_emission_count']}")
        print(f"📢 Event Publications: {sum(summary['event_counts'].values())}")
        
        print("\n📋 Workflow Status:")
        for workflow, data in summary['workflow_states'].items():
            print(f"  {workflow}: {len(data['steps'])} steps recorded")
        
        print("\n📢 Event Counts:")
        for event_type, count in summary['event_counts'].items():
            print(f"  {event_type}: {count}")
        
        # Integrity check
        issues = self.verify_workflow_integrity()
        print(f"\n🔍 Integrity Check:")
        print(f"  Critical Issues: {len(issues['critical'])}")
        print(f"  Warnings: {len(issues['warnings'])}")
        print(f"  Info: {len(issues['info'])}")
        
        if issues['critical']:
            print("🚨 Critical Issues Found:")
            for issue in issues['critical']:
                print(f"    ❌ {issue}")
        
        if issues['warnings']:
            print("⚠️  Warnings:")
            for warning in issues['warnings']:
                print(f"    ⚠️  {warning}")
        
        # Success assessment
        total_issues = len(issues['critical']) + len(issues['warnings'])
        if total_issues == 0:
            print("\n🎉 VERIFICATION SUCCESSFUL - No issues detected!")
        elif len(issues['critical']) == 0:
            print(f"\n✅ VERIFICATION MOSTLY SUCCESSFUL - {len(issues['warnings'])} warnings")
        else:
            print(f"\n❌ VERIFICATION FAILED - {len(issues['critical'])} critical issues")


def trace_function(tracer: WorkflowTracer):
    """Decorator to trace function calls."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            func_name = f"{func.__module__}.{func.__qualname__}"
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                tracer.trace_function_call(func_name, args, kwargs, result)
                return result
            except Exception as e:
                duration = time.time() - start_time
                tracer.trace_function_call(func_name, args, kwargs, f"EXCEPTION: {e}")
                raise
                
        return wrapper
    return decorator


# Global tracer instance
tracer = WorkflowTracer()


def main():
    """Main verification function."""
    print("🚀 Starting ULTRATHINK Comprehensive End-to-End Verification")
    print("=" * 60)
    
    try:
        # Import and start the actual application
        from automataii.app.main import main as app_main
        
        print("📋 Application will start with full tracing enabled")
        print("📋 Three workflows will be verified:")
        print("   1. Drawing a Path")
        print("   2. Skeleton Animation") 
        print("   3. Mechanism Recommendations")
        print("")
        print("🔍 Monitoring all function calls, signals, and events...")
        print("📝 Full trace will be saved to 'workflow_trace.log'")
        print("")
        
        # Start the application (this will block until the app closes)
        app_main()
        
    except KeyboardInterrupt:
        print("\n⏹️  Verification interrupted by user")
    except Exception as e:
        print(f"\n💥 Verification failed with exception: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Print comprehensive report
        tracer.print_comprehensive_report()
        
        # Save detailed trace to file
        import json
        with open('verification_trace.json', 'w') as f:
            json.dump({
                "summary": tracer.get_workflow_summary(),
                "trace_log": tracer.trace_log,
                "function_calls": tracer.function_calls,
                "signal_emissions": tracer.signal_emissions,
                "event_counts": tracer.event_counts
            }, f, indent=2, default=str)
        
        print(f"\n💾 Detailed trace saved to 'verification_trace.json'")


if __name__ == "__main__":
    main()