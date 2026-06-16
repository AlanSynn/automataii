# Automataii board assembly guides

Use this folder when you already have the fabricated kit parts and want to build on the 15x15 board.

## How to use

1. Open `board-15x15.svg` to identify row letters and column numbers.
2. Pick one guide SVG.
3. Follow one step card at a time: place the fastener, add spacers, add the part, then run the check.
4. Keep paper fasteners loose enough for rotation or sliding before flattening the tabs.

## Guides

- `gear-train-basic` — Two-gear crank (4 steps)
- `cam-follower-basic` — Cam and follower lift (4 steps)
- `four-bar-basic` — Four-bar linkage (4 steps)
- `gear-linkage-crank` — Gear crank linkage (4 steps)

## Data contract

- `recipes.json` is the semantic source of truth for board coordinates, parts, stack order, and app visual mappings.
- Guide SVGs are render targets. They include `data-step`, `data-board-coord`, `data-part-key`, `data-stack-layer`, `data-layout-box`, and `data-app-mechanism` metadata for tests and future app previews.
- Self-fabrication cut sheets stay in the sibling part and `sheets/` folders.
