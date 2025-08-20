# Mechanism Module
# Lines: ~50
# Public API: MechanismRegistry, MechanismInterface, EditorInterface
# Deps In: mechanism_design_tab.py
# Deps Out: None
# Coupling: Low (Registry pattern for loose coupling)
# Cohesion: Feature (mechanism management)
# Owner: Alan Synn
# Last Updated: 2025-01-20

"""
Modular mechanism system with registry pattern.
Each mechanism is a self-contained module with its own editor and serializer.
"""

from .registry import MechanismRegistry
from .interfaces.mechanism import MechanismInterface
from .interfaces.editor import EditorInterface
from .interfaces.serializer import BlueprintSerializer

# Import mechanism modules to register them
from . import four_bar
from . import cam
from . import gear
from . import planetary_gear

__all__ = [
    'MechanismRegistry',
    'MechanismInterface', 
    'EditorInterface',
    'BlueprintSerializer'
]