"""
Modular mechanism system with registry pattern.
Each mechanism is a self-contained module with its own editor and serializer.
"""

# Import mechanism modules to register them
# Note: planetary_gear was removed (not implemented)
from . import cam, four_bar, gear
from .interfaces.editor import EditorInterface
from .interfaces.mechanism import MechanismInterface
from .interfaces.serializer import BlueprintSerializer
from .registry import MechanismRegistry

__all__ = ["MechanismRegistry", "MechanismInterface", "EditorInterface", "BlueprintSerializer"]
