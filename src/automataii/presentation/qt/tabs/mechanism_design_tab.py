"""Compatibility shim for mechanism design tab.

The implementation now lives in ``automataii.ui.tabs.mechanism_design.tab``.
Importing from the legacy path continues to work while downstream code migrates.
"""

from automataii.presentation.qt.tabs.mechanism_design.tab import MechanismDesignTab

__all__ = ["MechanismDesignTab"]
