FCPXML Generator

Quickly create a Final Cut Pro timeline with title cards and subtitles from a simple JSON config.

Usage

- Generate the default demo timeline:
  - `python scripts/generate_fcpxml.py --out tmp/motionsmith_demo.fcpxml`
- Generate using the provided config (matches your AV script):
  - `python scripts/generate_fcpxml.py --config config/motionsmith_av.json --out tmp/motionsmith_demo.fcpxml`
- Generate with part cards overlaid (Part A–D):
  - `python scripts/generate_fcpxml.py --config config/motionsmith_av_with_parts.json --out tmp/motionsmith_demo_with_parts.fcpxml`

Import to Final Cut Pro

- In Final Cut Pro: `File` → `Import` → `XML...`
- Select the generated file under `tmp/`.
- Open Event `MotionSmith` and the Project named in your JSON (e.g., `MotionSmith Demo`).
- Replace the placeholder base with your visuals; Title items land in lanes 1–2 and can be moved/edited normally.

Config Schema

- `project_name`: Project name in FCP.
- `fps`, `width`, `height`: Sequence format (defaults: 30 fps, 1920×1080, Rec.709).
- `header_font`, `header_size`: Style for the first line in each title.
- `subtitle_font`, `subtitle_size`: Style for additional lines.
- `segments`: Sequential blocks on the timeline.
  - `name`: Label for the title.
  - `duration` (seconds): Length of the block.
  - `lines`: First line = header; remaining lines = subtitle.
  - `lane` (optional): FCP lane to place the title (string or number).
- `overlays` (optional): Titles with explicit `offset` in seconds (for Part A–D cards, etc.).
  - `name`, `duration`, `offset`, `lane`, `lines` as above.

Notes & Limitations

- Uses the built-in `Basic Title` effect; FCP resolves it via its UID. If you see a missing effect warning, replace with your preferred title template in FCP.
- No media is referenced (gap base only) to keep imports clean; add asset clips or transitions later as needed.
- Durations are in seconds; if you need exact frame counts (e.g., 29.97), adjust `--fps` and use frame-based durations in future iterations.
- This is a minimal generator; we can extend it to place media, transitions, and markers if you want.

