"""
Mechanism Foundry - Interactive Educational Mechanism Dictionary

A unified, interactive learning system for understanding mechanical systems through
hands-on interaction and exploration.

Architecture:
- A single, immersive workshop view (`MechanismFoundryTab`) provides all functionality,
  including mechanism selection, parametric controls, and real-time analysis.
- This replaces the previous hierarchical, multi-level navigation system.

Components:
- foundry_tab.py: Main entry widget and the core of the user experience.
- hci/: Advanced human-computer interaction components (controls, physics interaction).
- panels/: Reusable UI panels for controls and analysis.
- views/: (Legacy) Previously contained different views, now consolidated.
"""

from .foundry_tab import MechanismFoundryTab
from .enhanced_macanism_tab import EnhancedMacanismTab

__all__ = ['MechanismFoundryTab', 'EnhancedMacanismTab']