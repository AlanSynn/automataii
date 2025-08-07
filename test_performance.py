#!/usr/bin/env python
"""Performance test for the optimized enhanced mechanism tab"""

import sys
import time
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from automataii.ui.tabs.mechanism_foundry.enhanced_macanism_tab import EnhancedMacanismTab

class PerformanceTest:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.tab = EnhancedMacanismTab()
        self.tab.setWindowTitle("Performance Test - Optimized Mechanism Tab")
        self.tab.resize(1000, 700)
        
        # Performance tracking
        self.frame_count = 0
        self.start_time = time.time()
        
        # Timer to track performance
        self.perf_timer = QTimer()
        self.perf_timer.timeout.connect(self.update_performance)
        self.perf_timer.start(1000)  # Update every second
        
        self.tab.show()
        
        # Start animation after showing
        QTimer.singleShot(500, self.start_animation)
    
    def start_animation(self):
        """Start the mechanism animation"""
        if hasattr(self.tab, 'mechanism_widget') and self.tab.mechanism_widget:
            print("Starting optimized animation...")
            self.tab.mechanism_widget.start_animation()
            
            # Connect to frame updates for tracking
            self.tab.mechanism_widget.animation_timer.timeout.connect(self.count_frame)
        else:
            print("Warning: Mechanism widget not found!")
    
    def count_frame(self):
        """Count animation frames"""
        self.frame_count += 1
    
    def update_performance(self):
        """Update performance metrics"""
        elapsed = time.time() - self.start_time
        if elapsed > 0:
            fps = self.frame_count / elapsed
            print(f"Performance: {fps:.1f} FPS average over {elapsed:.1f}s ({self.frame_count} frames)")
            
            # Reset counters every 10 seconds for rolling average
            if elapsed > 10:
                self.frame_count = 0
                self.start_time = time.time()
    
    def run(self):
        """Run the performance test"""
        print("Starting performance test...")
        print("This will test the optimized rendering performance.")
        print("Look for:")
        print("- Smooth animation at ~60 FPS")
        print("- Reduced CPU usage compared to previous version")
        print("- No noticeable lag during mechanism motion")
        print("-" * 50)
        
        return self.app.exec()

def main():
    test = PerformanceTest()
    return test.run()

if __name__ == "__main__":
    main()