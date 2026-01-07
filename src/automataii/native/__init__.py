"""
Native (C++) acceleration modules for Automataii.

This package contains pybind11-wrapped C++ implementations of
performance-critical algorithms:

- arap_native: Accelerated ARAP deformation solver

Building:
    pip install .[native]
    cd src/automataii/native && mkdir build && cd build
    cmake .. && make

Usage:
    from automataii.native import arap_native
    result = arap_native.compute_rotation_matrices(edges, T1)

If the native module is not available, the package gracefully
falls back to numpy/numba implementations.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Lazy import of native modules
_arap_native = None


def get_arap_native():
    """
    Get the native ARAP module if available.

    Returns:
        Native module or None if not available
    """
    global _arap_native

    if _arap_native is not None:
        return _arap_native

    try:
        from automataii.native import arap_native as _module

        _arap_native = _module
        logger.info("Native ARAP module loaded successfully")
        return _arap_native
    except ImportError:
        logger.debug("Native ARAP module not available (this is OK)")
        return None


def is_native_available() -> bool:
    """Check if native acceleration is available."""
    return get_arap_native() is not None
