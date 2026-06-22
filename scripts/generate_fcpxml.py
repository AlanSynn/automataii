#!/usr/bin/env python3
"""
Generate a Final Cut Pro FCPXML timeline with Title overlays from a simple JSON spec.

Usage:
  python scripts/generate_fcpxml.py --out tmp/motionsmith_demo.fcpxml \
      --config config/motionsmith_av.json --fps 30 --width 1920 --height 1080

If --config is omitted, a built-in demo (matching the user's AV script) is used.
The JSON schema is minimal:

{
  "project_name": "MotionSmith Demo",
  "fps": 30,
  "width": 1920,
  "height": 1080,
  "segments": [
    {"name": "Title & Hero Shot", "duration": 3, "lines": ["MotionSmith title card"]},
    {"name": "Background & Problem", "duration": 11, "lines": ["Automata combine art, engineering, and storytelling.", "But designing them remains complex."]}
  ]
}

This generator creates a single sequence with a base gap and a Title overlay for each segment.
The first line is styled as a header; subsequent lines are styled as subtitle text.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import xml.sax.saxutils as saxutils


def default_config() -> dict:
    return {
        "project_name": "MotionSmith Demo",
        "fps": 30,
        "width": 1920,
        "height": 1080,
        # Derived from the AV script shared in the prompt
        "segments": [
            {
                "name": "Title & Hero Shot",
                "duration": 3,
                "lines": [
                    "MotionSmith title card",
                ],
            },
            {
                "name": "Background & Problem Setting",
                "duration": 11,
                "lines": [
                    "Automata combine art, engineering, and storytelling.",
                    "But designing them remains complex.",
                ],
            },
            {
                "name": "System Walkthrough",
                "duration": 34,
                "lines": [
                    "Our system translates sketches into real mechanisms.",
                    "Sketch → refine → candidates → export.",
                ],
            },
            {
                "name": "Fabrication Process",
                "duration": 14,
                "lines": [
                    "Material list and assembling guide.",
                    "Assemble linkages. Glue the cap.",
                    "Attach the character. Bring automata to life.",
                ],
            },
            {
                "name": "Artist Process",
                "duration": 39,
                "lines": [
                    "Co-designed with expert automata artists.",
                    "Supporting creative intent, not literal input.",
                    "Enabling fluent iteration across design stages.",
                ],
            },
            {
                "name": "Outcomes & Impact",
                "duration": 29,
                "lines": [
                    "Artists built automata with MotionSmith.",
                    "Creative agency and fabrication.",
                ],
            },
            {
                "name": "Closing",
                "duration": 4,
                "lines": [
                    "MotionSmith: Supporting creativity in mechanical design",
                ],
            },
        ],
    }


def read_config(path: str | None) -> dict:
    if not path:
        return default_config()
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def seconds_to_time_str(seconds: float) -> str:
    # FCPXML accepts e.g., "3s", "11s"; keep integer seconds where possible.
    if abs(seconds - int(seconds)) < 1e-6:
        return f"{int(seconds)}s"
    return f"{seconds:.6f}s"


def build_fcpxml(cfg: dict) -> str:
    width = int(cfg.get("width", 1920))
    height = int(cfg.get("height", 1080))
    fps = float(cfg.get("fps", 30))
    # Use 1/fps seconds for frameDuration; prefer integers where possible
    frame_duration = f"1/{int(fps)}s" if abs(fps - int(fps)) < 1e-6 else "1001/30000s"  # fallback to 29.97

    total_duration = sum(float(s.get("duration", 0)) for s in cfg.get("segments", []))
    total_duration_str = seconds_to_time_str(total_duration)

    # Text styles: header and subtitle
    header_font = cfg.get("header_font", "Helvetica")
    header_size = float(cfg.get("header_size", 72))
    subtitle_font = cfg.get("subtitle_font", header_font)
    subtitle_size = float(cfg.get("subtitle_size", 44))

    # Basic Title effect UID (Final Cut built-in). This value is commonly used in FCPXML exports.
    basic_title_uid = (
        "r2"
    )  # resource id we'll define below; kept as a symbol for clarity

    # Build resource section
    resources = f"""
    <resources>
      <format id=\"r1\" name=\"FFVideoFormat{height}p{int(fps)}\" frameDuration=\"{frame_duration}\" width=\"{width}\" height=\"{height}\" colorSpace=\"1-1-1 (Rec. 709)\"/>
      <effect id=\"r2\" name=\"Basic Title\" uid=\"/Titles.localized/Basics.localized/Basic Title.localized/Basic Title.moti\"/>
    </resources>
    """

    # Sequence spine with a base gap that spans total duration
    spine_items: list[str] = []
    offset = 0.0
    for seg in cfg.get("segments", []):
        name = seg.get("name", "Segment")
        duration = float(seg.get("duration", 0))
        lines = seg.get("lines", [])
        lane = str(seg.get("lane", "1"))
        if duration <= 0:
            continue

        # Build text runs: first line as header style, the rest as subtitle style
        text_runs = []
        if lines:
            header_text = saxutils.escape(str(lines[0]))
            text_runs.append(f"<text-style ref=\"tsHeader\">{header_text}</text-style>")
        for line in lines[1:]:
            subtitle_text = saxutils.escape(str(line))
            # Prepend newline for separation
            text_runs.append(f"<text-style ref=\"tsSubtitle\">\n{subtitle_text}</text-style>")

        text_xml = "".join(text_runs) if text_runs else "<text-style ref=\"tsHeader\"></text-style>"

        title = f"""
        <title name=\"{saxutils.escape(name)}\" lane=\"{lane}\" offset=\"{seconds_to_time_str(offset)}\" ref=\"{basic_title_uid}\" start=\"0s\" duration=\"{seconds_to_time_str(duration)}\">
          <text>
            {text_xml}
          </text>
          <text-style-def id=\"tsHeader\">
            <text-style font=\"{saxutils.escape(header_font)}\" fontSize=\"{header_size}\" fontFace=\"Regular\" fontColor=\"1 1 1 1\" alignment=\"center\"/>
          </text-style-def>
          <text-style-def id=\"tsSubtitle\">
            <text-style font=\"{saxutils.escape(subtitle_font)}\" fontSize=\"{subtitle_size}\" fontFace=\"Regular\" fontColor=\"1 1 1 1\" alignment=\"center\"/>
          </text-style-def>
        </title>
        """

        spine_items.append(title)
        offset += duration

    # Optional overlays with explicit offsets (e.g., Part A–D cards)
    for ov in cfg.get("overlays", []):
        name = ov.get("name", "Overlay")
        duration = float(ov.get("duration", 0))
        ov_offset = float(ov.get("offset", 0))
        lane = str(ov.get("lane", "2"))
        lines = ov.get("lines", [])
        if duration <= 0:
            continue

        text_runs = []
        if lines:
            header_text = saxutils.escape(str(lines[0]))
            text_runs.append(f"<text-style ref=\"tsHeader\">{header_text}</text-style>")
        for line in lines[1:]:
            subtitle_text = saxutils.escape(str(line))
            text_runs.append(f"<text-style ref=\"tsSubtitle\">\n{subtitle_text}</text-style>")

        text_xml = "".join(text_runs) if text_runs else "<text-style ref=\"tsHeader\"></text-style>"

        overlay_title = f"""
        <title name=\"{saxutils.escape(name)}\" lane=\"{lane}\" offset=\"{seconds_to_time_str(ov_offset)}\" ref=\"{basic_title_uid}\" start=\"0s\" duration=\"{seconds_to_time_str(duration)}\">\n          <text>\n            {text_xml}\n          </text>\n          <text-style-def id=\"tsHeader\">\n            <text-style font=\"{saxutils.escape(header_font)}\" fontSize=\"{header_size}\" fontFace=\"Regular\" fontColor=\"1 1 1 1\" alignment=\"center\"/>\n          </text-style-def>\n          <text-style-def id=\"tsSubtitle\">\n            <text-style font=\"{saxutils.escape(subtitle_font)}\" fontSize=\"{subtitle_size}\" fontFace=\"Regular\" fontColor=\"1 1 1 1\" alignment=\"center\"/>\n          </text-style-def>\n        </title>\n+        """
        spine_items.append(overlay_title)

    spine_xml = "\n".join(spine_items)
    project_name = saxutils.escape(cfg.get("project_name", "MotionSmith Demo"))

    sequence = f"""
    <library>
      <event name=\"MotionSmith\">
        <project name=\"{project_name}\">
          <sequence format=\"r1\" duration=\"{total_duration_str}\" tcStart=\"0s\" tcFormat=\"NDF\" audioLayout=\"stereo\" audioRate=\"48k\">
            <spine>
              <gap name=\"Base\" start=\"0s\" duration=\"{total_duration_str}\"/>
              {spine_xml}
            </spine>
          </sequence>
        </project>
      </event>
    </library>
    """

    resources_str = resources.strip()
    sequence_str = sequence.strip()
    fcpxml = "\n".join([
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
        "<!DOCTYPE fcpxml>",
        "<fcpxml version=\"1.10\">",
        resources_str,
        sequence_str,
        "</fcpxml>",
    ])

    return fcpxml


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Generate FCPXML timeline from simple JSON config")
    parser.add_argument("--config", type=str, default=None, help="Path to JSON config; if omitted, uses built-in demo config")
    parser.add_argument("--out", type=str, default="tmp/motionsmith_demo.fcpxml", help="Output FCPXML path")
    parser.add_argument("--fps", type=float, default=None, help="Override FPS (default from config or 30)")
    parser.add_argument("--width", type=int, default=None, help="Override width (default from config or 1920)")
    parser.add_argument("--height", type=int, default=None, help="Override height (default from config or 1080)")

    args = parser.parse_args(argv)

    cfg = read_config(args.config)
    if args.fps is not None:
        cfg["fps"] = args.fps
    if args.width is not None:
        cfg["width"] = args.width
    if args.height is not None:
        cfg["height"] = args.height

    xml = build_fcpxml(cfg)

    out_path = args.out
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(xml)

    print(f"Wrote FCPXML: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
