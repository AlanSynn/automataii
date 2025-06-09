"""Export handler for mechanism blueprints and other formats."""

import logging
from typing import List, Dict, Optional
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QFileDialog, QWidget


class ExportHandler(QObject):
    """Handles export operations for mechanisms."""
    
    # Signals
    export_started = pyqtSignal()
    export_completed = pyqtSignal(str)  # file_path
    export_failed = pyqtSignal(str)  # error_message
    
    def __init__(self, parent_widget: Optional[QWidget] = None):
        super().__init__()
        self._parent_widget = parent_widget
        self._logger = logging.getLogger(__name__)
    
    def export_blueprint(self, mechanisms: List[Dict]) -> Optional[str]:
        """Export mechanisms as SVG blueprint."""
        if not mechanisms:
            self._logger.warning("No mechanisms to export")
            self.export_failed.emit("No mechanisms to export")
            return None
        
        # Get save path from user
        file_path, _ = QFileDialog.getSaveFileName(
            self._parent_widget,
            "Save Blueprint",
            "mechanism_blueprint.svg",
            "SVG Files (*.svg);;All Files (*)"
        )
        
        if not file_path:
            return None
        
        self._logger.info(f"Exporting blueprint to: {file_path}")
        self.export_started.emit()
        
        try:
            # Generate SVG content
            svg_content = self._generate_svg_blueprint(mechanisms)
            
            # Write to file
            Path(file_path).write_text(svg_content)
            
            self._logger.info("Blueprint exported successfully")
            self.export_completed.emit(file_path)
            return file_path
            
        except Exception as e:
            error_msg = f"Failed to export blueprint: {str(e)}"
            self._logger.error(error_msg)
            self.export_failed.emit(error_msg)
            return None
    
    def _generate_svg_blueprint(self, mechanisms: List[Dict]) -> str:
        """Generate SVG content for blueprint."""
        # SVG header
        svg_parts = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600">',
            '<rect width="800" height="600" fill="white"/>',
            '<g stroke="black" stroke-width="1" fill="none">',
        ]
        
        # Add title
        svg_parts.append(
            '<text x="400" y="30" text-anchor="middle" '
            'font-family="Arial" font-size="20" fill="black">'
            'Mechanism Blueprint</text>'
        )
        
        # Add mechanism representations
        y_offset = 60
        for i, mechanism in enumerate(mechanisms):
            mechanism_type = mechanism.get("type", "Unknown")
            part_name = mechanism.get("part_name", "Unknown")
            
            # Add mechanism label
            svg_parts.append(
                f'<text x="50" y="{y_offset}" '
                f'font-family="Arial" font-size="14" fill="black">'
                f'{mechanism_type} - {part_name}</text>'
            )
            
            # Add placeholder mechanism drawing
            svg_parts.append(
                f'<rect x="50" y="{y_offset + 10}" '
                f'width="700" height="100" stroke="blue"/>'
            )
            
            y_offset += 130
        
        # Close SVG
        svg_parts.extend(['</g>', '</svg>'])
        
        return '\n'.join(svg_parts)
    
    def export_mechanism_data(self, mechanisms: List[Dict], format: str = "json") -> Optional[str]:
        """Export mechanism data in various formats."""
        if format == "json":
            return self._export_as_json(mechanisms)
        elif format == "csv":
            return self._export_as_csv(mechanisms)
        else:
            self._logger.error(f"Unsupported export format: {format}")
            return None
    
    def _export_as_json(self, mechanisms: List[Dict]) -> Optional[str]:
        """Export mechanisms as JSON."""
        import json
        
        file_path, _ = QFileDialog.getSaveFileName(
            self._parent_widget,
            "Export Mechanism Data",
            "mechanisms.json",
            "JSON Files (*.json);;All Files (*)"
        )
        
        if not file_path:
            return None
        
        try:
            # Convert QPointF objects to serializable format
            serializable_data = []
            for mech in mechanisms:
                mech_data = {
                    "type": mech.get("type"),
                    "part_name": mech.get("part_name"),
                }
                
                # Convert QPointF to dict
                for key in ["cam_center", "pivot_a", "pivot_d"]:
                    if key in mech:
                        point = mech[key]
                        if point:
                            mech_data[key] = {"x": point.x(), "y": point.y()}
                
                serializable_data.append(mech_data)
            
            # Write JSON
            Path(file_path).write_text(
                json.dumps(serializable_data, indent=2)
            )
            
            return file_path
            
        except Exception as e:
            self._logger.error(f"Failed to export JSON: {str(e)}")
            return None
    
    def _export_as_csv(self, mechanisms: List[Dict]) -> Optional[str]:
        """Export mechanisms as CSV."""
        # Implementation for CSV export
        pass