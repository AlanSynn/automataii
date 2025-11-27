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