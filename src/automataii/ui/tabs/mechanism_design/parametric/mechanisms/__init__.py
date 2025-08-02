"""
Mechanism-specific parametric editing implementations.
"""

# Import all available mechanism parametric editors
try:
    from .linkage_parametric import LinkageParametricEditor

    __all__ = ["LinkageParametricEditor"]
except ImportError:
    __all__ = []

try:
    from .gear_parametric import GearParametricEditor

    __all__.append("GearParametricEditor")
except ImportError:
    pass

try:
    from .cam_parametric import CamParametricEditor

    __all__.append("CamParametricEditor")
except ImportError:
    pass

try:
    from .belt_parametric import BeltParametricEditor

    __all__.append("BeltParametricEditor")
except ImportError:
    pass

try:
    from .spring_parametric import SpringParametricEditor

    __all__.append("SpringParametricEditor")
except ImportError:
    pass
