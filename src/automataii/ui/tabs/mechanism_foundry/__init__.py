"""
Mechanism Foundry - Interactive Educational Mechanism Dictionary

A unified, interactive learning system for understanding mechanical systems through
hands-on interaction and exploration.

Architecture:
- Clean, modular view using Controller pattern for mechanism visualization
- Protocol-based design for extensibility (Mechanism, MechanismRenderer protocols)
- Separation of concerns: UI → Controller → Domain Logic

Components:
- foundry_view.py: Main UI widget (380 LOC, replaces 3,771 LOC monolith)
- MechanismFoundryController: Configuration and catalog management
- Mechanism implementations: fourbar, cam_follower (fourbar.compute, cam.compute)
- Renderers: LinkageRenderer for fourbar, custom rendering for cam
"""

from .foundry_view import MechanismFoundryView

__all__ = ['MechanismFoundryView']
