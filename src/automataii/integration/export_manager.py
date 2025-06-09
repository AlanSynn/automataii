"""Manager for exporting automata designs to various formats."""

import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
import xml.etree.ElementTree as ET

from .mechanism_adapter import MechanismAdapter, MechanismPlacement


class ExportManager:
    """Handles export of automata designs to various formats."""
    
    def __init__(self, adapter: MechanismAdapter):
        self.adapter = adapter
        self.supported_formats = ['json', 'stl', 'svg', 'dxf', 'step']
        
    def export_design(self, base_config: Dict[str, Any], 
                     output_path: str, format: str = 'json') -> bool:
        """Export complete automata design."""
        if format not in self.supported_formats:
            raise ValueError(f"Unsupported format: {format}")
            
        export_method = getattr(self, f'_export_{format}', None)
        if not export_method:
            return False
            
        return export_method(base_config, output_path)
        
    def _export_json(self, base_config: Dict[str, Any], output_path: str) -> bool:
        """Export design as JSON for further processing."""
        design_data = {
            'metadata': {
                'version': '1.0',
                'created': datetime.now().isoformat(),
                'units': 'mm'
            },
            'base': base_config,
            'mechanisms': [],
            'connections': []
        }
        
        # Add mechanism placements
        for mech_id, placement in self.adapter.placements.items():
            mech_data = {
                'id': mech_id,
                'position': placement.base_position,
                'rotation': placement.rotation,
                'scale': placement.scale,
                'connection_points': [
                    {
                        'position': cp.position,
                        'normal': cp.normal,
                        'type': cp.type,
                        'diameter': cp.diameter
                    }
                    for cp in placement.connection_points
                ]
            }
            design_data['mechanisms'].append(mech_data)
            
        # Add connection mappings
        for mech_id in self.adapter.placements:
            mappings = self.adapter.get_connection_mappings(mech_id)
            design_data['connections'].append({
                'mechanism_id': mech_id,
                'mappings': mappings
            })
            
        # Write to file
        try:
            with open(output_path, 'w') as f:
                json.dump(design_data, f, indent=2)
            return True
        except Exception as e:
            print(f"Error exporting JSON: {e}")
            return False
            
    def _export_svg(self, base_config: Dict[str, Any], output_path: str) -> bool:
        """Export 2D projection as SVG."""
        # Create SVG root
        svg = ET.Element('svg', {
            'width': '800',
            'height': '600',
            'viewBox': '-400 -300 800 600',
            'xmlns': 'http://www.w3.org/2000/svg'
        })
        
        # Add background
        ET.SubElement(svg, 'rect', {
            'x': '-400',
            'y': '-300',
            'width': '800',
            'height': '600',
            'fill': 'white'
        })
        
        # Draw base outline
        self._draw_base_svg(svg, base_config)
        
        # Draw mechanism placements
        for mech_id, placement in self.adapter.placements.items():
            self._draw_mechanism_svg(svg, placement)
            
        # Save SVG
        try:
            tree = ET.ElementTree(svg)
            tree.write(output_path, encoding='utf-8', xml_declaration=True)
            return True
        except Exception as e:
            print(f"Error exporting SVG: {e}")
            return False
            
    def _draw_base_svg(self, svg: ET.Element, base_config: Dict[str, Any]):
        """Draw base outline in SVG."""
        base_type = base_config.get('type', 'rectangular')
        
        if base_type == 'rectangular':
            width = base_config.get('width', 200)
            depth = base_config.get('depth', 150)
            ET.SubElement(svg, 'rect', {
                'x': str(-width/2),
                'y': str(-depth/2),
                'width': str(width),
                'height': str(depth),
                'fill': 'none',
                'stroke': 'black',
                'stroke-width': '2'
            })
        elif base_type == 'cylindrical':
            radius = base_config.get('radius', 100)
            ET.SubElement(svg, 'circle', {
                'cx': '0',
                'cy': '0',
                'r': str(radius),
                'fill': 'none',
                'stroke': 'black',
                'stroke-width': '2'
            })
            
    def _draw_mechanism_svg(self, svg: ET.Element, placement: MechanismPlacement):
        """Draw mechanism placement in SVG."""
        # Draw connection points
        for cp in placement.connection_points:
            color = {
                'motor': 'red',
                'support': 'blue',
                'output': 'green'
            }.get(cp.type, 'gray')
            
            # Transform to world position
            world_pos = self.adapter._transform_to_world(
                cp.position, placement.base_position, placement.rotation
            )
            
            ET.SubElement(svg, 'circle', {
                'cx': str(world_pos[0]),
                'cy': str(world_pos[1]),
                'r': str(cp.diameter/2),
                'fill': color,
                'fill-opacity': '0.5',
                'stroke': color,
                'stroke-width': '1'
            })
            
    def _export_stl(self, base_config: Dict[str, Any], output_path: str) -> bool:
        """Export 3D model as STL (placeholder for actual implementation)."""
        # This would require a proper 3D library like trimesh or numpy-stl
        # For now, we'll create a simple text file indicating the export
        try:
            with open(output_path, 'w') as f:
                f.write("solid automata\n")
                f.write("  # STL export not fully implemented\n")
                f.write("  # Base type: {}\n".format(base_config.get('type', 'unknown')))
                f.write("  # Mechanisms: {}\n".format(len(self.adapter.placements)))
                f.write("endsolid automata\n")
            return True
        except Exception as e:
            print(f"Error creating STL placeholder: {e}")
            return False
            
    def _export_dxf(self, base_config: Dict[str, Any], output_path: str) -> bool:
        """Export 2D profiles as DXF (placeholder)."""
        # This would require a DXF library like ezdxf
        try:
            with open(output_path, 'w') as f:
                f.write("0\nSECTION\n2\nHEADER\n")
                f.write("9\n$ACADVER\n1\nAC1015\n")
                f.write("0\nENDSEC\n")
                f.write("0\nSECTION\n2\nENTITIES\n")
                f.write("0\nENDSEC\n")
                f.write("0\nEOF\n")
            return True
        except Exception as e:
            print(f"Error creating DXF placeholder: {e}")
            return False
            
    def _export_step(self, base_config: Dict[str, Any], output_path: str) -> bool:
        """Export as STEP file for CAD (placeholder)."""
        # This would require a STEP library like PythonOCC
        try:
            with open(output_path, 'w') as f:
                f.write("ISO-10303-21;\n")
                f.write("HEADER;\n")
                f.write("FILE_DESCRIPTION(('Automata Export'),'2;1');\n")
                f.write("FILE_NAME('{}','{}',(''),(''),'','','');\n".format(
                    os.path.basename(output_path),
                    datetime.now().isoformat()
                ))
                f.write("FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));\n")
                f.write("ENDSEC;\n")
                f.write("DATA;\n")
                f.write("ENDSEC;\n")
                f.write("END-ISO-10303-21;\n")
            return True
        except Exception as e:
            print(f"Error creating STEP placeholder: {e}")
            return False
            
    def get_export_info(self, format: str) -> Dict[str, Any]:
        """Get information about export format."""
        format_info = {
            'json': {
                'name': 'JSON Data',
                'extension': '.json',
                'description': 'Complete design data for further processing',
                'binary': False
            },
            'svg': {
                'name': 'SVG Drawing',
                'extension': '.svg',
                'description': '2D vector drawing of the design',
                'binary': False
            },
            'stl': {
                'name': 'STL Model',
                'extension': '.stl',
                'description': '3D model for 3D printing',
                'binary': True
            },
            'dxf': {
                'name': 'DXF Drawing',
                'extension': '.dxf',
                'description': '2D CAD drawing for laser cutting',
                'binary': False
            },
            'step': {
                'name': 'STEP Model',
                'extension': '.step',
                'description': '3D CAD model for engineering software',
                'binary': False
            }
        }
        
        return format_info.get(format, {})