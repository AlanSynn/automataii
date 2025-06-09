"""
Image view module - imports the refactored ImageProcessingView for backward compatibility.

This file maintains the original import path while the actual implementation
has been refactored into a modular structure under gui/views/image/.
"""

from .image import ImageProcessingView

__all__ = ["ImageProcessingView"]