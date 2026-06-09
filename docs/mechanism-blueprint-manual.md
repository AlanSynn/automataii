# Mechanism Blueprint Manual

This manual defines the production checks for mechanism blueprint output and
Design-tab visual consistency.

## CAM

- The CAM profile is generated from the shared domain profile helper used by
  Design previews, manufacturing SVG export, and blueprint drawing.
- The contact point is the local profile support point under the scene-vertical
  follower. The follower base is placed above that contact point by the follower
  rod length in scene units.
- Reverse direction changes the traversal phase of the CAM profile; it does not
  mirror or regenerate the profile shape. Use it to preview clockwise vs.
  counter-clockwise motion while preserving the same cam geometry.
- Blueprint drawings use the historical print orientation so the original
  blueprint shape remains familiar while still using the same profile data as
  the live preview. Multi-lobe and harmonic CAMs created from Foundry parameters
  must appear in the blueprint with the same shape controls.

## 4-bar linkage

- A 4-bar blueprint must show both ground pivots, the crank end, rocker end, and
  coupler point. The coupler point is the output reference used for path matching
  unless the user chooses a joint output mode.
- Drag editing should preserve finite link lengths and keep the displayed joints
  aligned with the simulated mechanism state.

## Gear mechanisms

- Gear blueprints must show gear centers, pitch/contact circles, and mesh
  spacing. The mesh point should remain consistent with the Design-tab preview
  after drag editing or project reload.
- Simple gears and planetary gears should keep direction indicators and tracking
  markers distinct from CAM contact/follower markers.

## Units and export checklist

- Metric export reports millimeters and imperial export reports inch-derived
  dimensions. Always verify the selected unit label appears in the export
  success message and generated blueprint metadata.
- Before release, smoke-test temporary save files, full project save/load,
  CAM/4-bar/gear drag editing, recommendation template previews, and blueprint
  export for both metric and imperial workflows.
