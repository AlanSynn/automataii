"""Converters for exporting base configurations to various formats."""

from typing import Optional, List, Tuple, Dict
import xml.etree.ElementTree as ET
from datetime import datetime
import math

from automataii.modules.automata_base.models.base_config import BaseConfiguration
from automataii.modules.automata_base.models.dimensions import (
    Dimensions2D, Dimensions3D, MountingPoint, Point2D, Point3D
)
from automataii.modules.automata_base.enums.base_types import (
    BaseType, MaterialType, AssemblyMethod
)


def base_to_svg(
    config: BaseConfiguration,
    scale: float = 1.0,
    show_mounting_points: bool = True,
    show_dimensions: bool = False,
    show_grid: bool = False,
    show_labels: bool = True,
    show_cut_lines: bool = True,
    show_engrave_lines: bool = True,
    export_mode: str = "display",  # "display", "laser", "print"
) -> str:
    """
    Convert base configuration to professional SVG format with comprehensive styling.
    
    Args:
        config: Base configuration to convert
        scale: Scale factor for output
        show_mounting_points: Whether to show mounting points
        show_dimensions: Whether to show dimension annotations
        show_grid: Whether to show background grid
        show_labels: Whether to show part labels and annotations
        show_cut_lines: Whether to show cut lines (for laser cutting)
        show_engrave_lines: Whether to show engrave lines
        export_mode: Export mode - "display", "laser", or "print"
        
    Returns:
        SVG string representation suitable for manufacturing
    """
    # Get 2D footprint
    footprint = config.footprint
    width = footprint.width * scale
    height = footprint.height * scale
    
    # Calculate margins based on what's shown
    margin = 60 if show_dimensions else 40
    grid_size = 10 * scale  # 10mm grid
    
    # Create SVG root with proper namespace declarations
    svg = ET.Element('svg', {
        'xmlns': 'http://www.w3.org/2000/svg',
        'xmlns:xlink': 'http://www.w3.org/1999/xlink',
        'width': str(width + 2 * margin),
        'height': str(height + 2 * margin),
        'viewBox': f'{-margin} {-margin} {width + 2 * margin} {height + 2 * margin}',
        'version': '1.1',
    })
    
    # Add metadata
    _add_metadata(svg, config)
    
    # Add comprehensive styles
    _add_comprehensive_styles(svg, config, export_mode)
    
    # Add definitions (patterns, markers, etc.)
    defs = ET.SubElement(svg, 'defs')
    _add_svg_definitions(defs, grid_size)
    
    # Create layer groups
    layers = _create_layer_structure(svg)
    
    # Add grid if requested
    if show_grid and export_mode == "display":
        _add_grid(layers['grid'], width, height, grid_size, margin)
    
    # Draw base outline with appropriate styling
    _draw_base_outline(layers['outline'], config, width, height, scale)
    
    # Add construction lines if box or pedestal
    if config.base_type in [BaseType.BOX_ENCLOSED, BaseType.BOX_OPEN, BaseType.PEDESTAL]:
        _add_construction_lines(layers['construction'], config, width, height, scale)
    
    # Draw mounting points
    if show_mounting_points:
        _draw_mounting_points(layers['mounting'], config, scale, export_mode)
    
    # Add engrave details
    if show_engrave_lines:
        _add_engrave_details(layers['engrave'], config, width, height, scale)
    
    # Add dimensions
    if show_dimensions and export_mode != "laser":
        _add_comprehensive_dimensions(layers['dimensions'], config, width, height, scale)
    
    # Add labels and annotations
    if show_labels and export_mode != "laser":
        _add_labels_and_annotations(layers['labels'], config, width, height, scale)
    
    # Add title block
    if export_mode == "print":
        _add_title_block(layers['annotations'], config, width, height, margin)
    
    # Convert to string with pretty printing
    return _pretty_print_svg(svg)


def _add_metadata(svg: ET.Element, config: BaseConfiguration):
    """Add metadata to SVG for tracking and documentation."""
    metadata = ET.SubElement(svg, 'metadata')
    desc = ET.SubElement(metadata, 'desc')
    desc.text = f"Automata Base: {config.name}"
    
    # Add RDF metadata for better compatibility
    rdf = ET.SubElement(metadata, 'rdf:RDF', {
        'xmlns:rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
        'xmlns:dc': 'http://purl.org/dc/elements/1.1/',
        'xmlns:cc': 'http://creativecommons.org/ns#'
    })
    
    work = ET.SubElement(rdf, 'cc:Work')
    ET.SubElement(work, 'dc:title').text = config.name
    ET.SubElement(work, 'dc:date').text = datetime.now().isoformat()
    ET.SubElement(work, 'dc:description').text = f"Base Type: {config.base_type.value}, Material: {config.primary_material.value}"
    ET.SubElement(work, 'dc:creator').text = "Automataii Base Generator"


def _add_comprehensive_styles(svg: ET.Element, config: BaseConfiguration, export_mode: str):
    """Add comprehensive CSS styles for different elements and export modes."""
    style = ET.SubElement(svg, 'style', {'type': 'text/css'})
    
    # Base styles for different materials
    material_colors = {
        MaterialType.WOOD: '#8B4513',
        MaterialType.MDF: '#D2691E',
        MaterialType.PLYWOOD: '#DEB887',
        MaterialType.ACRYLIC: '#87CEEB',
        MaterialType.ALUMINUM: '#C0C0C0',
        MaterialType.STEEL: '#708090',
        MaterialType.PLASTIC_3D_PRINTED: '#FF6347',
        MaterialType.RESIN_3D_PRINTED: '#FFD700',
        MaterialType.CARDBOARD: '#F4A460',
        MaterialType.COMPOSITE: '#696969',
    }
    
    base_color = material_colors.get(config.primary_material, '#808080')
    
    if export_mode == "laser":
        # Laser cutting specific styles
        style.text = """
            /* Laser cutting styles - optimized for manufacturing */
            .base-outline { fill: none; stroke: #FF0000; stroke-width: 0.1mm; }
            .cut-line { fill: none; stroke: #FF0000; stroke-width: 0.1mm; }
            .engrave-line { fill: none; stroke: #0000FF; stroke-width: 0.1mm; }
            .mounting-hole { fill: none; stroke: #FF0000; stroke-width: 0.1mm; }
            .construction-line { display: none; }
            .dimension-line { display: none; }
            .dimension-text { display: none; }
            .label-text { display: none; }
            .grid-line { display: none; }
            .annotation { display: none; }
        """
    elif export_mode == "print":
        # Print/documentation styles
        style.text = f"""
            /* Print documentation styles */
            .base-outline {{ fill: none; stroke: #000000; stroke-width: 1pt; }}
            .base-fill {{ fill: {base_color}; fill-opacity: 0.1; }}
            .cut-line {{ fill: none; stroke: #FF0000; stroke-width: 0.5pt; stroke-dasharray: 5,3; }}
            .engrave-line {{ fill: none; stroke: #0000FF; stroke-width: 0.5pt; stroke-dasharray: 2,2; }}
            .mounting-hole {{ fill: #FFFFFF; stroke: #000000; stroke-width: 0.5pt; }}
            .countersink {{ fill: none; stroke: #666666; stroke-width: 0.5pt; stroke-dasharray: 1,1; }}
            .construction-line {{ fill: none; stroke: #CCCCCC; stroke-width: 0.25pt; stroke-dasharray: 3,3; }}
            .dimension-line {{ stroke: #0000FF; stroke-width: 0.25pt; }}
            .dimension-text {{ font-family: Arial, sans-serif; font-size: 10pt; fill: #0000FF; }}
            .label-text {{ font-family: Arial, sans-serif; font-size: 8pt; fill: #000000; }}
            .grid-line {{ stroke: #E0E0E0; stroke-width: 0.1pt; }}
            .annotation {{ font-family: Arial, sans-serif; font-size: 12pt; fill: #000000; }}
            .title-block {{ fill: none; stroke: #000000; stroke-width: 1pt; }}
            .title-text {{ font-family: Arial, sans-serif; font-size: 14pt; fill: #000000; font-weight: bold; }}
        """
    else:  # display mode
        # Rich display styles with material visualization
        style.text = f"""
            /* Display/visualization styles */
            .base-outline {{ fill: none; stroke: #000000; stroke-width: 2px; }}
            .base-fill {{ fill: {base_color}; fill-opacity: 0.3; }}
            .base-shadow {{ fill: #000000; fill-opacity: 0.2; filter: url(#dropshadow); }}
            .cut-line {{ fill: none; stroke: #FF0000; stroke-width: 1.5px; stroke-dasharray: 8,4; }}
            .engrave-line {{ fill: none; stroke: #0066CC; stroke-width: 1px; stroke-dasharray: 4,2; }}
            .mounting-hole {{ fill: #FFFFFF; stroke: #CC0000; stroke-width: 1.5px; }}
            .countersink {{ fill: none; stroke: #FF6666; stroke-width: 1px; stroke-dasharray: 2,2; }}
            .construction-line {{ fill: none; stroke: #CCCCCC; stroke-width: 0.5px; stroke-dasharray: 5,5; }}
            .dimension-line {{ stroke: #0000FF; stroke-width: 0.5px; }}
            .dimension-text {{ font-family: 'Courier New', monospace; font-size: 12px; fill: #0000FF; }}
            .dimension-arrow {{ fill: #0000FF; }}
            .label-text {{ font-family: Arial, sans-serif; font-size: 10px; fill: #333333; }}
            .label-background {{ fill: #FFFFFF; fill-opacity: 0.8; stroke: #CCCCCC; stroke-width: 0.5px; }}
            .grid-line {{ stroke: #F0F0F0; stroke-width: 0.5px; }}
            .grid-major {{ stroke: #E0E0E0; stroke-width: 1px; }}
            .annotation {{ font-family: Arial, sans-serif; font-size: 14px; fill: #000000; }}
            
            /* Base type specific styles */
            .flat-base {{ }}
            .box-base {{ stroke-dasharray: none; }}
            .pedestal-base {{ stroke-width: 2.5px; }}
            .wall-mounted-base {{ stroke-dasharray: 10,5; }}
            .modular-base {{ stroke-dasharray: 5,2,2,2; }}
            
            /* Interactive hover effects for display mode */
            .mounting-hole:hover {{ fill: #FFE0E0; stroke-width: 2px; }}
            .base-outline:hover {{ stroke-width: 3px; }}
        """


def _add_svg_definitions(defs: ET.Element, grid_size: float):
    """Add SVG definitions for patterns, markers, filters, etc."""
    # Arrow markers for dimension lines
    arrow = ET.SubElement(defs, 'marker', {
        'id': 'dimension-arrow',
        'markerWidth': '10',
        'markerHeight': '7',
        'refX': '10',
        'refY': '3.5',
        'orient': 'auto',
        'markerUnits': 'strokeWidth'
    })
    ET.SubElement(arrow, 'polygon', {
        'points': '0,0 10,3.5 0,7',
        'fill': '#0000FF',
        'stroke': 'none'
    })
    
    # Grid pattern
    pattern = ET.SubElement(defs, 'pattern', {
        'id': 'grid-pattern',
        'x': '0',
        'y': '0',
        'width': str(grid_size),
        'height': str(grid_size),
        'patternUnits': 'userSpaceOnUse'
    })
    ET.SubElement(pattern, 'line', {
        'x1': '0',
        'y1': '0',
        'x2': '0',
        'y2': str(grid_size),
        'class': 'grid-line'
    })
    ET.SubElement(pattern, 'line', {
        'x1': '0',
        'y1': '0',
        'x2': str(grid_size),
        'y2': '0',
        'class': 'grid-line'
    })
    
    # Drop shadow filter
    filter_shadow = ET.SubElement(defs, 'filter', {
        'id': 'dropshadow',
        'x': '-50%',
        'y': '-50%',
        'width': '200%',
        'height': '200%'
    })
    ET.SubElement(filter_shadow, 'feGaussianBlur', {
        'in': 'SourceAlpha',
        'stdDeviation': '3'
    })
    ET.SubElement(filter_shadow, 'feOffset', {
        'dx': '2',
        'dy': '2',
        'result': 'offsetblur'
    })
    ET.SubElement(filter_shadow, 'feComponentTransfer')
    ET.SubElement(filter_shadow, 'feMerge')
    
    # Texture patterns for different materials
    _add_material_patterns(defs)


def _add_material_patterns(defs: ET.Element):
    """Add texture patterns for different materials."""
    # Wood grain pattern
    wood_pattern = ET.SubElement(defs, 'pattern', {
        'id': 'wood-grain',
        'x': '0',
        'y': '0',
        'width': '100',
        'height': '100',
        'patternUnits': 'userSpaceOnUse'
    })
    for i in range(5):
        ET.SubElement(wood_pattern, 'line', {
            'x1': '0',
            'y1': str(i * 20),
            'x2': '100',
            'y2': str(i * 20 + 10),
            'stroke': '#654321',
            'stroke-width': '0.5',
            'opacity': '0.3'
        })
    
    # Metal brushed pattern
    metal_pattern = ET.SubElement(defs, 'pattern', {
        'id': 'metal-brushed',
        'x': '0',
        'y': '0',
        'width': '4',
        'height': '4',
        'patternUnits': 'userSpaceOnUse'
    })
    ET.SubElement(metal_pattern, 'rect', {
        'x': '0',
        'y': '0',
        'width': '4',
        'height': '4',
        'fill': '#C0C0C0'
    })
    ET.SubElement(metal_pattern, 'line', {
        'x1': '0',
        'y1': '0',
        'x2': '0',
        'y2': '4',
        'stroke': '#A0A0A0',
        'stroke-width': '0.5'
    })


def _create_layer_structure(svg: ET.Element) -> Dict[str, ET.Element]:
    """Create organized layer structure for the SVG."""
    layers = {}
    
    # Create layers in proper z-order
    layer_names = [
        'grid', 'shadow', 'fill', 'construction', 'outline', 
        'mounting', 'engrave', 'dimensions', 'labels', 'annotations'
    ]
    
    for name in layer_names:
        layers[name] = ET.SubElement(svg, 'g', {
            'id': f'layer-{name}',
            'class': f'{name}-layer'
        })
    
    return layers


def _add_grid(layer: ET.Element, width: float, height: float, grid_size: float, margin: float):
    """Add background grid for reference."""
    # Major grid lines every 5 units
    major_grid = 5 * grid_size
    
    # Vertical lines
    x = 0
    while x <= width:
        ET.SubElement(layer, 'line', {
            'x1': str(x),
            'y1': str(-margin),
            'x2': str(x),
            'y2': str(height + margin),
            'class': 'grid-major' if x % major_grid == 0 else 'grid-line'
        })
        x += grid_size
    
    # Horizontal lines
    y = 0
    while y <= height:
        ET.SubElement(layer, 'line', {
            'x1': str(-margin),
            'y1': str(y),
            'x2': str(width + margin),
            'y2': str(y),
            'class': 'grid-major' if y % major_grid == 0 else 'grid-line'
        })
        y += grid_size


def _draw_base_outline(layer: ET.Element, config: BaseConfiguration, width: float, height: float, scale: float):
    """Draw the main base outline with appropriate styling."""
    # Add shadow first (in shadow layer)
    shadow_layer = layer.parentNode.querySelector('#layer-shadow') if hasattr(layer, 'parentNode') else None
    
    # Add fill (in fill layer)
    fill_layer = layer.parentNode.querySelector('#layer-fill') if hasattr(layer, 'parentNode') else None
    
    # Get base type specific class
    base_class = f"{config.base_type.value.replace('_', '-')}-base"
    
    if config.base_type == BaseType.FLAT_RECTANGULAR:
        # Rounded rectangle for flat rectangular base
        rect_attrs = {
            'x': '0',
            'y': '0',
            'width': str(width),
            'height': str(height),
            'rx': str(5 * scale),  # Scaled rounded corners
            'ry': str(5 * scale),
            'class': f'base-outline {base_class}'
        }
        ET.SubElement(layer, 'rect', rect_attrs)
        
    elif config.base_type == BaseType.FLAT_CIRCULAR:
        # Circle for flat circular base
        cx = width / 2
        cy = height / 2
        radius = min(width, height) / 2
        circle_attrs = {
            'cx': str(cx),
            'cy': str(cy),
            'r': str(radius),
            'class': f'base-outline {base_class}'
        }
        ET.SubElement(layer, 'circle', circle_attrs)
        
    elif config.base_type in [BaseType.BOX_ENCLOSED, BaseType.BOX_OPEN]:
        # Box bases - show as rectangle with internal divisions
        rect_attrs = {
            'x': '0',
            'y': '0',
            'width': str(width),
            'height': str(height),
            'class': f'base-outline {base_class}'
        }
        ET.SubElement(layer, 'rect', rect_attrs)
        
    elif config.base_type == BaseType.PEDESTAL:
        # Pedestal - show as rounded rectangle with thicker outline
        rect_attrs = {
            'x': '0',
            'y': '0',
            'width': str(width),
            'height': str(height),
            'rx': str(10 * scale),
            'ry': str(10 * scale),
            'class': f'base-outline {base_class}'
        }
        ET.SubElement(layer, 'rect', rect_attrs)
        
    elif config.base_type == BaseType.WALL_MOUNTED:
        # Wall mounted - rectangle with mounting brackets indicated
        rect_attrs = {
            'x': '0',
            'y': '0',
            'width': str(width),
            'height': str(height),
            'class': f'base-outline {base_class}'
        }
        ET.SubElement(layer, 'rect', rect_attrs)
        
        # Add bracket indicators
        bracket_width = width * 0.1
        bracket_height = height * 0.05
        for x in [0, width - bracket_width]:
            ET.SubElement(layer, 'rect', {
                'x': str(x),
                'y': str(-bracket_height),
                'width': str(bracket_width),
                'height': str(bracket_height),
                'class': 'cut-line'
            })
            
    elif config.base_type == BaseType.MODULAR:
        # Modular - show connection points
        rect_attrs = {
            'x': '0',
            'y': '0',
            'width': str(width),
            'height': str(height),
            'class': f'base-outline {base_class}'
        }
        ET.SubElement(layer, 'rect', rect_attrs)
        
        # Add modular connection indicators
        connection_size = 10 * scale
        for x in [0, width/2 - connection_size/2, width - connection_size]:
            for y in [0, height - connection_size]:
                ET.SubElement(layer, 'rect', {
                    'x': str(x),
                    'y': str(y),
                    'width': str(connection_size),
                    'height': str(connection_size),
                    'class': 'engrave-line'
                })
    
    else:  # CUSTOM or default
        # Default rectangle
        rect_attrs = {
            'x': '0',
            'y': '0',
            'width': str(width),
            'height': str(height),
            'class': f'base-outline {base_class}'
        }
        ET.SubElement(layer, 'rect', rect_attrs)


def _add_construction_lines(layer: ET.Element, config: BaseConfiguration, width: float, height: float, scale: float):
    """Add construction/fold lines for box-type bases."""
    if config.base_type == BaseType.BOX_ENCLOSED:
        # Add fold lines for box sides
        wall_height = config.dimensions.depth * scale if config.is_3d else 50 * scale
        
        # Top and bottom fold lines
        for y in [0, height]:
            ET.SubElement(layer, 'line', {
                'x1': '0',
                'y1': str(y),
                'x2': str(width),
                'y2': str(y),
                'class': 'construction-line'
            })
        
        # Side fold lines
        for x in [0, width]:
            ET.SubElement(layer, 'line', {
                'x1': str(x),
                'y1': '0',
                'x2': str(x),
                'y2': str(height),
                'class': 'construction-line'
            })
        
        # Add tabs for assembly
        tab_width = 20 * scale
        tab_positions = [width * 0.25, width * 0.5, width * 0.75]
        for pos in tab_positions:
            # Top tabs
            ET.SubElement(layer, 'rect', {
                'x': str(pos - tab_width/2),
                'y': str(-tab_width),
                'width': str(tab_width),
                'height': str(tab_width),
                'class': 'cut-line'
            })
            # Bottom tabs
            ET.SubElement(layer, 'rect', {
                'x': str(pos - tab_width/2),
                'y': str(height),
                'width': str(tab_width),
                'height': str(tab_width),
                'class': 'cut-line'
            })


def _draw_mounting_points(layer: ET.Element, config: BaseConfiguration, scale: float, export_mode: str):
    """Draw mounting points with appropriate detail."""
    for i, mp in enumerate(config.mounting_points):
        if isinstance(mp.position, Point2D):
            x = mp.position.x * scale
            y = mp.position.y * scale
            r = mp.hole_diameter * scale / 2
            
            # Main mounting hole
            hole = ET.SubElement(layer, 'circle', {
                'cx': str(x),
                'cy': str(y),
                'r': str(r),
                'class': 'mounting-hole',
                'id': f'mounting-hole-{i}'
            })
            
            # Add countersink if present
            if mp.countersink and mp.countersink_diameter:
                cs_r = mp.countersink_diameter * scale / 2
                ET.SubElement(layer, 'circle', {
                    'cx': str(x),
                    'cy': str(y),
                    'r': str(cs_r),
                    'class': 'countersink'
                })
            
            # Add cross-hairs for precise positioning (not in laser mode)
            if export_mode != "laser":
                # Horizontal line
                ET.SubElement(layer, 'line', {
                    'x1': str(x - r - 5),
                    'y1': str(y),
                    'x2': str(x + r + 5),
                    'y2': str(y),
                    'class': 'construction-line'
                })
                # Vertical line
                ET.SubElement(layer, 'line', {
                    'x1': str(x),
                    'y1': str(y - r - 5),
                    'x2': str(x),
                    'y2': str(y + r + 5),
                    'class': 'construction-line'
                })


def _add_engrave_details(layer: ET.Element, config: BaseConfiguration, width: float, height: float, scale: float):
    """Add engraving details like logos, text, or decorative elements."""
    # Add part name/ID
    if config.name:
        text_size = 12 * scale
        ET.SubElement(layer, 'text', {
            'x': str(width / 2),
            'y': str(height - 10 * scale),
            'text-anchor': 'middle',
            'font-size': str(text_size),
            'class': 'engrave-line'
        }).text = config.name
    
    # Add material type indicator
    material_text = config.primary_material.value.upper()
    ET.SubElement(layer, 'text', {
        'x': str(10 * scale),
        'y': str(height - 10 * scale),
        'text-anchor': 'start',
        'font-size': str(8 * scale),
        'class': 'engrave-line'
    }).text = material_text
    
    # Add decorative corner marks for certain base types
    if config.base_type in [BaseType.BOX_ENCLOSED, BaseType.PEDESTAL]:
        corner_size = 15 * scale
        corners = [
            (0, 0, 1, 1),  # top-left
            (width - corner_size, 0, -1, 1),  # top-right
            (0, height - corner_size, 1, -1),  # bottom-left
            (width - corner_size, height - corner_size, -1, -1)  # bottom-right
        ]
        
        for x, y, dx, dy in corners:
            # L-shaped corner marks
            path = f"M {x} {y + corner_size * dy} L {x} {y} L {x + corner_size * dx} {y}"
            ET.SubElement(layer, 'path', {
                'd': path,
                'class': 'engrave-line',
                'fill': 'none'
            })


def _add_comprehensive_dimensions(layer: ET.Element, config: BaseConfiguration, width: float, height: float, scale: float):
    """Add comprehensive dimension annotations."""
    offset = 25
    
    # Width dimension
    _add_dimension_line_enhanced(
        layer,
        (0, -offset),
        (width, -offset),
        f"{config.footprint.width:.1f} {config.footprint.unit.value}",
        'horizontal'
    )
    
    # Height dimension
    _add_dimension_line_enhanced(
        layer,
        (-offset, 0),
        (-offset, height),
        f"{config.footprint.height:.1f} {config.footprint.unit.value}",
        'vertical'
    )
    
    # Add depth dimension for 3D bases
    if config.is_3d and isinstance(config.dimensions, Dimensions3D):
        # Show depth as isometric projection
        depth_offset = 40
        ET.SubElement(layer, 'text', {
            'x': str(width + depth_offset),
            'y': str(height / 2),
            'text-anchor': 'middle',
            'class': 'dimension-text',
            'transform': f'rotate(-90 {width + depth_offset} {height / 2})'
        }).text = f"Depth: {config.dimensions.depth:.1f} {config.dimensions.unit.value}"
    
    # Add mounting hole dimensions
    if config.mounting_points:
        for i, mp in enumerate(config.mounting_points[:2]):  # Show first two for clarity
            if isinstance(mp.position, Point2D):
                x = mp.position.x * scale
                y = mp.position.y * scale
                
                # Dimension from edge
                if i == 0:  # First hole
                    _add_dimension_line_enhanced(
                        layer,
                        (0, y + 15),
                        (x, y + 15),
                        f"{mp.position.x:.1f}",
                        'horizontal',
                        arrow_size=5
                    )
                    _add_dimension_line_enhanced(
                        layer,
                        (x + 15, 0),
                        (x + 15, y),
                        f"{mp.position.y:.1f}",
                        'vertical',
                        arrow_size=5
                    )
    
    # Material thickness annotation
    if config.material_thickness:
        ET.SubElement(layer, 'text', {
            'x': str(width / 2),
            'y': str(-offset - 20),
            'text-anchor': 'middle',
            'class': 'annotation'
        }).text = f"Material Thickness: {config.material_thickness} {config.footprint.unit.value}"


def _add_dimension_line_enhanced(
    parent: ET.Element,
    start: Tuple[float, float],
    end: Tuple[float, float],
    text: str,
    orientation: str = 'horizontal',
    arrow_size: float = 10
):
    """Add enhanced dimension line with proper arrows and text positioning."""
    # Create dimension group
    dim_group = ET.SubElement(parent, 'g', {'class': 'dimension-group'})
    
    # Extension lines
    ext_length = 10
    if orientation == 'horizontal':
        # Left extension
        ET.SubElement(dim_group, 'line', {
            'x1': str(start[0]),
            'y1': str(start[1] - ext_length),
            'x2': str(start[0]),
            'y2': str(start[1] + 5),
            'class': 'dimension-line'
        })
        # Right extension
        ET.SubElement(dim_group, 'line', {
            'x1': str(end[0]),
            'y1': str(end[1] - ext_length),
            'x2': str(end[0]),
            'y2': str(end[1] + 5),
            'class': 'dimension-line'
        })
    else:  # vertical
        # Top extension
        ET.SubElement(dim_group, 'line', {
            'x1': str(start[0] - ext_length),
            'y1': str(start[1]),
            'x2': str(start[0] + 5),
            'y2': str(start[1]),
            'class': 'dimension-line'
        })
        # Bottom extension
        ET.SubElement(dim_group, 'line', {
            'x1': str(end[0] - ext_length),
            'y1': str(end[1]),
            'x2': str(end[0] + 5),
            'y2': str(end[1]),
            'class': 'dimension-line'
        })
    
    # Main dimension line
    ET.SubElement(dim_group, 'line', {
        'x1': str(start[0]),
        'y1': str(start[1]),
        'x2': str(end[0]),
        'y2': str(end[1]),
        'class': 'dimension-line',
        'marker-start': 'url(#dimension-arrow)',
        'marker-end': 'url(#dimension-arrow)'
    })
    
    # Add text with background
    mid_x = (start[0] + end[0]) / 2
    mid_y = (start[1] + end[1]) / 2
    
    # Text background for better readability
    text_elem = ET.SubElement(dim_group, 'text', {
        'x': str(mid_x),
        'y': str(mid_y + (5 if orientation == 'horizontal' else 0)),
        'class': 'dimension-text',
        'text-anchor': 'middle',
        'dominant-baseline': 'middle'
    })
    text_elem.text = text


def _add_labels_and_annotations(layer: ET.Element, config: BaseConfiguration, width: float, height: float, scale: float):
    """Add labels and annotations for clarity."""
    # Add mounting point labels
    for i, mp in enumerate(config.mounting_points):
        if isinstance(mp.position, Point2D):
            x = mp.position.x * scale
            y = mp.position.y * scale
            
            # Create label with background
            label_group = ET.SubElement(layer, 'g', {'class': 'label-group'})
            
            # Background rectangle
            label_width = 30
            label_height = 15
            ET.SubElement(label_group, 'rect', {
                'x': str(x + 10),
                'y': str(y - label_height/2),
                'width': str(label_width),
                'height': str(label_height),
                'rx': '3',
                'class': 'label-background'
            })
            
            # Label text
            ET.SubElement(label_group, 'text', {
                'x': str(x + 10 + label_width/2),
                'y': str(y),
                'text-anchor': 'middle',
                'dominant-baseline': 'middle',
                'class': 'label-text'
            }).text = f"H{i+1}"
            
            # Add hole size annotation
            hole_text = f"⌀{mp.hole_diameter}{config.footprint.unit.value}"
            ET.SubElement(label_group, 'text', {
                'x': str(x + 10 + label_width/2),
                'y': str(y + 12),
                'text-anchor': 'middle',
                'class': 'label-text',
                'font-size': '8'
            }).text = hole_text
    
    # Add assembly method annotation
    if config.assembly_method:
        assembly_text = f"Assembly: {config.assembly_method.value.replace('_', ' ').title()}"
        ET.SubElement(layer, 'text', {
            'x': str(10),
            'y': str(20),
            'text-anchor': 'start',
            'class': 'annotation'
        }).text = assembly_text
    
    # Add weight/load annotations if available
    annotations_y = 40
    if config.weight:
        ET.SubElement(layer, 'text', {
            'x': str(10),
            'y': str(annotations_y),
            'text-anchor': 'start',
            'class': 'label-text'
        }).text = f"Weight: {config.weight} kg"
        annotations_y += 15
    
    if config.max_load:
        ET.SubElement(layer, 'text', {
            'x': str(10),
            'y': str(annotations_y),
            'text-anchor': 'start',
            'class': 'label-text'
        }).text = f"Max Load: {config.max_load} kg"


def _add_title_block(layer: ET.Element, config: BaseConfiguration, width: float, height: float, margin: float):
    """Add professional title block for printed documentation."""
    # Title block dimensions
    tb_width = 200
    tb_height = 100
    tb_x = width - tb_width + margin/2
    tb_y = height + margin/2
    
    # Title block border
    ET.SubElement(layer, 'rect', {
        'x': str(tb_x),
        'y': str(tb_y),
        'width': str(tb_width),
        'height': str(tb_height),
        'class': 'title-block'
    })
    
    # Horizontal divisions
    divisions = [30, 50, 70]
    for y_offset in divisions:
        ET.SubElement(layer, 'line', {
            'x1': str(tb_x),
            'y1': str(tb_y + y_offset),
            'x2': str(tb_x + tb_width),
            'y2': str(tb_y + y_offset),
            'class': 'title-block'
        })
    
    # Title
    ET.SubElement(layer, 'text', {
        'x': str(tb_x + tb_width/2),
        'y': str(tb_y + 20),
        'text-anchor': 'middle',
        'class': 'title-text'
    }).text = config.name
    
    # Details
    details = [
        (f"Type: {config.base_type.value}", tb_y + 40),
        (f"Material: {config.primary_material.value}", tb_y + 60),
        (f"Date: {datetime.now().strftime('%Y-%m-%d')}", tb_y + 80),
        (f"Scale: 1:{int(1/scale)}" if scale != 1 else "Scale: 1:1", tb_y + 95)
    ]
    
    for text, y_pos in details:
        ET.SubElement(layer, 'text', {
            'x': str(tb_x + 10),
            'y': str(y_pos),
            'text-anchor': 'start',
            'class': 'label-text'
        }).text = text


def _pretty_print_svg(elem: ET.Element) -> str:
    """Pretty print SVG with proper indentation."""
    import xml.dom.minidom
    
    # Convert to string first
    rough_string = ET.tostring(elem, encoding='unicode')
    
    # Parse and pretty print
    dom = xml.dom.minidom.parseString(rough_string)
    pretty_string = dom.toprettyxml(indent='  ')
    
    # Remove extra blank lines
    lines = pretty_string.split('\n')
    cleaned_lines = [line for line in lines if line.strip()]
    
    return '\n'.join(cleaned_lines)


def base_to_dxf(
    config: BaseConfiguration,
    scale: float = 1.0,
    layer_config: Optional[Dict[str, Dict[str, any]]] = None,
    export_mode: str = "manufacturing",  # "manufacturing", "documentation", "laser"
    include_dimensions: bool = False,
    include_annotations: bool = False,
    units: str = "MILLIMETERS",
) -> str:
    """
    Convert base configuration to professional DXF format.
    
    This generates DXF files suitable for CAD/CAM software, laser cutters, and CNC machines
    with proper layer structure, entity types, and manufacturing-ready geometry.
    
    Args:
        config: Base configuration to convert
        scale: Scale factor for output (default 1.0 = 1:1)
        layer_config: Custom layer configuration with colors and linetypes
        export_mode: Export mode - "manufacturing", "documentation", or "laser"
        include_dimensions: Whether to include dimension entities
        include_annotations: Whether to include text annotations
        units: Drawing units (MILLIMETERS, INCHES, etc.)
        
    Returns:
        Complete DXF file content as string
    """
    # Initialize DXF builder
    dxf = DXFBuilder(units=units)
    
    # Set up default layer configuration if not provided
    if layer_config is None:
        layer_config = _get_default_layer_config(export_mode)
    
    # Create layers
    for layer_name, layer_props in layer_config.items():
        dxf.add_layer(
            name=layer_name,
            color=layer_props.get('color', 7),  # 7 = white/black
            linetype=layer_props.get('linetype', 'CONTINUOUS'),
            lineweight=layer_props.get('lineweight', 0)
        )
    
    # Get scaled dimensions
    footprint = config.footprint
    width = footprint.width * scale
    height = footprint.height * scale
    
    # Set up drawing limits
    dxf.set_limits(0, 0, width * 1.2, height * 1.2)
    
    # Draw base geometry based on type
    _draw_base_geometry_dxf(dxf, config, width, height, scale, export_mode)
    
    # Add mounting points
    _draw_mounting_points_dxf(dxf, config, scale, export_mode)
    
    # Add construction geometry if needed
    if config.base_type in [BaseType.BOX_ENCLOSED, BaseType.BOX_OPEN, BaseType.PEDESTAL]:
        _add_construction_geometry_dxf(dxf, config, width, height, scale)
    
    # Add dimensions if requested
    if include_dimensions and export_mode != "laser":
        _add_dimensions_dxf(dxf, config, width, height, scale)
    
    # Add annotations if requested
    if include_annotations and export_mode != "laser":
        _add_annotations_dxf(dxf, config, width, height, scale)
    
    # Add manufacturing notes
    if export_mode == "manufacturing":
        _add_manufacturing_notes_dxf(dxf, config, width, height)
    
    # Generate complete DXF file
    return dxf.generate()


class DXFBuilder:
    """Professional DXF file builder with proper structure and entity support."""
    
    def __init__(self, units: str = "MILLIMETERS"):
        self.units = units
        self.layers = {}
        self.entities = []
        self.header_vars = {}
        self.limits = (0, 0, 100, 100)
        self._init_header()
    
    def _init_header(self):
        """Initialize standard header variables."""
        self.header_vars = {
            '$ACADVER': 'AC1024',  # AutoCAD 2010
            '$INSBASE': (0.0, 0.0, 0.0),
            '$EXTMIN': (0.0, 0.0, 0.0),
            '$EXTMAX': (100.0, 100.0, 0.0),
            '$LIMMIN': (0.0, 0.0),
            '$LIMMAX': (100.0, 100.0),
            '$ORTHOMODE': 0,
            '$REGENMODE': 1,
            '$FILLMODE': 1,
            '$QTEXTMODE': 0,
            '$MIRRTEXT': 1,
            '$LTSCALE': 1.0,
            '$ATTMODE': 1,
            '$TEXTSIZE': 2.5,
            '$TRACEWID': 1.0,
            '$TEXTSTYLE': 'STANDARD',
            '$CLAYER': '0',
            '$CELTYPE': 'BYLAYER',
            '$CECOLOR': 256,
            '$CELTSCALE': 1.0,
            '$DISPSILH': 0,
            '$DIMSCALE': 1.0,
            '$DIMASZ': 2.5,
            '$DIMEXO': 0.625,
            '$DIMDLI': 3.75,
            '$DIMRND': 0.0,
            '$DIMDLE': 0.0,
            '$DIMEXE': 1.25,
            '$DIMTP': 0.0,
            '$DIMTM': 0.0,
            '$DIMTXT': 2.5,
            '$DIMCEN': 2.5,
            '$DIMTSZ': 0.0,
            '$DIMTOL': 0,
            '$DIMLIM': 0,
            '$DIMTIH': 0,
            '$DIMTOH': 0,
            '$DIMSE1': 0,
            '$DIMSE2': 0,
            '$DIMTAD': 1,
            '$DIMZIN': 8,
            '$DIMBLK': '',
            '$DIMASO': 1,
            '$DIMSHO': 1,
            '$DIMPOST': '',
            '$DIMAPOST': '',
            '$DIMALT': 0,
            '$DIMALTD': 3,
            '$DIMALTF': 0.03937,
            '$DIMLFAC': 1.0,
            '$DIMTOFL': 1,
            '$DIMTVP': 0.0,
            '$DIMTIX': 0,
            '$DIMSOXD': 0,
            '$DIMSAH': 0,
            '$DIMBLK1': '',
            '$DIMBLK2': '',
            '$DIMSTYLE': 'STANDARD',
            '$DIMCLRD': 0,
            '$DIMCLRE': 0,
            '$DIMCLRT': 0,
            '$DIMTFAC': 1.0,
            '$DIMGAP': 0.625,
            '$DIMJUST': 0,
            '$DIMSD1': 0,
            '$DIMSD2': 0,
            '$DIMTOLJ': 0,
            '$DIMTZIN': 8,
            '$DIMALTZ': 0,
            '$DIMALTTZ': 0,
            '$DIMUPT': 0,
            '$DIMDEC': 2,
            '$DIMTDEC': 2,
            '$DIMALTU': 2,
            '$DIMALTTD': 3,
            '$DIMTXSTY': 'STANDARD',
            '$DIMAUNIT': 0,
            '$DIMADEC': 0,
            '$DIMALTRND': 0.0,
            '$DIMAZIN': 0,
            '$DIMDSEP': '.',
            '$DIMATFIT': 3,
            '$DIMFRAC': 0,
            '$DIMLDRBLK': '',
            '$DIMLUNIT': 2,
            '$DIMLWD': -2,
            '$DIMLWE': -2,
            '$DIMTMOVE': 0,
            '$LUNITS': 2,
            '$LUPREC': 4,
            '$SKETCHINC': 1.0,
            '$FILLETRAD': 0.0,
            '$AUNITS': 0,
            '$AUPREC': 0,
            '$MENU': '.',
            '$ELEVATION': 0.0,
            '$PELEVATION': 0.0,
            '$THICKNESS': 0.0,
            '$LIMCHECK': 0,
            '$CHAMFERA': 0.0,
            '$CHAMFERB': 0.0,
            '$CHAMFERC': 0.0,
            '$CHAMFERD': 0.0,
            '$SKPOLY': 0,
            '$TDCREATE': 2459000.0,  # Julian date
            '$TDUCREATE': 2459000.0,
            '$TDUPDATE': 2459000.0,
            '$TDUUPDATE': 2459000.0,
            '$TDINDWG': 0.0,
            '$TDUSRTIMER': 0.0,
            '$USRTIMER': 1,
            '$ANGBASE': 0.0,
            '$ANGDIR': 0,
            '$PDMODE': 0,
            '$PDSIZE': 0.0,
            '$PLINEWID': 0.0,
            '$SPLFRAME': 0,
            '$SPLINETYPE': 6,
            '$SPLINESEGS': 8,
            '$HANDSEED': 'FFF',
            '$SURFTAB1': 6,
            '$SURFTAB2': 6,
            '$SURFTYPE': 6,
            '$SURFU': 6,
            '$SURFV': 6,
            '$UCSBASE': '',
            '$UCSNAME': '',
            '$UCSORG': (0.0, 0.0, 0.0),
            '$UCSXDIR': (1.0, 0.0, 0.0),
            '$UCSYDIR': (0.0, 1.0, 0.0),
            '$UCSORTHOREF': '',
            '$UCSORTHOVIEW': 0,
            '$UCSORGTOP': (0.0, 0.0, 0.0),
            '$UCSORGBOTTOM': (0.0, 0.0, 0.0),
            '$UCSORGLEFT': (0.0, 0.0, 0.0),
            '$UCSORGRIGHT': (0.0, 0.0, 0.0),
            '$UCSORGFRONT': (0.0, 0.0, 0.0),
            '$UCSORGBACK': (0.0, 0.0, 0.0),
            '$PUCSBASE': '',
            '$PUCSNAME': '',
            '$PUCSORG': (0.0, 0.0, 0.0),
            '$PUCSXDIR': (1.0, 0.0, 0.0),
            '$PUCSYDIR': (0.0, 1.0, 0.0),
            '$PUCSORTHOREF': '',
            '$PUCSORTHOVIEW': 0,
            '$PUCSORGTOP': (0.0, 0.0, 0.0),
            '$PUCSORGBOTTOM': (0.0, 0.0, 0.0),
            '$PUCSORGLEFT': (0.0, 0.0, 0.0),
            '$PUCSORGRIGHT': (0.0, 0.0, 0.0),
            '$PUCSORGFRONT': (0.0, 0.0, 0.0),
            '$PUCSORGBACK': (0.0, 0.0, 0.0),
            '$USERI1': 0,
            '$USERI2': 0,
            '$USERI3': 0,
            '$USERI4': 0,
            '$USERI5': 0,
            '$USERR1': 0.0,
            '$USERR2': 0.0,
            '$USERR3': 0.0,
            '$USERR4': 0.0,
            '$USERR5': 0.0,
            '$WORLDVIEW': 1,
            '$SHADEDGE': 3,
            '$SHADEDIF': 70,
            '$TILEMODE': 1,
            '$MAXACTVP': 64,
            '$PINSBASE': (0.0, 0.0, 0.0),
            '$PLIMCHECK': 0,
            '$PEXTMIN': (0.0, 0.0, 0.0),
            '$PEXTMAX': (0.0, 0.0, 0.0),
            '$PLIMMIN': (0.0, 0.0),
            '$PLIMMAX': (12.0, 9.0),
            '$UNITMODE': 0,
            '$VISRETAIN': 1,
            '$PLINEGEN': 0,
            '$PSLTSCALE': 1,
            '$TREEDEPTH': 3020,
            '$CMLSTYLE': 'STANDARD',
            '$CMLJUST': 0,
            '$CMLSCALE': 1.0,
            '$PROXYGRAPHICS': 1,
            '$MEASUREMENT': 1 if self.units == 'MILLIMETERS' else 0,
        }
    
    def set_limits(self, x_min: float, y_min: float, x_max: float, y_max: float):
        """Set drawing limits."""
        self.limits = (x_min, y_min, x_max, y_max)
        self.header_vars['$LIMMIN'] = (x_min, y_min)
        self.header_vars['$LIMMAX'] = (x_max, y_max)
        self.header_vars['$EXTMIN'] = (x_min, y_min, 0.0)
        self.header_vars['$EXTMAX'] = (x_max, y_max, 0.0)
    
    def add_layer(self, name: str, color: int = 7, linetype: str = 'CONTINUOUS', lineweight: int = 0):
        """Add a layer definition."""
        self.layers[name] = {
            'color': color,
            'linetype': linetype,
            'lineweight': lineweight,
            'frozen': False,
            'locked': False,
            'on': True
        }
    
    def add_line(self, start: Tuple[float, float], end: Tuple[float, float], layer: str = '0', color: Optional[int] = None):
        """Add a line entity."""
        self.entities.append({
            'type': 'LINE',
            'layer': layer,
            'color': color,
            'start': start,
            'end': end
        })
    
    def add_circle(self, center: Tuple[float, float], radius: float, layer: str = '0', color: Optional[int] = None):
        """Add a circle entity."""
        self.entities.append({
            'type': 'CIRCLE',
            'layer': layer,
            'color': color,
            'center': center,
            'radius': radius
        })
    
    def add_arc(self, center: Tuple[float, float], radius: float, start_angle: float, end_angle: float, 
                layer: str = '0', color: Optional[int] = None):
        """Add an arc entity."""
        self.entities.append({
            'type': 'ARC',
            'layer': layer,
            'color': color,
            'center': center,
            'radius': radius,
            'start_angle': start_angle,
            'end_angle': end_angle
        })
    
    def add_polyline(self, points: List[Tuple[float, float]], closed: bool = True, 
                     layer: str = '0', color: Optional[int] = None):
        """Add a polyline entity."""
        self.entities.append({
            'type': 'LWPOLYLINE',
            'layer': layer,
            'color': color,
            'points': points,
            'closed': closed
        })
    
    def add_text(self, position: Tuple[float, float], text: str, height: float = 2.5,
                 rotation: float = 0.0, layer: str = '0', color: Optional[int] = None,
                 alignment: str = 'LEFT', style: str = 'STANDARD'):
        """Add a text entity."""
        self.entities.append({
            'type': 'TEXT',
            'layer': layer,
            'color': color,
            'position': position,
            'text': text,
            'height': height,
            'rotation': rotation,
            'alignment': alignment,
            'style': style
        })
    
    def add_dimension(self, start: Tuple[float, float], end: Tuple[float, float],
                      dim_line_pos: Tuple[float, float], text: Optional[str] = None,
                      layer: str = '0', color: Optional[int] = None):
        """Add a linear dimension entity."""
        self.entities.append({
            'type': 'DIMENSION',
            'layer': layer,
            'color': color,
            'start': start,
            'end': end,
            'dim_line_pos': dim_line_pos,
            'text': text
        })
    
    def add_hatch(self, boundary_points: List[Tuple[float, float]], pattern: str = 'SOLID',
                  scale: float = 1.0, angle: float = 0.0, layer: str = '0', color: Optional[int] = None):
        """Add a hatch entity."""
        self.entities.append({
            'type': 'HATCH',
            'layer': layer,
            'color': color,
            'boundary': boundary_points,
            'pattern': pattern,
            'scale': scale,
            'angle': angle
        })
    
    def generate(self) -> str:
        """Generate complete DXF file content."""
        dxf_content = []
        
        # Add header section
        dxf_content.extend(self._generate_header())
        
        # Add classes section (minimal)
        dxf_content.extend(self._generate_classes())
        
        # Add tables section
        dxf_content.extend(self._generate_tables())
        
        # Add blocks section
        dxf_content.extend(self._generate_blocks())
        
        # Add entities section
        dxf_content.extend(self._generate_entities())
        
        # Add objects section
        dxf_content.extend(self._generate_objects())
        
        # Add EOF
        dxf_content.extend(['  0', 'EOF'])
        
        return '\n'.join(dxf_content)
    
    def _generate_header(self) -> List[str]:
        """Generate HEADER section."""
        lines = ['  0', 'SECTION', '  2', 'HEADER']
        
        for var_name, value in self.header_vars.items():
            lines.extend(['  9', var_name])
            
            if isinstance(value, tuple):
                if len(value) == 2:  # 2D point
                    lines.extend([' 10', f'{value[0]:.6f}', ' 20', f'{value[1]:.6f}'])
                else:  # 3D point
                    lines.extend([' 10', f'{value[0]:.6f}', ' 20', f'{value[1]:.6f}', ' 30', f'{value[2]:.6f}'])
            elif isinstance(value, float):
                lines.extend([' 40', f'{value:.6f}'])
            elif isinstance(value, int):
                lines.extend([' 70', str(value)])
            elif isinstance(value, str):
                lines.extend(['  1', value])
        
        lines.extend(['  0', 'ENDSEC'])
        return lines
    
    def _generate_classes(self) -> List[str]:
        """Generate CLASSES section."""
        return ['  0', 'SECTION', '  2', 'CLASSES', '  0', 'ENDSEC']
    
    def _generate_tables(self) -> List[str]:
        """Generate TABLES section with layers, linetypes, etc."""
        lines = ['  0', 'SECTION', '  2', 'TABLES']
        
        # VPORT table
        lines.extend([
            '  0', 'TABLE', '  2', 'VPORT', ' 70', '1',
            '  0', 'VPORT', '  2', '*ACTIVE', ' 70', '0',
            ' 10', '0.0', ' 20', '0.0', ' 11', '1.0', ' 21', '1.0',
            ' 12', f'{(self.limits[0] + self.limits[2]) / 2:.6f}',
            ' 22', f'{(self.limits[1] + self.limits[3]) / 2:.6f}',
            ' 13', '0.0', ' 23', '0.0', ' 14', '10.0', ' 24', '10.0',
            ' 15', '10.0', ' 25', '10.0', ' 16', '0.0', ' 26', '0.0', ' 36', '1.0',
            ' 17', '0.0', ' 27', '0.0', ' 37', '0.0', ' 40', f'{max(self.limits[2] - self.limits[0], self.limits[3] - self.limits[1]):.6f}',
            ' 41', '2.0', ' 42', '50.0', ' 43', '0.0', ' 44', '0.0', ' 50', '0.0', ' 51', '0.0',
            ' 71', '0', ' 72', '100', ' 73', '1', ' 74', '3', ' 75', '0', ' 76', '0', ' 77', '0', ' 78', '0',
            '  0', 'ENDTAB'
        ])
        
        # LTYPE table
        lines.extend([
            '  0', 'TABLE', '  2', 'LTYPE', ' 70', '4',
            '  0', 'LTYPE', '  2', 'BYBLOCK', ' 70', '0', '  3', '', ' 72', '65', ' 73', '0', ' 40', '0.0',
            '  0', 'LTYPE', '  2', 'BYLAYER', ' 70', '0', '  3', '', ' 72', '65', ' 73', '0', ' 40', '0.0',
            '  0', 'LTYPE', '  2', 'CONTINUOUS', ' 70', '0', '  3', 'Solid line', ' 72', '65', ' 73', '0', ' 40', '0.0',
            '  0', 'LTYPE', '  2', 'DASHED', ' 70', '0', '  3', '- - - - - -', ' 72', '65', ' 73', '2', ' 40', '0.75',
            ' 49', '0.5', ' 74', '0', ' 49', '-0.25', ' 74', '0',
            '  0', 'LTYPE', '  2', 'HIDDEN', ' 70', '0', '  3', '- - - - - -', ' 72', '65', ' 73', '2', ' 40', '0.375',
            ' 49', '0.25', ' 74', '0', ' 49', '-0.125', ' 74', '0',
            '  0', 'LTYPE', '  2', 'CENTER', ' 70', '0', '  3', '__ _ __ _ __', ' 72', '65', ' 73', '4', ' 40', '2.0',
            ' 49', '1.25', ' 74', '0', ' 49', '-0.25', ' 74', '0', ' 49', '0.25', ' 74', '0', ' 49', '-0.25', ' 74', '0',
            '  0', 'ENDTAB'
        ])
        
        # LAYER table
        lines.extend(['  0', 'TABLE', '  2', 'LAYER', ' 70', str(len(self.layers) + 1)])
        
        # Default layer 0
        lines.extend([
            '  0', 'LAYER', '  2', '0', ' 70', '0', ' 62', '7', '  6', 'CONTINUOUS', '370', '0'
        ])
        
        # User-defined layers
        for layer_name, props in self.layers.items():
            flags = 0
            if props['frozen']:
                flags |= 1
            if props['locked']:
                flags |= 4
            
            lines.extend([
                '  0', 'LAYER', '  2', layer_name, ' 70', str(flags),
                ' 62', str(props['color'] if props['on'] else -props['color']),
                '  6', props['linetype'], '370', str(props['lineweight'])
            ])
        
        lines.extend(['  0', 'ENDTAB'])
        
        # STYLE table
        lines.extend([
            '  0', 'TABLE', '  2', 'STYLE', ' 70', '1',
            '  0', 'STYLE', '  2', 'STANDARD', ' 70', '0', ' 40', '0.0', ' 41', '1.0',
            ' 50', '0.0', ' 71', '0', ' 42', '0.2', '  3', 'txt', '  4', '',
            '  0', 'ENDTAB'
        ])
        
        # VIEW table (empty)
        lines.extend(['  0', 'TABLE', '  2', 'VIEW', ' 70', '0', '  0', 'ENDTAB'])
        
        # UCS table (empty)
        lines.extend(['  0', 'TABLE', '  2', 'UCS', ' 70', '0', '  0', 'ENDTAB'])
        
        # APPID table
        lines.extend([
            '  0', 'TABLE', '  2', 'APPID', ' 70', '1',
            '  0', 'APPID', '  2', 'ACAD', ' 70', '0',
            '  0', 'ENDTAB'
        ])
        
        # DIMSTYLE table
        lines.extend([
            '  0', 'TABLE', '  2', 'DIMSTYLE', ' 70', '1',
            '  0', 'DIMSTYLE', '  2', 'STANDARD', ' 70', '0', '  3', '', '  4', '',
            '  5', '', '  6', '', '  7', '', ' 40', '1.0', ' 41', '0.18', ' 42', '0.0625',
            ' 43', '0.38', ' 44', '0.18', ' 45', '0.0', ' 46', '0.0', ' 47', '0.0',
            ' 48', '0.0', '140', '0.18', '141', '0.09', '142', '0.0', '143', '25.4',
            '144', '1.0', '145', '0.0', '146', '1.0', '147', '0.09', ' 71', '0',
            ' 72', '0', ' 73', '1', ' 74', '1', ' 75', '0', ' 76', '0', ' 77', '0',
            ' 78', '0', '170', '0', '171', '2', '172', '0', '173', '0', '174', '0',
            '175', '0', '176', '0', '177', '0', '178', '0',
            '  0', 'ENDTAB'
        ])
        
        # BLOCK_RECORD table
        lines.extend([
            '  0', 'TABLE', '  2', 'BLOCK_RECORD', ' 70', '2',
            '  0', 'BLOCK_RECORD', '  2', '*MODEL_SPACE', ' 70', '0',
            '  0', 'BLOCK_RECORD', '  2', '*PAPER_SPACE', ' 70', '0',
            '  0', 'ENDTAB'
        ])
        
        lines.extend(['  0', 'ENDSEC'])
        return lines
    
    def _generate_blocks(self) -> List[str]:
        """Generate BLOCKS section."""
        lines = ['  0', 'SECTION', '  2', 'BLOCKS']
        
        # Model space block
        lines.extend([
            '  0', 'BLOCK', '  8', '0', '  2', '*MODEL_SPACE', ' 70', '0',
            ' 10', '0.0', ' 20', '0.0', ' 30', '0.0', '  3', '*MODEL_SPACE',
            '  1', '', '  0', 'ENDBLK', '  8', '0'
        ])
        
        # Paper space block
        lines.extend([
            '  0', 'BLOCK', '  8', '0', '  2', '*PAPER_SPACE', ' 70', '0',
            ' 10', '0.0', ' 20', '0.0', ' 30', '0.0', '  3', '*PAPER_SPACE',
            '  1', '', '  0', 'ENDBLK', '  8', '0'
        ])
        
        lines.extend(['  0', 'ENDSEC'])
        return lines
    
    def _generate_entities(self) -> List[str]:
        """Generate ENTITIES section with all drawing entities."""
        lines = ['  0', 'SECTION', '  2', 'ENTITIES']
        
        for entity in self.entities:
            if entity['type'] == 'LINE':
                lines.extend(self._generate_line(entity))
            elif entity['type'] == 'CIRCLE':
                lines.extend(self._generate_circle(entity))
            elif entity['type'] == 'ARC':
                lines.extend(self._generate_arc(entity))
            elif entity['type'] == 'LWPOLYLINE':
                lines.extend(self._generate_polyline(entity))
            elif entity['type'] == 'TEXT':
                lines.extend(self._generate_text(entity))
            elif entity['type'] == 'DIMENSION':
                lines.extend(self._generate_dimension(entity))
            elif entity['type'] == 'HATCH':
                lines.extend(self._generate_hatch(entity))
        
        lines.extend(['  0', 'ENDSEC'])
        return lines
    
    def _generate_line(self, entity: dict) -> List[str]:
        """Generate LINE entity."""
        lines = ['  0', 'LINE', '  8', entity['layer']]
        if entity.get('color') is not None:
            lines.extend([' 62', str(entity['color'])])
        lines.extend([
            ' 10', f"{entity['start'][0]:.6f}",
            ' 20', f"{entity['start'][1]:.6f}",
            ' 30', '0.0',
            ' 11', f"{entity['end'][0]:.6f}",
            ' 21', f"{entity['end'][1]:.6f}",
            ' 31', '0.0'
        ])
        return lines
    
    def _generate_circle(self, entity: dict) -> List[str]:
        """Generate CIRCLE entity."""
        lines = ['  0', 'CIRCLE', '  8', entity['layer']]
        if entity.get('color') is not None:
            lines.extend([' 62', str(entity['color'])])
        lines.extend([
            ' 10', f"{entity['center'][0]:.6f}",
            ' 20', f"{entity['center'][1]:.6f}",
            ' 30', '0.0',
            ' 40', f"{entity['radius']:.6f}"
        ])
        return lines
    
    def _generate_arc(self, entity: dict) -> List[str]:
        """Generate ARC entity."""
        lines = ['  0', 'ARC', '  8', entity['layer']]
        if entity.get('color') is not None:
            lines.extend([' 62', str(entity['color'])])
        lines.extend([
            ' 10', f"{entity['center'][0]:.6f}",
            ' 20', f"{entity['center'][1]:.6f}",
            ' 30', '0.0',
            ' 40', f"{entity['radius']:.6f}",
            ' 50', f"{entity['start_angle']:.6f}",
            ' 51', f"{entity['end_angle']:.6f}"
        ])
        return lines
    
    def _generate_polyline(self, entity: dict) -> List[str]:
        """Generate LWPOLYLINE entity."""
        lines = ['  0', 'LWPOLYLINE', '  8', entity['layer']]
        if entity.get('color') is not None:
            lines.extend([' 62', str(entity['color'])])
        lines.extend([
            ' 90', str(len(entity['points'])),
            ' 70', '1' if entity['closed'] else '0'
        ])
        for x, y in entity['points']:
            lines.extend([' 10', f'{x:.6f}', ' 20', f'{y:.6f}'])
        return lines
    
    def _generate_text(self, entity: dict) -> List[str]:
        """Generate TEXT entity."""
        lines = ['  0', 'TEXT', '  8', entity['layer']]
        if entity.get('color') is not None:
            lines.extend([' 62', str(entity['color'])])
        lines.extend([
            ' 10', f"{entity['position'][0]:.6f}",
            ' 20', f"{entity['position'][1]:.6f}",
            ' 30', '0.0',
            ' 40', f"{entity['height']:.6f}",
            '  1', entity['text'],
            ' 50', f"{entity['rotation']:.6f}",
            '  7', entity['style']
        ])
        
        # Add alignment codes if not default (LEFT)
        if entity['alignment'] != 'LEFT':
            align_map = {
                'CENTER': (1, 4),
                'RIGHT': (2, 6),
                'ALIGNED': (3, 5),
                'MIDDLE': (4, 5),
                'FIT': (5, 5)
            }
            if entity['alignment'] in align_map:
                h_align, v_align = align_map[entity['alignment']]
                lines.extend([' 72', str(h_align), ' 73', str(v_align)])
                # For justified text, need to specify alignment point
                lines.extend([
                    ' 11', f"{entity['position'][0]:.6f}",
                    ' 21', f"{entity['position'][1]:.6f}",
                    ' 31', '0.0'
                ])
        
        return lines
    
    def _generate_dimension(self, entity: dict) -> List[str]:
        """Generate linear DIMENSION entity (simplified)."""
        # This is a simplified linear dimension
        # Full dimension support would require block definitions
        lines = ['  0', 'DIMENSION', '  8', entity['layer']]
        if entity.get('color') is not None:
            lines.extend([' 62', str(entity['color'])])
        
        # Calculate dimension properties
        dx = entity['end'][0] - entity['start'][0]
        dy = entity['end'][1] - entity['start'][1]
        angle = math.atan2(dy, dx) * 180 / math.pi
        length = math.sqrt(dx*dx + dy*dy)
        
        lines.extend([
            '  2', '*D1',  # Dimension block name
            ' 10', f"{entity['dim_line_pos'][0]:.6f}",
            ' 20', f"{entity['dim_line_pos'][1]:.6f}",
            ' 30', '0.0',
            ' 11', f"{(entity['start'][0] + entity['end'][0]) / 2:.6f}",
            ' 21', f"{(entity['start'][1] + entity['end'][1]) / 2:.6f}",
            ' 31', '0.0',
            ' 70', '1',  # Aligned dimension
            '  1', entity.get('text', f'{length:.2f}'),
            ' 13', f"{entity['start'][0]:.6f}",
            ' 23', f"{entity['start'][1]:.6f}",
            ' 33', '0.0',
            ' 14', f"{entity['end'][0]:.6f}",
            ' 24', f"{entity['end'][1]:.6f}",
            ' 34', '0.0',
            ' 50', f'{angle:.6f}'
        ])
        
        return lines
    
    def _generate_hatch(self, entity: dict) -> List[str]:
        """Generate HATCH entity (simplified)."""
        lines = ['  0', 'HATCH', '  8', entity['layer']]
        if entity.get('color') is not None:
            lines.extend([' 62', str(entity['color'])])
        
        lines.extend([
            '  2', entity['pattern'],
            ' 70', '1',  # Solid fill
            ' 71', '0',  # Associative
            ' 91', '1',  # Number of boundary paths
            ' 92', '7',  # Boundary path type flags
            ' 72', '1',  # Has polyline boundary
            ' 73', '1',  # Is closed
            ' 93', str(len(entity['boundary'])),  # Number of vertices
        ])
        
        # Add boundary vertices
        for x, y in entity['boundary']:
            lines.extend([' 10', f'{x:.6f}', ' 20', f'{y:.6f}'])
        
        lines.extend([
            ' 97', '0',  # Number of source boundary objects
            ' 75', '0',  # Hatch style
            ' 76', '1',  # Hatch pattern type
            ' 52', f"{entity['angle']:.6f}",
            ' 41', f"{entity['scale']:.6f}",
            ' 77', '0',  # Hatch pattern double
            ' 78', '1',  # Number of pattern definition lines
            ' 53', '45.0',
            ' 43', '0.0',
            ' 44', '0.0',
            ' 45', '-0.0883883',
            ' 46', '0.0883883',
            ' 79', '0',
            ' 98', '1',
            ' 10', '0.0',
            ' 20', '0.0'
        ])
        
        return lines
    
    def _generate_objects(self) -> List[str]:
        """Generate OBJECTS section."""
        return ['  0', 'SECTION', '  2', 'OBJECTS', '  0', 'ENDSEC']


def _get_default_layer_config(export_mode: str) -> Dict[str, Dict[str, any]]:
    """Get default layer configuration based on export mode."""
    if export_mode == "laser":
        return {
            'CUT': {'color': 1, 'linetype': 'CONTINUOUS', 'lineweight': 0},  # Red for cutting
            'ENGRAVE': {'color': 5, 'linetype': 'CONTINUOUS', 'lineweight': 0},  # Blue for engraving
            'REFERENCE': {'color': 8, 'linetype': 'DASHED', 'lineweight': 0},  # Gray for reference
        }
    elif export_mode == "manufacturing":
        return {
            'OUTLINE': {'color': 7, 'linetype': 'CONTINUOUS', 'lineweight': 50},  # Black/white
            'HIDDEN': {'color': 8, 'linetype': 'HIDDEN', 'lineweight': 25},  # Gray
            'CENTER': {'color': 1, 'linetype': 'CENTER', 'lineweight': 25},  # Red
            'DIMENSION': {'color': 5, 'linetype': 'CONTINUOUS', 'lineweight': 25},  # Blue
            'HATCH': {'color': 9, 'linetype': 'CONTINUOUS', 'lineweight': 0},  # Light gray
            'TEXT': {'color': 2, 'linetype': 'CONTINUOUS', 'lineweight': 35},  # Yellow
            'CUT': {'color': 1, 'linetype': 'CONTINUOUS', 'lineweight': 50},  # Red
            'ENGRAVE': {'color': 5, 'linetype': 'CONTINUOUS', 'lineweight': 25},  # Blue
            'FOLD': {'color': 3, 'linetype': 'DASHED', 'lineweight': 35},  # Green
            'DRILL': {'color': 6, 'linetype': 'CONTINUOUS', 'lineweight': 35},  # Magenta
        }
    else:  # documentation
        return {
            'OUTLINE': {'color': 7, 'linetype': 'CONTINUOUS', 'lineweight': 70},
            'HIDDEN': {'color': 8, 'linetype': 'HIDDEN', 'lineweight': 35},
            'CENTER': {'color': 1, 'linetype': 'CENTER', 'lineweight': 25},
            'DIMENSION': {'color': 5, 'linetype': 'CONTINUOUS', 'lineweight': 25},
            'TEXT': {'color': 7, 'linetype': 'CONTINUOUS', 'lineweight': 35},
            'HATCH': {'color': 254, 'linetype': 'CONTINUOUS', 'lineweight': 0},
            'SECTION': {'color': 4, 'linetype': 'CONTINUOUS', 'lineweight': 50},
            'PHANTOM': {'color': 8, 'linetype': 'DASHED', 'lineweight': 25},
        }


def _draw_base_geometry_dxf(dxf: DXFBuilder, config: BaseConfiguration, width: float, height: float, 
                            scale: float, export_mode: str):
    """Draw base geometry in DXF format."""
    # Determine layers based on export mode
    outline_layer = 'CUT' if export_mode == 'laser' else 'OUTLINE'
    
    if config.base_type == BaseType.FLAT_RECTANGULAR:
        # Rounded rectangle with proper corner radius
        corner_radius = min(5 * scale, width * 0.1, height * 0.1)
        
        if corner_radius > 0:
            # Draw rounded rectangle using lines and arcs
            points = []
            
            # Top edge (with corners)
            dxf.add_line((corner_radius, 0), (width - corner_radius, 0), outline_layer)
            # Right edge
            dxf.add_line((width, corner_radius), (width, height - corner_radius), outline_layer)
            # Bottom edge
            dxf.add_line((width - corner_radius, height), (corner_radius, height), outline_layer)
            # Left edge
            dxf.add_line((0, height - corner_radius), (0, corner_radius), outline_layer)
            
            # Corner arcs
            dxf.add_arc((corner_radius, corner_radius), corner_radius, 180, 270, outline_layer)  # Top-left
            dxf.add_arc((width - corner_radius, corner_radius), corner_radius, 270, 360, outline_layer)  # Top-right
            dxf.add_arc((width - corner_radius, height - corner_radius), corner_radius, 0, 90, outline_layer)  # Bottom-right
            dxf.add_arc((corner_radius, height - corner_radius), corner_radius, 90, 180, outline_layer)  # Bottom-left
        else:
            # Simple rectangle
            dxf.add_polyline([
                (0, 0), (width, 0), (width, height), (0, height)
            ], closed=True, layer=outline_layer)
    
    elif config.base_type == BaseType.FLAT_CIRCULAR:
        # Circle
        cx = width / 2
        cy = height / 2
        radius = min(width, height) / 2
        dxf.add_circle((cx, cy), radius, outline_layer)
    
    elif config.base_type == BaseType.BOX_ENCLOSED:
        # Box with fold lines - create unfolded pattern
        wall_height = config.dimensions.depth * scale if config.is_3d else 50 * scale
        
        # Base rectangle
        dxf.add_polyline([
            (0, 0), (width, 0), (width, height), (0, height)
        ], closed=True, layer=outline_layer)
        
        # Add walls as separate pieces with tabs
        tab_width = 15 * scale
        tab_height = 10 * scale
        
        # Top wall with tabs
        top_wall_points = [
            (0, -wall_height),
            (0, 0),
            (tab_width, 0),
            (tab_width, tab_height),
            (width - tab_width, tab_height),
            (width - tab_width, 0),
            (width, 0),
            (width, -wall_height)
        ]
        dxf.add_polyline(top_wall_points, closed=True, layer=outline_layer)
        
        # Add fold line
        dxf.add_line((0, 0), (width, 0), 'FOLD' if export_mode == 'manufacturing' else 'HIDDEN')
        
        # Similar for other walls...
        
    elif config.base_type == BaseType.PEDESTAL:
        # Pedestal with thicker border indication
        corner_radius = 10 * scale
        
        # Outer boundary
        dxf.add_polyline([
            (corner_radius, 0),
            (width - corner_radius, 0),
            (width, corner_radius),
            (width, height - corner_radius),
            (width - corner_radius, height),
            (corner_radius, height),
            (0, height - corner_radius),
            (0, corner_radius)
        ], closed=True, layer=outline_layer)
        
        # Inner boundary for thickness indication
        inset = config.material_thickness * scale if config.material_thickness else 5 * scale
        dxf.add_polyline([
            (inset + corner_radius, inset),
            (width - inset - corner_radius, inset),
            (width - inset, inset + corner_radius),
            (width - inset, height - inset - corner_radius),
            (width - inset - corner_radius, height - inset),
            (inset + corner_radius, height - inset),
            (inset, height - inset - corner_radius),
            (inset, inset + corner_radius)
        ], closed=True, layer='HIDDEN')
    
    elif config.base_type == BaseType.WALL_MOUNTED:
        # Wall mounted with brackets
        dxf.add_polyline([
            (0, 0), (width, 0), (width, height), (0, height)
        ], closed=True, layer=outline_layer)
        
        # Mounting brackets
        bracket_width = width * 0.15
        bracket_height = height * 0.08
        bracket_hole_radius = 3 * scale
        
        # Left bracket
        bracket_left = [
            (0, -bracket_height),
            (bracket_width, -bracket_height),
            (bracket_width, 0),
            (0, 0)
        ]
        dxf.add_polyline(bracket_left, closed=True, layer=outline_layer)
        dxf.add_circle((bracket_width/2, -bracket_height/2), bracket_hole_radius, 'DRILL')
        
        # Right bracket
        bracket_right = [
            (width - bracket_width, -bracket_height),
            (width, -bracket_height),
            (width, 0),
            (width - bracket_width, 0)
        ]
        dxf.add_polyline(bracket_right, closed=True, layer=outline_layer)
        dxf.add_circle((width - bracket_width/2, -bracket_height/2), bracket_hole_radius, 'DRILL')
    
    elif config.base_type == BaseType.MODULAR:
        # Modular with connection features
        dxf.add_polyline([
            (0, 0), (width, 0), (width, height), (0, height)
        ], closed=True, layer=outline_layer)
        
        # Modular connection slots
        slot_width = 20 * scale
        slot_height = 5 * scale
        slot_positions = [width * 0.25, width * 0.5, width * 0.75]
        
        for pos in slot_positions:
            # Top slots
            dxf.add_polyline([
                (pos - slot_width/2, 0),
                (pos + slot_width/2, 0),
                (pos + slot_width/2, slot_height),
                (pos - slot_width/2, slot_height)
            ], closed=True, layer=outline_layer)
            
            # Bottom slots
            dxf.add_polyline([
                (pos - slot_width/2, height - slot_height),
                (pos + slot_width/2, height - slot_height),
                (pos + slot_width/2, height),
                (pos - slot_width/2, height)
            ], closed=True, layer=outline_layer)
    
    else:  # CUSTOM or default
        # Simple rectangle
        dxf.add_polyline([
            (0, 0), (width, 0), (width, height), (0, height)
        ], closed=True, layer=outline_layer)


def _draw_mounting_points_dxf(dxf: DXFBuilder, config: BaseConfiguration, scale: float, export_mode: str):
    """Draw mounting points in DXF format."""
    drill_layer = 'CUT' if export_mode == 'laser' else 'DRILL'
    
    for i, mp in enumerate(config.mounting_points):
        if isinstance(mp.position, Point2D):
            x = mp.position.x * scale
            y = mp.position.y * scale
            r = mp.hole_diameter * scale / 2
            
            # Main hole
            dxf.add_circle((x, y), r, drill_layer)
            
            # Countersink if present
            if mp.countersink and mp.countersink_diameter:
                cs_r = mp.countersink_diameter * scale / 2
                dxf.add_circle((x, y), cs_r, 'ENGRAVE' if export_mode == 'laser' else 'HIDDEN')
            
            # Center marks for manufacturing
            if export_mode == 'manufacturing':
                mark_size = 2 * scale
                dxf.add_line((x - mark_size, y), (x + mark_size, y), 'CENTER')
                dxf.add_line((x, y - mark_size), (x, y + mark_size), 'CENTER')


def _add_construction_geometry_dxf(dxf: DXFBuilder, config: BaseConfiguration, width: float, height: float, scale: float):
    """Add construction geometry for assembly."""
    if config.base_type == BaseType.BOX_ENCLOSED:
        # Add internal dividers or support structures
        divider_thickness = 3 * scale
        
        # Example: Cross dividers for box
        if width > 100 * scale and height > 100 * scale:
            # Vertical divider
            dxf.add_polyline([
                (width/2 - divider_thickness/2, 0),
                (width/2 + divider_thickness/2, 0),
                (width/2 + divider_thickness/2, height),
                (width/2 - divider_thickness/2, height)
            ], closed=True, layer='CUT')
            
            # Horizontal divider with slots
            slot_depth = height * 0.5
            dxf.add_polyline([
                (0, height/2 - divider_thickness/2),
                (width/2 - divider_thickness/2, height/2 - divider_thickness/2),
                (width/2 - divider_thickness/2, height/2 - divider_thickness/2 - slot_depth),
                (width/2 + divider_thickness/2, height/2 - divider_thickness/2 - slot_depth),
                (width/2 + divider_thickness/2, height/2 - divider_thickness/2),
                (width, height/2 - divider_thickness/2),
                (width, height/2 + divider_thickness/2),
                (width/2 + divider_thickness/2, height/2 + divider_thickness/2),
                (width/2 + divider_thickness/2, height/2 + divider_thickness/2 + slot_depth),
                (width/2 - divider_thickness/2, height/2 + divider_thickness/2 + slot_depth),
                (width/2 - divider_thickness/2, height/2 + divider_thickness/2),
                (0, height/2 + divider_thickness/2)
            ], closed=True, layer='CUT')


def _add_dimensions_dxf(dxf: DXFBuilder, config: BaseConfiguration, width: float, height: float, scale: float):
    """Add dimension entities to DXF."""
    dim_offset = 15 * scale
    
    # Overall width dimension
    dxf.add_dimension(
        start=(0, -dim_offset),
        end=(width, -dim_offset),
        dim_line_pos=(width/2, -dim_offset - 5),
        text=f'{config.footprint.width:.1f}',
        layer='DIMENSION'
    )
    
    # Overall height dimension
    dxf.add_dimension(
        start=(-dim_offset, 0),
        end=(-dim_offset, height),
        dim_line_pos=(-dim_offset - 5, height/2),
        text=f'{config.footprint.height:.1f}',
        layer='DIMENSION'
    )
    
    # Mounting hole dimensions
    for i, mp in enumerate(config.mounting_points[:2]):  # First two holes
        if isinstance(mp.position, Point2D):
            x = mp.position.x * scale
            y = mp.position.y * scale
            
            # Distance from left edge
            dxf.add_dimension(
                start=(0, y + dim_offset/2),
                end=(x, y + dim_offset/2),
                dim_line_pos=(x/2, y + dim_offset),
                text=f'{mp.position.x:.1f}',
                layer='DIMENSION'
            )
            
            # Distance from bottom edge
            dxf.add_dimension(
                start=(x + dim_offset/2, 0),
                end=(x + dim_offset/2, y),
                dim_line_pos=(x + dim_offset, y/2),
                text=f'{mp.position.y:.1f}',
                layer='DIMENSION'
            )
            
            # Hole diameter
            leader_offset = 20 * scale
            dxf.add_line((x + mp.hole_diameter * scale / 2, y), 
                        (x + leader_offset, y + leader_offset), 'DIMENSION')
            dxf.add_text((x + leader_offset + 5, y + leader_offset), 
                        f'⌀{mp.hole_diameter}', height=2.5 * scale, layer='DIMENSION')


def _add_annotations_dxf(dxf: DXFBuilder, config: BaseConfiguration, width: float, height: float, scale: float):
    """Add text annotations to DXF."""
    # Title
    dxf.add_text(
        position=(width/2, height + 20 * scale),
        text=config.name,
        height=5 * scale,
        alignment='CENTER',
        layer='TEXT'
    )
    
    # Material specification
    material_text = f'MATERIAL: {config.primary_material.value.upper()}'
    if config.material_thickness:
        material_text += f' {config.material_thickness}{config.footprint.unit.value}'
    
    dxf.add_text(
        position=(10 * scale, height + 10 * scale),
        text=material_text,
        height=3 * scale,
        layer='TEXT'
    )
    
    # Manufacturing notes
    notes_y = height + 30 * scale
    notes = []
    
    if config.assembly_method:
        notes.append(f'ASSEMBLY: {config.assembly_method.value.replace("_", " ").upper()}')
    
    if config.weight:
        notes.append(f'WEIGHT: {config.weight} KG')
    
    if config.max_load:
        notes.append(f'MAX LOAD: {config.max_load} KG')
    
    for i, note in enumerate(notes):
        dxf.add_text(
            position=(10 * scale, notes_y + i * 4 * scale),
            text=note,
            height=2.5 * scale,
            layer='TEXT'
        )
    
    # Add scale
    dxf.add_text(
        position=(width - 50 * scale, height + 10 * scale),
        text=f'SCALE 1:{int(1/scale) if scale < 1 else 1}',
        height=3 * scale,
        layer='TEXT'
    )
    
    # Add units
    dxf.add_text(
        position=(width - 50 * scale, height + 5 * scale),
        text=f'UNITS: {config.footprint.unit.value.upper()}',
        height=2.5 * scale,
        layer='TEXT'
    )


def _add_manufacturing_notes_dxf(dxf: DXFBuilder, config: BaseConfiguration, width: float, height: float):
    """Add manufacturing-specific notes and tolerances."""
    notes_x = width + 20
    notes_y = 20
    line_spacing = 5
    
    manufacturing_notes = [
        "MANUFACTURING NOTES:",
        "1. ALL DIMENSIONS IN " + config.footprint.unit.value.upper(),
        "2. TOLERANCES: ±0.1mm UNLESS NOTED",
        "3. DEBURR ALL EDGES",
        "4. SURFACE FINISH: 3.2 µm Ra",
    ]
    
    if config.primary_material == MaterialType.ALUMINUM:
        manufacturing_notes.extend([
            "5. MATERIAL: ALUMINUM 6061-T6",
            "6. ANODIZE: CLEAR OR AS SPECIFIED"
        ])
    elif config.primary_material in [MaterialType.WOOD, MaterialType.MDF, MaterialType.PLYWOOD]:
        manufacturing_notes.extend([
            "5. SAND ALL SURFACES",
            "6. APPLY FINISH AS SPECIFIED"
        ])
    elif config.primary_material == MaterialType.ACRYLIC:
        manufacturing_notes.extend([
            "5. FLAME POLISH EDGES",
            "6. REMOVE PROTECTIVE FILM AFTER CUTTING"
        ])
    
    for i, note in enumerate(manufacturing_notes):
        dxf.add_text(
            position=(notes_x, notes_y + i * line_spacing),
            text=note,
            height=3.0,
            layer='TEXT'
        )
    
    # Add revision block
    rev_y = notes_y + len(manufacturing_notes) * line_spacing + 10
    dxf.add_text(
        position=(notes_x, rev_y),
        text=f"REV: A  DATE: {datetime.now().strftime('%Y-%m-%d')}",
        height=3.0,
        layer='TEXT'
    )