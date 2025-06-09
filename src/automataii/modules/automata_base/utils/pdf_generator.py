"""
PDF Generation for assembly instructions.

This module provides tools to generate professional PDF documentation
including assembly instructions, parts lists, and technical drawings
for automata bases.
"""

from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime
import logging
import base64
from io import BytesIO

# We'll use ReportLab for PDF generation
try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.units import inch, mm
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        PageBreak, Image, KeepTogether
    )
    from reportlab.graphics.shapes import Drawing, Line, Rect, String
    from reportlab.graphics import renderPDF
    from reportlab.pdfgen import canvas
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    logging.warning("ReportLab not installed. PDF generation will be limited.")

from automataii.modules.automata_base.models.base_config import BaseConfiguration
from automataii.modules.automata_base.enums.base_types import MaterialType
from automataii.modules.automata_base.utils.converters import base_to_svg

logger = logging.getLogger(__name__)


class PDFGenerator:
    """Generates PDF assembly instructions for automata bases."""
    
    def __init__(self, base_config: BaseConfiguration, 
                 page_size: str = "letter"):
        """
        Initialize PDF generator.
        
        Args:
            base_config: Base configuration to document
            page_size: Page size ("letter" or "A4")
        """
        self.config = base_config
        if REPORTLAB_AVAILABLE:
            self.page_size = letter if page_size == "letter" else A4
            self.styles = getSampleStyleSheet()
            self.story = []
            # Custom styles
            self._create_custom_styles()
        else:
            self.page_size = page_size
            self.styles = None
            self.story = []
    
    def _create_custom_styles(self):
        """Create custom paragraph styles."""
        if not REPORTLAB_AVAILABLE:
            return
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a1a1a'),
            alignment=TA_CENTER,
            spaceAfter=30
        ))
        
        self.styles.add(ParagraphStyle(
            name='SectionHeading',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#333333'),
            spaceAfter=12
        ))
        
        self.styles.add(ParagraphStyle(
            name='InfoText',
            parent=self.styles['Normal'],
            fontSize=10,
            leading=14
        ))
    
    def _add_header(self):
        """Add document header."""
        # Title
        title = Paragraph(
            f"Assembly Instructions: {self.config.name}",
            self.styles['CustomTitle']
        )
        self.story.append(title)
        
        # Date and version
        date_text = Paragraph(
            f"Generated: {datetime.now().strftime('%B %d, %Y')}<br/>"
            f"Version: 1.0",
            self.styles['InfoText']
        )
        self.story.append(date_text)
        self.story.append(Spacer(1, 0.5*inch))
    
    def _add_overview(self):
        """Add base overview section."""
        self.story.append(Paragraph("Overview", self.styles['SectionHeading']))
        
        # Base specifications table
        data = [
            ['Specification', 'Value'],
            ['Base Type', self.config.base_type.value.replace('_', ' ').title()],
            ['Primary Material', self.config.primary_material.value.replace('_', ' ').title()],
            ['Material Thickness', f"{self.config.material_thickness} mm"],
            ['Mounting Type', self.config.mounting_type.value.replace('_', ' ').title()],
        ]
        
        # Add dimensions
        if hasattr(self.config.dimensions, 'width'):
            data.append(['Width', f"{self.config.dimensions.width} {self.config.dimensions.unit.value}"])
        if hasattr(self.config.dimensions, 'height'):
            data.append(['Height', f"{self.config.dimensions.height} {self.config.dimensions.unit.value}"])
        if hasattr(self.config.dimensions, 'depth'):
            data.append(['Depth', f"{self.config.dimensions.depth} {self.config.dimensions.unit.value}"])
        
        table = Table(data, colWidths=[3*inch, 2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        self.story.append(table)
        self.story.append(Spacer(1, 0.3*inch))
    
    def _add_materials_list(self):
        """Add materials and tools list."""
        self.story.append(Paragraph("Materials Required", self.styles['SectionHeading']))
        
        # Materials table
        materials_data = [['Material', 'Quantity', 'Specifications']]
        
        # Primary material
        material_name = self.config.primary_material.value.replace('_', ' ').title()
        dimensions_str = self._get_dimensions_string()
        materials_data.append([
            material_name,
            '1 piece',
            f"{dimensions_str}, {self.config.material_thickness}mm thick"
        ])
        
        # Fasteners based on mounting points
        if self.config.mounting_points:
            unique_threads = set(mp.thread_type for mp in self.config.mounting_points)
            for thread in unique_threads:
                count = sum(1 for mp in self.config.mounting_points if mp.thread_type == thread)
                materials_data.append([
                    f"{thread} Screws",
                    f"{count} pieces",
                    "Length depends on mounting surface"
                ])
        
        table = Table(materials_data, colWidths=[2*inch, 1.5*inch, 2.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        self.story.append(table)
        self.story.append(Spacer(1, 0.2*inch))
        
        # Tools required
        self.story.append(Paragraph("Tools Required", self.styles['SectionHeading']))
        
        tools = self._get_required_tools()
        tools_text = "<br/>".join([f"• {tool}" for tool in tools])
        self.story.append(Paragraph(tools_text, self.styles['InfoText']))
        self.story.append(Spacer(1, 0.3*inch))
    
    def _get_dimensions_string(self) -> str:
        """Get dimensions as a formatted string."""
        dims = self.config.dimensions
        if hasattr(dims, 'width') and hasattr(dims, 'height'):
            if hasattr(dims, 'depth'):
                return f"{dims.width} × {dims.height} × {dims.depth} {dims.unit.value}"
            else:
                return f"{dims.width} × {dims.height} {dims.unit.value}"
        return "See technical drawing"
    
    def _get_required_tools(self) -> List[str]:
        """Get list of required tools based on material and assembly method."""
        tools = []
        
        # Material-specific tools
        material_tools = {
            MaterialType.WOOD: ["Saw", "Drill", "Sandpaper", "Wood glue"],
            MaterialType.PLYWOOD: ["Circular saw", "Drill", "Sandpaper"],
            MaterialType.MDF: ["Jigsaw", "Drill", "Router (optional)"],
            MaterialType.ACRYLIC: ["Laser cutter or acrylic cutter", "Drill with plastic bits", "Acrylic cement"],
            MaterialType.ALUMINUM: ["Metal saw", "Drill with metal bits", "File", "Deburring tool"],
            MaterialType.STEEL: ["Metal cutting tools", "Drill with metal bits", "File", "Deburring tool"],
            MaterialType.PLASTIC_3D_PRINTED: ["3D printer", "Support removal tools", "Sandpaper"],
        }
        
        if self.config.primary_material in material_tools:
            tools.extend(material_tools[self.config.primary_material])
        
        # Add common tools
        tools.extend(["Measuring tape or ruler", "Pencil or marker", "Safety glasses"])
        
        # Add specific tools for mounting
        if self.config.mounting_points:
            tools.append("Screwdriver or drill driver")
            if any(mp.countersink for mp in self.config.mounting_points):
                tools.append("Countersink bit")
        
        return list(set(tools))  # Remove duplicates
    
    def _add_assembly_steps(self):
        """Add step-by-step assembly instructions."""
        self.story.append(PageBreak())
        self.story.append(Paragraph("Assembly Instructions", self.styles['SectionHeading']))
        
        steps = self._generate_assembly_steps()
        
        for i, step in enumerate(steps, 1):
            step_title = Paragraph(f"Step {i}: {step['title']}", 
                                 self.styles['Heading3'])
            step_text = Paragraph(step['description'], self.styles['InfoText'])
            
            self.story.append(KeepTogether([step_title, step_text]))
            
            if 'note' in step:
                note_text = Paragraph(f"<i>Note: {step['note']}</i>", 
                                    self.styles['InfoText'])
                self.story.append(note_text)
            
            self.story.append(Spacer(1, 0.2*inch))
    
    def _generate_assembly_steps(self) -> List[Dict[str, str]]:
        """Generate assembly steps based on base type."""
        steps = []
        
        # Material preparation
        steps.append({
            'title': 'Prepare Materials',
            'description': f'Cut the {self.config.primary_material.value.replace("_", " ")} '
                         f'to the specified dimensions: {self._get_dimensions_string()}. '
                         f'Ensure all edges are smooth and deburred.',
            'note': 'Wear appropriate safety equipment when cutting materials.'
        })
        
        # Marking mounting holes
        if self.config.mounting_points:
            steps.append({
                'title': 'Mark Mounting Holes',
                'description': 'Using the technical drawing as a guide, mark the positions '
                             'of all mounting holes on the material. Double-check measurements '
                             'before proceeding.',
                'note': 'Measure twice, drill once!'
            })
            
            steps.append({
                'title': 'Drill Mounting Holes',
                'description': 'Drill holes at the marked positions. Use the appropriate '
                             'drill bit size for each hole as specified in the technical drawing.',
                'note': 'Use a drill press if available for perpendicular holes.'
            })
        
        # Type-specific assembly
        if self.config.base_type.value.startswith('BOX'):
            steps.extend(self._get_box_assembly_steps())
        elif self.config.base_type.value == 'PEDESTAL':
            steps.extend(self._get_pedestal_assembly_steps())
        elif self.config.base_type.value == 'WALL_MOUNTED':
            steps.extend(self._get_wall_mount_steps())
        
        # Final steps
        steps.append({
            'title': 'Final Inspection',
            'description': 'Inspect the assembled base for any rough edges, loose connections, '
                         'or alignment issues. Make any necessary adjustments.',
        })
        
        steps.append({
            'title': 'Mount Mechanism',
            'description': 'Attach your automata mechanism to the base using the provided '
                         'mounting points. Ensure all connections are secure.',
            'note': 'Test the mechanism movement after mounting to ensure smooth operation.'
        })
        
        return steps
    
    def _get_box_assembly_steps(self) -> List[Dict[str, str]]:
        """Get assembly steps for box-type bases."""
        return [
            {
                'title': 'Assemble Box Sides',
                'description': 'Join the box sides together using wood glue and/or screws. '
                             'Ensure all corners are square and joints are tight.',
            },
            {
                'title': 'Attach Bottom',
                'description': 'Secure the bottom panel to the assembled sides. '
                             'Check that the box sits flat on a level surface.',
            }
        ]
    
    def _get_pedestal_assembly_steps(self) -> List[Dict[str, str]]:
        """Get assembly steps for pedestal bases."""
        return [
            {
                'title': 'Assemble Pedestal Structure',
                'description': 'Join the pedestal components according to the design. '
                             'Ensure the top platform is level and stable.',
            }
        ]
    
    def _get_wall_mount_steps(self) -> List[Dict[str, str]]:
        """Get assembly steps for wall-mounted bases."""
        return [
            {
                'title': 'Mark Wall Mounting Points',
                'description': 'Hold the base against the wall and mark the mounting hole positions. '
                             'Use a level to ensure the base will be mounted straight.',
            },
            {
                'title': 'Install Wall Anchors',
                'description': 'Drill holes in the wall and install appropriate anchors '
                             'for your wall type (drywall, concrete, etc.).',
            },
            {
                'title': 'Mount Base to Wall',
                'description': 'Secure the base to the wall using appropriate screws. '
                             'Ensure all mounting points are tight and the base is level.',
            }
        ]
    
    def _add_technical_drawing(self):
        """Add technical drawing section."""
        self.story.append(PageBreak())
        self.story.append(Paragraph("Technical Drawing", self.styles['SectionHeading']))
        
        # Generate SVG of the base
        svg_content = base_to_svg(self.config, mode='technical')
        
        # Note about SVG to PDF conversion
        note = Paragraph(
            "<i>Note: For accurate technical drawings, refer to the exported DXF or SVG files. "
            "The diagram below shows the general layout and mounting hole positions.</i>",
            self.styles['InfoText']
        )
        self.story.append(note)
        self.story.append(Spacer(1, 0.2*inch))
        
        # Add basic dimension diagram using ReportLab drawing
        drawing = self._create_dimension_diagram()
        if drawing:
            self.story.append(drawing)
    
    def _create_dimension_diagram(self):
        """Create a simple dimension diagram."""
        if not REPORTLAB_AVAILABLE:
            return None
        
        # Create drawing
        dims = self.config.dimensions
        if hasattr(dims, 'width') and hasattr(dims, 'height'):
            # Scale to fit on page
            max_size = 5 * inch
            scale = min(max_size / dims.width, max_size / dims.height)
            
            width = dims.width * scale
            height = dims.height * scale
            
            d = Drawing(width + 2*inch, height + 2*inch)
            
            # Draw base outline
            d.add(Rect(inch, inch, width, height, 
                      strokeColor=colors.black, fillColor=None, strokeWidth=2))
            
            # Add dimension lines
            # Width dimension
            d.add(Line(inch, 0.5*inch, inch + width, 0.5*inch, 
                      strokeColor=colors.black, strokeWidth=1))
            d.add(String(inch + width/2, 0.3*inch, f"{dims.width} {dims.unit.value}",
                        textAnchor='middle'))
            
            # Height dimension
            d.add(Line(0.5*inch, inch, 0.5*inch, inch + height,
                      strokeColor=colors.black, strokeWidth=1))
            d.add(String(0.3*inch, inch + height/2, f"{dims.height} {dims.unit.value}",
                        textAnchor='middle'))
            
            # Add mounting holes
            for mp in self.config.mounting_points:
                x = inch + mp.position.x * scale
                y = inch + mp.position.y * scale
                radius = mp.hole_diameter * scale / 2
                
                # Draw hole marker
                d.add(Line(x - radius, y, x + radius, y,
                          strokeColor=colors.red, strokeWidth=1))
                d.add(Line(x, y - radius, x, y + radius,
                          strokeColor=colors.red, strokeWidth=1))
                
                # Add label
                d.add(String(x + radius + 5, y, mp.thread_type,
                            fontSize=8, fillColor=colors.red))
            
            return d
        
        return None
    
    def _add_safety_notes(self):
        """Add safety notes section."""
        self.story.append(Paragraph("Safety Notes", self.styles['SectionHeading']))
        
        safety_notes = [
            "Always wear appropriate safety equipment including safety glasses and gloves.",
            "Use tools according to manufacturer's instructions.",
            "Work in a well-ventilated area, especially when using adhesives or finishes.",
            "Keep work area clean and organized to prevent accidents.",
            "Double-check all measurements before cutting or drilling.",
            "Ensure the base is stable before mounting any mechanisms.",
        ]
        
        for note in safety_notes:
            self.story.append(Paragraph(f"• {note}", self.styles['InfoText']))
        
        self.story.append(Spacer(1, 0.3*inch))
    
    def _add_maintenance_tips(self):
        """Add maintenance tips section."""
        self.story.append(Paragraph("Maintenance Tips", self.styles['SectionHeading']))
        
        # Material-specific maintenance
        material_maintenance = {
            MaterialType.WOOD: [
                "Apply wood finish or sealant to protect against moisture.",
                "Check for splits or cracks periodically.",
                "Re-tighten screws if they become loose over time."
            ],
            MaterialType.ALUMINUM: [
                "Clean with mild soap and water.",
                "Check for corrosion, especially at connection points.",
                "Apply a thin layer of machine oil to moving parts."
            ],
            MaterialType.ACRYLIC: [
                "Clean with acrylic-safe cleaners only.",
                "Avoid exposure to harsh chemicals.",
                "Check for stress cracks around mounting holes."
            ],
        }
        
        tips = material_maintenance.get(self.config.primary_material, [
            "Regularly inspect all connections and mounting points.",
            "Keep the base clean and free from debris.",
            "Store in a dry location when not in use."
        ])
        
        for tip in tips:
            self.story.append(Paragraph(f"• {tip}", self.styles['InfoText']))
    
    def generate(self, output_path: Path) -> Path:
        """
        Generate PDF assembly instructions.
        
        Args:
            output_path: Path to save the PDF file
        
        Returns:
            Path to the generated PDF
        """
        if not REPORTLAB_AVAILABLE:
            # Fallback: create a simple text file
            with open(output_path.with_suffix('.txt'), 'w') as f:
                f.write(f"Assembly Instructions for {self.config.name}\n")
                f.write("=" * 50 + "\n\n")
                f.write("PDF generation requires ReportLab library.\n")
                f.write("Install with: pip install reportlab\n\n")
                f.write(f"Base Type: {self.config.base_type.value}\n")
                f.write(f"Material: {self.config.primary_material.value}\n")
                f.write(f"Dimensions: {self._get_dimensions_string()}\n")
            return output_path.with_suffix('.txt')
        
        # Create PDF document
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=self.page_size,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18,
        )
        
        # Build content
        self.story = []
        self._add_header()
        self._add_overview()
        self._add_materials_list()
        self._add_assembly_steps()
        self._add_technical_drawing()
        self._add_safety_notes()
        self._add_maintenance_tips()
        
        # Generate PDF
        doc.build(self.story)
        
        logger.info(f"Generated PDF assembly instructions: {output_path}")
        return output_path


def generate_assembly_pdf(config: BaseConfiguration, output_path: Path) -> Path:
    """
    Convenience function to generate assembly PDF.
    
    Args:
        config: Base configuration
        output_path: Output file path
    
    Returns:
        Path to generated PDF
    """
    generator = PDFGenerator(config)
    return generator.generate(output_path)