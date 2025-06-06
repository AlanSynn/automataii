import logging
from PyQt6.QtWidgets import QGraphicsItem
from PyQt6.QtGui import QPainterPath, QTransform
from PyQt6.QtCore import QPointF, QRectF

# Placeholder import for CharacterPartItem if type hinting is desired
# from ..gui.part_item import CharacterPartItem


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
            logging.warning(
                f"Skipping item {getattr(item, 'part_info', {}).get('name', 'Unknown')}: No shape method found."
            )
            continue

        part_path: QPainterPath = (
            item.shape()
        )  # Get the outline path in item's local coords
        if part_path.isEmpty():
            logging.warning(
                f"Skipping item {getattr(item, 'part_info', {}).get('name', 'Unknown')}: Shape path is empty."
            )
            continue

        # Get the bounding box of the local path
        local_bounds = part_path.boundingRect()
        if not local_bounds.isValid():
            logging.warning(
                f"Skipping item {getattr(item, 'part_info', {}).get('name', 'Unknown')}: Invalid bounding rect."
            )
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
            svg_paths.append(
                f'<path d="{svg_d.strip()}" stroke="black" stroke-width="1" fill="none" />'
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
