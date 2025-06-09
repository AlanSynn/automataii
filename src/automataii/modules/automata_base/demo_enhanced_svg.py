#!/usr/bin/env python3
"""Demonstration of the enhanced SVG export functionality"""

import xml.etree.ElementTree as ET
from datetime import datetime
import xml.dom.minidom

# Sample SVG generation to demonstrate the enhanced features
def create_demo_svg():
    """Create a demonstration SVG with all the enhanced features"""
    
    # Create SVG root with proper namespace declarations
    svg = ET.Element('svg', {
        'xmlns': 'http://www.w3.org/2000/svg',
        'xmlns:xlink': 'http://www.w3.org/1999/xlink',
        'width': '400',
        'height': '300',
        'viewBox': '-50 -50 400 300',
        'version': '1.1',
    })
    
    # Add metadata
    metadata = ET.SubElement(svg, 'metadata')
    desc = ET.SubElement(metadata, 'desc')
    desc.text = "Enhanced Automata Base: Demo Base"
    
    # Add comprehensive styles
    style = ET.SubElement(svg, 'style', {'type': 'text/css'})
    style.text = """
        /* Display/visualization styles */
        .base-outline { fill: none; stroke: #000000; stroke-width: 2px; }
        .base-fill { fill: #DEB887; fill-opacity: 0.3; }
        .base-shadow { fill: #000000; fill-opacity: 0.2; filter: url(#dropshadow); }
        .cut-line { fill: none; stroke: #FF0000; stroke-width: 1.5px; stroke-dasharray: 8,4; }
        .engrave-line { fill: none; stroke: #0066CC; stroke-width: 1px; stroke-dasharray: 4,2; }
        .mounting-hole { fill: #FFFFFF; stroke: #CC0000; stroke-width: 1.5px; }
        .countersink { fill: none; stroke: #FF6666; stroke-width: 1px; stroke-dasharray: 2,2; }
        .construction-line { fill: none; stroke: #CCCCCC; stroke-width: 0.5px; stroke-dasharray: 5,5; }
        .dimension-line { stroke: #0000FF; stroke-width: 0.5px; }
        .dimension-text { font-family: 'Courier New', monospace; font-size: 12px; fill: #0000FF; }
        .dimension-arrow { fill: #0000FF; }
        .label-text { font-family: Arial, sans-serif; font-size: 10px; fill: #333333; }
        .label-background { fill: #FFFFFF; fill-opacity: 0.8; stroke: #CCCCCC; stroke-width: 0.5px; }
        .grid-line { stroke: #F0F0F0; stroke-width: 0.5px; }
        .grid-major { stroke: #E0E0E0; stroke-width: 1px; }
        .annotation { font-family: Arial, sans-serif; font-size: 14px; fill: #000000; }
        .title-block { fill: none; stroke: #000000; stroke-width: 1pt; }
        .title-text { font-family: Arial, sans-serif; font-size: 14pt; fill: #000000; font-weight: bold; }
        
        /* Base type specific styles */
        .flat-rectangular-base { }
        .box-base { stroke-dasharray: none; }
        .pedestal-base { stroke-width: 2.5px; }
        
        /* Interactive hover effects */
        .mounting-hole:hover { fill: #FFE0E0; stroke-width: 2px; }
        .base-outline:hover { stroke-width: 3px; }
    """
    
    # Add definitions
    defs = ET.SubElement(svg, 'defs')
    
    # Arrow marker for dimensions
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
    
    # Create layer groups
    layers = {}
    layer_names = ['grid', 'shadow', 'fill', 'construction', 'outline', 
                   'mounting', 'engrave', 'dimensions', 'labels', 'annotations']
    
    for name in layer_names:
        layers[name] = ET.SubElement(svg, 'g', {
            'id': f'layer-{name}',
            'class': f'{name}-layer'
        })
    
    # Add grid
    for x in range(0, 301, 10):
        ET.SubElement(layers['grid'], 'line', {
            'x1': str(x),
            'y1': '0',
            'x2': str(x),
            'y2': '200',
            'class': 'grid-major' if x % 50 == 0 else 'grid-line'
        })
    
    for y in range(0, 201, 10):
        ET.SubElement(layers['grid'], 'line', {
            'x1': '0',
            'y1': str(y),
            'x2': '300',
            'y2': str(y),
            'class': 'grid-major' if y % 50 == 0 else 'grid-line'
        })
    
    # Add shadow
    shadow_rect = ET.SubElement(layers['shadow'], 'rect', {
        'x': '3',
        'y': '3',
        'width': '300',
        'height': '200',
        'rx': '5',
        'ry': '5',
        'class': 'base-shadow'
    })
    
    # Add fill
    fill_rect = ET.SubElement(layers['fill'], 'rect', {
        'x': '0',
        'y': '0',
        'width': '300',
        'height': '200',
        'rx': '5',
        'ry': '5',
        'class': 'base-fill'
    })
    
    # Draw base outline
    base_rect = ET.SubElement(layers['outline'], 'rect', {
        'x': '0',
        'y': '0',
        'width': '300',
        'height': '200',
        'rx': '5',
        'ry': '5',
        'class': 'base-outline flat-rectangular-base'
    })
    
    # Add mounting points
    mounting_points = [(30, 30), (270, 30), (30, 170), (270, 170)]
    for i, (x, y) in enumerate(mounting_points):
        # Main hole
        ET.SubElement(layers['mounting'], 'circle', {
            'cx': str(x),
            'cy': str(y),
            'r': '4',
            'class': 'mounting-hole',
            'id': f'mounting-hole-{i}'
        })
        
        # Countersink
        ET.SubElement(layers['mounting'], 'circle', {
            'cx': str(x),
            'cy': str(y),
            'r': '8',
            'class': 'countersink'
        })
        
        # Cross-hairs
        ET.SubElement(layers['mounting'], 'line', {
            'x1': str(x - 10),
            'y1': str(y),
            'x2': str(x + 10),
            'y2': str(y),
            'class': 'construction-line'
        })
        ET.SubElement(layers['mounting'], 'line', {
            'x1': str(x),
            'y1': str(y - 10),
            'x2': str(x),
            'y2': str(y + 10),
            'class': 'construction-line'
        })
    
    # Add engrave details
    ET.SubElement(layers['engrave'], 'text', {
        'x': '150',
        'y': '190',
        'text-anchor': 'middle',
        'font-size': '12',
        'class': 'engrave-line'
    }).text = 'Demo Automata Base'
    
    ET.SubElement(layers['engrave'], 'text', {
        'x': '10',
        'y': '190',
        'text-anchor': 'start',
        'font-size': '8',
        'class': 'engrave-line'
    }).text = 'PLYWOOD'
    
    # Add corner marks
    corner_size = 15
    corners = [(0, 0, 1, 1), (285, 0, -1, 1), (0, 185, 1, -1), (285, 185, -1, -1)]
    for x, y, dx, dy in corners:
        path = f"M {x} {y + corner_size * dy} L {x} {y} L {x + corner_size * dx} {y}"
        ET.SubElement(layers['engrave'], 'path', {
            'd': path,
            'class': 'engrave-line',
            'fill': 'none'
        })
    
    # Add dimensions
    # Width dimension
    dim_group = ET.SubElement(layers['dimensions'], 'g', {'class': 'dimension-group'})
    ET.SubElement(dim_group, 'line', {
        'x1': '0',
        'y1': '-25',
        'x2': '300',
        'y2': '-25',
        'class': 'dimension-line',
        'marker-start': 'url(#dimension-arrow)',
        'marker-end': 'url(#dimension-arrow)'
    })
    ET.SubElement(dim_group, 'text', {
        'x': '150',
        'y': '-20',
        'text-anchor': 'middle',
        'class': 'dimension-text'
    }).text = '300 mm'
    
    # Height dimension
    ET.SubElement(dim_group, 'line', {
        'x1': '-25',
        'y1': '0',
        'x2': '-25',
        'y2': '200',
        'class': 'dimension-line',
        'marker-start': 'url(#dimension-arrow)',
        'marker-end': 'url(#dimension-arrow)'
    })
    ET.SubElement(dim_group, 'text', {
        'x': '-30',
        'y': '100',
        'text-anchor': 'middle',
        'class': 'dimension-text',
        'transform': 'rotate(-90 -30 100)'
    }).text = '200 mm'
    
    # Add labels
    for i, (x, y) in enumerate(mounting_points[:2]):
        label_group = ET.SubElement(layers['labels'], 'g', {'class': 'label-group'})
        
        # Background
        ET.SubElement(label_group, 'rect', {
            'x': str(x + 10),
            'y': str(y - 7.5),
            'width': '30',
            'height': '15',
            'rx': '3',
            'class': 'label-background'
        })
        
        # Label
        ET.SubElement(label_group, 'text', {
            'x': str(x + 25),
            'y': str(y),
            'text-anchor': 'middle',
            'dominant-baseline': 'middle',
            'class': 'label-text'
        }).text = f'H{i+1}'
        
        # Hole size
        ET.SubElement(label_group, 'text', {
            'x': str(x + 25),
            'y': str(y + 12),
            'text-anchor': 'middle',
            'class': 'label-text',
            'font-size': '8'
        }).text = '⌀4mm'
    
    # Add annotations
    ET.SubElement(layers['annotations'], 'text', {
        'x': '10',
        'y': '20',
        'text-anchor': 'start',
        'class': 'annotation'
    }).text = 'Assembly: Screws'
    
    ET.SubElement(layers['annotations'], 'text', {
        'x': '10',
        'y': '40',
        'text-anchor': 'start',
        'class': 'label-text'
    }).text = 'Weight: 0.5 kg'
    
    ET.SubElement(layers['annotations'], 'text', {
        'x': '10',
        'y': '55',
        'text-anchor': 'start',
        'class': 'label-text'
    }).text = 'Max Load: 2.0 kg'
    
    # Pretty print
    rough_string = ET.tostring(svg, encoding='unicode')
    dom = xml.dom.minidom.parseString(rough_string)
    pretty_string = dom.toprettyxml(indent='  ')
    
    # Remove extra blank lines
    lines = pretty_string.split('\n')
    cleaned_lines = [line for line in lines if line.strip()]
    
    return '\n'.join(cleaned_lines)


def main():
    """Generate demonstration SVG files"""
    
    print("Enhanced SVG Export Demonstration")
    print("=" * 50)
    
    # Generate the demonstration SVG
    svg_content = create_demo_svg()
    
    # Save to file
    with open("demo_enhanced_base.svg", "w") as f:
        f.write(svg_content)
    
    print("\n✅ Generated: demo_enhanced_base.svg")
    print(f"   Size: {len(svg_content)} characters")
    
    # Create a laser-cutting version
    print("\n🔧 Creating laser-cutting version...")
    
    # Modify styles for laser cutting
    laser_svg = svg_content.replace(
        "/* Display/visualization styles */",
        "/* Laser cutting styles - optimized for manufacturing */\n" +
        "        .grid-line { display: none; }\n" +
        "        .grid-major { display: none; }\n" +
        "        .base-fill { display: none; }\n" +
        "        .base-shadow { display: none; }\n" +
        "        .construction-line { display: none; }\n" +
        "        .dimension-line { display: none; }\n" +
        "        .dimension-text { display: none; }\n" +
        "        .label-text { display: none; }\n" +
        "        .label-background { display: none; }\n" +
        "        .annotation { display: none; }\n" +
        "        .base-outline { fill: none; stroke: #FF0000; stroke-width: 0.1mm; }\n" +
        "        .mounting-hole { fill: none; stroke: #FF0000; stroke-width: 0.1mm; }\n" +
        "        .engrave-line { fill: none; stroke: #0000FF; stroke-width: 0.1mm; }\n" +
        "        .countersink { display: none; }\n" +
        "        /* Display/visualization styles (disabled) */"
    )
    
    with open("demo_laser_base.svg", "w") as f:
        f.write(laser_svg)
    
    print("✅ Generated: demo_laser_base.svg")
    
    print("\n" + "=" * 50)
    print("✨ Demonstration Complete!")
    print("\nGenerated files showcase:")
    print("  • Professional CSS styling with hover effects")
    print("  • Organized layer structure")
    print("  • Material-specific coloring (plywood)")
    print("  • Proper dimension annotations with arrows")
    print("  • Mounting points with cross-hairs and labels")
    print("  • Engraving details and corner marks")
    print("  • Grid background for reference")
    print("  • Drop shadow effects")
    print("  • Title and metadata")
    print("\nFeatures of the enhanced converter:")
    print("  • Multiple export modes (display, laser, print)")
    print("  • Support for all base types (rectangular, circular, box, etc.)")
    print("  • Material-aware styling")
    print("  • Manufacturing-ready output")
    print("  • Professional documentation features")
    print("\nOpen the files in a web browser or vector editor to explore!")


if __name__ == "__main__":
    main()