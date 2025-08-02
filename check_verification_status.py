#!/usr/bin/env python3
"""
Quick verification status checker
Shows current state of verification traces and analysis
"""

import json
from pathlib import Path
from datetime import datetime

def check_status():
    """Check current verification status"""
    print("AUTOMATAII VERIFICATION STATUS")
    print("="*60)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60 + "\n")
    
    # Check trace files
    trace_files = {
        "workflow_trace.log": Path("workflow_trace.log"),
        "verification_trace.json": Path("verification_trace.json"),
        "trace_analysis_results.json": Path("trace_analysis_results.json"),
        "verification_results.json": Path("verification_results.json"),
        "verification_summary.txt": Path("verification_summary.txt")
    }
    
    print("TRACE FILES:")
    for name, path in trace_files.items():
        if path.exists():
            size = path.stat().st_size
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
            print(f"  ✓ {name}: {size} bytes (modified: {mtime.strftime('%H:%M:%S')})")
        else:
            print(f"  ✗ {name}: Not found")
    
    # Check JSON trace content
    json_trace = Path("verification_trace.json")
    if json_trace.exists():
        print("\nJSON TRACE SUMMARY:")
        try:
            with open(json_trace, 'r') as f:
                data = json.load(f)
            
            summary = data.get("summary", {})
            print(f"  Total entries: {summary.get('total_entries', 0)}")
            print(f"  Function calls: {summary.get('function_call_count', 0)}")
            print(f"  Signal emissions: {summary.get('signal_emission_count', 0)}")
            
            workflows = summary.get("workflow_states", {})
            print("\n  Workflow States:")
            for workflow, state in workflows.items():
                active = "Active" if state.get("active") else "Inactive"
                steps = len(state.get("steps", []))
                print(f"    - {workflow}: {active} ({steps} steps)")
                
            event_counts = summary.get("event_counts", {})
            if event_counts:
                print("\n  Event Counts:")
                for event, count in event_counts.items():
                    print(f"    - {event}: {count}")
            
        except Exception as e:
            print(f"  Error reading JSON trace: {e}")
    
    # Check analysis results
    analysis_results = Path("trace_analysis_results.json")
    if analysis_results.exists():
        print("\nANALYSIS RESULTS:")
        try:
            with open(analysis_results, 'r') as f:
                results = json.load(f)
            
            for workflow, data in results.items():
                status = "✓ PASSED" if data.get("passed") else "✗ FAILED"
                summary = data.get("summary", "No summary")
                print(f"  {workflow}: {status}")
                print(f"    {summary}")
                
                if data.get("issues"):
                    print(f"    Issues: {', '.join(data['issues'])}")
                    
        except Exception as e:
            print(f"  Error reading analysis results: {e}")
    
    # Check running processes
    print("\nRUNNING PROCESSES:")
    import subprocess
    
    try:
        ps_result = subprocess.run(
            ["ps", "aux"], 
            capture_output=True, 
            text=True
        )
        
        processes = {
            "Automataii": False,
            "Verification Tracer": False
        }
        
        for line in ps_result.stdout.split('\n'):
            if "automataii" in line.lower() and "grep" not in line:
                processes["Automataii"] = True
            if "verification_tracer" in line and "grep" not in line:
                processes["Verification Tracer"] = True
        
        for name, running in processes.items():
            status = "✓ Running" if running else "✗ Not running"
            print(f"  {name}: {status}")
            
    except Exception as e:
        print(f"  Error checking processes: {e}")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    check_status()