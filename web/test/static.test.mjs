import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const html = readFileSync("index.html", "utf8");
const app = readFileSync("src/app.js", "utf8");
const styles = readFileSync("src/styles.css", "utf8");
const build = readFileSync("scripts/build.mjs", "utf8");
const webReadme = readFileSync("README.md", "utf8");
const parityAudit = readFileSync("PARITY_AUDIT.md", "utf8");
const archTrace = readFileSync("../arch/feature-traceability.md", "utf8");
const archAdded = readFileSync("../arch/added-web-features.md", "utf8");
const archUxAudit = readFileSync("../arch/ui-ux-flow-audit.md", "utf8");

test("static shell exposes primary workflow and accessible status/dialog hooks", () => {
  for (const tab of ["character", "editor", "design", "foundry"]) assert.match(html, new RegExp(`data-tab="${tab}"`));
  assert.match(html, /role="status"/);
  assert.match(html, /aria-live="polite"/);
  assert.match(html, /id="modal-root"/);
  assert.match(app, /role="dialog"/);
  assert.match(app, /aria-modal="true"/);
});

test("browser app wires core user-flow actions", () => {
  for (const action of ["use-demo", "toggle-drawing", "get-mechanism", "foundry-export", "export-blueprint", "recover-autosave", "load-onnx-model", "run-onnx-segmentation", "capture-camera", "edit-recognition", "apply-recognition-edit", "apply-skeleton-edit", "save-layout", "restore-layout", "reset-layout", "about", "check-updates"]) {
    assert.match(app, new RegExp(action));
  }
});

test("UI shell has motion feedback with reduced-motion fallback", () => {
  assert.match(styles, /prefers-reduced-motion: no-preference/);
  assert.match(styles, /prefers-reduced-motion: reduce/);
  assert.match(styles, /transition:/);
  assert.match(styles, /@keyframes view-in/);
  assert.match(styles, /@keyframes dialog-in/);
});

test("static shell exposes ONNX model input and frontend-only export options", () => {
  assert.match(html, /id="onnx-model-input"/);
  assert.match(app, /Segmentation Mode/);
  assert.match(app, /ONNX Runtime Web/);
  assert.match(app, /zip/);
  assert.match(app, /pdf/);
});


test("project-derived HTML attributes use escaping helpers", () => {
  assert.match(app, /function escapeAttr/);
  for (const sink of ["data-part", "data-mechanism", "data-joint", "value"]) {
    assert.ok(app.includes(`${sink}=\"\${escapeAttr`), `${sink} must use escapeAttr`);
  }
});

test("local storage and ONNX failure paths preserve project contracts", () => {
  assert.match(app, /return raw \? importProjectJson\(raw\) : null/);
  assert.match(app, /commit\(importProjectJson\(raw\), "Autosave recovered\."/);
  assert.match(app, /Project unchanged/);
  assert.doesNotMatch(app, /catch \(error\) \{\s*commit\(createDemoProject/s);
});

test("ONNX model URLs are guarded before browser inference", () => {
  assert.match(app, /function normalizeOnnxModelUrl/);
  assert.match(app, /must be HTTPS, same-origin HTTP, localhost HTTP, or relative/);
  assert.match(app, /ONNX model URL rejected/);
  assert.match(build, /Missing ONNX Runtime Web assets/);
  assert.match(build, /vendor copy failed/);
});

test("root arch docs track frontend-only migration and added web features", () => {
  for (const doc of [webReadme, parityAudit, archTrace, archAdded, archUxAudit]) {
    assert.match(doc, /ONNX Runtime Web/);
    assert.match(doc, /frontend-only|Frontend-only|browser/i);
  }
  for (const phrase of ["LocalStorage", "ZIP", "PDF", "camera", "Off"]) {
    assert.match(`${webReadme}\n${parityAudit}\n${archTrace}\n${archAdded}`, new RegExp(phrase, "i"));
  }
  assert.match(archTrace, /No `Missing` items/);
  assert.match(archUxAudit, /UI\/UX Flow Audit/);
  assert.match(archUxAudit, /workaround/i);
  assert.match(archUxAudit, /File System Access API/);
  assert.match(archUxAudit, /reduced-motion/i);
});
