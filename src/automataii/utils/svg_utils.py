import os

SVG_TEMPLATE = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
  <path d="{path_data}" fill="{fill_color}" stroke="{stroke_color}" stroke-width="{stroke_width}" />
</svg>
"""


def contour_to_svg_path(contour) -> str:
    """윤곽선 데이터를 SVG 경로 문자열로 변환합니다."""
    if contour is None or len(contour) < 1:
        return ""
    path_data = "M " + " L ".join(
        [f"{p[0]},{p[1]}" for p_arr in contour for p in p_arr]
    )  # Adjusted for typical contour structure
    # If contour is already a list of points (e.g., [[x1,y1], [x2,y2]]), then:
    # path_data = "M " + " L ".join([f"{p[0]},{p[1]}" for p in contour])
    path_data += " Z"  # 경로 닫기
    return path_data


def save_svg(
    path_data: str,
    width: int,
    height: int,
    output_path: str,
    fill: str = "rgba(255,255,255,0.5)",
    stroke: str = "black",
    stroke_width: int = 1,
) -> bool:
    """SVG 파일로 저장합니다."""
    content = SVG_TEMPLATE.format(
        width=width,
        height=height,
        path_data=path_data,
        fill_color=fill,
        stroke_color=stroke,
        stroke_width=stroke_width,
    )
    try:
        with open(output_path, "w") as f:
            f.write(content)
        return True
    except IOError as e:
        print(
            f"Error saving SVG to {output_path}: {e}"
        )  # Consider logging instead of print
        return False
