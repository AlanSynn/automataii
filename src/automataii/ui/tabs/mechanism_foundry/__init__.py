"""
Mechanism Foundry - Interactive Educational Mechanism Dictionary

A hierarchical learning system for understanding mechanical systems through
progressive exploration and hands-on interaction.

Architecture:
- Level 1: Category Hub - Visual entry point with mechanism categories
- Level 2: Mechanism Index - Master-detail browsing within categories  
- Level 3: Mechanism Workshop - Focused learning workspace

Components:
- foundry_tab.py: Main entry widget
- components/: Reusable widgets (cards, controls, navigation)
- views/: Main pages (category hub, mechanism workshop)
- panels/: Workshop content (overview, playground, analysis)
"""

from .foundry_tab import MechanismFoundryTab

__all__ = ['MechanismFoundryTab']