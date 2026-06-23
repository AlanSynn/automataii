import test from "node:test";
import assert from "node:assert/strict";
import {
  addMechanism,
  addOrUpdatePath,
  computeMechanismState,
  createDemoProject,
  createMechanism,
  createSegmentedProject,
  generateBlueprintPackage,
  importProjectJson,
  pointAtProgress,
  recommendMechanism,
  smoothPathPoints,
  validateProject,
} from "../src/automataii-core.js";
import { crc32, createZipBytes } from "../src/zip.js";
import { postprocessOnnxOutputs, splitBodyBox } from "../src/onnx-segmentation.js";

test("demo project matches v2 project contract", () => {
  const project = createDemoProject();
  assert.equal(project.metadata.version, "2.0");
  assert.ok(project.parts.head);
  assert.ok(project.skeleton.joints.root);
  assert.deepEqual(validateProject(project), { ok: true, errors: [] });
});

test("v1 layers migrate to v2 parts", () => {
  const migrated = importProjectJson(JSON.stringify({ project_name: "Old", layers: { arm: { anchor_joint: "root", roi: [1, 2, 3, 4] } } }));
  assert.equal(migrated.metadata.version, "2.0");
  assert.ok(migrated.parts.arm);
  assert.equal(migrated.layers, undefined);
});

test("path recommendation and interpolation preserve workflow semantics", () => {
  const project = addOrUpdatePath(createDemoProject(), "lower_leg_left", [[0, 0], [0, 100], [5, 200]], { isClosed: false, smoothness: 50 });
  const rec = recommendMechanism(project.paths.lower_leg_left);
  assert.equal(rec.type, "cam_follower");
  assert.ok(smoothPathPoints(project.paths.lower_leg_left.points, project.paths.lower_leg_left.smoothness).length > project.paths.lower_leg_left.points.length);
  assert.ok(Number.isFinite(pointAtProgress(project.paths.lower_leg_left, 0.5).y));
});

test("mechanism layers serialize and compute finite states", () => {
  let project = createDemoProject();
  const mechanism = createMechanism("lower_arm_right", "four_bar");
  project = addMechanism(project, mechanism);
  const state = computeMechanismState(mechanism.type, mechanism.params, 45);
  assert.equal(state.metadata.type, "four_bar");
  assert.ok(Number.isFinite(state.positions.A[0]));
  assert.equal(validateProject(project).ok, true);
});

test("cam gear and planetary foundry states are available", () => {
  for (const type of ["cam_follower", "gear_train", "gear_linkage", "planetary_gear", "five_bar", "six_bar", "slider_crank"]) {
    const state = computeMechanismState(type, {}, 30);
    assert.ok(state.safety_status.message);
    assert.ok(Object.keys(state.positions).length > 0);
  }
});

test("blueprint package includes manifest project and svg", () => {
  const project = addMechanism(createDemoProject(), createMechanism("head", "cam_follower"));
  const pkg = generateBlueprintPackage(project);
  assert.equal(pkg.manifest.counts.mechanisms, 1);
  assert.match(pkg.blueprint_svg, /<svg/);
  assert.equal(pkg.project.metadata.version, "2.0");
  assert.match(pkg.assembly.readme, /assembly package/);
  assert.ok(pkg.assembly.recipes.recipes.length);
  assert.match(pkg.assembly.assembly_guide_svg, /Assembly guide/);
  assert.match(pkg.assembly.kit_parts_to_cut_svg, /Kit parts to cut/);
});


test("unknown mechanism types are rejected instead of silently falling back", () => {
  assert.throws(() => computeMechanismState("mystery_machine", {}, 0), /Unsupported mechanism type/);
  const project = createDemoProject();
  project.mechanisms.bad = { id: "bad", part_name: "head", type: "mystery_machine", params: {}, enabled: true };
  const validation = validateProject(project);
  assert.equal(validation.ok, false);
  assert.match(validation.errors.join("\n"), /unsupported type/);
});


test("blank mechanism types are invalid outside explicit UI defaults", () => {
  assert.throws(() => computeMechanismState("", {}, 0), /Unsupported mechanism type/);
  const project = createDemoProject();
  project.mechanisms.bad = { id: "bad", part_name: "head", params: {}, enabled: true };
  const validation = validateProject(project);
  assert.equal(validation.ok, false);
  assert.match(validation.errors.join("\n"), /unsupported type/);
});

test("blueprint SVG sanitizes project-controlled fill colors", () => {
  const project = createDemoProject();
  project.parts.head.fill_color = '" onload="alert(1)';
  const pkg = generateBlueprintPackage(project);
  assert.doesNotMatch(pkg.blueprint_svg, /onload=/);
  assert.match(pkg.blueprint_svg, /fill="#ccd"/);
});


test("createMechanism only defaults omitted type, not blank type", () => {
  assert.equal(createMechanism("head").type, "four_bar");
  assert.throws(() => createMechanism("head", ""), /Unsupported mechanism type/);
});


test("import rejects invalid mechanism types immediately", () => {
  assert.throws(() => importProjectJson(JSON.stringify({ mechanisms: { bad: { id: "bad", part_name: "head", type: "mystery_machine" } } })), /unsupported type/);
  assert.throws(() => importProjectJson(JSON.stringify({ mechanisms: { bad: { id: "bad", part_name: "head", type: "" } } })), /unsupported type/);
});

test("project validation rejects missing roots and dangling path references", () => {
  assert.match(validateProject({}).errors.join("\n"), /Missing metadata/);
  const missingPart = createDemoProject();
  missingPart.paths.ghost = { part_name: "ghost", points: [[0, 0], [1, 1]], is_closed: false };
  assert.match(validateProject(missingPart).errors.join("\n"), /Path references missing part: ghost/);
  const invalidPoints = createDemoProject();
  invalidPoints.paths.head = { part_name: "head", points: "not-points", is_closed: false };
  assert.match(validateProject(invalidPoints).errors.join("\n"), /Path head has invalid points/);
});

test("blueprint SVG sanitizes raw unnormalized numeric path payloads", () => {
  const project = createDemoProject();
  project.parts.head.roi = ['0" onload="alert(1)', 2, 3, 4];
  project.paths.head = { part_name: "head", points: [['0" onload="alert(1)', 'javascript:alert(1)']], is_closed: false, enabled: true };
  const pkg = generateBlueprintPackage(project);
  assert.doesNotMatch(pkg.blueprint_svg, /onload=/);
  assert.doesNotMatch(pkg.blueprint_svg, /javascript:/);
});

test("ONNX mask postprocess creates editable body-part boxes", () => {
  const mask = new Float32Array(16);
  for (let i = 5; i <= 10; i += 1) mask[i] = 1;
  const boxes = postprocessOnnxOutputs({ mask: { dims: [1, 1, 4, 4], data: mask } }, 400, 400);
  assert.ok(boxes.head);
  assert.ok(boxes.torso);
  const project = createSegmentedProject({ name: "onnx", boxes });
  assert.equal(validateProject(project).ok, true);
});

test("ONNX box postprocess maps model boxes to known parts", () => {
  const boxes = postprocessOnnxOutputs({ boxes: { dims: [2, 4], data: new Float32Array([0, 0, 0.5, 0.25, 10, 20, 60, 90]) } }, 200, 100);
  assert.deepEqual(boxes.head, [0, 0, 100, 25]);
  assert.deepEqual(boxes.torso, [10, 20, 50, 70]);
});

test("body silhouette split covers the full character workflow parts", () => {
  const boxes = splitBodyBox([10, 20, 200, 400]);
  for (const part of ["head", "torso", "lower_arm_left", "lower_leg_right"]) assert.ok(boxes[part]);
});

test("zip writer creates a valid uncompressed archive footer and crc", () => {
  assert.equal(crc32(new TextEncoder().encode("abc")).toString(16), "352441c2");
  const zip = createZipBytes([{ name: "manifest.json", content: "{}" }, { name: "blueprint.svg", content: "<svg/>" }]);
  assert.equal(new DataView(zip.buffer).getUint32(zip.length - 22, true), 0x06054b50);
  assert.ok(new TextDecoder().decode(zip).includes("manifest.json"));
});
