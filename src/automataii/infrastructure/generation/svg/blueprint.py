import logging
import math
from collections.abc import Sequence
from html import escape as escape_xml

from automataii.domain.generation.contour import AdvancedContourExtractor
from automataii.domain.generation.contour.models import ManufacturingContour
from automataii.domain.generation.layout import LayoutItem
from automataii.infrastructure.generation.processors.png_blueprint import (
    PNGBlueprintProcessor,
)


def _positive_dimension(value: object, default: float) -> float:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) and number > 0.0 else default


def _safe_svg_text(value: object) -> str:
    return escape_xml(str(value or ""), quote=True)


def _safe_snapshot_data_uri(snapshot_data_uri: object) -> str | None:
    if not isinstance(snapshot_data_uri, str):
        return None
    value = snapshot_data_uri.strip()
    allowed_prefixes = (
        "data:image/png;base64,",
        "data:image/jpeg;base64,",
        "data:image/jpg;base64,",
        "data:image/webp;base64,",
        "data:image/gif;base64,",
    )
    if not value.lower().startswith(allowed_prefixes):
        return None
    return escape_xml(value, quote=True)


def _layout_item_name(item: object, fallback: str) -> str:
    for attr_name in ("name", "label", "part_name"):
        raw_value = getattr(item, attr_name, None)
        if raw_value:
            return _safe_svg_text(raw_value)
    return _safe_svg_text(fallback)


def _cut_sheet_handoff_panel(
    *,
    page_width_mm: float,
    part_count: int,
    mechanism_count: int,
) -> str:
    panel_width = page_width_mm - 40
    return f'''
  <g id="cut-sheet-handoff" transform="translate(20,120)">
    <rect x="0" y="0" width="{panel_width}" height="90"
          fill="#fff7ed" stroke="#ea580c" stroke-width="1.5" rx="6"/>
    <text x="20" y="24" class="callout-header">Make Parts / Cut Sheets boundary</text>
    <text x="20" y="44" class="callout-text">
      Cut/drill only: this sheet is not the board assembly order.
    </text>
    <text x="20" y="61" class="callout-text">
      Character body components: {part_count} | Mechanism parts: {mechanism_count} |
      Drill 4mm holes when shown.
    </text>
    <text x="20" y="78" class="callout-text">
      Paper fasteners are hardware, not cut parts; spacer/bracket stack order lives in
      assembly-guide.pdf.
    </text>
  </g>
'''


def generate_single_large_blueprint(
    layout_items: Sequence[LayoutItem] | None,
    page_width_mm: object,
    page_height_mm: object,
    title: object = "Manufacturing Blueprint",
    scale_info: object = "",
    snapshot_data_uri: str | None = None,
    unit_system: str = "metric",
) -> str:
    """
    Generate a single large-format blueprint with all content.
    Uses generous spacing to ensure all parts and mechanisms are clearly visible.

    Args:
        layout_items: List of LayoutItem objects
        page_width_mm: Page width in millimeters
        page_height_mm: Page height in millimeters
        title: Blueprint title
        scale_info: Scale information text
        snapshot_data_uri: Optional snapshot image data URI
        unit_system: "metric" for mm, "imperial" for inches

    Returns:
        SVG string containing the complete blueprint
    """
    logger = logging.getLogger(__name__)
    layout_items = list(layout_items) if layout_items is not None else []
    page_width_mm = max(120.0, _positive_dimension(page_width_mm, 800.0))
    page_height_mm = max(120.0, _positive_dimension(page_height_mm, 600.0))
    title = _safe_svg_text(title)
    scale_info = _safe_svg_text(scale_info)
    snapshot_data_uri = _safe_snapshot_data_uri(snapshot_data_uri)
    unit_system = "imperial" if unit_system == "imperial" else "metric"

    # Compute page geometry before the header is emitted. The previous fixed
    # 800x600 sheet could clip current-design exports once labels, mechanisms,
    # or snapshots pushed content below the footer.
    part_items = [item for item in layout_items if getattr(item, "item_type", None) == "part"]
    mechanism_items = [
        item for item in layout_items if getattr(item, "item_type", None) == "mechanism"
    ]
    margin_x = 50.0
    spacing = 40.0
    mech_spacing = 60.0

    def item_size(item: object, *, height_extra: float = 0.0) -> tuple[float, float]:
        bounds = getattr(item, "bounds", None)
        width = _positive_dimension(getattr(bounds, "width", 0.0), 1.0)
        height = _positive_dimension(getattr(bounds, "height", 0.0), 1.0) + height_extra
        return width, height

    max_item_width = 0.0
    for item in part_items:
        max_item_width = max(max_item_width, item_size(item)[0])
    for item in mechanism_items:
        # Mechanism SVGs reserve a right-side parameter panel.
        max_item_width = max(max_item_width, item_size(item)[0] + 195.0)
    if max_item_width:
        page_width_mm = max(page_width_mm, max_item_width + (2 * margin_x) + spacing)

    def section_bottom(
        items: list[object],
        start_y: float,
        *,
        local_y: float,
        item_spacing: float,
        item_width_extra: float,
        item_height_extra: float,
        bottom_padding: float,
    ) -> float:
        if not items:
            return start_y
        x = 0.0
        y = local_y
        row_height = 0.0
        row_width = max(1.0, page_width_mm - (2 * margin_x))
        for item in items:
            width, height = item_size(item, height_extra=item_height_extra)
            effective_width = width + item_width_extra
            if x > 0.0 and x + effective_width + item_spacing > row_width:
                x = 0.0
                y += row_height + item_spacing
                row_height = 0.0
            x += effective_width + item_spacing
            row_height = max(row_height, height)
        return start_y + y + row_height + bottom_padding

    required_height = 240.0 + (280.0 if snapshot_data_uri else 0.0)
    required_height = section_bottom(
        part_items,
        required_height,
        local_y=40.0,
        item_spacing=spacing,
        item_width_extra=0.0,
        item_height_extra=28.0,
        bottom_padding=80.0,
    )
    required_height = section_bottom(
        mechanism_items,
        required_height,
        local_y=50.0,
        item_spacing=mech_spacing,
        item_width_extra=195.0,
        item_height_extra=70.0,
        bottom_padding=80.0,
    )
    page_height_mm = max(page_height_mm, required_height + 100.0)
    title_clip_width = max(80.0, page_width_mm - 290.0)

    # Unit conversion functions
    def format_dimension(value_mm: float) -> str:
        value_mm = _positive_dimension(value_mm, 0.0)
        if unit_system == "imperial":
            inches = value_mm / 25.4
            if inches < 1.0:
                return f"{inches * 1000:.0f} mil"  # thousandths of inch
            elif inches < 12.0:
                return f'{inches:.2f}"'
            else:
                feet = inches / 12.0
                return f"{feet:.2f}'"
        else:
            return f"{value_mm:.1f}mm"

    # Start building SVG content
    svg_parts = []

    # Collect all clip path definitions from parts
    clip_definitions = []
    for item in layout_items:
        if hasattr(item, "svg_content") and "data-clip-def=" in item.svg_content:
            import html

            # Extract clip definition from data attribute
            start = item.svg_content.find('data-clip-def="') + len('data-clip-def="')
            end = item.svg_content.find('"', start)
            if start > len('data-clip-def="') - 1 and end > start:
                clip_def_encoded = item.svg_content[start:end]
                clip_def = html.unescape(clip_def_encoded)
                clip_definitions.append(f"    {clip_def}")

    # SVG header with large dimensions and consolidated defs
    svg_header = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{page_width_mm}mm" height="{page_height_mm}mm"
     viewBox="0 0 {page_width_mm} {page_height_mm}"
     xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" version="1.1">
  <defs>
    <clipPath id="title-block-title-clip">
      <rect x="40" y="28" width="{title_clip_width}" height="28"/>
    </clipPath>
    <style>
      .blueprint-text {{ font-family: Arial, sans-serif; }}
      .section-title {{ font-size: 20px; font-weight: bold; }}
      .part-outline {{ fill: none; stroke: black; stroke-width: 2.0; }}
      .part-label {{ font-family: Arial, sans-serif; font-size: 14px; font-weight: bold; }}
      .mechanism-label {{ font-family: Arial, sans-serif; font-size: 12px; font-weight: bold; }}
      .dimension-line {{ stroke: #666; stroke-width: 0.75; stroke-dasharray: 3,3; }}
      .dimension-text {{ font-family: Arial, sans-serif; font-size: 10px; fill: #333; }}
      .cutting-path {{ stroke: red; stroke-width: 0.5; stroke-dasharray: 2,2; fill: none; }}
      .pivot-drill-hole {{ fill: none; stroke: #2563eb; stroke-width: 0.75; }}
      .drill-hole-label {{ font-family: Arial, sans-serif; font-size: 7px; fill: #1d4ed8; }}
      .manufacturing-note {{ font-family: Arial, sans-serif; font-size: 9px; fill: #555; }}
      .gear-mechanism {{ }}
      .linkage-mechanism {{ }}
      .cam-mechanism {{ }}
      .pulley-mechanism {{ }}
      .belt-mechanism {{ }}
      .spring-mechanism {{ }}
      .damper-mechanism {{ }}
      .parameter-text {{ font-family: Arial, sans-serif; font-size: 8px; fill: #222; }}
      .parameter-header {{ font-family: Arial, sans-serif; font-size: 9px; font-weight: bold; fill: #333; }}
      .unit-info {{ font-family: Arial, sans-serif; font-size: 6px; fill: #888; font-style: italic; }}
      .callout-header {{ font-family: Arial, sans-serif; font-size: 13px; font-weight: bold; fill: #9a3412; }}
      .callout-text {{ font-family: Arial, sans-serif; font-size: 10px; fill: #431407; }}
      .part-guidance {{ font-family: Arial, sans-serif; font-size: 8px; fill: #374151; }}
    </style>
{chr(10).join(clip_definitions) if clip_definitions else ""}
  </defs>

  <!-- Page Border -->
  <rect x="10" y="10" width="{page_width_mm - 20}" height="{page_height_mm - 20}"
        fill="none" stroke="black" stroke-width="3"/>

  <!-- Title Block -->
  <g id="title-block">
    <rect x="20" y="20" width="{page_width_mm - 40}" height="90"
          fill="#f8f8f8" stroke="black" stroke-width="2"/>
    <text x="40" y="50" class="section-title" font-size="20"
          clip-path="url(#title-block-title-clip)">{title}</text>
    <text x="40" y="75" class="blueprint-text" font-size="12">{scale_info}</text>
    <text x="40" y="95" class="blueprint-text" font-size="10">
      Board preset: 15×15 holes | 4mm part holes | Assembly PDF gives placement
    </text>
    <text x="{page_width_mm - 40}" y="50" class="blueprint-text" font-size="12" text-anchor="end">
      Generated: {get_timestamp()}
    </text>
    <text x="{page_width_mm - 40}" y="75" class="blueprint-text" font-size="12" text-anchor="end">
      MotionSmith Platform v2.0
    </text>
  </g>
'''
    svg_parts.append(svg_header)

    logger.info(f"Large blueprint: {len(part_items)} parts, {len(mechanism_items)} mechanisms")
    svg_parts.append(
        _cut_sheet_handoff_panel(
            page_width_mm=page_width_mm,
            part_count=len(part_items),
            mechanism_count=len(mechanism_items),
        )
    )

    # Main content area with generous spacing
    content_y: float = 240.0

    # Optional snapshot section at top-right
    if snapshot_data_uri:
        snapshot_w = 320
        snapshot_h = 240
        snap_x = page_width_mm - margin_x - snapshot_w
        snap_y = content_y
        svg_parts.append(f'<g id="snapshot" transform="translate({snap_x},{snap_y})">')
        svg_parts.append('<text x="0" y="-10" class="section-title">Scene Snapshot</text>')
        svg_parts.append(
            f'<image href="{snapshot_data_uri}" x="0" y="0" width="{snapshot_w}" height="{snapshot_h}" />'
        )
        svg_parts.append("</g>")
        # Advance content below snapshot
        content_y += snapshot_h + 40

    # Add parts section
    if part_items:
        svg_parts.append(f'<g id="parts-section" transform="translate({margin_x},{content_y})">')
        svg_parts.append(
            '<text x="0" y="0" class="section-title">Character body component cut sheets</text>'
        )
        material_info = (
            "Cut RED outlines | Drill BLUE 4mm pivot/drive holes when shown | "
            "Board coordinates are in Assembly Guide"
        )
        if unit_system == "imperial":
            material_info = (
                "Cut RED outlines | Drill BLUE 4mm pivot/drive holes when shown | "
                'Use 1/8" sheet stock when self-fabricating'
            )
        svg_parts.append(f'<text x="0" y="25" class="manufacturing-note">{material_info}</text>')

        # Arrange parts in a grid with generous spacing
        parts_y: float = 40.0
        parts_x: float = 0.0
        max_row_height: float = 0.0
        row_width = page_width_mm - (2 * margin_x)

        for item in part_items:
            bounds = getattr(item, "bounds", None)
            item_width = _positive_dimension(getattr(bounds, "width", 0.0), 1.0)
            item_height = _positive_dimension(getattr(bounds, "height", 0.0), 1.0)
            # Check if we need to start a new row
            if parts_x > 0.0 and parts_x + item_width + spacing > row_width:
                parts_x = 0.0
                parts_y += max_row_height + spacing
                max_row_height = 0

            # Add part with its original SVG content (cleaned of data attributes)
            clean_svg_content = str(getattr(item, "svg_content", "") or "")
            # Remove the data-clip-def attribute since we've moved the definitions to the main defs section
            if "data-clip-def=" in clean_svg_content:
                start = clean_svg_content.find(' data-clip-def="')
                if start >= 0:
                    end = clean_svg_content.find('"', start + len(' data-clip-def="')) + 1
                    clean_svg_content = clean_svg_content[:start] + clean_svg_content[end:]

            svg_parts.append(f'<g transform="translate({parts_x},{parts_y})">')
            svg_parts.append(clean_svg_content)
            part_name = _layout_item_name(item, "Character component")
            note_y = item_height + 12
            svg_parts.append(f'<text x="0" y="{note_y}" class="part-guidance">{part_name}</text>')
            svg_parts.append(
                f'<text x="0" y="{note_y + 11}" class="part-guidance">'
                "Fastener/spacer location is assigned in the Assembly Guide.</text>"
            )
            svg_parts.append("</g>")

            # Update position for next item
            parts_x += item_width + spacing
            max_row_height = max(max_row_height, item_height + 28)

        content_y += parts_y + max_row_height + 80
        svg_parts.append("</g>")

    # Add mechanisms section with extra space
    if mechanism_items:
        svg_parts.append(
            f'<g id="mechanisms-section" transform="translate({margin_x},{content_y})">'
        )
        svg_parts.append('<text x="0" y="0" class="section-title">Mechanisms</text>')
        svg_parts.append(
            '<text x="0" y="25" class="manufacturing-note">'
            "Printable mechanism parts; use Board Assembly Guide for hole coordinates, stack order, "
            "spacers, brackets, and paper fasteners.</text>"
        )

        # Arrange mechanisms in a grid with extra generous spacing
        mech_y: float = 50.0
        mech_x: float = 0.0
        max_row_height = 0.0
        row_width = page_width_mm - (2 * margin_x)  # Define row_width for mechanisms section

        for item in mechanism_items:
            bounds = getattr(item, "bounds", None)
            item_width = _positive_dimension(getattr(bounds, "width", 0.0), 1.0)
            item_height = _positive_dimension(getattr(bounds, "height", 0.0), 1.0) + 70.0
            effective_width = item_width + 195.0
            # Check if we need to start a new row
            if mech_x > 0.0 and mech_x + effective_width + mech_spacing > row_width:
                mech_x = 0.0
                mech_y += max_row_height + mech_spacing
                max_row_height = 0

            # Add mechanism with its SVG content
            svg_parts.append(f'<g transform="translate({mech_x},{mech_y})">')
            svg_parts.append(str(getattr(item, "svg_content", "") or ""))
            svg_parts.append("</g>")

            logger.debug(
                "Added mechanism at (%s,%s): %s",
                mech_x,
                mech_y,
                getattr(item, "name", "unknown"),
            )

            # Update position for next item
            mech_x += effective_width + mech_spacing
            max_row_height = max(max_row_height, item_height)

        svg_parts.append("</g>")

    # Add footer with unit information
    footer_y = page_height_mm - 60
    svg_parts.append(f'''
  <g id="footer">
    <line x1="20" y1="{footer_y}" x2="{page_width_mm - 20}" y2="{footer_y}"
          stroke="black" stroke-width="1"/>
    <text x="40" y="{footer_y + 20}" class="manufacturing-note">
      Make Parts / Cut Sheets | Cut/drill only | {len(layout_items)} items total
    </text>
    <text x="{page_width_mm - 40}" y="{footer_y + 20}" class="manufacturing-note" text-anchor="end">
      MotionSmith Manufacturing System
    </text>
  </g>
</svg>''')

    return "".join(svg_parts)


def _generate_single_part_page(
    item: LayoutItem,
    page_num: int,
    total_pages: int,
    page_width_mm: float,
    page_height_mm: float,
    margin_mm: float,
    title: str,
    scale_info: str,
    snapshot_data_uri: str | None,
    unit_system: str = "metric",
) -> str:
    """Generate a single page for one character part"""

    content_width = page_width_mm - (2 * margin_mm)
    content_height = page_height_mm - (2 * margin_mm)

    # Unit conversion function
    def format_dimension(value_mm: float) -> str:
        if unit_system == "imperial":
            inches = value_mm / 25.4
            if inches < 1.0:
                return f"{inches * 1000:.0f} mil"
            elif inches < 12.0:
                return f'{inches:.2f}"'
            else:
                feet = inches / 12.0
                return f"{feet:.2f}'"
        else:
            return f"{value_mm:.1f}mm"

    def get_unit_label() -> str:
        return "Imperial" if unit_system == "imperial" else "Metric"

    # Calculate scaling to fit part on page
    available_width = content_width * 0.8  # Leave some margins
    available_height = content_height * 0.6  # Leave space for title and annotations

    scale_x = available_width / item.bounds.width if item.bounds.width > 0 else 1.0
    scale_y = available_height / item.bounds.height if item.bounds.height > 0 else 1.0
    page_scale = min(scale_x, scale_y, 1.0)  # Don't scale up, only down if needed

    # Center the part on the page
    scaled_width = item.bounds.width * page_scale
    scaled_height = item.bounds.height * page_scale
    part_x = margin_mm + (content_width - scaled_width) / 2
    part_y = margin_mm + 80 + (available_height - scaled_height) / 2  # 80mm for header

    # Extract clip definitions from the item's SVG content
    clip_definitions = []
    clean_svg_content = item.svg_content
    if "data-clip-def=" in item.svg_content:
        import html

        start = item.svg_content.find('data-clip-def="') + len('data-clip-def="')
        end = item.svg_content.find('"', start)
        if start > len('data-clip-def="') - 1 and end > start:
            clip_def_encoded = item.svg_content[start:end]
            clip_def = html.unescape(clip_def_encoded)
            clip_definitions.append(f"    {clip_def}")

            # Remove the data attribute from content
            attr_start = item.svg_content.find(' data-clip-def="')
            attr_end = item.svg_content.find('"', attr_start + len(' data-clip-def="')) + 1
            clean_svg_content = item.svg_content[:attr_start] + item.svg_content[attr_end:]

    # Material specifications based on unit system
    material_info = "Material: 3mm Plywood/Acrylic | Cut on RED dashed lines"
    if unit_system == "imperial":
        material_info = 'Material: 1/8" Plywood/Acrylic | Cut on RED dashed lines'

    # Generate page SVG
    page_svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{page_width_mm}" height="{page_height_mm}"
     xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" version="1.1">
  <defs>
    <style>
      .blueprint-text {{ font-family: Arial, sans-serif; }}
      .page-title {{ font-size: 16px; font-weight: bold; }}
      .part-title {{ font-size: 20px; font-weight: bold; }}
      .part-outline {{ fill: none; stroke: black; stroke-width: 2.0; }}
      .part-label {{ font-family: Arial, sans-serif; font-size: 14px; font-weight: bold; }}
      .dimension-line {{ stroke: #666; stroke-width: 0.75; stroke-dasharray: 3,3; }}
      .dimension-text {{ font-family: Arial, sans-serif; font-size: 10px; fill: #333; }}
      .cutting-path {{ stroke: red; stroke-width: 0.5; stroke-dasharray: 2,2; fill: none; }}
      .manufacturing-note {{ font-family: Arial, sans-serif; font-size: 9px; fill: #555; }}
      .unit-info {{ font-family: Arial, sans-serif; font-size: 6px; fill: #888; font-style: italic; }}
    </style>
{chr(10).join(clip_definitions) if clip_definitions else ""}
  </defs>

  <!-- Page Border -->
  <rect x="{margin_mm / 2}" y="{margin_mm / 2}" width="{page_width_mm - margin_mm}" height="{page_height_mm - margin_mm}"
        fill="none" stroke="black" stroke-width="1"/>

  <!-- Header -->
  <g id="header">
    <text x="{margin_mm}" y="{margin_mm + 20}" class="page-title">{title}</text>
    <text x="{margin_mm}" y="{margin_mm + 35}" class="blueprint-text" font-size="12">{scale_info}</text>
    <text x="{margin_mm}" y="{margin_mm + 50}" class="unit-info">Units: {get_unit_label()}</text>
    <text x="{page_width_mm - margin_mm}" y="{margin_mm + 20}" class="blueprint-text" font-size="10" text-anchor="end">
      Page {page_num} of {total_pages}
    </text>
    <text x="{page_width_mm - margin_mm}" y="{margin_mm + 35}" class="blueprint-text" font-size="10" text-anchor="end">
      Generated: {get_timestamp()}
    </text>
  </g>

  <!-- Part Title -->
  <text x="{page_width_mm / 2}" y="{margin_mm + 70}" class="part-title" text-anchor="middle">{item.name}</text>

  <!-- Part Content (scaled and centered) -->
  <g transform="translate({part_x:.1f},{part_y:.1f}) scale({page_scale:.3f})">
    {clean_svg_content}
  </g>

  <!-- Manufacturing Information -->
  <g id="manufacturing-info">
    <text x="{margin_mm}" y="{page_height_mm - 75}" class="manufacturing-note">
      Actual Size: {format_dimension(item.bounds.width)} × {format_dimension(item.bounds.height)}
    </text>
    <text x="{margin_mm}" y="{page_height_mm - 60}" class="manufacturing-note">
      Page Scale: {page_scale:.1%} (1:{1 / page_scale:.1f})
    </text>
    <text x="{margin_mm}" y="{page_height_mm - 45}" class="manufacturing-note">
      {material_info}
    </text>
    <text x="{margin_mm}" y="{page_height_mm - 30}" class="manufacturing-note">
      Units: {get_unit_label()} | Precision manufacturing dimensions
    </text>
  </g>

  <!-- Footer -->
  <line x1="{margin_mm}" y1="{page_height_mm - 15}" x2="{page_width_mm - margin_mm}" y2="{page_height_mm - 15}"
        stroke="black" stroke-width="0.5"/>
  <text x="{page_width_mm / 2}" y="{page_height_mm - 5}" class="blueprint-text" font-size="8" text-anchor="middle">
    MotionSmith Manufacturing System - Part Blueprint
  </text>
</svg>'''

    return page_svg


def _generate_single_mechanism_page(
    item: LayoutItem,
    page_num: int,
    total_pages: int,
    page_width_mm: float,
    page_height_mm: float,
    margin_mm: float,
    title: str,
    scale_info: str,
    snapshot_data_uri: str | None,
    unit_system: str = "metric",
) -> str:
    """Generate a single page for one mechanism with enhanced details"""

    content_width = page_width_mm - (2 * margin_mm)
    content_height = page_height_mm - (2 * margin_mm)

    # Unit conversion function
    def format_dimension(value_mm: float) -> str:
        if unit_system == "imperial":
            inches = value_mm / 25.4
            if inches < 1.0:
                return f"{inches * 1000:.0f} mil"
            elif inches < 12.0:
                return f'{inches:.2f}"'
            else:
                feet = inches / 12.0
                return f"{feet:.2f}'"
        else:
            return f"{value_mm:.1f}mm"

    def get_unit_label() -> str:
        return "Imperial" if unit_system == "imperial" else "Metric"

    # Calculate scaling to fit mechanism on page
    available_width = content_width * 0.8
    available_height = content_height * 0.6

    scale_x = available_width / item.bounds.width if item.bounds.width > 0 else 1.0
    scale_y = available_height / item.bounds.height if item.bounds.height > 0 else 1.0
    page_scale = min(scale_x, scale_y, 2.0)  # Allow up to 2x scaling for small mechanisms

    # Center the mechanism on the page
    scaled_width = item.bounds.width * page_scale
    scaled_height = item.bounds.height * page_scale
    mech_x = margin_mm + (content_width - scaled_width) / 2
    mech_y = margin_mm + 80 + (available_height - scaled_height) / 2

    # Material specifications based on unit system
    material_info = "Material: Steel/Aluminum bars and joints"
    if unit_system == "imperial":
        material_info = "Material: Steel/Aluminum bars and joints (standard/imperial sizes)"

    # Generate page SVG with enhanced mechanism visualization
    page_svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{page_width_mm}" height="{page_height_mm}"
     xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" version="1.1">
  <defs>
    <style>
      .blueprint-text {{ font-family: Arial, sans-serif; }}
      .page-title {{ font-size: 16px; font-weight: bold; }}
      .mechanism-title {{ font-size: 20px; font-weight: bold; }}
      .dimension-line {{ stroke: #666; stroke-width: 0.75; stroke-dasharray: 3,3; }}
      .dimension-text {{ font-family: Arial, sans-serif; font-size: 10px; fill: #333; }}
      .manufacturing-note {{ font-family: Arial, sans-serif; font-size: 9px; fill: #555; }}
      .mechanism-label {{ font-family: Arial, sans-serif; font-size: 12px; font-weight: bold; }}
      .parameter-text {{ font-family: Arial, sans-serif; font-size: 8px; fill: #222; }}
      .parameter-header {{ font-family: Arial, sans-serif; font-size: 9px; font-weight: bold; fill: #333; }}
      .unit-info {{ font-family: Arial, sans-serif; font-size: 6px; fill: #888; font-style: italic; }}
    </style>
  </defs>

  <!-- Page Border -->
  <rect x="{margin_mm / 2}" y="{margin_mm / 2}" width="{page_width_mm - margin_mm}" height="{page_height_mm - margin_mm}"
        fill="none" stroke="black" stroke-width="1"/>

  <!-- Header -->
  <g id="header">
    <text x="{margin_mm}" y="{margin_mm + 20}" class="page-title">{title} - Mechanism</text>
    <text x="{margin_mm}" y="{margin_mm + 35}" class="blueprint-text" font-size="12">{scale_info}</text>
    <text x="{margin_mm}" y="{margin_mm + 50}" class="unit-info">Units: {get_unit_label()}</text>
    <text x="{page_width_mm - margin_mm}" y="{margin_mm + 20}" class="blueprint-text" font-size="10" text-anchor="end">
      Page {page_num} of {total_pages}
    </text>
    <text x="{page_width_mm - margin_mm}" y="{margin_mm + 35}" class="blueprint-text" font-size="10" text-anchor="end">
      Generated: {get_timestamp()}
    </text>
  </g>

  <!-- Mechanism Title -->
  <text x="{page_width_mm / 2}" y="{margin_mm + 70}" class="mechanism-title" text-anchor="middle">{item.name}</text>

  <!-- Mechanism Content (scaled and centered) -->
  <g transform="translate({mech_x:.1f},{mech_y:.1f}) scale({page_scale:.3f})">
    {item.svg_content}
  </g>

  <!-- Manufacturing Information -->
  <g id="manufacturing-info">
    <text x="{margin_mm}" y="{page_height_mm - 90}" class="manufacturing-note">
      Mechanism Dimensions: {format_dimension(item.bounds.width)} × {format_dimension(item.bounds.height)}
    </text>
    <text x="{margin_mm}" y="{page_height_mm - 75}" class="manufacturing-note">
      Page Scale: {page_scale:.1%} (1:{1 / page_scale:.1f})
    </text>
    <text x="{margin_mm}" y="{page_height_mm - 60}" class="manufacturing-note">
      {material_info}
    </text>
    <text x="{margin_mm}" y="{page_height_mm - 45}" class="manufacturing-note">
      Assembly: Follow joint positions and link dimensions precisely
    </text>
    <text x="{margin_mm}" y="{page_height_mm - 30}" class="manufacturing-note">
      Units: {get_unit_label()} | Precision mechanism dimensions
    </text>
  </g>

  <!-- Footer -->
  <line x1="{margin_mm}" y1="{page_height_mm - 15}" x2="{page_width_mm - margin_mm}" y2="{page_height_mm - 15}"
        stroke="black" stroke-width="0.5"/>
  <text x="{page_width_mm / 2}" y="{page_height_mm - 5}" class="blueprint-text" font-size="8" text-anchor="middle">
    MotionSmith Manufacturing System - Mechanism Blueprint
  </text>
</svg>'''

    return page_svg


def get_timestamp() -> str:
    """Get current timestamp for blueprint."""
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%d %H:%M")


def generate_detailed_part_content(part_items: Sequence[object], padding: float = 20.0) -> str:
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
                logging.warning("Skipping item: No manufacturing contour extracted from PNG")
                # Fallback to original method if PNG extraction fails
                fallback_svg = _create_fallback_part_svg(item, current_x, current_y, padding)
                if fallback_svg:
                    svg_parts.append(fallback_svg)
                    current_x += 100 + padding  # Default size for fallback
                    max_row_height = max(max_row_height, 100)
                continue

            # Get part name
            part_name = "Unknown Part"
            if hasattr(item, "part_info") and item.part_info:
                part_name = getattr(item.part_info, "name", "Unknown Part")

            # Get contour dimensions
            cx, cy, width, height = manufacturing_contour.bounding_rect

            # Create manufacturing-precision SVG
            part_svg = _create_manufacturing_part_svg(
                manufacturing_contour, current_x, current_y, part_name
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
    return "\n".join(svg_parts)


def _create_manufacturing_part_svg(
    manufacturing_contour: ManufacturingContour, x_offset: float, y_offset: float, part_name: str
) -> str:
    """Create manufacturing-precision SVG using extracted PNG contours"""

    # Get contour dimensions
    cx, cy, width, height = manufacturing_contour.bounding_rect

    # Apply offset to SVG path
    extractor = AdvancedContourExtractor()
    offset_path = extractor._apply_offset_to_path(
        manufacturing_contour.svg_path, x_offset - cx, y_offset - cy
    )

    # Create detailed manufacturing part SVG
    part_svg = f'''
    <g class="manufacturing-part" data-name="{part_name}">
        <!-- PNG-extracted contour outline -->
        <path d="{offset_path}" class="part-outline"/>

        <!-- Cutting path for manufacturing -->
        <path d="{offset_path}" class="cut-line"/>

        <!-- Part label -->
        <text x="{x_offset + width / 2:.2f}" y="{y_offset - 5:.2f}"
              class="part-label" text-anchor="middle">{part_name}</text>

        <!-- Dimensions -->
        <g class="dimensions">
            <!-- Width dimension -->
            <line x1="{x_offset:.2f}" y1="{y_offset + height + 10:.2f}"
                  x2="{x_offset + width:.2f}" y2="{y_offset + height + 10:.2f}"
                  class="dimension-line"/>
            <text x="{x_offset + width / 2:.2f}" y="{y_offset + height + 20:.2f}"
                  class="dimension-text" text-anchor="middle">{width:.1f}mm</text>

            <!-- Height dimension -->
            <line x1="{x_offset - 10:.2f}" y1="{y_offset:.2f}"
                  x2="{x_offset - 10:.2f}" y2="{y_offset + height:.2f}"
                  class="dimension-line"/>
            <text x="{x_offset - 15:.2f}" y="{y_offset + height / 2:.2f}"
                  class="dimension-text" text-anchor="middle"
                  transform="rotate(-90, {x_offset - 15:.2f}, {y_offset + height / 2:.2f})">
                  {height:.1f}mm</text>
        </g>

        <!-- Manufacturing notes -->
        <text x="{x_offset:.2f}" y="{y_offset + height + 35:.2f}"
              class="dimension-text" font-size="7px">
              PNG-Contour | Area: {manufacturing_contour.area:.0f}mm² | Perimeter: {manufacturing_contour.perimeter:.1f}mm
        </text>

        <!-- Assembly anchor point -->
        <circle cx="{x_offset + width / 2:.2f}" cy="{y_offset + height / 2:.2f}"
                r="2" fill="blue" opacity="0.7"/>
    </g>
    '''

    return part_svg


def _create_fallback_part_svg(
    item: object, x_offset: float, y_offset: float, padding: float
) -> str:
    """Fallback SVG creation when PNG extraction fails"""

    try:
        # Get part name
        part_name = "Unknown Part"
        if hasattr(item, "part_info") and item.part_info:
            part_name = getattr(item.part_info, "name", "Unknown Part")

        # Create simple placeholder rectangle
        width = 80
        height = 80

        part_svg = f'''
    <g class="fallback-part" data-name="{part_name}">
        <!-- Fallback rectangle -->
        <rect x="{x_offset:.2f}" y="{y_offset:.2f}" width="{width}" height="{height}"
              class="part-outline" fill="none"/>

        <!-- Part label -->
        <text x="{x_offset + width / 2:.2f}" y="{y_offset - 5:.2f}"
              class="part-label" text-anchor="middle">{part_name}</text>

        <!-- Warning text -->
        <text x="{x_offset + width / 2:.2f}" y="{y_offset + height / 2:.2f}"
              class="dimension-text" text-anchor="middle" font-size="8px" fill="red">
              PNG Not Found</text>
    </g>
    '''

        return part_svg

    except Exception as e:
        logging.error(f"Error creating fallback part SVG: {e}")
        return ""
