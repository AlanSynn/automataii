Title: Stage 3 — Blueprint Enhancements (BOM, PDF, Multi‑Views, Dual Packets)

Background
- PAPER.md: fabrication‑ready blueprints with multiple views (orthographic, isometric, exploded/sectional), BOM, export as SVG/PDF, two packets (character and mechanism), adjustable kerf/spacing/min sizes.
- Current status: Single‑page SVG export exists with enhanced mechanism details. BOM and multi‑views exist in a standalone generator skeleton but are not integrated; PDF export is not implemented.

Problem Statement
- Integrate advanced blueprint features into the main export flow, ensuring selectable unit systems and per‑fabrication settings.

Goals
- Add BOM, orthographic/isometric/exploded views per mechanism, and PDF export.
- Support dual packet export (character packet and mechanism packet).
- UI for kerf width, spacing, minimum size thresholds.

Functional Requirements
- Export dialog additions:
  - Output format: SVG, PDF.
  - Packet selection: Character, Mechanism, Both.
  - Fabrication settings: kerf (mm/inch), spacing, min feature size; presets per material.
- Blueprint composition:
  - Integrate BlueprintGenerator multi‑view sections for mechanisms.
  - Generate BOM table from mechanism layers and part items (name, qty, material).
  - Layout optimizer remains responsible for placement within page bounds.

Acceptance Criteria
- Users can export PDF with multi‑view technical drawings and a BOM.
- SVG/PDF reflect unit system choice (metric/imperial) and configured kerf.
- Character and mechanism packets export independently and together.

Test Plan
- Unit: BOM generation correctness; PDF pipeline outputs non‑empty, parsable files.
- Integration: open exported PDFs in viewers; visually verify multi‑views and dimensions.

Implementation Notes
- Use Qt PDF (QtSvg/QPrinter if available) or a minimal headless SVG→PDF path for portability.
- Ensure no external network dependency for export.

Milestones
1) Export dialog + settings plumbing (1–2 days)
2) BOM + multi‑view integration (2–3 days)
3) PDF pipeline + tests (1–2 days)

