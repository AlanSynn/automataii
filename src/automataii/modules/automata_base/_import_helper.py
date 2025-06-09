"""
Import helper for automata_base module.

This module provides a flexible import mechanism that works in multiple scenarios:
1. As a standalone package (python -m automata_base)
2. As part of the automataii package
3. When individual files are imported directly
"""

import sys
from pathlib import Path

# Get the automata_base directory
AUTOMATA_BASE_DIR = Path(__file__).parent
MODULES_DIR = AUTOMATA_BASE_DIR.parent
SRC_DIR = MODULES_DIR.parent

def setup_imports():
    """Set up imports for the automata_base module."""
    # Add paths if not already present
    paths_to_add = [
        str(AUTOMATA_BASE_DIR),  # For direct imports
        str(MODULES_DIR),        # For automata_base imports
        str(SRC_DIR),           # For automataii imports
    ]
    
    for path in paths_to_add:
        if path not in sys.path:
            sys.path.insert(0, path)
    
    return AUTOMATA_BASE_DIR

# Automatically set up imports when this module is imported
BASE_DIR = setup_imports()