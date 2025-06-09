#!/usr/bin/env python3
"""
Smoke Test - Quick verification that Automataii can start
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))


def smoke_test():
    """Quick smoke test - can the app start?"""
    print("\n🔥 AUTOMATAII SMOKE TEST\n")
    
    try:
        # Test imports
        print("📦 Importing core modules...")
        from PyQt6.QtWidgets import QApplication
        from automataii.gui.main_window.main_window import AutomataDesigner
        print("✅ Core imports successful")
        
        # Test app creation
        print("\n🚀 Creating application...")
        app = QApplication([])
        window = AutomataDesigner()
        print("✅ Application created successfully")
        
        # Test critical components exist
        print("\n🔍 Verifying components...")
        assert window.project_data_manager is not None, "Project manager missing"
        assert window.skeleton_manager is not None, "Skeleton manager missing"
        assert window.ik_manager is not None, "IK manager missing"
        assert window.landing_tab is not None, "Landing tab missing"
        assert window.image_proc_tab is not None, "Image processing tab missing"
        assert window.editor_tab is not None, "Editor tab missing"
        assert window.mechanism_generation_tab is not None, "Mechanism tab missing"
        print("✅ All critical components present")
        
        # Clean exit
        app.quit()
        
        print("\n" + "="*40)
        print("✅ SMOKE TEST PASSED - APP IS HEALTHY!")
        print("="*40 + "\n")
        
        return True
        
    except Exception as e:
        print(f"\n❌ SMOKE TEST FAILED: {e}\n")
        return False


if __name__ == "__main__":
    success = smoke_test()
    sys.exit(0 if success else 1)