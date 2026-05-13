"""Generate MS4N mechanism-first automata kit SVG sheets.

The generated sheets use the same Illustrator/user-unit scale as kit/bar-board.svg:
- A4-ish viewBox: 771.82 x 1073.65
- board grid pitch: ~75.12 units (about 20.4 mm if the board holes are M5 clearance)
- moving linkage hole radius follows the existing kit/bars-2.svg: 7.09 units

Laser convention:
- red (#ed1c24) = cut
- blue (#0071bc) = score/engrave construction labels
- light gray = non-cut helper/print preview
"""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, pi, sin
from pathlib import Path
from xml.sax.saxutils import escape

PAGE_W = 771.82
PAGE_H = 1073.65
PITCH = 75.12
HOLE_R = 7.09
BOARD_HOLE_R = 9.21
CUT = "#ed1c24"
SCORE = "#0071bc"
GUIDE = "#999999"
FILL = "#ffffff"

OUT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Pt:
    x: float
    y: float


def fmt(n: float) -> str:
    return f"{n:.2f}".rstrip("0").rstrip(".")


def attrs(**values: str | float | int) -> str:
    return " ".join(f'{key}="{escape(str(value))}"' for key, value in values.items())


class Svg:
    def __init__(self, filename: str, title: str, *, width: float = PAGE_W, height: float = PAGE_H):
        self.filename = filename
        self.title = title
        self.width = width
        self.height = height
        self.parts: list[str] = []

    def add(self, element: str) -> None:
        self.parts.append(element)

    def group(self, label: str) -> None:
        self.add(f'  <g id="{escape(label)}">')

    def end_group(self) -> None:
        self.add("  </g>")

    def line(self, x1: float, y1: float, x2: float, y2: float, cls: str = "score") -> None:
        self.add(f'    <line class="{cls}" {attrs(x1=fmt(x1), y1=fmt(y1), x2=fmt(x2), y2=fmt(y2))}/>' )

    def circle(self, cx: float, cy: float, r: float, cls: str = "cut") -> None:
        self.add(f'    <circle class="{cls}" {attrs(cx=fmt(cx), cy=fmt(cy), r=fmt(r))}/>' )

    def rect(self, x: float, y: float, w: float, h: float, cls: str = "cut", *, rx: float = 0) -> None:
        more = f' rx="{fmt(rx)}" ry="{fmt(rx)}"' if rx else ""
        self.add(f'    <rect class="{cls}" {attrs(x=fmt(x), y=fmt(y), width=fmt(w), height=fmt(h))}{more}/>' )

    def path(self, d: str, cls: str = "cut") -> None:
        self.add(f'    <path class="{cls}" d="{d}"/>' )

    def polygon(self, points: list[Pt], cls: str = "cut") -> None:
        p = " ".join(f"{fmt(pt.x)},{fmt(pt.y)}" for pt in points)
        self.add(f'    <polygon class="{cls}" points="{p}"/>' )

    def text(self, x: float, y: float, value: str, cls: str = "label", *, size: float = 14, anchor: str = "start") -> None:
        self.add(
            f'    <text class="{cls}" {attrs(x=fmt(x), y=fmt(y), **{"font-size": fmt(size), "text-anchor": anchor})}>{escape(value)}</text>'
        )

    def save(self) -> Path:
        body = "\n".join(self.parts)
        svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {fmt(self.width)} {fmt(self.height)}" version="1.1">
  <title>{escape(self.title)}</title>
  <defs>
    <style>
      .cut {{ fill: none; stroke: {CUT}; stroke-width: 1; stroke-miterlimit: 10; }}
      .score {{ fill: none; stroke: {SCORE}; stroke-width: 0.8; stroke-miterlimit: 10; }}
      .guide {{ fill: none; stroke: {GUIDE}; stroke-width: 0.5; stroke-dasharray: 4 4; }}
      .fillcut {{ fill: {FILL}; stroke: {CUT}; stroke-width: 1; stroke-miterlimit: 10; }}
      .label {{ fill: #333333; font-family: Arial, Helvetica, sans-serif; font-size: 14px; }}
      .tiny {{ fill: #333333; font-family: Arial, Helvetica, sans-serif; font-size: 9px; }}
      .card {{ fill: #ffffff; stroke: {CUT}; stroke-width: 1; }}
      .soft {{ fill: #f5f7fa; stroke: {GUIDE}; stroke-width: 0.5; }}
    </style>
  </defs>
{body}
</svg>
'''
        path = OUT / self.filename
        path.write_text(svg, encoding="utf-8")
        return path


def rounded_capsule(x1: float, y: float, x2: float, radius: float) -> str:
    return (
        f"M {fmt(x1)} {fmt(y - radius)} "
        f"L {fmt(x2)} {fmt(y - radius)} "
        f"A {fmt(radius)} {fmt(radius)} 0 0 1 {fmt(x2)} {fmt(y + radius)} "
        f"L {fmt(x1)} {fmt(y + radius)} "
        f"A {fmt(radius)} {fmt(radius)} 0 0 1 {fmt(x1)} {fmt(y - radius)} Z"
    )


def bar(svg: Svg, x: float, y: float, holes: int, label: str, *, pitch: float = PITCH, hole_r: float = HOLE_R) -> None:
    pad = 25.5
    x1 = x
    x2 = x + (holes - 1) * pitch
    radius = 24.8
    svg.path(rounded_capsule(x1, y, x2, radius), "cut")
    for idx in range(holes):
        svg.circle(x + idx * pitch, y, hole_r, "cut")
    svg.text(x1, y + 42, label, "tiny", size=9, anchor="middle")
    svg.text(x2, y + 42, f"{holes}H", "tiny", size=9, anchor="middle")
    # Explanation tick marks: makes one-change card discussions easier.
    for idx in range(holes - 1):
        tx = x + idx * pitch + pitch / 2
        svg.line(tx, y - pad, tx, y - pad + 8, "score")
        svg.line(tx, y + pad - 8, tx, y + pad, "score")


def slotted_bar(svg: Svg, x: float, y: float, holes: int, label: str) -> None:
    x1 = x
    x2 = x + (holes - 1) * PITCH
    radius = 24.8
    svg.path(rounded_capsule(x1, y, x2, radius), "cut")
    slot_len = max(10, (holes - 2) * PITCH)
    slot_x1 = x + PITCH / 2
    slot_x2 = slot_x1 + slot_len
    svg.path(rounded_capsule(slot_x1, y, slot_x2, 6.5), "cut")
    svg.circle(x1, y, HOLE_R, "cut")
    svg.circle(x2, y, HOLE_R, "cut")
    svg.text((x1 + x2) / 2, y + 42, label, "tiny", size=9, anchor="middle")


def washer(svg: Svg, cx: float, cy: float, outer_r: float, inner_r: float, label: str) -> None:
    svg.circle(cx, cy, outer_r, "cut")
    svg.circle(cx, cy, inner_r, "cut")
    svg.text(cx, cy + outer_r + 13, label, "tiny", size=8, anchor="middle")


def polar_path(cx: float, cy: float, points: list[tuple[float, float]]) -> str:
    coords = [Pt(cx + r * cos(theta), cy + r * sin(theta)) for theta, r in points]
    start = coords[0]
    rest = " ".join(f"L {fmt(pt.x)} {fmt(pt.y)}" for pt in coords[1:])
    return f"M {fmt(start.x)} {fmt(start.y)} {rest} Z"


def cam_points(kind: str, samples: int = 96) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    for i in range(samples):
        t = 2 * pi * i / samples
        if kind == "circle":
            r = 47
        elif kind == "eccentric":
            r = 42 + 16 * (1 + cos(t)) / 2
        elif kind == "oval":
            # convert ellipse to radial curve
            a, b = 62, 42
            r = (a * b) / ((b * cos(t)) ** 2 + (a * sin(t)) ** 2) ** 0.5
        elif kind == "pear":
            r = 40 + 22 * (1 + cos(t - 0.45)) / 2 + 6 * sin(2 * t)
        elif kind == "bump":
            r = 39 + 28 * max(0, cos(t)) ** 3
        else:
            r = 45
        pts.append((t, r))
    return pts


def cam(svg: Svg, cx: float, cy: float, kind: str, label: str) -> None:
    svg.path(polar_path(cx, cy, cam_points(kind)), "cut")
    svg.circle(cx, cy, HOLE_R, "cut")
    svg.circle(cx + 22, cy, 3.5, "score")
    svg.line(cx, cy, cx + 22, cy, "score")
    svg.text(cx, cy + 78, label, "tiny", size=9, anchor="middle")


def gear(svg: Svg, cx: float, cy: float, teeth: int, root_r: float, outer_r: float, label: str) -> None:
    pts: list[Pt] = []
    # four points per tooth for a coarse laser-friendly educational gear.
    for i in range(teeth * 4):
        t = 2 * pi * i / (teeth * 4)
        phase = i % 4
        r = outer_r if phase in (1, 2) else root_r
        pts.append(Pt(cx + r * cos(t), cy + r * sin(t)))
    svg.polygon(pts, "cut")
    svg.circle(cx, cy, HOLE_R, "cut")
    svg.circle(cx, cy, root_r * 0.55, "score")
    for k in range(4):
        t = 2 * pi * k / 4
        svg.circle(cx + root_r * 0.35 * cos(t), cy + root_r * 0.35 * sin(t), 4.2, "cut")
    svg.text(cx, cy + outer_r + 16, label, "tiny", size=9, anchor="middle")


def pulley(svg: Svg, cx: float, cy: float, r: float, label: str) -> None:
    svg.circle(cx, cy, r, "cut")
    svg.circle(cx, cy, r - 8, "score")
    svg.circle(cx, cy, HOLE_R, "cut")
    for k in range(6):
        t = 2 * pi * k / 6
        svg.circle(cx + (r - 20) * cos(t), cy + (r - 20) * sin(t), 3.2, "cut")
    svg.text(cx, cy + r + 14, label, "tiny", size=9, anchor="middle")


def card(svg: Svg, x: float, y: float, w: float, h: float, title: str, lines: list[str], *, tag: str) -> None:
    svg.rect(x, y, w, h, "card", rx=8)
    svg.text(x + 10, y + 22, title, "label", size=12)
    svg.text(x + w - 10, y + 22, tag, "tiny", size=8, anchor="end")
    yy = y + 43
    for line in lines:
        svg.text(x + 10, yy, line, "tiny", size=8)
        yy += 13
    # Three evidence checkboxes.
    for idx, label in enumerate(["바꾼 것", "달라진 motion", "왜?"]):
        cy = y + h - 42 + idx * 13
        svg.rect(x + 10, cy - 8, 7, 7, "score")
        svg.text(x + 23, cy - 1, label, "tiny", size=7)


def generate_linkage_sheet() -> Path:
    svg = Svg("ms4n-01-linkage-bars.svg", "MS4N 01 Linkage Length Lab and One-Change Bars")
    svg.text(24, 30, "MS4N-01 Linkage Length Lab: bars use the bar-board pitch", "label", size=16)
    y = 82
    for row, holes in enumerate([2, 3, 4, 5, 6, 7, 8]):
        bar(svg, 65, y + row * 70, holes, f"fixed {holes}-hole")
    for row, holes in enumerate([3, 4, 5, 6, 7]):
        slotted_bar(svg, 65, 605 + row * 70, holes, f"one-change slot {holes}H")
    # Rocker flags and pivot labels.
    for i, label in enumerate(["INPUT", "OUTPUT", "FIXED", "TRACE"]):
        x = 555 + (i % 2) * 105
        y0 = 100 + (i // 2) * 140
        svg.path(f"M {fmt(x)} {fmt(y0)} L {fmt(x + 70)} {fmt(y0 + 28)} L {fmt(x)} {fmt(y0 + 56)} Z", "cut")
        svg.circle(x + 15, y0 + 28, HOLE_R, "cut")
        svg.text(x + 35, y0 + 34, label, "tiny", size=9, anchor="middle")
    for i in range(12):
        washer(svg, 540 + (i % 4) * 48, 425 + (i // 4) * 58, 18, HOLE_R, "spacer")
    svg.text(540, 620, "연구 포인트: link length / pivot 위치만 바꿔 before-after path를 비교", "tiny", size=10)
    return svg.save()


def generate_board_guide_sheet() -> Path:
    svg = Svg("ms4n-00-bar-board-guide.svg", "MS4N 00 Bar Board Guide Overlay")
    svg.text(24, 30, "MS4N-00 bar-board guide overlay: use with kit/bar-board.svg", "label", size=16)

    # The existing bar-board is an 11 x 15 grid with a slight Illustrator offset.
    # This overlay intentionally avoids red cut lines; it is for engraving/printing
    # labels and research zones on top of the already-cut board.
    x0, y0 = 10.92, 11.0
    cols, rows = 11, 15
    for col in range(cols):
        x = x0 + col * PITCH
        svg.text(x, 63, chr(ord("A") + col), "tiny", size=9, anchor="middle")
        svg.line(x, 72, x, PAGE_H - 42, "guide")
    for row in range(rows):
        y = y0 + row * PITCH
        svg.text(33, y + 3, str(row + 1), "tiny", size=9, anchor="middle")
        svg.line(48, y, PAGE_W - 35, y, "guide")
        for col in range(cols):
            x = x0 + col * PITCH
            svg.circle(x, y, BOARD_HOLE_R, "score")

    zones = [
        (70, 105, 250, 250, "CAM ZONE", "shape → lift/rhythm"),
        (355, 105, 330, 250, "LINKAGE ZONE", "length/pivot → path"),
        (70, 405, 250, 240, "GEAR ZONE", "ratio → timing"),
        (355, 405, 330, 240, "CHARACTER ZONE", "motion → expression"),
        (70, 720, 615, 210, "TRACE / EXPLANATION", "before → change → after → why"),
    ]
    for x, y, w, h, title, subtitle in zones:
        svg.rect(x, y, w, h, "score", rx=12)
        svg.text(x + 12, y + 25, title, "label", size=12)
        svg.text(x + 12, y + 43, subtitle, "tiny", size=8)

    prompts = [
        "1. 무엇을 바꿨나?",
        "2. 움직임이 어떻게 달라졌나?",
        "3. 왜 그렇게 됐나?",
    ]
    for idx, prompt in enumerate(prompts):
        svg.rect(105 + idx * 190, 965, 160, 48, "score", rx=8)
        svg.text(185 + idx * 190, 994, prompt, "tiny", size=9, anchor="middle")
    return svg.save()


def generate_cam_sheet() -> Path:
    svg = Svg("ms4n-02-cam-follower-kit.svg", "MS4N 02 Cam Shape Composer")
    svg.text(24, 30, "MS4N-02 Cam Shape Composer: cam shape → follower height/rhythm", "label", size=16)
    positions = [(110, 125), (270, 125), (430, 125), (590, 125), (110, 300), (270, 300)]
    for (cx, cy), (kind, label) in zip(
        positions,
        [
            ("circle", "circle / steady"),
            ("eccentric", "eccentric / bounce"),
            ("oval", "oval / smooth rise"),
            ("pear", "pear / slow-fast"),
            ("bump", "single bump / surprise"),
            ("pear", "pear copy / compare"),
        ],
    ):
        cam(svg, cx, cy, kind, label)
    # Followers: straight, roller, pointed.
    for i, label in enumerate(["flat follower", "roller follower", "point follower"]):
        x = 390 + i * 115
        y = 300
        svg.rect(x, y - 12, 30, 205, "cut", rx=10)
        svg.path(rounded_capsule(x + 15, y + 20, x + 15, 6), "score")
        svg.circle(x + 15, y + 35, HOLE_R, "cut")
        svg.circle(x + 15, y + 110, HOLE_R, "cut")
        if i == 0:
            svg.rect(x - 20, y + 190, 70, 16, "cut", rx=3)
        elif i == 1:
            svg.circle(x + 15, y + 198, 20, "cut")
            svg.circle(x + 15, y + 198, 5, "cut")
        else:
            svg.path(f"M {fmt(x - 15)} {fmt(y + 190)} L {fmt(x + 45)} {fmt(y + 190)} L {fmt(x + 15)} {fmt(y + 220)} Z", "cut")
        svg.text(x + 15, y + 235, label, "tiny", size=8, anchor="middle")
    # Rails and guide slots.
    for row in range(3):
        y = 595 + row * 90
        svg.path(rounded_capsule(85, y, 325, 18), "cut")
        svg.path(rounded_capsule(110, y, 300, 5.5), "cut")
        svg.circle(85, y, HOLE_R, "cut")
        svg.circle(325, y, HOLE_R, "cut")
        svg.text(205, y + 36, f"vertical guide rail {row + 1}", "tiny", size=8, anchor="middle")
    # Handles and cam hubs.
    for i in range(6):
        cx = 430 + (i % 3) * 90
        cy = 610 + (i // 3) * 120
        svg.circle(cx, cy, 32, "cut")
        svg.circle(cx, cy, HOLE_R, "cut")
        svg.circle(cx + 20, cy, 4, "cut")
        svg.text(cx, cy + 48, "hub", "tiny", size=8, anchor="middle")
    svg.text(84, 920, "Prompt: 이 봉우리를 더 가파르게 만들면 follower의 높이/속도/리듬은 어떻게 변할까?", "tiny", size=10)
    return svg.save()


def generate_crank_slider_sheet() -> Path:
    svg = Svg("ms4n-03-crank-slider-kit.svg", "MS4N 03 Crank Slider and Motion Trace Passport")
    svg.text(24, 30, "MS4N-03 Crank-Slider: crank radius → stroke amplitude", "label", size=16)
    # Crank wheels with multiple radius holes.
    for idx, (cx, cy, r) in enumerate([(115, 135, 60), (300, 135, 75), (505, 135, 92)]):
        svg.circle(cx, cy, r, "cut")
        svg.circle(cx, cy, HOLE_R, "cut")
        for rr in [PITCH * 0.35, PITCH * 0.55, PITCH * 0.75]:
            svg.circle(cx + rr, cy, HOLE_R, "cut")
            svg.line(cx, cy, cx + rr, cy, "score")
        svg.text(cx, cy + r + 18, f"crank wheel {idx + 1}", "tiny", size=9, anchor="middle")
    # Slider rails.
    for row in range(4):
        y = 335 + row * 105
        svg.path(rounded_capsule(75, y, 640, 22), "cut")
        svg.path(rounded_capsule(120, y, 595, 7), "cut")
        for x in [75, 150, 225, 300, 375, 450, 525, 600]:
            svg.circle(x, y, 4.5, "score")
        svg.circle(75, y, HOLE_R, "cut")
        svg.circle(640, y, HOLE_R, "cut")
        svg.text(357, y + 39, f"slider rail {row + 1} / trace scale", "tiny", size=8, anchor="middle")
    # Slider blocks.
    for i in range(8):
        x = 90 + (i % 4) * 145
        y = 780 + (i // 4) * 105
        svg.rect(x, y, 95, 52, "cut", rx=10)
        svg.circle(x + 24, y + 26, HOLE_R, "cut")
        svg.circle(x + 71, y + 26, HOLE_R, "cut")
        svg.line(x + 10, y + 12, x + 85, y + 12, "score")
        svg.text(x + 47.5, y + 72, "slider block", "tiny", size=8, anchor="middle")
    return svg.save()


def generate_gear_sheet() -> Path:
    svg = Svg("ms4n-04-gears-pulleys-kit.svg", "MS4N 04 Gear Mood Dial and Belt Transfer")
    svg.text(24, 30, "MS4N-04 Gear Mood Dial: gear ratio/direction → speed/timing", "label", size=16)
    gear(svg, 115, 145, 16, 44, 54, "G16 fast")
    gear(svg, 300, 145, 24, 63, 76, "G24 medium")
    gear(svg, 540, 155, 32, 87, 102, "G32 slow")
    gear(svg, 150, 405, 20, 54, 66, "G20")
    gear(svg, 370, 410, 28, 76, 91, "G28")
    gear(svg, 620, 405, 18, 49, 60, "G18 idler")
    for i, (r, label) in enumerate([(36, "small pulley"), (52, "medium pulley"), (72, "large pulley")]):
        pulley(svg, 145 + i * 210, 705, r, label)
    # Direction arrows / labels for printing on gear modules.
    for i, text in enumerate(["clockwise", "counter", "idler flips", "ratio card"]):
        x = 90 + i * 165
        y = 865
        svg.rect(x, y, 130, 70, "cut", rx=8)
        svg.text(x + 65, y + 27, text, "tiny", size=9, anchor="middle")
        svg.path(f"M {fmt(x + 38)} {fmt(y + 45)} C {fmt(x + 58)} {fmt(y + 20)} {fmt(x + 92)} {fmt(y + 30)} {fmt(x + 92)} {fmt(y + 51)}", "score")
        svg.path(f"M {fmt(x + 92)} {fmt(y + 51)} L {fmt(x + 82)} {fmt(y + 43)} L {fmt(x + 96)} {fmt(y + 39)}", "score")
    return svg.save()


def generate_character_sheet() -> Path:
    svg = Svg("ms4n-05-character-connectors.svg", "MS4N 05 Character Action Layer and Output Interfaces")
    svg.text(24, 30, "MS4N-05 Character connectors: output motion → expressive action", "label", size=16)
    # Generic body plates.
    for i, label in enumerate(["body A", "body B"]):
        x = 70 + i * 320
        y = 80
        svg.path(
            f"M {fmt(x + 70)} {fmt(y)} C {fmt(x + 130)} {fmt(y + 5)} {fmt(x + 160)} {fmt(y + 65)} {fmt(x + 140)} {fmt(y + 135)} "
            f"C {fmt(x + 125)} {fmt(y + 190)} {fmt(x + 30)} {fmt(y + 190)} {fmt(x + 15)} {fmt(y + 135)} "
            f"C {fmt(x - 5)} {fmt(y + 65)} {fmt(x + 10)} {fmt(y + 5)} {fmt(x + 70)} {fmt(y)} Z",
            "cut",
        )
        for hx, hy in [(35, 65), (105, 65), (70, 25), (70, 115), (35, 145), (105, 145)]:
            svg.circle(x + hx, y + hy, HOLE_R, "cut")
        svg.text(x + 70, y + 213, label, "tiny", size=9, anchor="middle")
    # Arms/wings with multiple attachment points.
    for row, name in enumerate(["arm", "wing", "tail", "head bob"]):
        for col in range(2):
            x = 60 + col * 340
            y = 360 + row * 110
            svg.path(
                f"M {fmt(x)} {fmt(y + 25)} C {fmt(x + 70)} {fmt(y - 20)} {fmt(x + 190)} {fmt(y - 15)} {fmt(x + 260)} {fmt(y + 25)} "
                f"C {fmt(x + 190)} {fmt(y + 65)} {fmt(x + 70)} {fmt(y + 70)} {fmt(x)} {fmt(y + 25)} Z",
                "cut",
            )
            for hx in [32, 95, 160, 225]:
                svg.circle(x + hx, y + 25, HOLE_R, "cut")
            svg.text(x + 130, y + 82, f"{name} {col + 1}", "tiny", size=8, anchor="middle")
    # Output interface tabs.
    for i in range(8):
        x = 70 + (i % 4) * 160
        y = 845 + (i // 4) * 85
        svg.rect(x, y, 105, 40, "cut", rx=8)
        svg.circle(x + 25, y + 20, HOLE_R, "cut")
        svg.circle(x + 80, y + 20, HOLE_R, "cut")
        svg.text(x + 52, y + 58, "motion tab", "tiny", size=8, anchor="middle")
    return svg.save()


def generate_trace_cards_sheet() -> Path:
    svg = Svg("ms4n-06-trace-prompt-cards.svg", "MS4N 06 One-Change Prompt and Research Trace Cards")
    svg.text(24, 30, "MS4N-06 Prompt cards: one change → one motion consequence → one explanation", "label", size=15)
    card_w, card_h = 170, 128
    cards = [
        ("Pivot만 옮기기", ["다른 것은 그대로", "움직임 path 비교", "왜 달라졌나?"], "PIVOT"),
        ("Link 길이만 바꾸기", ["짧게/길게", "진폭/방향 관찰", "예측 먼저 쓰기"], "LINK"),
        ("Cam 모양만 바꾸기", ["봉우리/완만함", "높이/리듬 관찰", "trace에 표시"], "CAM"),
        ("Gear만 바꾸기", ["작은/큰 기어", "속도/방향 관찰", "비율 설명"], "GEAR"),
        ("연결점만 바꾸기", ["캐릭터 팔/날개", "표현 의미 비교", "감정 단어 붙이기"], "ATTACH"),
        ("Jam Detective", ["멈춘 곳 찾기", "마찰/충돌/정렬", "수정 전후 기록"], "FAIL"),
        ("Prediction", ["바꾸기 전 예측", "실제와 비교", "틀렸다면 왜?"], "PRED"),
        ("Mismatch", ["시뮬레이션 vs 실제", "헐거움/마찰/재료", "새 가설 만들기"], "TWIN"),
        ("Teacher Prompt", ["무엇을 바꿨니?", "어떻게 달라졌니?", "증거는 어디 있니?"], "TEACH"),
        ("Portfolio", ["before 사진", "after 사진", "내 설명 고르기"], "TRACE"),
    ]
    for i, (title, lines, tag) in enumerate(cards):
        x = 35 + (i % 4) * 182
        y = 65 + (i // 4) * 160
        card(svg, x, y, card_w, card_h, title, lines, tag=tag)
    # Fiducial marker blanks / trace dots.
    svg.text(40, 570, "Blank fiducial/trace markers: print labels or replace with ArUco/AprilTag IDs", "tiny", size=10)
    for i in range(24):
        x = 45 + (i % 8) * 86
        y = 610 + (i // 8) * 90
        svg.rect(x, y, 48, 48, "cut", rx=3)
        svg.rect(x + 10, y + 10, 28, 28, "score")
        svg.text(x + 24, y + 65, f"M{i + 1:02d}", "tiny", size=8, anchor="middle")
    svg.text(40, 930, "연구 trace 필드: changed_parameter / motion_consequence / explanation / breakdown / repair", "tiny", size=10)
    return svg.save()


def generate_fabrication_sheet() -> Path:
    svg = Svg("ms4n-07-fabrication-checks.svg", "MS4N 07 Fabrication Checker, Tolerance, Spacers")
    svg.text(24, 30, "MS4N-07 Fabrication checks: turn physical breakdowns into explanation data", "label", size=15)
    # Hole tolerance ladder.
    svg.text(55, 75, "Hole tolerance ladder (test before workshop)", "label", size=12)
    radii = [5.8, 6.3, 6.8, 7.1, 7.5, 8.0, 8.5, 9.2, 9.8]
    for i, r in enumerate(radii):
        cx = 65 + i * 70
        cy = 125
        svg.circle(cx, cy, 24, "cut")
        svg.circle(cx, cy, r, "cut")
        svg.text(cx, cy + 46, f"r{r}", "tiny", size=8, anchor="middle")
    # Spacers and washers.
    svg.text(55, 220, "Washers / spacer stack labels", "label", size=12)
    labels = ["0.5", "1", "2", "3", "5", "8", "10", "15", "20", "30", "loose", "tight"]
    for i, label in enumerate(labels):
        cx = 70 + (i % 6) * 105
        cy = 280 + (i // 6) * 95
        washer(svg, cx, cy, 28, HOLE_R, f"{label}mm")
    # Interference gauges.
    svg.text(55, 505, "Interference / clearance gauges", "label", size=12)
    for i, gap in enumerate([5, 8, 10, 12, 15, 20]):
        x = 60 + i * 110
        y = 560
        svg.rect(x, y, 80, 52, "cut", rx=6)
        svg.path(rounded_capsule(x + 20, y + 26, x + 60, gap / 2), "cut")
        svg.text(x + 40, y + 72, f"gap {gap}", "tiny", size=8, anchor="middle")
    # Failure tags.
    failures = ["FRICTION", "COLLISION", "LOOSE", "OVER-CONSTRAINED", "MISALIGNED", "MATERIAL BEND"]
    for i, label in enumerate(failures):
        x = 55 + (i % 3) * 225
        y = 720 + (i // 3) * 110
        svg.rect(x, y, 180, 72, "cut", rx=8)
        svg.text(x + 90, y + 30, label, "label", size=11, anchor="middle")
        svg.text(x + 90, y + 52, "failure → evidence → repair", "tiny", size=8, anchor="middle")
    return svg.save()


def write_readme(paths: list[Path]) -> Path:
    text = """# MS4N physical kit SVG package

This folder now contains a mechanism-first kit package that uses `kit/bar-board.svg` as the base board.

## Coordinate and fabrication assumptions

- Base board: `bar-board.svg`
- Board viewBox: `0 0 771.82 1073.65`
- Grid pitch: approximately `75.12` SVG units between holes
- Board hole radius: `9.21` SVG units
- Moving linkage/module hole radius: `7.09` SVG units, matching `bars-2.svg`
- Laser convention: red = cut, blue = score/engrave, gray = guide/print helper

## Generated sheets

| File | Role | MS4N module covered |
|---|---|---|
| `ms4n-00-bar-board-guide.svg` | Engraving/print overlay for `bar-board.svg` | Analog-Digital Twin Board, shared base |
| `ms4n-01-linkage-bars.svg` | Adjustable and fixed bars, flags, spacers | Linkage Length Lab, One-Change Challenge |
| `ms4n-02-cam-follower-kit.svg` | Cam profiles, followers, guide rails, hubs | Cam Shape Composer |
| `ms4n-03-crank-slider-kit.svg` | Crank wheels, slider rails, slider blocks | Crank-Slider, Motion Trace Passport |
| `ms4n-04-gears-pulleys-kit.svg` | Educational gears, pulleys, direction cards | Gear Mood Dial |
| `ms4n-05-character-connectors.svg` | Body plates, arms/wings/tails, output tabs | Mechanism Storyboard Blocks |
| `ms4n-06-trace-prompt-cards.svg` | One-change cards, teacher prompts, marker blanks | Trace Passport, Worksheet Studio |
| `ms4n-07-fabrication-checks.svg` | Tolerance ladder, washers, clearance gauges, failure tags | Fabrication Checker, Jam Detective |

## Recommended CHI demo flow

1. Mount a simple mechanism on `bar-board.svg`.
2. Draw one prompt card from `ms4n-06-trace-prompt-cards.svg`.
3. Change exactly one variable: cam shape, pivot, link length, gear, or attachment point.
4. Record before/after physical motion and digital motion trace.
5. Ask the learner to explain: what changed, what motion changed, and why.
6. If it jams, attach a failure tag from `ms4n-07-fabrication-checks.svg` and treat it as a repair episode.

## Research unit

Each activity should produce one `Mechanism Change Episode`:

```text
before_state → changed_parameter → motion_consequence → learner_explanation → breakdown/repair
```

This is the evidence unit for the CHI paper, not just the finished automata artifact.

## Regeneration

Run:

```bash
python3 kit/generate_ms4n_kit.py
```

"""
    text += "\n## Current generated files\n\n"
    for path in paths:
        text += f"- `{path.name}`\n"
    out = OUT / "MS4N_KIT_README.md"
    out.write_text(text, encoding="utf-8")
    return out


def main() -> None:
    paths = [
        generate_board_guide_sheet(),
        generate_linkage_sheet(),
        generate_cam_sheet(),
        generate_crank_slider_sheet(),
        generate_gear_sheet(),
        generate_character_sheet(),
        generate_trace_cards_sheet(),
        generate_fabrication_sheet(),
    ]
    paths.append(write_readme(paths))
    for path in paths:
        print(path.relative_to(OUT.parent))


if __name__ == "__main__":
    main()
