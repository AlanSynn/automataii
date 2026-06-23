import {
  MECHANISM_CATALOG,
  PROJECT_EXTENSION,
  addMechanism,
  addOrUpdatePath,
  canonicalMechanismType,
  clearPath,
  clone,
  computeMechanismState,
  createDemoProject,
  createEmptyProject,
  createImageProject,
  createMechanism,
  createSegmentedProject,
  defaultParams,
  deleteMechanism,
  generateBlueprintPackage,
  generateBlueprintSvg,
  getMechanismEntry,
  importProjectJson,
  pointAtProgress,
  recommendMechanism,
  smoothPathPoints,
  touch,
  updateMechanism,
  validateProject,
} from "./automataii-core.js";
import { loadOnnxSegmenter } from "./onnx-segmentation.js";
import { createZipBlob } from "./zip.js";

const PROJECT_KEY = "automataii:web:project:v2";
const AUTOSAVE_KEY = "automataii:web:autosave:v2";
const SETTINGS_KEY = "automataii:web:settings:v1";
const LAYOUT_KEY = "automataii:web:layout:v1";
const DEFAULT_SETTINGS = {
  theme: "Light",
  toolbar: true,
  showPartProperties: false,
  animationDuration: 2,
  timing: "Linear",
  performance: "Balanced",
  physicsSnap: "Balanced",
  detailedProcessing: false,
  smoothness: 50,
  unit: "mm",
  gridEnabled: true,
  gridCellCm: 2,
  blueprintFormat: "svg",
  segmentationMode: "Local heuristic",
  onnxExecutionProvider: "wasm",
  onnxModelUrl: "",
  autosaveEnabled: true,
  autosaveInterval: 60,
};

const app = {
  tab: "character",
  project: loadProject() || createDemoProject(),
  settings: loadSettings(),
  selectedPart: null,
  selectedMechanism: null,
  drawing: false,
  pathType: "closed",
  draftPath: [],
  animation: { playing: false, start: 0, progress: 0 },
  foundryType: "four_bar",
  foundryParams: defaultParams("four_bar"),
  foundryFilter: "",
  undo: [],
  redo: [],
  status: "Ready.",
  busy: false,
  onnxModel: null,
  onnxModelBuffer: null,
  onnxModelName: "",
  cameraStream: null,
  imageCache: new Map(),
};

const $ = (id) => document.getElementById(id);
const main = $("main");
const toolbar = $("toolbar");
const status = $("status");
const modalRoot = $("modal-root");
const projectInput = $("project-file-input");
const imageInput = $("image-file-input");
let onnxInput = $("onnx-model-input");
if (!onnxInput) {
  onnxInput = document.createElement("input");
  onnxInput.id = "onnx-model-input";
  onnxInput.type = "file";
  onnxInput.accept = ".onnx,.ort,application/octet-stream";
  onnxInput.hidden = true;
  document.body.appendChild(onnxInput);
}

function init() {
  app.selectedPart ||= Object.keys(app.project.parts)[0] || null;
  app.selectedMechanism ||= Object.keys(app.project.mechanisms)[0] || null;
  document.addEventListener("click", onClick);
  document.addEventListener("input", onInput);
  document.addEventListener("change", onChange);
  document.addEventListener("keydown", onKeyDown);
  projectInput.addEventListener("change", onProjectFile);
  imageInput.addEventListener("change", onImageFile);
  onnxInput.addEventListener("change", onOnnxModelFile);
  setInterval(() => {
    if (app.settings.autosaveEnabled) localStorage.setItem(AUTOSAVE_KEY, JSON.stringify(app.project));
  }, Math.max(10, Number(app.settings.autosaveInterval) || 60) * 1000);
  render();
  requestAnimationFrame(tick);
}

function loadProject() {
  try {
    const raw = localStorage.getItem(PROJECT_KEY);
    return raw ? importProjectJson(raw) : null;
  } catch {
    localStorage.removeItem(PROJECT_KEY);
    return null;
  }
}

function loadSettings() {
  try { return { ...DEFAULT_SETTINGS, ...JSON.parse(localStorage.getItem(SETTINGS_KEY)) }; }
  catch { return { ...DEFAULT_SETTINGS }; }
}

function saveProjectLocal() {
  localStorage.setItem(PROJECT_KEY, JSON.stringify(app.project));
  localStorage.setItem(AUTOSAVE_KEY, JSON.stringify(app.project));
}

function saveSettings() {
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(app.settings));
  document.body.classList.toggle("dark", app.settings.theme === "Dark");
}

function commit(project, message) {
  app.undo.push(clone(app.project));
  if (app.undo.length > 50) app.undo.shift();
  app.redo = [];
  app.project = touch(project);
  saveProjectLocal();
  setStatus(message);
  render();
}

function setStatus(message) {
  app.status = message;
  status.textContent = message;
}

function render() {
  normalizeSelection();
  saveSettings();
  renderTabs();
  renderToolbar();
  main.innerHTML = renderTab();
  status.textContent = app.status;
  drawAllCanvases();
}

function normalizeSelection() {
  if (app.selectedPart && !app.project.parts?.[app.selectedPart]) app.selectedPart = Object.keys(app.project.parts || {})[0] || null;
  if (app.selectedMechanism && !app.project.mechanisms?.[app.selectedMechanism]) app.selectedMechanism = Object.keys(app.project.mechanisms || {})[0] || null;
}

function renderTabs() {
  document.querySelectorAll(".tab-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === app.tab);
    button.setAttribute("aria-current", button.dataset.tab === app.tab ? "page" : "false");
  });
}

function renderToolbar() {
  toolbar.classList.toggle("hidden", !app.settings.toolbar);
  toolbar.innerHTML = `
    <button class="tool-button" data-action="new-project" type="button">New</button>
    <button class="tool-button" data-action="load-project" type="button">Load Project…</button>
    <button class="tool-button" data-action="recover-autosave" type="button">Recover Autosave</button>
    <button class="tool-button" data-action="save-project" type="button">Save Project</button>
    <button class="tool-button" data-action="export-project" type="button">Export Copy</button>
    <button class="tool-button" data-action="export-blueprint" type="button">Export Blueprint Package</button>
    <button class="tool-button" data-action="undo" type="button" ${app.undo.length ? "" : "disabled"}>Back (Undo)</button>
    <button class="tool-button" data-action="redo" type="button" ${app.redo.length ? "" : "disabled"}>Forward (Redo)</button>
    <button class="tool-button" data-action="open-options" type="button">Preferences…</button>
    <button class="tool-button" data-action="save-layout" type="button">Save Layout</button>
    <button class="tool-button" data-action="restore-layout" type="button">Restore Layout</button>
    <button class="tool-button" data-action="about" type="button">About</button>
    <button class="tool-button" data-action="check-updates" type="button">Check Updates</button>
  `;
}

function renderTab() {
  if (app.tab === "editor") return renderEditor();
  if (app.tab === "design") return renderDesign();
  if (app.tab === "foundry") return renderFoundry();
  return renderCharacter();
}

function renderCharacter() {
  const partCount = Object.keys(app.project.parts || {}).length;
  const jointCount = Object.keys(app.project.skeleton?.joints || {}).length;
  const onnxActive = app.settings.segmentationMode === "ONNX Runtime Web";
  return `
    <section class="workspace" data-view="character">
      <aside class="panel">
        <h2>Character Selection</h2>
        <p class="help">Choose a sample drawing, image, or camera frame. Segmentation mode: ${escapeHtml(app.settings.segmentationMode)}.</p>
        <fieldset class="group controls">
          <legend>Input Drawing</legend>
          <button class="success" data-action="use-demo" type="button">Use Stick Figure Example</button>
          <button class="secondary" data-action="load-image" type="button">Load Image File</button>
          <button class="secondary" data-action="capture-camera" type="button">Capture Camera</button>
        </fieldset>
        <fieldset class="group controls">
          <legend>ONNX Runtime Web</legend>
          <button class="secondary" data-action="load-onnx-model" type="button">Load ONNX Model…</button>
          <button class="secondary" data-action="load-onnx-url" type="button">Load Model URL</button>
          <button class="primary" data-action="run-onnx-segmentation" type="button" ${onnxActive && app.project.image_path ? "" : "disabled"}>Run Segmentation</button>
          <p class="help">${app.onnxModelName ? `Loaded: ${escapeHtml(app.onnxModelName)}` : "ONNX is optional. Turn it off or use Local heuristic in Preferences."}</p>
        </fieldset>
        <fieldset class="group controls">
          <legend>Recognition Editing</legend>
          <button class="secondary" data-action="edit-recognition" type="button" ${partCount || app.project.image_path ? "" : "disabled"}>Edit Parts / Skeleton / Boxes</button>
          <button class="secondary" data-action="edit-skeleton" type="button" ${jointCount ? "" : "disabled"}>Edit Skeleton Joints</button>
          <button class="secondary" data-action="save-skeleton" type="button" ${jointCount ? "" : "disabled"}>Save Skeleton</button>
          <button class="secondary" data-action="assign-character" type="button">Replace Character</button>
        </fieldset>
        ${app.settings.detailedProcessing ? renderProcessingSteps() : ""}
        <fieldset class="group controls">
          <legend>View Controls</legend>
          <div class="button-row"><button class="tool-button" data-action="zoom-in" type="button">+</button><button class="tool-button" data-action="zoom-out" type="button">−</button><button class="tool-button" data-action="zoom-fit" type="button">⌖</button><button class="tool-button" data-action="zoom-reset" type="button">1:1</button></div>
        </fieldset>
        <fieldset class="group controls">
          <legend>Download / Output Location</legend>
          <p class="help">Browser builds save generated projects and skeleton files to your Downloads folder.</p>
          <button class="secondary" data-action="choose-output" type="button">Choose Save Folder…</button>
        </fieldset>
      </aside>
      <section class="canvas-card">
        <div class="canvas-toolbar"><strong>${partCount} parts · ${jointCount} joints</strong><button class="primary" data-tab-target="editor" type="button">Continue to Path Editor</button></div>
        <canvas id="character-canvas" width="900" height="620" aria-label="Character preview"></canvas>
      </section>
    </section>`;
}

function renderEditor() {
  const parts = Object.values(app.project.parts || {});
  const selected = app.selectedPart && app.project.parts[app.selectedPart];
  const path = app.selectedPart ? app.project.paths[app.selectedPart] : null;
  return `
    <section class="workspace" data-view="editor">
      <aside class="panel">
        <h2>Path Editor</h2>
        <fieldset class="group"><legend>1 Parts</legend>${renderPartList(parts)}</fieldset>
        <fieldset class="group controls"><legend>2 Motion Path</legend>
          <p class="help">${selected ? `Selected: ${escapeHtml(selected.name)}` : "Select a part"}</p>
          <div class="button-row" role="radiogroup" aria-label="Path type">
            <label><input name="path-type" type="radio" value="closed" ${app.pathType === "closed" ? "checked" : ""}/> Closed</label>
            <label><input name="path-type" type="radio" value="open" ${app.pathType === "open" ? "checked" : ""}/> Open</label>
          </div>
          <button class="primary" data-action="toggle-drawing" type="button" ${selected ? "" : "disabled"}>${app.drawing ? "Stop Drawing" : "✏️ Start Drawing Path"}</button>
          <button class="danger" data-action="clear-path" type="button" ${path ? "" : "disabled"}>Clear</button>
          <label class="form-row">Smoothness <input type="range" min="0" max="100" value="${escapeAttr(path?.smoothness ?? app.settings.smoothness)}" data-setting="smoothness" /></label>
          <p class="help">${path ? `${smoothPathPoints(path.points, path.smoothness, path.is_closed).length} smoothed path points from ${path.points.length} drawn points.` : "Click points in the canvas while drawing."}</p>
        </fieldset>
        ${app.settings.showPartProperties ? renderPartProperties(selected) : ""}
        <fieldset class="group controls"><legend>3 Animation</legend>${renderAnimationButtons()}</fieldset>
      </aside>
      <section class="canvas-card">
        <div class="canvas-toolbar"><strong>${selected ? escapeHtml(selected.name) : "No part selected"}</strong><button class="primary" data-tab-target="design" type="button">Continue to Mechanism Design</button></div>
        <canvas id="editor-canvas" width="900" height="620" aria-label="Path editor canvas"></canvas>
      </section>
    </section>`;
}

function renderDesign() {
  const parts = Object.values(app.project.parts || {});
  const mechanisms = Object.values(app.project.mechanisms || {});
  const selectedMechanism = app.project.mechanisms[app.selectedMechanism];
  return `
    <section class="workspace" data-view="design">
      <aside class="panel">
        <h2>Mechanism Design</h2>
        <fieldset class="group"><legend>1 Parts for Mechanisms</legend>${renderPartList(parts, true)}</fieldset>
        <fieldset class="group controls"><legend>2 Mechanism Generation</legend>
          <div class="button-row"><button class="success" data-action="get-mechanism" type="button" ${app.selectedPart ? "" : "disabled"}>Get Mechanism</button><button class="secondary" data-action="assign-character" type="button">Assign Character</button></div>
          <button class="secondary" data-action="toggle-parametric" type="button" ${selectedMechanism ? "" : "disabled"}>Parametric Edit</button>
        </fieldset>
        ${app.settings.showPartProperties ? renderPartProperties(app.project.parts[app.selectedPart]) : ""}
        <fieldset class="group"><legend>Mechanism Layers</legend>${renderMechanismList(mechanisms)}</fieldset>
        ${selectedMechanism ? renderParamControls(selectedMechanism, "design") : ""}
        <fieldset class="group controls"><legend>3 Animation</legend>${renderAnimationButtons()}</fieldset>
        <fieldset class="group controls"><legend>4 Blueprint Export</legend><button class="primary" data-action="export-blueprint" type="button">Export Blueprint Package</button><p class="help">Includes parts, paths, mechanism layers, and SVG blueprint.</p></fieldset>
      </aside>
      <section class="canvas-card">
        <div class="canvas-toolbar"><strong>${mechanisms.length} mechanism layers</strong><button class="primary" data-tab-target="foundry" type="button">Open Mechanism Foundry</button></div>
        <canvas id="design-canvas" width="900" height="620" aria-label="Mechanism design canvas"></canvas>
      </section>
    </section>`;
}

function renderFoundry() {
  const entries = MECHANISM_CATALOG.filter((entry) => {
    const q = app.foundryFilter.trim().toLowerCase();
    return !q || `${entry.name} ${entry.category} ${entry.tags.join(" ")}`.toLowerCase().includes(q);
  });
  const entry = getMechanismEntry(app.foundryType);
  return `
    <section class="workspace" data-view="foundry">
      <aside class="panel">
        <h2>Mechanism Foundry</h2>
        <input class="search" type="search" placeholder="Search mechanisms…" data-field="foundry-filter" value="${escapeAttr(app.foundryFilter)}" aria-label="Search mechanisms" />
        <ul class="catalog-list">${entries.map((item) => `<li><button class="list-item ${item.key === app.foundryType ? "active" : ""}" data-foundry-type="${escapeAttr(item.key)}" type="button"><strong>${escapeHtml(item.icon)} ${escapeHtml(item.name)}</strong><br/><small>${escapeHtml(item.category)} · ${escapeHtml(item.complexity)}</small></button></li>`).join("")}</ul>
        <fieldset class="group"><legend>Information</legend><p>${escapeHtml(entry.description)}</p><p class="help">${escapeHtml(entry.goal)}</p><p>${entry.tags.map((tag) => `<span class="badge">${escapeHtml(tag)}</span>`).join(" ")}</p></fieldset>
        ${renderFoundryParams(entry)}
        <fieldset class="group controls"><legend>Transfer</legend><button class="success" data-action="foundry-export" type="button">Export to Mechanism Design</button><p class="help">Adds this mechanism to the currently selected part.</p></fieldset>
      </aside>
      <section class="canvas-card">
        <div class="canvas-toolbar"><strong>${entry.name}</strong><div class="button-row">${renderAnimationButtons()}</div></div>
        <canvas id="foundry-canvas" width="900" height="620" aria-label="Mechanism foundry preview"></canvas>
      </section>
    </section>`;
}

function renderOptions() {
  return `<section class="panel"><h2>Options</h2><div class="options-grid">
    ${selectSetting("Theme", "theme", ["Light", "Dark"])}
    ${checkSetting("Show Toolbar", "toolbar")}
    ${checkSetting("Show Part Properties Panel", "showPartProperties")}
    ${numberSetting("Animation Duration (s)", "animationDuration", 0.1, 60, 0.1)}
    ${selectSetting("Timing Profile", "timing", ["Linear", "Ease-In", "Ease-Out", "Ease-In-Out"])}
    ${selectSetting("Performance Preset", "performance", ["Fast", "Balanced", "High"])}
    ${selectSetting("Physics Snap Mode", "physicsSnap", ["Fast", "Balanced", "High"])}
    ${checkSetting("Show Detailed Processing Steps", "detailedProcessing")}
    ${selectSetting("Segmentation Mode", "segmentationMode", ["Local heuristic", "ONNX Runtime Web", "Off"])}
    ${selectSetting("ONNX Execution Provider", "onnxExecutionProvider", ["wasm", "webgl", "webgpu"])}
    ${textSetting("ONNX Model URL", "onnxModelUrl")}
    ${selectSetting("Units", "unit", ["mm", "cm", "in"])}
    ${checkSetting("Grid System Enabled", "gridEnabled")}
    ${numberSetting("Grid Cell Size (cm)", "gridCellCm", 0.5, 5, 0.5)}
    ${selectSetting("Blueprint Export Format", "blueprintFormat", ["svg", "json", "zip", "pdf"])}
    ${checkSetting("Enable Autosave", "autosaveEnabled")}
    ${numberSetting("Autosave Interval (s)", "autosaveInterval", 10, 3600, 10)}
  </div><div class="button-row"><button class="secondary" data-action="save-layout" type="button">Save Workspace Layout</button><button class="secondary" data-action="restore-layout" type="button">Restore Workspace Layout</button><button class="danger" data-action="reset-layout" type="button">Reset Workspace Layout</button></div></section>`;
}

function renderProcessingSteps() {
  return `<fieldset class="group"><legend>Processing Steps</legend><ol class="help"><li>Load image or camera frame.</li><li>Apply ${escapeHtml(app.settings.segmentationMode)} segmentation mode.</li><li>Create editable parts, skeleton joints, and motion-ready boxes.</li></ol></fieldset>`;
}

function renderPartProperties(part) {
  if (!part) return `<fieldset class="group"><legend>Part Properties</legend><p class="empty">Select a part to inspect properties.</p></fieldset>`;
  const roi = (part.roi || []).map((v) => Number(v).toFixed(1)).join(", ");
  return `<fieldset class="group"><legend>Part Properties</legend><p><strong>${escapeHtml(part.name)}</strong></p><p class="help">Anchor: ${escapeHtml(part.anchor_joint || "root")} · ROI: ${escapeHtml(roi || "n/a")} · Opacity: ${Number(part.opacity ?? 1).toFixed(2)}</p></fieldset>`;
}

function renderPartList(parts, showPathStatus = false) {
  if (!parts.length) return `<p class="empty">No character parts loaded.</p>`;
  return `<ul class="part-list">${parts.map((part) => {
    const hasPath = Boolean(app.project.paths[part.name]);
    return `<li><button class="list-item ${part.name === app.selectedPart ? "active" : ""}" data-part="${escapeAttr(part.name)}" type="button"><strong>${escapeHtml(part.name.replaceAll("_", " "))}</strong>${showPathStatus ? `<span class="badge">${hasPath ? "path" : "no path"}</span>` : ""}<br/><small>${escapeHtml(part.anchor_joint || "root")}</small></button></li>`;
  }).join("")}</ul>`;
}

function renderMechanismList(mechanisms) {
  if (!mechanisms.length) return `<p class="empty">No mechanisms yet. Draw a path and click Get Mechanism.</p>`;
  return `<ul class="mechanism-list">${mechanisms.map((mechanism) => {
    const entry = getMechanismEntry(mechanism.type);
    const name = entry?.name || `Unsupported: ${mechanism.type}`;
    return `<li><button class="list-item ${mechanism.id === app.selectedMechanism ? "active" : ""}" data-mechanism="${escapeAttr(mechanism.id)}" type="button"><strong>${escapeHtml(name)}</strong><span class="badge">${mechanism.enabled ? "on" : "off"}</span><br/><small>${escapeHtml(mechanism.part_name)}</small></button></li>`;
  }).join("")}</ul><div class="button-row"><button class="secondary" data-action="toggle-mechanism" type="button" ${app.selectedMechanism ? "" : "disabled"}>Enable / Disable</button><button class="danger" data-action="delete-mechanism" type="button" ${app.selectedMechanism ? "" : "disabled"}>Delete</button></div>`;
}

function renderAnimationButtons() {
  return `<div class="button-row"><button class="primary" data-action="play" type="button">Play</button><button class="secondary" data-action="stop" type="button">Stop</button><button class="secondary" data-action="reset" type="button">Reset</button></div>`;
}

function renderParamControls(mechanism, scope) {
  const entry = getMechanismEntry(mechanism.type);
  if (!entry) return `<fieldset class="group"><legend>Parametric Edit</legend><p class="empty">Unsupported mechanism type: ${escapeHtml(mechanism.type)}</p></fieldset>`;
  return `<fieldset class="group"><legend>Parametric Edit — ${escapeHtml(entry.name)}</legend>${Object.entries(entry.parameters).map(([key, spec]) => {
    const value = Number(mechanism.params[key] ?? spec.default);
    return `<label class="form-row">${escapeHtml(spec.name)} <span><input type="range" min="${spec.min}" max="${spec.max}" step="${spec.type === "int" ? 1 : 0.1}" value="${escapeAttr(value)}" data-mechanism-param="${escapeAttr(key)}" data-scope="${escapeAttr(scope)}" /> <output>${value}${spec.unit || ""}</output></span></label>`;
  }).join("")}</fieldset>`;
}

function renderFoundryParams(entry) {
  return `<fieldset class="group"><legend>Parameters</legend>${Object.entries(entry.parameters).map(([key, spec]) => {
    const value = Number(app.foundryParams[key] ?? spec.default);
    return `<label class="form-row">${escapeHtml(spec.name)} <span><input type="range" min="${spec.min}" max="${spec.max}" step="${spec.type === "int" ? 1 : 0.1}" value="${escapeAttr(value)}" data-foundry-param="${escapeAttr(key)}" /> <output>${value}${spec.unit || ""}</output></span></label>`;
  }).join("")}</fieldset>`;
}

function selectSetting(label, key, values) {
  return `<label class="group">${label}<br/><select data-setting="${escapeAttr(key)}">${values.map((value) => `<option value="${escapeAttr(value)}" ${app.settings[key] === value ? "selected" : ""}>${value}</option>`).join("")}</select></label>`;
}

function checkSetting(label, key) {
  return `<label class="group"><input type="checkbox" data-setting="${escapeAttr(key)}" ${app.settings[key] ? "checked" : ""}/> ${label}</label>`;
}

function numberSetting(label, key, min, max, step) {
  return `<label class="group">${label}<br/><input type="number" data-setting="${escapeAttr(key)}" min="${min}" max="${max}" step="${step}" value="${escapeAttr(app.settings[key])}" /></label>`;
}

function textSetting(label, key) {
  return `<label class="group">${label}<br/><input type="url" data-setting="${escapeAttr(key)}" value="${escapeAttr(app.settings[key])}" placeholder="optional https:// or ./models/model.onnx" /></label>`;
}
function onClick(event) {
  const button = event.target.closest("button");
  if (button?.dataset.tab) { app.tab = button.dataset.tab; render(); main.focus(); return; }
  if (button?.dataset.tabTarget) { app.tab = button.dataset.tabTarget; render(); main.focus(); return; }
  if (button?.dataset.action) handleAction(button.dataset.action);
  if (button?.dataset.part) { app.selectedPart = button.dataset.part; app.draftPath = []; app.drawing = false; render(); }
  if (button?.dataset.mechanism) { app.selectedMechanism = button.dataset.mechanism; render(); }
  if (button?.dataset.foundryType) {
    app.foundryType = button.dataset.foundryType;
    app.foundryParams = defaultParams(app.foundryType);
    render();
  }
}

function onInput(event) {
  const target = event.target;
  if (target.dataset.field === "foundry-filter") { app.foundryFilter = target.value; render(); return; }
  if (target.dataset.setting) {
    const key = target.dataset.setting;
    app.settings[key] = target.type === "checkbox" ? target.checked : target.type === "number" ? Number(target.value) : target.value;
    if (key.startsWith("onnx") || key === "segmentationMode") app.onnxModel = null;
    if (key === "smoothness" && app.selectedPart && app.project.paths[app.selectedPart]) {
      const path = app.project.paths[app.selectedPart];
      app.project = addOrUpdatePath(app.project, app.selectedPart, path.points, { isClosed: path.is_closed, enabled: path.enabled, smoothness: app.settings.smoothness });
      saveProjectLocal();
    }
    saveSettings();
    render();
    return;
  }
  if (target.dataset.foundryParam) {
    const key = target.dataset.foundryParam;
    app.foundryParams[key] = target.step === "1" ? Math.round(Number(target.value)) : Number(target.value);
    target.nextElementSibling.textContent = target.value;
    drawFoundryCanvas();
    return;
  }
  if (target.dataset.mechanismParam && app.selectedMechanism) {
    const key = target.dataset.mechanismParam;
    const value = target.step === "1" ? Math.round(Number(target.value)) : Number(target.value);
    app.project = updateMechanism(app.project, app.selectedMechanism, { params: { [key]: value } });
    saveProjectLocal();
    target.nextElementSibling.textContent = target.value;
    drawDesignCanvas();
  }
}

function onChange(event) {
  if (event.target.name === "path-type") app.pathType = event.target.value;
}

function onKeyDown(event) {
  const meta = event.ctrlKey || event.metaKey;
  if (event.key === "Tab" && !modalRoot.hidden) trapDialogFocus(event);
  if (meta && event.key.toLowerCase() === "s") { event.preventDefault(); downloadProject(false); }
  if (meta && event.key.toLowerCase() === "o") { event.preventDefault(); projectInput.click(); }
  if (meta && event.key.toLowerCase() === "z" && !event.shiftKey) { event.preventDefault(); undo(); }
  if ((meta && event.key.toLowerCase() === "y") || (meta && event.shiftKey && event.key.toLowerCase() === "z")) { event.preventDefault(); redo(); }
  if (event.key === "Escape" && !modalRoot.hidden) closeModal();
}

function trapDialogFocus(event) {
  const focusable = [...modalRoot.querySelectorAll("button,input,select,textarea,a,[tabindex]:not([tabindex='-1'])")].filter((el) => !el.disabled);
  if (!focusable.length) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
}

function handleAction(action) {
  const actions = {
    "new-project": () => commit(createEmptyProject("Untitled Web Project"), "New project created."),
    "load-project": () => projectInput.click(),
    "recover-autosave": recoverAutosave,
    "save-project": () => downloadProject(false),
    "export-project": () => downloadProject(true),
    "export-blueprint": downloadBlueprint,
    undo,
    redo,
    "open-options": openOptions,
    "save-layout": saveWorkspaceLayout,
    "restore-layout": restoreWorkspaceLayout,
    "reset-layout": resetWorkspaceLayout,
    about: () => openInfo("About Automataii", "Automataii is an interactive mechanism design and character animation platform. This frontend-only build preserves the desktop workflow in the browser."),
    "check-updates": () => openInfo("Updates", "The desktop auto-updater is not used in the frontend-only web build. Redeploy or pull the latest static web bundle to update."),
    "use-demo": () => commit(createDemoProject(), "Stick figure example loaded."),
    "load-image": () => imageInput.click(),
    "capture-camera": openCameraCapture,
    "load-onnx-model": () => onnxInput.click(),
    "load-onnx-url": loadOnnxModelFromUrl,
    "run-onnx-segmentation": () => processCurrentImageWithOnnx(),
    "edit-recognition": openRecognitionEditor,
    "edit-skeleton": openSkeletonEditor,
    "save-skeleton": downloadSkeleton,
    "assign-character": () => commit(createDemoProject({ name: app.project.metadata?.name || "Assigned Character" }), "Demo character assigned."),
    "choose-output": () => openInfo("Output Location", "Browsers cannot choose arbitrary folders without extra permissions. Downloads are used for project, skeleton, and blueprint exports."),
    "zoom-in": () => setStatus("Zoom in uses browser zoom in this static app."),
    "zoom-out": () => setStatus("Zoom out uses browser zoom in this static app."),
    "zoom-fit": () => drawAllCanvases(),
    "zoom-reset": () => drawAllCanvases(),
    "toggle-drawing": toggleDrawing,
    "clear-path": () => app.selectedPart && commit(clearPath(app.project, app.selectedPart), `Cleared path for ${app.selectedPart}.`),
    play: () => { app.animation.playing = true; app.animation.start = performance.now() - app.animation.progress * app.settings.animationDuration * 1000; setStatus("Animation playing."); },
    stop: () => { app.animation.playing = false; setStatus("Animation stopped."); },
    reset: () => { app.animation.playing = false; app.animation.progress = 0; drawAllCanvases(); setStatus("Animation reset."); },
    "get-mechanism": addRecommendedMechanism,
    "toggle-parametric": () => setStatus("Parametric sliders are available below the selected mechanism."),
    "toggle-mechanism": toggleMechanism,
    "delete-mechanism": removeSelectedMechanism,
    "foundry-export": exportFoundryToDesign,
  };
  actions[action]?.();
}

function onProjectFile(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  file.text().then((text) => {
    try {
      const project = importProjectJson(text);
      commit(project, `Loaded ${file.name}.`);
    } catch (error) {
      setStatus(error.message);
    } finally {
      projectInput.value = "";
    }
  });
}

function onImageFile(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    processImageSource(reader.result, file.name.replace(/\.[^.]+$/, ""));
    imageInput.value = "";
  };
  reader.readAsDataURL(file);
}

async function onOnnxModelFile(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  try {
    app.onnxModelBuffer = await file.arrayBuffer();
    app.onnxModelName = file.name;
    app.onnxModel = null;
    app.settings.segmentationMode = "ONNX Runtime Web";
    saveSettings();
    setStatus(`ONNX model loaded: ${file.name}`);
    render();
  } catch (error) {
    setStatus(`ONNX model load failed: ${error.message}`);
  } finally {
    onnxInput.value = "";
  }
}

function undo() {
  if (!app.undo.length) return;
  app.redo.push(clone(app.project));
  app.project = app.undo.pop();
  saveProjectLocal();
  setStatus("Undid last action.");
  render();
}

function redo() {
  if (!app.redo.length) return;
  app.undo.push(clone(app.project));
  app.project = app.redo.pop();
  saveProjectLocal();
  setStatus("Redid action.");
  render();
}

function recoverAutosave() {
  try {
    const raw = localStorage.getItem(AUTOSAVE_KEY);
    if (!raw) { setStatus("No autosave recovery files found."); return; }
    commit(importProjectJson(raw), "Autosave recovered.");
  } catch (error) {
    setStatus(`Autosave recovery failed: ${error.message}`);
  }
}

function downloadProject(copy) {
  const name = safeName(app.project.metadata?.name || "automataii-project");
  downloadJson(app.project, `${name}${copy ? "-copy" : ""}${PROJECT_EXTENSION}`);
  setStatus(copy ? "Project copy exported." : "Project saved to Downloads.");
}

function downloadBlueprint() {
  const packageData = generateBlueprintPackage(app.project);
  const base = safeName(app.project.metadata?.name || "automataii-blueprint");
  if (app.settings.blueprintFormat === "json") downloadJson(packageData, `${base}-blueprint-package.json`);
  else if (app.settings.blueprintFormat === "zip") downloadZipPackage(packageData, base);
  else if (app.settings.blueprintFormat === "pdf") printBlueprintPdf(packageData.blueprint_svg);
  else downloadText(packageData.blueprint_svg, `${base}-blueprint.svg`, "image/svg+xml");
  setStatus("Blueprint package exported.");
}

function downloadZipPackage(packageData, base) {
  const projectName = `${base}${PROJECT_EXTENSION}`;
  const files = [
    { name: "manifest.json", content: JSON.stringify(packageData.manifest, null, 2) },
    { name: projectName, content: JSON.stringify(packageData.project, null, 2) },
    { name: "blueprint.svg", content: packageData.blueprint_svg },
  ];
  if (packageData.assembly) {
    files.push(
      { name: "assembly/README.md", content: packageData.assembly.readme },
      { name: "assembly/recipes.json", content: JSON.stringify(packageData.assembly.recipes, null, 2) },
      { name: "assembly/physical-contract.json", content: JSON.stringify(packageData.assembly.physical_contract, null, 2) },
      { name: "assembly/svg-fallback/assembly/assembly-guide.svg", content: packageData.assembly.assembly_guide_svg },
      { name: "assembly/svg-fallback/parts/kit-parts-to-cut.svg", content: packageData.assembly.kit_parts_to_cut_svg },
    );
  }
  if (packageData.project.skeleton) files.push({ name: "skeleton-char_cfg.json", content: JSON.stringify(packageData.project.skeleton, null, 2) });
  downloadBlob(createZipBlob(files), `${base}-fabrication-kit.zip`);
}

function printBlueprintPdf(svg) {
  const win = window.open("", "_blank", "noopener,noreferrer");
  if (!win) { downloadText(svg, "blueprint.svg", "image/svg+xml"); return; }
  win.document.write(`<!doctype html><title>Automataii Blueprint</title><style>body{margin:0;padding:24px;font-family:Arial,sans-serif}svg{width:100%;height:auto}@media print{button{display:none}}</style><button onclick="print()">Print / Save PDF</button>${svg}`);
  win.document.close();
  win.focus();
}

function saveWorkspaceLayout() {
  localStorage.setItem(LAYOUT_KEY, JSON.stringify({
    tab: app.tab,
    toolbar: app.settings.toolbar,
    theme: app.settings.theme,
    showPartProperties: app.settings.showPartProperties,
  }));
  setStatus("Workspace layout saved.");
}

function restoreWorkspaceLayout() {
  try {
    const layout = JSON.parse(localStorage.getItem(LAYOUT_KEY) || "{}");
    if (layout.tab) app.tab = layout.tab;
    app.settings = {
      ...app.settings,
      toolbar: layout.toolbar ?? app.settings.toolbar,
      theme: layout.theme ?? app.settings.theme,
      showPartProperties: layout.showPartProperties ?? app.settings.showPartProperties,
    };
    saveSettings();
    setStatus("Workspace layout restored.");
    render();
  } catch (error) {
    setStatus(`Workspace layout restore failed: ${error.message}`);
  }
}

function resetWorkspaceLayout() {
  localStorage.removeItem(LAYOUT_KEY);
  app.tab = "character";
  app.settings.toolbar = true;
  app.settings.showPartProperties = false;
  saveSettings();
  setStatus("Workspace layout reset.");
  render();
}

function downloadSkeleton() {
  if (!app.project.skeleton) return;
  downloadJson(app.project.skeleton, `${safeName(app.project.metadata?.name || "skeleton")}-char_cfg.json`);
  setStatus("Skeleton downloaded.");
}

async function processImageSource(imageSrc, name) {
  if (app.settings.segmentationMode === "Off") {
    commit(createImageProject({ name, imagePath: imageSrc }), `Loaded ${name}; segmentation is off.`);
    return;
  }
  if (app.settings.segmentationMode !== "ONNX Runtime Web") {
    commit(createDemoProject({ name, imagePath: imageSrc }), `Loaded ${name}; local editable parts generated.`);
    return;
  }
  try {
    setBusy(true, "Running ONNX Runtime Web segmentation…");
    const boxes = await runOnnx(imageSrc);
    commit(createSegmentedProject({ name, imagePath: imageSrc, boxes, source: "onnx" }), `ONNX segmentation completed for ${name}.`);
  } catch (error) {
    setStatus(`ONNX segmentation failed: ${error.message}. Project unchanged; switch Segmentation Mode to Local heuristic or Off if you want fallback processing.`);
    render();
  } finally {
    setBusy(false);
  }
}

async function runOnnx(imageSrc) {
  if (!app.onnxModel) {
    const modelUrl = app.settings.onnxModelUrl.trim() ? normalizeOnnxModelUrl(app.settings.onnxModelUrl) : "";
    app.onnxModel = await loadOnnxSegmenter({
      modelBuffer: app.onnxModelBuffer,
      modelUrl: app.onnxModelBuffer ? "" : modelUrl,
      executionProvider: app.settings.onnxExecutionProvider,
    });
    app.onnxModelName ||= modelUrl || "ONNX model";
  }
  return app.onnxModel.segment(imageSrc);
}

async function processCurrentImageWithOnnx() {
  if (!app.project.image_path) { setStatus("Load an image before running ONNX segmentation."); return; }
  await processImageSource(app.project.image_path, app.project.metadata?.name || "ONNX Segmented Character");
}

async function loadOnnxModelFromUrl() {
  let url = "";
  try {
    url = normalizeOnnxModelUrl(app.settings.onnxModelUrl);
  } catch (error) {
    setStatus(`ONNX model URL rejected: ${error.message}`);
    return;
  }
  if (!url) { setStatus("Enter an ONNX Model URL in Preferences first."); return; }
  app.onnxModelBuffer = null;
  app.onnxModel = null;
  app.onnxModelName = url;
  app.settings.segmentationMode = "ONNX Runtime Web";
  saveSettings();
  setStatus(`ONNX model URL set: ${url}`);
  render();
}

function normalizeOnnxModelUrl(raw) {
  const text = String(raw || "").trim();
  if (!text) return "";
  const url = new URL(text, window.location.href);
  const localHttp = ["localhost", "127.0.0.1", "::1"].includes(url.hostname);
  const sameOrigin = url.origin === window.location.origin;
  if (url.protocol !== "https:" && !(url.protocol === "http:" && (sameOrigin || localHttp))) {
    throw new Error("ONNX model URL must be HTTPS, same-origin HTTP, localhost HTTP, or relative.");
  }
  return url.href;
}

function setBusy(value, message) {
  app.busy = value;
  if (message) setStatus(message);
  document.body.classList.toggle("busy", value);
}

function toggleDrawing() {
  if (!app.selectedPart) return;
  if (app.drawing) {
    app.drawing = false;
    if (app.draftPath.length >= 2) {
      commit(addOrUpdatePath(app.project, app.selectedPart, app.draftPath, { isClosed: app.pathType === "closed", smoothness: app.settings.smoothness }), `Saved path for ${app.selectedPart}.`);
    } else {
      app.draftPath = [];
      setStatus("Path needs at least two points.");
      render();
    }
  } else {
    app.drawing = true;
    app.draftPath = app.project.paths[app.selectedPart]?.points?.slice() || [];
    setStatus("Drawing mode: click points in the canvas.");
    render();
  }
}

function addRecommendedMechanism() {
  if (!app.selectedPart) return;
  const path = app.project.paths[app.selectedPart];
  const rec = recommendMechanism(path);
  const mechanism = createMechanism(app.selectedPart, rec.type);
  const project = addMechanism(app.project, mechanism);
  app.selectedMechanism = mechanism.id;
  commit(project, `${getMechanismEntry(rec.type)?.name || rec.type} added: ${rec.reason}`);
}

function toggleMechanism() {
  const mechanism = app.project.mechanisms[app.selectedMechanism];
  if (!mechanism) return;
  commit(updateMechanism(app.project, mechanism.id, { enabled: !mechanism.enabled }), "Mechanism layer toggled.");
}

function removeSelectedMechanism() {
  if (!app.selectedMechanism) return;
  const id = app.selectedMechanism;
  app.selectedMechanism = null;
  commit(deleteMechanism(app.project, id), "Mechanism deleted.");
}

function exportFoundryToDesign() {
  app.selectedPart ||= Object.keys(app.project.parts)[0] || null;
  if (!app.selectedPart) {
    commit(createDemoProject(), "Demo character assigned; choose a part before exporting foundry mechanism.");
    app.selectedPart = Object.keys(app.project.parts)[0];
  }
  const mechanism = createMechanism(app.selectedPart, app.foundryType, app.foundryParams);
  app.selectedMechanism = mechanism.id;
  commit(addMechanism(app.project, mechanism), `${getMechanismEntry(app.foundryType)?.name || app.foundryType} exported to Mechanism Design.`);
  app.tab = "design";
  render();
}

async function openCameraCapture() {
  if (!navigator.mediaDevices?.getUserMedia) {
    openInfo("Camera Capture", "This browser does not support camera capture. Use Load Image File instead.");
    return;
  }
  openDialog("Camera Capture", `<video class="camera-preview" autoplay playsinline></video><div class="button-row"><button class="primary" data-action="capture-frame" type="button">Capture Frame</button></div>`);
  try {
    app.cameraStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    const video = modalRoot.querySelector("video");
    video.srcObject = app.cameraStream;
    modalRoot.querySelector("[data-action='capture-frame']").addEventListener("click", () => captureCameraFrame(video));
  } catch (error) {
    closeModal();
    setStatus(`Camera unavailable: ${error.message}`);
  }
}

function captureCameraFrame(video) {
  const width = video.videoWidth || 640;
  const height = video.videoHeight || 480;
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  canvas.getContext("2d").drawImage(video, 0, 0, width, height);
  const imageSrc = canvas.toDataURL("image/png");
  closeModal();
  processImageSource(imageSrc, "Camera Capture");
}

function openOptions() {
  openDialog("Preferences", renderOptions());
}

function openInfo(title, body) {
  openDialog(title, `<p>${escapeHtml(body)}</p>`);
}

function openRecognitionEditor() {
  if (!Object.keys(app.project.parts || {}).length) {
    if (!app.project.image_path) { setStatus("Load an image before editing recognition boxes."); return; }
    commit(createDemoProject({ name: app.project.metadata?.name || "Manual Segmentation", imagePath: app.project.image_path }), "Editable recognition parts initialized.");
  }
  const partRows = Object.values(app.project.parts || {}).map((part) => {
    const [x = 0, y = 0, w = 30, h = 30] = part.roi || [0, 0, 30, 30];
    return `<div class="form-row"><strong>${escapeHtml(part.name)}</strong><span><input type="number" data-box-part="${escapeAttr(part.name)}" data-box-field="x" value="${escapeAttr(x)}" aria-label="${escapeAttr(part.name)} x" /><input type="number" data-box-part="${escapeAttr(part.name)}" data-box-field="y" value="${escapeAttr(y)}" aria-label="${escapeAttr(part.name)} y" /><input type="number" data-box-part="${escapeAttr(part.name)}" data-box-field="w" value="${escapeAttr(w)}" min="1" aria-label="${escapeAttr(part.name)} width" /><input type="number" data-box-part="${escapeAttr(part.name)}" data-box-field="h" value="${escapeAttr(h)}" min="1" aria-label="${escapeAttr(part.name)} height" /></span></div>`;
  }).join("");
  const jointRows = Object.values(app.project.skeleton?.joints || {}).map((joint) => `<label class="form-row">${escapeHtml(joint.name || joint.id)} <span><input type="number" value="${escapeAttr(joint.position[0])}" data-joint="${escapeAttr(joint.id)}" data-axis="0" /> <input type="number" value="${escapeAttr(joint.position[1])}" data-joint="${escapeAttr(joint.id)}" data-axis="1" /></span></label>`).join("");
  openDialog("Edit Parts / Skeleton / Boxes", `<p class="help">Adjust body-part rectangles and skeleton joints. This is the browser equivalent of the desktop manual segmentation editor.</p><fieldset class="group"><legend>Part Boxes: x · y · width · height</legend>${partRows}</fieldset><fieldset class="group"><legend>Skeleton Joints</legend>${jointRows || "<p class='empty'>No skeleton joints.</p>"}</fieldset><button class="primary" data-action="apply-recognition-edit" type="button">Apply Recognition Edit</button>`);
  modalRoot.querySelector("[data-action='apply-recognition-edit']").addEventListener("click", applyRecognitionEdit);
}

function applyRecognitionEdit() {
  const project = clone(app.project);
  const boxes = {};
  modalRoot.querySelectorAll("[data-box-part]").forEach((input) => {
    const box = (boxes[input.dataset.boxPart] ||= {});
    box[input.dataset.boxField] = Number(input.value);
  });
  for (const [name, box] of Object.entries(boxes)) {
    const part = project.parts[name];
    if (!part) continue;
    const w = Math.max(1, Number(box.w) || 1);
    const h = Math.max(1, Number(box.h) || 1);
    part.roi = [Number(box.x) || 0, Number(box.y) || 0, w, h];
    part.local_pivot_offset = [w / 2, h / 2];
  }
  modalRoot.querySelectorAll("[data-joint]").forEach((input) => {
    const joint = project.skeleton?.joints?.[input.dataset.joint];
    if (joint) joint.position[Number(input.dataset.axis)] = Number(input.value);
  });
  closeModal();
  commit(project, "Manual recognition boxes and skeleton updated.");
}

function openSkeletonEditor() {
  const joints = Object.values(app.project.skeleton?.joints || {});
  const rows = joints.map((joint) => `<label class="form-row">${escapeHtml(joint.name || joint.id)} <span><input type="number" value="${joint.position[0]}" data-joint="${escapeAttr(joint.id)}" data-axis="0" /> <input type="number" value="${joint.position[1]}" data-joint="${escapeAttr(joint.id)}" data-axis="1" /></span></label>`).join("");
  openDialog("Edit Skeleton Joints", `<div class="controls">${rows}</div><button class="primary" data-action="apply-skeleton-edit" type="button">Apply Skeleton</button>`);
  modalRoot.querySelector("[data-action='apply-skeleton-edit']").addEventListener("click", () => {
    const project = clone(app.project);
    modalRoot.querySelectorAll("[data-joint]").forEach((input) => {
      const joint = project.skeleton.joints[input.dataset.joint];
      joint.position[Number(input.dataset.axis)] = Number(input.value);
    });
    closeModal();
    commit(project, "Skeleton joints updated.");
  });
}

function openDialog(title, html) {
  modalRoot.hidden = false;
  modalRoot.innerHTML = `<section class="dialog" role="dialog" aria-modal="true" aria-labelledby="dialog-title" tabindex="-1"><header><h2 id="dialog-title">${escapeHtml(title)}</h2><button class="tool-button" data-close-dialog type="button">Close</button></header>${html}</section>`;
  modalRoot.querySelector("[data-close-dialog]").addEventListener("click", closeModal);
  modalRoot.querySelector(".dialog").focus();
}

function closeModal() {
  app.cameraStream?.getTracks().forEach((track) => track.stop());
  app.cameraStream = null;
  modalRoot.hidden = true;
  modalRoot.innerHTML = "";
}

function downloadJson(value, filename) {
  downloadText(JSON.stringify(value, null, 2), filename, "application/json");
}

function downloadText(text, filename, type) {
  downloadBlob(new Blob([text], { type }), filename);
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function tick(now) {
  if (app.animation.playing) {
    const duration = Math.max(0.1, Number(app.settings.animationDuration) || 2) * 1000;
    app.animation.progress = ((now - app.animation.start) % duration) / duration;
    drawAllCanvases();
  }
  requestAnimationFrame(tick);
}

function animationProgress() {
  const t = Math.max(0, Math.min(1, app.animation.progress));
  if (app.settings.timing === "Ease-In") return t * t;
  if (app.settings.timing === "Ease-Out") return 1 - (1 - t) * (1 - t);
  if (app.settings.timing === "Ease-In-Out") return t < 0.5 ? 2 * t * t : 1 - ((-2 * t + 2) ** 2) / 2;
  return t;
}

function drawAllCanvases() {
  drawCharacterCanvas();
  drawEditorCanvas();
  drawDesignCanvas();
  drawFoundryCanvas();
}
function drawCharacterCanvas() {
  const canvas = $("character-canvas");
  if (!canvas) return;
  const ctx = setupCanvas(canvas);
  drawProject(ctx, canvas, { showPaths: true, showMechanisms: false });
}

function drawEditorCanvas() {
  const canvas = $("editor-canvas");
  if (!canvas) return;
  const ctx = setupCanvas(canvas);
  drawProject(ctx, canvas, { showPaths: true, showMechanisms: false });
  canvas.onclick = (event) => {
    if (!app.drawing || !app.selectedPart) return;
    const rect = canvas.getBoundingClientRect();
    const point = [(event.clientX - rect.left) * (canvas.width / rect.width), (event.clientY - rect.top) * (canvas.height / rect.height)];
    const world = screenToWorld(point, canvas);
    app.draftPath.push(world);
    drawEditorCanvas();
  };
  if (app.draftPath.length) drawPolyline(ctx, smoothPathPoints(app.draftPath, app.settings.smoothness, app.pathType === "closed"), canvas, app.pathType === "closed", "#ff595e", 3, true);
}

function drawDesignCanvas() {
  const canvas = $("design-canvas");
  if (!canvas) return;
  const ctx = setupCanvas(canvas);
  drawProject(ctx, canvas, { showPaths: true, showMechanisms: true });
}

function drawFoundryCanvas() {
  const canvas = $("foundry-canvas");
  if (!canvas) return;
  const ctx = setupCanvas(canvas);
  drawGrid(ctx, canvas);
  const state = computeMechanismState(app.foundryType, app.foundryParams, animationProgress() * 360);
  drawMechanismState(ctx, canvas, state, { x: canvas.width / 2, y: canvas.height / 2 }, 2.2);
  drawSafety(ctx, state.safety_status);
}

function setupCanvas(canvas) {
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = getComputedStyle(document.body).getPropertyValue("--canvas") || "#f8fafc";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  drawGrid(ctx, canvas);
  return ctx;
}

function drawGrid(ctx, canvas) {
  if (!app.settings.gridEnabled) return;
  ctx.save();
  ctx.strokeStyle = document.body.classList.contains("dark") ? "rgba(255,255,255,.06)" : "rgba(25,130,196,.08)";
  ctx.lineWidth = 1;
  const step = Math.max(8, Number(app.settings.gridCellCm || 2) * 15);
  for (let x = 0; x <= canvas.width; x += step) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height); ctx.stroke(); }
  for (let y = 0; y <= canvas.height; y += step) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(canvas.width, y); ctx.stroke(); }
  ctx.restore();
}

function drawProject(ctx, canvas, options) {
  const bounds = projectBounds();
  const transform = makeTransform(bounds, canvas);
  drawImageBackground(ctx, transform);
  const parts = Object.values(app.project.parts || {}).sort((a, b) => (a.z_index || 0) - (b.z_index || 0));
  for (const part of parts) drawPart(ctx, part, transform, part.name === app.selectedPart);
  drawSkeleton(ctx, transform);
  if (options.showPaths) {
    for (const path of Object.values(app.project.paths || {})) drawPolyline(ctx, smoothPathPoints(path.points, path.smoothness, path.is_closed), canvas, path.is_closed, path.part_name === app.selectedPart ? "#ff595e" : "#6a4c93", 3, false, transform);
    const selectedPath = app.selectedPart ? app.project.paths[app.selectedPart] : null;
    const p = selectedPath ? pointAtProgress(selectedPath, animationProgress()) : null;
    if (p) drawPoint(ctx, transformPoint([p.x, p.y], transform), 8, "#ffca3a");
  }
  if (options.showMechanisms) {
    for (const mechanism of Object.values(app.project.mechanisms || {})) {
      if (!mechanism.enabled) continue;
      const part = app.project.parts[mechanism.part_name];
      const anchor = partAnchor(part);
      const screen = transformPoint(anchor, transform);
      try {
        const state = computeMechanismState(mechanism.type, mechanism.params, animationProgress() * 360 * Number(mechanism.params.speed || 1));
        drawMechanismState(ctx, canvas, state, { x: screen[0], y: screen[1] }, 1.4, mechanism.id === app.selectedMechanism);
      } catch (error) {
        drawNotice(ctx, error.message);
      }
    }
  }
  const validation = validateProject(app.project);
  if (!validation.ok) drawNotice(ctx, validation.errors[0]);
}

function drawImageBackground(ctx, transform) {
  const src = app.project.image_path;
  if (!src || !String(src).startsWith("data:image")) return;
  let img = app.imageCache.get(src);
  if (!img) {
    img = new Image();
    img.onload = drawAllCanvases;
    img.src = src;
    app.imageCache.set(src, img);
  }
  if (!img.complete) return;
  ctx.save();
  ctx.globalAlpha = 0.18;
  const topLeft = transformPoint([0, 0], transform);
  const bottomRight = transformPoint([400, 420], transform);
  ctx.drawImage(img, topLeft[0], topLeft[1], bottomRight[0] - topLeft[0], bottomRight[1] - topLeft[1]);
  ctx.restore();
}

function drawPart(ctx, part, transform, selected) {
  const [x = 0, y = 0, w = 30, h = 30] = part.roi || [0, 0, 30, 30];
  const p = transformPoint([x, y], transform);
  const size = [w * transform.scale, h * transform.scale];
  ctx.save();
  ctx.globalAlpha = Number(part.opacity ?? 1);
  ctx.fillStyle = part.fill_color || "rgba(128,128,128,.6)";
  ctx.strokeStyle = selected ? "#ff595e" : "#33485a";
  ctx.lineWidth = selected ? 4 : 1.5;
  roundRect(ctx, p[0], p[1], size[0], size[1], 10);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = selected ? "#ff595e" : "#27313b";
  ctx.font = "13px Arial";
  ctx.fillText(part.name.replaceAll("_", " "), p[0] + 6, p[1] + 18);
  ctx.restore();
}

function drawSkeleton(ctx, transform) {
  const skeleton = app.project.skeleton;
  if (!skeleton) return;
  ctx.save();
  ctx.strokeStyle = "rgba(25,130,196,.82)";
  ctx.lineWidth = 3;
  for (const bone of skeleton.bones || []) {
    const a = skeleton.joints[bone.from];
    const b = skeleton.joints[bone.to];
    if (!a || !b) continue;
    const p1 = transformPoint(a.position, transform);
    const p2 = transformPoint(b.position, transform);
    ctx.beginPath(); ctx.moveTo(p1[0], p1[1]); ctx.lineTo(p2[0], p2[1]); ctx.stroke();
  }
  for (const joint of Object.values(skeleton.joints || {})) drawPoint(ctx, transformPoint(joint.position, transform), 5, joint.is_locked ? "#6a4c93" : "#1982c4");
  ctx.restore();
}

function drawPolyline(ctx, points, canvas, closed, color, width, withPoints, transform = null) {
  if (!points || points.length < 1) return;
  const mapped = points.map((point) => transform ? transformPoint(point, transform) : transformPoint(point, makeTransform(projectBounds(), canvas)));
  ctx.save();
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.beginPath();
  ctx.moveTo(mapped[0][0], mapped[0][1]);
  for (const p of mapped.slice(1)) ctx.lineTo(p[0], p[1]);
  if (closed && mapped.length > 2) ctx.closePath();
  ctx.stroke();
  if (withPoints) mapped.forEach((p) => drawPoint(ctx, p, 5, color));
  ctx.restore();
}

function drawMechanismState(ctx, canvas, state, origin, scale = 1, highlighted = false) {
  const positions = state.positions || {};
  const map = (point) => [origin.x + point[0] * scale, origin.y - point[1] * scale];
  const line = (a, b, color = highlighted ? "#ff595e" : "#27313b") => {
    if (!positions[a] || !positions[b]) return;
    const p1 = map(positions[a]); const p2 = map(positions[b]);
    ctx.save(); ctx.strokeStyle = color; ctx.lineWidth = highlighted ? 4 : 3; ctx.beginPath(); ctx.moveTo(p1[0], p1[1]); ctx.lineTo(p2[0], p2[1]); ctx.stroke(); ctx.restore();
  };
  ctx.save();
  if (state.metadata?.type === "cam_follower") {
    const profile = state.metadata.cam_profile || [];
    ctx.beginPath();
    profile.forEach((point, i) => { const p = map(point); if (i) ctx.lineTo(p[0], p[1]); else ctx.moveTo(p[0], p[1]); });
    ctx.closePath(); ctx.fillStyle = "rgba(255,202,58,.5)"; ctx.strokeStyle = "#8a6b00"; ctx.fill(); ctx.stroke();
    line("contact_point", "follower_base", "#1982c4");
  } else if (state.metadata?.type?.includes("gear") || state.metadata?.type === "planetary_gear") {
    for (const [name, point] of Object.entries(positions)) {
      if (!name.endsWith("center")) continue;
      const p = map(point);
      const radius = name.startsWith("sun") ? state.metadata.sun_radius : name.startsWith("planet") ? state.metadata.planet_radius : state.metadata[name.replace("_center", "").replace("gear", "r")] || 22;
      drawGear(ctx, p, Math.max(12, radius * scale), name.includes("2") || name.includes("planet") ? "#8ac926" : "#1982c4");
    }
    line("gear1_center", "gear1_indicator_end", "#ff595e");
    line("gear2_center", "gear2_indicator_end", "#6a4c93");
    line("gear2_center", "linkage_pin", "#ff595e");
    line("linkage_pin", "output_tip", "#ffca3a");
  } else if (Array.isArray(state.metadata?.linkage_nodes)) {
    const nodes = state.metadata.linkage_nodes;
    for (let i = 0; i < nodes.length - 1; i += 1) line(nodes[i], nodes[i + 1]);
    if (state.metadata.type !== "slider_crank") line(nodes[nodes.length - 1], nodes[0]);
  } else {
    line("O1", "A"); line("A", "B"); line("B", "O4"); line("O4", "O1");
  }
  for (const point of Object.values(positions)) drawPoint(ctx, map(point), 5, highlighted ? "#ff595e" : "#27313b");
  drawSafety(ctx, state.safety_status);
  ctx.restore();
}

function drawSafety(ctx, safety) {
  if (!safety) return;
  const color = safety.level === "danger" ? "#ff595e" : safety.level === "warning" ? "#ffca3a" : "#8ac926";
  ctx.save();
  ctx.fillStyle = "rgba(255,255,255,.92)";
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  roundRect(ctx, 18, 18, 360, 42, 10);
  ctx.fill(); ctx.stroke();
  ctx.fillStyle = "#27313b";
  ctx.font = "15px Arial";
  ctx.fillText(`${safety.level.toUpperCase()}: ${safety.message}`, 32, 44);
  ctx.restore();
}

function drawNotice(ctx, message) {
  ctx.save();
  ctx.fillStyle = "rgba(255,89,94,.92)";
  ctx.fillRect(18, 70, 420, 34);
  ctx.fillStyle = "white";
  ctx.font = "14px Arial";
  ctx.fillText(message, 28, 92);
  ctx.restore();
}

function drawGear(ctx, p, radius, color) {
  ctx.save();
  ctx.translate(p[0], p[1]);
  ctx.fillStyle = color;
  ctx.strokeStyle = "#27313b";
  ctx.lineWidth = 2;
  ctx.beginPath();
  for (let i = 0; i < 28; i += 1) {
    const a = (i / 28) * Math.PI * 2;
    const r = radius * (i % 2 ? 0.88 : 1);
    const x = r * Math.cos(a), y = r * Math.sin(a);
    if (i) ctx.lineTo(x, y); else ctx.moveTo(x, y);
  }
  ctx.closePath(); ctx.globalAlpha = 0.62; ctx.fill(); ctx.globalAlpha = 1; ctx.stroke();
  ctx.beginPath(); ctx.arc(0, 0, radius * 0.18, 0, Math.PI * 2); ctx.fillStyle = "#fff"; ctx.fill(); ctx.stroke();
  ctx.restore();
}

function projectBounds() {
  const boxes = Object.values(app.project.parts || {}).map((part) => part.roi || [0, 0, 30, 30]);
  const points = [];
  for (const [x, y, w, h] of boxes) points.push([x, y], [x + w, y + h]);
  for (const path of Object.values(app.project.paths || {})) points.push(...path.points);
  if (!points.length) return { minX: 0, minY: 0, maxX: 400, maxY: 420 };
  return { minX: Math.min(...points.map((p) => p[0])), minY: Math.min(...points.map((p) => p[1])), maxX: Math.max(...points.map((p) => p[0])), maxY: Math.max(...points.map((p) => p[1])) };
}

function makeTransform(bounds, canvas) {
  const pad = 70;
  const w = Math.max(1, bounds.maxX - bounds.minX);
  const h = Math.max(1, bounds.maxY - bounds.minY);
  const scale = Math.min((canvas.width - pad * 2) / w, (canvas.height - pad * 2) / h);
  return { scale, dx: pad - bounds.minX * scale + (canvas.width - pad * 2 - w * scale) / 2, dy: pad - bounds.minY * scale + (canvas.height - pad * 2 - h * scale) / 2 };
}

function transformPoint(point, t) { return [point[0] * t.scale + t.dx, point[1] * t.scale + t.dy]; }
function screenToWorld(point, canvas) { const t = makeTransform(projectBounds(), canvas); return [(point[0] - t.dx) / t.scale, (point[1] - t.dy) / t.scale]; }
function partAnchor(part) { const [x = 0, y = 0, w = 30, h = 30] = part?.roi || [0, 0, 30, 30]; return [x + w / 2, y + h / 2]; }
function drawPoint(ctx, p, r, color) { ctx.save(); ctx.fillStyle = color; ctx.beginPath(); ctx.arc(p[0], p[1], r, 0, Math.PI * 2); ctx.fill(); ctx.restore(); }
function roundRect(ctx, x, y, w, h, r) { ctx.beginPath(); if (typeof ctx.roundRect === "function") ctx.roundRect(x, y, w, h, r); else fallbackRoundRect(ctx, x, y, w, h, r); }
function fallbackRoundRect(ctx, x, y, w, h, r) { ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); }
function safeName(value) { return String(value).trim().toLowerCase().replace(/[^a-z0-9_-]+/g, "-").replace(/^-|-$/g, "") || "automataii"; }
function escapeHtml(value) { return String(value).replace(/[<>&'"]/g, (ch) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", "'": "&#39;", '"': "&quot;" })[ch]); }
function escapeAttr(value) { return escapeHtml(value).replace(/`/g, "&#96;"); }

init();
