# Automataii fabrication templates

This directory contains fabrication-ready SVG masters for the physical Automataii pegboard kit.

## Two supported workflows

1. **Pre-fabricated prototyping kit** — cut/print the six workshop sheets in `sheets/`, keep the parts as a classroom/workshop set, and mount them on the physical pegboard with the existing bracket hardware.
2. **Self-fabrication** — use the individual SVGs in `gears/`, `linkages/`, `cams/`, and `brackets/` to make replacement or custom parts with a laser cutter, CNC router, 3D-print workflow, scroll saw, table saw plus drill jig, or similar shop process.

## Physical assumptions

- Default committed pitch: `20.0 mm` (`2.00 cm`) board spacing.
- Nominal axle/linkage/bracket hole diameter: `6.0 mm`.
- Gear presets: 16, 20, 24, and 32 teeth.
- Linkage lengths: 2, 4, 6, and 8 board cells.
- Cam presets: circle, eccentric, oval, pear.
- Bracket presets: 2-hole straight, 3-hole straight, L 3-hole, triangle 3-hole.
- Default profile key: `motionsmith-ms4n`. Legacy `ms4n` / `motionsmith-ms4n`
  identifiers are compatibility labels; the committed fabrication contract is
  this 20.0 mm / 6.0 mm board unless a custom output directory is generated.
- Red paths are cuts, blue circles are drill/cut holes, gray lines are score/reference geometry.

## Tolerance note

These files are nominal geometry, not material-specific kerf compensation. Before a workshop run, cut a small test coupon and adjust hole scaling/kerf for the chosen material, fasteners, printer, bit, or laser. The gears are educational/prototyping gears for automata experiments, not certified power-transmission gears.

## Relationship to `kit/`

`kit/` and `fabrication/` are intentionally separate physical-asset packages:

- `kit/` contains the existing educational/module-oriented MS4N activity sheets, prompt cards, checks, and broad classroom materials.
- `fabrication/` is the nominal-millimetre manufacturing package for the constrained physical parts requested here: gears, linkage bars, cams, brackets, and workshop cut sheets.
- Shared physical assumptions should come from `automataii.shared.physical_kit`; do not hand-edit generated `fabrication/` SVGs without updating the generator and sync test.

## Contents

- `manifest.json` — machine-readable inventory and dimensions.
- `gears/` — one SVG per gear preset; each gear includes a 6 mm axle hole and 6 mm linkage/bracket/crank/handle attachment holes.
- `linkages/` — one SVG per linkage length; holes are spaced on the board pitch.
- `cams/` — one SVG per cam preset; each cam includes a 6 mm axle hole and 6 mm linkage/bracket/crank/handle attachment holes.
- `brackets/` — bracket plates for the pegboard/bracket assembly style shown in the reference image.
- `sheets/` — six workshop sheets for pre-fabricated sets.

Managed files in this generated package: 24.

## Regeneration

```bash
uv run python scripts/generate_fabrication_templates.py --output fabrication
```

For a custom 2.5 cm board pitch, generate to a separate directory instead of overwriting the committed package:

```bash
uv run python scripts/generate_fabrication_templates.py --output /tmp/automataii-fabrication-2_5cm --grid-cell-cm 2.5
```
