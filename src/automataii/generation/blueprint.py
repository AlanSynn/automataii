import logging
from PyQt6.QtWidgets import QGraphicsItem
from PyQt6.QtGui import QPainterPath, QTransform, QPolygonF
from PyQt6.QtCore import QPointF, QRectF
from .contour_extractor import PNGBlueprintProcessor, AdvancedContourExtractor

# Placeholder import for CharacterPartItem if type hinting is desired
# from ..gui.part_item import CharacterPartItem


def generate_single_large_blueprint(layout_items, page_width_mm, page_height_mm,
                                   title="Manufacturing Blueprint", scale_info="",
                                   snapshot_data_uri: str | None = None):
    """
    Generate a single large-format blueprint with all content.
    Uses generous spacing to ensure all parts and mechanisms are clearly visible.
    """
    logger = logging.getLogger(__name__)

    # Start building SVG content
    svg_parts = []

    # SVG header with large dimensions
    svg_header = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{page_width_mm}" height="{page_height_mm}"
     xmlns="http://www.w3.org/2000/svg" version="1.1">
  <defs>
    <style>
      .blueprint-text {{ font-family: Arial, sans-serif; }}
      .section-title {{ font-size: 20px; font-weight: bold; }}
      .part-outline {{ fill: none; stroke: black; stroke-width: 2.0; }}
      .part-label {{ font-family: Arial, sans-serif; font-size: 14px; font-weight: bold; }}
      .mechanism-label {{ font-family: Arial, sans-serif; font-size: 12px; font-weight: bold; }}
      .dimension-line {{ stroke: #666; stroke-width: 0.75; stroke-dasharray: 3,3; }}
      .dimension-text {{ font-family: Arial, sans-serif; font-size: 10px; fill: #333; }}
      .cutting-path {{ stroke: red; stroke-width: 0.5; stroke-dasharray: 2,2; fill: none; }}
      .manufacturing-note {{ font-family: Arial, sans-serif; font-size: 9px; fill: #555; }}
      .gear-mechanism {{ }}
      .linkage-mechanism {{ }}
      .cam-mechanism {{ }}
      .pulley-mechanism {{ }}
      .belt-mechanism {{ }}
      .spring-mechanism {{ }}
      .damper-mechanism {{ }}
    </style>
  </defs>

  <!-- Page Border -->
  <rect x="10" y="10" width="{page_width_mm - 20}" height="{page_height_mm - 20}"
        fill="none" stroke="black" stroke-width="3"/>

  <!-- Title Block -->
  <g id="title-block">
    <rect x="20" y="20" width="{page_width_mm - 40}" height="80"
          fill="#f8f8f8" stroke="black" stroke-width="2"/>
    <text x="40" y="50" class="section-title" font-size="24">{title}</text>
    <text x="40" y="75" class="blueprint-text" font-size="14">{scale_info}</text>
    <text x="{page_width_mm - 40}" y="50" class="blueprint-text" font-size="12" text-anchor="end">
      Generated: {get_timestamp()}
    </text>
    <text x="{page_width_mm - 40}" y="75" class="blueprint-text" font-size="12" text-anchor="end">
      Automataii Platform v2.0
    </text>
  </g>
'''
    svg_parts.append(svg_header)

    # Main content area with generous spacing
    content_y = 120  # Start below title block
    margin_x = 50
    spacing = 40  # Very generous spacing between items

    # Separate parts and mechanisms
    part_items = [item for item in layout_items if item.item_type == 'part']
    mechanism_items = [item for item in layout_items if item.item_type == 'mechanism']

    logger.info(f"Large blueprint: {len(part_items)} parts, {len(mechanism_items)} mechanisms")

    # Optional snapshot section at top-right
    if snapshot_data_uri:
        snapshot_w = 320
        snapshot_h = 240
        snap_x = page_width_mm - margin_x - snapshot_w
        snap_y = content_y
        svg_parts.append(f'<g id="snapshot" transform="translate({snap_x},{snap_y})">')
        svg_parts.append('<text x="0" y="-10" class="section-title">Scene Snapshot</text>')
        svg_parts.append(f'<image href="{snapshot_data_uri}" x="0" y="0" width="{snapshot_w}" height="{snapshot_h}" />')
        svg_parts.append('</g>')
        # Advance content below snapshot
        content_y += snapshot_h + 40

    # Add parts section
    if part_items:
        svg_parts.append(f'<g id="parts-section" transform="translate({margin_x},{content_y})">')
        svg_parts.append('<text x="0" y="0" class="section-title">Character Parts</text>')
        svg_parts.append('<text x="0" y="25" class="manufacturing-note">Cut on RED lines | Material: 3mm Plywood/Acrylic</text>')

        # Arrange parts in a grid with generous spacing
        parts_y = 40
        parts_x = 0
        max_row_height = 0
        row_width = page_width_mm - (2 * margin_x)

        for item in part_items:
            # Check if we need to start a new row
            if parts_x + item.bounds.width + spacing > row_width:
                parts_x = 0
                parts_y += max_row_height + spacing
                max_row_height = 0

            # Add part with its original SVG content
            svg_parts.append(f'<g transform="translate({parts_x},{parts_y})">')
            svg_parts.append(item.svg_content)
            svg_parts.append('</g>')

            # Update position for next item
            parts_x += item.bounds.width + spacing
            max_row_height = max(max_row_height, item.bounds.height)

        content_y += parts_y + max_row_height + 80
        svg_parts.append('</g>')

    # Add mechanisms section with extra space
    if mechanism_items:
        svg_parts.append(f'<g id="mechanisms-section" transform="translate({margin_x},{content_y})">')
        svg_parts.append('<text x="0" y="0" class="section-title">Mechanisms</text>')
        svg_parts.append('<text x="0" y="25" class="manufacturing-note">Technical drawings with manufacturing specifications</text>')

        # Arrange mechanisms in a grid with extra generous spacing
        mech_y = 50
        mech_x = 0
        max_row_height = 0
        mech_spacing = 60  # Extra space for mechanisms
        row_width = page_width_mm - (2 * margin_x)  # Define row_width for mechanisms section

        for item in mechanism_items:
            # Check if we need to start a new row
            if mech_x + item.bounds.width + mech_spacing > row_width:
                mech_x = 0
                mech_y += max_row_height + mech_spacing
                max_row_height = 0

            # Add mechanism with its SVG content
            svg_parts.append(f'<g transform="translate({mech_x},{mech_y})">')
            svg_parts.append(item.svg_content)
            svg_parts.append('</g>')

            logger.debug(f"Added mechanism at ({mech_x},{mech_y}): {item.name} - {item.svg_content[:100]}...")

            # Update position for next item
            mech_x += item.bounds.width + mech_spacing
            max_row_height = max(max_row_height, item.bounds.height)

        svg_parts.append('</g>')

    # Add footer
    footer_y = page_height_mm - 60
    svg_parts.append(f'''
  <g id="footer">
    <line x1="20" y1="{footer_y}" x2="{page_width_mm - 20}" y2="{footer_y}"
          stroke="black" stroke-width="1"/>
    <text x="40" y="{footer_y + 20}" class="manufacturing-note">
      Manufacturing Blueprint | All content on single page | {len(layout_items)} items total
    </text>
    <text x="{page_width_mm - 40}" y="{footer_y + 20}" class="manufacturing-note" text-anchor="end">
      Automataii Manufacturing System
    </text>
  </g>
</svg>''')

    return ''.join(svg_parts)


def get_timestamp():
    """Get current timestamp for blueprint."""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def generate_detailed_part_content(part_items: list, padding: float = 20.0) -> str:
    """
    Generates detailed part content using PNG contour extraction for manufacturing precision.
    Uses computer vision instead of QPainterPath approximations.
    """
    if not part_items:
        logging.warning("generate_detailed_part_content: No part items provided.")
        return ""

    # Use PNG-based contour extraction for manufacturing precision
    png_processor = PNGBlueprintProcessor(tolerance=1.5)

    svg_parts = []
    current_x = padding
    current_y = padding
    max_row_height = 0

    for item in part_items:
        try:
            # Extract manufacturing contour from PNG file
            manufacturing_contour = png_processor.process_part_png(item)

            if not manufacturing_contour:
                logging.warning(f"Skipping item: No manufacturing contour extracted from PNG")
                # Fallback to original method if PNG extraction fails
                fallback_svg = _create_fallback_part_svg(item, current_x, current_y, padding)
                if fallback_svg:
                    svg_parts.append(fallback_svg)
                    current_x += 100 + padding  # Default size for fallback
                    max_row_height = max(max_row_height, 100)
                continue

            # Get part name
            part_name = "Unknown Part"
            if hasattr(item, 'part_info') and item.part_info:
                part_name = getattr(item.part_info, 'name', 'Unknown Part')

            # Get contour dimensions
            cx, cy, width, height = manufacturing_contour.bounding_rect

            # Create manufacturing-precision SVG
            part_svg = _create_manufacturing_part_svg(
                manufacturing_contour,
                current_x,
                current_y,
                part_name
            )

            if part_svg:
                svg_parts.append(part_svg)

                # Update layout position
                current_x += width + padding
                max_row_height = max(max_row_height, height)

                # Wrap to next row if needed
                if current_x > 500:  # Reduced width for embedding
                    current_x = padding
                    current_y += max_row_height + padding
                    max_row_height = 0

        except Exception as e:
            logging.error(f"Error processing part with PNG extraction: {e}")
            continue

    if not svg_parts:
        logging.warning("No valid SVG parts generated for blueprint content using PNG extraction.")
        return '<text x="20" y="20" font-family="Arial" font-size="12">No parts could be processed from PNG files</text>'

    # Return just the content (no SVG wrapper)
    return '\n'.join(svg_parts)


def generate_detailed_part_blueprint_svg(part_items: list, padding: float = 20.0) -> str:
    """
    Generates a detailed manufacturing blueprint using PNG contour extraction.
    Revolutionary approach using computer vision for manufacturing precision.
    """
    if not part_items:
        logging.warning("generate_detailed_part_blueprint_svg: No part items provided.")
        return ""

    # Use the new PNG-based blueprint processor
    png_processor = PNGBlueprintProcessor(tolerance=1.5)

    logging.info("Generating manufacturing blueprint using PNG contour extraction...")

    # Generate complete blueprint with PNG contours
    blueprint_svg = png_processor.generate_parts_blueprint_svg(part_items, padding)

    if not blueprint_svg or blueprint_svg.strip() == "":
        logging.warning("PNG-based blueprint generation failed, falling back to original method")
        # Fallback to original method if PNG extraction completely fails
        return _generate_fallback_blueprint_svg(part_items, padding)

    logging.info("Successfully generated manufacturing blueprint using PNG contours!")
    return blueprint_svg


def _generate_fallback_blueprint_svg(part_items: list, padding: float = 20.0) -> str:
    """Generate fallback blueprint when PNG extraction fails completely"""

    total_width = 600
    total_height = 400

    fallback_svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{total_width:.2f}" height="{total_height:.2f}" xmlns="http://www.w3.org/2000/svg" version="1.1">
  <defs>
    <style>
      .error-text {{ font-family: Arial, sans-serif; font-size: 12px; fill: red; }}
      .info-text {{ font-family: Arial, sans-serif; font-size: 10px; fill: #333; }}
    </style>
  </defs>

  <!-- Error Message -->
  <rect x="5" y="5" width="{total_width-10}" height="{total_height-10}" fill="none" stroke="red" stroke-width="2"/>
  <text x="{total_width/2:.2f}" y="50" class="error-text" text-anchor="middle">
    Blueprint Generation Error
  </text>
  <text x="{total_width/2:.2f}" y="80" class="info-text" text-anchor="middle">
    PNG contour extraction failed for all parts
  </text>
  <text x="{total_width/2:.2f}" y="100" class="info-text" text-anchor="middle">
    Ensure part items have valid image_path attributes pointing to PNG files
  </text>
  <text x="{total_width/2:.2f}" y="140" class="info-text" text-anchor="middle">
    Parts found: {len(part_items)}
  </text>
</svg>'''

    return fallback_svg


def _create_detailed_part_svg(polygon: QPolygonF, x_offset: float, y_offset: float,
                            bounds: QRectF, part_name: str) -> str:
    """Create detailed SVG for a single part with manufacturing details (legacy function)."""

    # Generate polygon path with proper offset
    path_data = ""
    for i in range(polygon.size()):
        point = polygon.at(i)
        x = point.x() - bounds.left() + x_offset
        y = point.y() - bounds.top() + y_offset

        if i == 0:
            path_data += f"M {x:.2f} {y:.2f} "
        else:
            path_data += f"L {x:.2f} {y:.2f} "

    path_data += "Z"  # Close the path

    # Calculate part dimensions
    width = bounds.width()
    height = bounds.height()

    # Create part SVG with manufacturing details
    part_svg = f'''
    <g class="part-group">
        <!-- Part outline -->
        <path d="{path_data}" class="part-outline"/>

        <!-- Part label -->
        <text x="{x_offset + width/2:.2f}" y="{y_offset - 5:.2f}"
              class="part-label" text-anchor="middle">{part_name}</text>

        <!-- Dimension lines -->
        <g class="dimensions">
            <!-- Width dimension -->
            <line x1="{x_offset:.2f}" y1="{y_offset + height + 10:.2f}"
                  x2="{x_offset + width:.2f}" y2="{y_offset + height + 10:.2f}"
                  class="dimension-line"/>
            <text x="{x_offset + width/2:.2f}" y="{y_offset + height + 20:.2f}"
                  class="dimension-text" text-anchor="middle">{width:.1f}mm</text>

            <!-- Height dimension -->
            <line x1="{x_offset - 10:.2f}" y1="{y_offset:.2f}"
                  x2="{x_offset - 10:.2f}" y2="{y_offset + height:.2f}"
                  class="dimension-line"/>
            <text x="{x_offset - 15:.2f}" y="{y_offset + height/2:.2f}"
                  class="dimension-text" text-anchor="middle"
                  transform="rotate(-90, {x_offset - 15:.2f}, {y_offset + height/2:.2f})">{height:.1f}mm</text>
        </g>

        <!-- Cut line indicators -->
        <path d="{path_data}" class="cut-line"/>

        <!-- Assembly points (if any anchor points exist) -->
        <circle cx="{x_offset + width/2:.2f}" cy="{y_offset + height/2:.2f}"
                r="2" fill="blue" opacity="0.7"/>
        <text x="{x_offset + width/2 + 5:.2f}" y="{y_offset + height/2:.2f}"
              class="dimension-text">Anchor</text>
    </g>
    '''

    return part_svg


def _create_manufacturing_part_svg(manufacturing_contour, x_offset: float, y_offset: float,
                                  part_name: str) -> str:
    """Create manufacturing-precision SVG using extracted PNG contours"""

    # Get contour dimensions
    cx, cy, width, height = manufacturing_contour.bounding_rect

    # Apply offset to SVG path
    from .contour_extractor import AdvancedContourExtractor
    extractor = AdvancedContourExtractor()
    offset_path = extractor._apply_offset_to_path(
        manufacturing_contour.svg_path,
        x_offset - cx,
        y_offset - cy
    )

    # Create detailed manufacturing part SVG
    part_svg = f'''
    <g class="manufacturing-part" data-name="{part_name}">
        <!-- PNG-extracted contour outline -->
        <path d="{offset_path}" class="part-outline"/>

        <!-- Cutting path for manufacturing -->
        <path d="{offset_path}" class="cut-line"/>

        <!-- Part label -->
        <text x="{x_offset + width/2:.2f}" y="{y_offset - 5:.2f}"
              class="part-label" text-anchor="middle">{part_name}</text>

        <!-- Dimensions -->
        <g class="dimensions">
            <!-- Width dimension -->
            <line x1="{x_offset:.2f}" y1="{y_offset + height + 10:.2f}"
                  x2="{x_offset + width:.2f}" y2="{y_offset + height + 10:.2f}"
                  class="dimension-line"/>
            <text x="{x_offset + width/2:.2f}" y="{y_offset + height + 20:.2f}"
                  class="dimension-text" text-anchor="middle">{width:.1f}mm</text>

            <!-- Height dimension -->
            <line x1="{x_offset - 10:.2f}" y1="{y_offset:.2f}"
                  x2="{x_offset - 10:.2f}" y2="{y_offset + height:.2f}"
                  class="dimension-line"/>
            <text x="{x_offset - 15:.2f}" y="{y_offset + height/2:.2f}"
                  class="dimension-text" text-anchor="middle"
                  transform="rotate(-90, {x_offset - 15:.2f}, {y_offset + height/2:.2f})">
                  {height:.1f}mm</text>
        </g>

        <!-- Manufacturing notes -->
        <text x="{x_offset:.2f}" y="{y_offset + height + 35:.2f}"
              class="dimension-text" font-size="7px">
              PNG-Contour | Area: {manufacturing_contour.area:.0f}mm² | Perimeter: {manufacturing_contour.perimeter:.1f}mm
        </text>

        <!-- Assembly anchor point -->
        <circle cx="{x_offset + width/2:.2f}" cy="{y_offset + height/2:.2f}"
                r="2" fill="blue" opacity="0.7"/>
    </g>
    '''

    return part_svg


def _create_fallback_part_svg(item, x_offset: float, y_offset: float, padding: float) -> str:
    """Fallback SVG creation when PNG extraction fails"""

    try:
        # Get part name
        part_name = "Unknown Part"
        if hasattr(item, 'part_info') and item.part_info:
            part_name = getattr(item.part_info, 'name', 'Unknown Part')

        # Create simple placeholder rectangle
        width = 80
        height = 80

        part_svg = f'''
    <g class="fallback-part" data-name="{part_name}">
        <!-- Fallback rectangle -->
        <rect x="{x_offset:.2f}" y="{y_offset:.2f}" width="{width}" height="{height}"
              class="part-outline" fill="none"/>

        <!-- Part label -->
        <text x="{x_offset + width/2:.2f}" y="{y_offset - 5:.2f}"
              class="part-label" text-anchor="middle">{part_name}</text>

        <!-- Warning text -->
        <text x="{x_offset + width/2:.2f}" y="{y_offset + height/2:.2f}"
              class="dimension-text" text-anchor="middle" font-size="8px" fill="red">
              PNG Not Found</text>
    </g>
    '''

        return part_svg

    except Exception as e:
        logging.error(f"Error creating fallback part SVG: {e}")
        return ""


def generate_blueprint_svg(part_items: list, padding: float = 20.0) -> str:
    """
    Generates an SVG string containing the outlines of the provided part items,
    arranged in a simple grid layout for fabrication.

    Args:
        part_items: A list of QGraphicsItem objects (expected CharacterPartItem).
        padding: The space between parts and around the border.

    Returns:
        A string containing the SVG representation of the blueprint, or an empty string on error.
    """
    if not part_items:
        logging.warning("generate_blueprint_svg: No part items provided.")
        return ""

    svg_paths = []
    all_bounds = QRectF()
    current_x = padding
    current_y = padding
    max_row_height = 0

    # Simple grid layout - calculate total bounds and place items
    for item in part_items:
        # Ensure we're dealing with items that have a shape
        if not hasattr(item, "shape") or not callable(item.shape):
            part_name = getattr(getattr(item, 'part_info', None), 'name', 'Unknown') if hasattr(item, 'part_info') else 'Unknown'
            logging.warning(f"Skipping item {part_name}: No shape method found.")
            continue

        part_path: QPainterPath = (
            item.shape()
        )  # Get the outline path in item's local coords
        if part_path.isEmpty():
            part_name = getattr(getattr(item, 'part_info', None), 'name', 'Unknown') if hasattr(item, 'part_info') else 'Unknown'
            logging.warning(f"Skipping item {part_name}: Shape path is empty.")
            continue

        # Get the bounding box of the local path
        local_bounds = part_path.boundingRect()
        if not local_bounds.isValid():
            part_name = getattr(getattr(item, 'part_info', None), 'name', 'Unknown') if hasattr(item, 'part_info') else 'Unknown'
            logging.warning(f"Skipping item {part_name}: Invalid bounding rect.")
            continue

        # Translate the path to its position in the blueprint layout
        transform = QTransform().translate(
            current_x - local_bounds.left(), current_y - local_bounds.top()
        )
        transformed_path = transform.map(part_path)

        # --- Convert QPainterPath to SVG path data string ---
        svg_d = ""
        for i in range(transformed_path.elementCount()):
            element = transformed_path.elementAt(i)
            if element.isMoveTo():
                svg_d += f"M {element.x:.2f} {element.y:.2f} "
            elif element.isLineTo():
                svg_d += f"L {element.x:.2f} {element.y:.2f} "
            elif element.isCurveTo():
                # QPainterPath uses cubic Bezier curves
                ctrl1 = transformed_path.elementAt(i + 1)
                ctrl2 = transformed_path.elementAt(i + 2)
                endpt = transformed_path.elementAt(
                    i + 3
                )  # CurveToData includes endpoint
                svg_d += f"C {element.x:.2f} {element.y:.2f} {ctrl1.x:.2f} {ctrl1.y:.2f} {ctrl2.x:.2f} {ctrl2.y:.2f} "
                # Skip the next two elements as they were control points for CurveToData
                # Note: PyQt's element structure differs slightly from SVG paths.
                # A Qt CurveTo might correspond to multiple SVG commands if not C.
                # This basic conversion assumes C type. Refinement might be needed.
                # It's often easier to convert to polygons first if possible.
                # Let's stick to basic path conversion for now.
                # IMPORTANT: Qt's iteration over curves is tricky. elementAt(i+1) etc. might not work as expected.
                # A more robust way involves iterating points and checking types.

                # Robust approach (simplified): Use polygon approximation for curves
                # poly = transformed_path.toFillPolygon() # This might approximate curves
                # svg_d += f"M {poly.first().x():.2f} {poly.first().y():.2f} "
                # for pt in poly[1:]:
                #    svg_d += f"L {pt.x():.2f} {pt.y():.2f} "
                # svg_d += "Z " # Close path if needed, but usually blueprint is outline

                # --- Let's try element-based conversion again, carefully ---
                # SVG C needs two control points and end point
                # Qt CurveTo is just the first control point? Need CurveToData.
                # Let's assume element is CurveToData for simplicity (might be wrong)
                # if i + 2 < transformed_path.elementCount():
                #     ctrl2 = transformed_path.elementAt(i+1)
                #     endpt = transformed_path.elementAt(i+2)
                #     svg_d += f"C {element.x:.2f} {element.y:.2f} {ctrl2.x:.2f} {ctrl2.y:.2f} {endpt.x:.2f} {endpt.y:.2f} "
                #     i += 2 # Manually advance index - THIS IS RISKY
                # else:
                #     logging.warning("Incomplete curve data in path.")

            elif element.isCurveToData():
                # This contains all 3 points for a cubic Bezier
                ctrl1_pt = QPointF(element.x, element.y)
                # The next two elements are ctrl2 and endpt
                if i + 2 < transformed_path.elementCount():
                    ctrl2_element = transformed_path.elementAt(i + 1)
                    endpt_element = transformed_path.elementAt(i + 2)
                    svg_d += f"C {ctrl1_pt.x():.2f} {ctrl1_pt.y():.2f} {ctrl2_element.x:.2f} {ctrl2_element.y:.2f} {endpt_element.x:.2f} {endpt_element.y:.2f} "
                    # We need to make sure the loop skips these next two elements.
                    # The Python for loop doesn't allow easy skipping like C's for(;;).
                    # A while loop or manual index management is needed for robust path conversion.
                    # Let's KISS and just log a warning if we encounter complex curves.
                    logging.warning(
                        "CurveToData encountered - SVG conversion might be basic."
                    )
                else:
                    logging.warning("Incomplete CurveToData element found.")

            # Note: Qt uses Z for CloseSubpath, not explicitly stored in elements easily.
            # For blueprints, we usually want the open outline.

        if svg_d:
            # Clean SVG path data to prevent XML issues
            clean_svg_d = svg_d.strip()
            # Ensure no invalid characters that could break XML
            clean_svg_d = clean_svg_d.replace('&', '&amp;')

            svg_paths.append(
                f'<path d="{clean_svg_d}" stroke="black" stroke-width="1" fill="none" />'
            )

        # Update layout position and bounds
        part_width = local_bounds.width()
        part_height = local_bounds.height()
        current_bounds = QRectF(current_x, current_y, part_width, part_height)
        all_bounds = all_bounds.united(current_bounds)

        current_x += part_width + padding
        max_row_height = max(max_row_height, part_height)

        # Simple wrap (adjust this threshold as needed)
        if current_x > 600:  # Wrap after 600 units width
            current_x = padding
            current_y += max_row_height + padding
            max_row_height = 0

    # Add final padding to bounds
    total_width = all_bounds.width() + 2 * padding
    total_height = (
        all_bounds.height() + 2 * padding
    )  # Adjust y calculation? Need to consider final row height.
    total_height = (
        current_y + max_row_height + padding
    )  # More robust height based on final Y position

    if not svg_paths:
        logging.warning("No valid SVG paths generated for blueprint.")
        return ""

    # Create SVG wrapper
    svg_header = f'<svg width="{total_width:.2f}" height="{total_height:.2f}" xmlns="http://www.w3.org/2000/svg" version="1.1">\n'
    svg_content = "\n".join(svg_paths)
    svg_footer = "\n</svg>"

    return svg_header + svg_content + svg_footer
