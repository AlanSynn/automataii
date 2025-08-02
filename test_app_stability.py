#!/usr/bin/env python3
"""
Test script to debug app stability issues.
"""

import os
import sys
import time
import signal
import subprocess

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_app_stability():
    """Test the app stability and capture output."""
    print("🧪 Testing App Stability")
    print("=" * 50)
    
    # Start the app as a subprocess
    cmd = ["uv", "run", "python", "-m", "automataii.app.main"]
    process = subprocess.Popen(
        cmd, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    print("🚀 App started with PID:", process.pid)
    print("📝 Monitoring output...")
    print("-" * 50)
    
    last_line = None
    crash_detected = False
    start_time = time.time()
    
    try:
        for line in process.stdout:
            print(line.rstrip())
            last_line = line.rstrip()
            
            # Check if we got to the critical point
            if "MainWindow: Project data loaded successfully" in line:
                print("\n⚠️  CRITICAL POINT REACHED - Monitoring for crash...")
                
        # Wait for process to finish
        return_code = process.wait(timeout=5)
        
    except subprocess.TimeoutExpired:
        print("\n✅ App is still running after 5 seconds - seems stable!")
        process.terminate()
        return_code = -1
    except KeyboardInterrupt:
        print("\n⌨️  Test interrupted by user")
        process.terminate()
        return_code = -2
    
    print("-" * 50)
    
    if return_code == 0:
        print(f"\n❌ App exited normally with code 0")
        print(f"   Last line: {last_line}")
    elif return_code > 0:
        print(f"\n❌ App CRASHED with exit code: {return_code}")
        print(f"   Last line before crash: {last_line}")
    elif return_code == -1:
        print(f"\n✅ App appears stable - no crash detected!")
    
    elapsed = time.time() - start_time
    print(f"\n⏱️  Test duration: {elapsed:.2f} seconds")
    
    return return_code

if __name__ == "__main__":
    exit_code = test_app_stability()
    
    if exit_code > 0:
        print("\n🔍 CRASH DETECTED - Checking for core dumps or crash logs...")
        # Check for crash logs
        crash_log_paths = [
            "~/Library/Logs/DiagnosticReports/",
            "/var/log/",
            "."
        ]
        
        for path in crash_log_paths:
            expanded_path = os.path.expanduser(path)
            if os.path.exists(expanded_path):
                print(f"   Checking {expanded_path}...")
    
    sys.exit(0 if exit_code <= 0 else 1)