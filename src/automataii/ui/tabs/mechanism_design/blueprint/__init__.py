"""
Blueprint Generation System for Mechanism Design

This module provides comprehensive blueprint generation capabilities that transform
2D mechanism designs into manufacturable blueprints with CAD-level precision.

Features:
- Multi-format export (DXF, SVG, PDF) with professional quality
- Automatic dimensioning and annotation generation
- Engineering drawing standards compliance (ISO, ANSI)
- Material specifications and manufacturing notes
- Assembly instructions and part lists
- Integration with 3D simulation data for enhanced accuracy

The system leverages physics-based simulation data to ensure that generated
blueprints accurately represent the mechanical behavior and constraints of
the designed mechanisms.
"""

from .export_manager import BlueprintExportManager
from .exporters import DxfExporter, SvgExporter, PdfExporter
from .drawing_standards import DrawingStandards, ISO_Standard, ANSI_Standard
from .dimensioning import AutoDimensioning, DimensionManager
from .annotation import AnnotationManager, MaterialSpec, ManufacturingNote

__all__ = [
    'BlueprintExportManager',
    'DxfExporter', 
    'SvgExporter',
    'PdfExporter',
    'DrawingStandards',
    'ISO_Standard',
    'ANSI_Standard',
    'AutoDimensioning',
    'DimensionManager',
    'AnnotationManager',
    'MaterialSpec',
    'ManufacturingNote'
]