# MS4N physical kit SVG package

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


## Current generated files

- `ms4n-00-bar-board-guide.svg`
- `ms4n-01-linkage-bars.svg`
- `ms4n-02-cam-follower-kit.svg`
- `ms4n-03-crank-slider-kit.svg`
- `ms4n-04-gears-pulleys-kit.svg`
- `ms4n-05-character-connectors.svg`
- `ms4n-06-trace-prompt-cards.svg`
- `ms4n-07-fabrication-checks.svg`
