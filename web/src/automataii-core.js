const PROJECT_VERSION = "2.0";
const PROJECT_EXTENSION = ".automataii";

const MECHANISM_ALIASES = {
  fourbar: "four_bar",
  four_bar: "four_bar",
  four_bar_linkage: "four_bar",
  "4_bar_linkage": "four_bar",
  fivebar: "five_bar",
  five_bar: "five_bar",
  five_bar_linkage: "five_bar",
  "5_bar_linkage": "five_bar",
  sixbar: "six_bar",
  six_bar: "six_bar",
  six_bar_linkage: "six_bar",
  "6_bar_linkage": "six_bar",
  cam: "cam_follower",
  cam_follower: "cam_follower",
  gear: "gear_train",
  gear_train: "gear_train",
  gear_linkage: "gear_linkage",
  "gear+linkage": "gear_linkage",
  planetary: "planetary_gear",
  planetary_gear: "planetary_gear",
  slider_crank: "slider_crank",
  "slider-crank": "slider_crank",
  slidercrank: "slider_crank",
};

const rgba = (r, g, b, a = 0.8) => `rgba(${r},${g},${b},${a})`;

export const MECHANISM_CATALOG = [
  {
    key: "four_bar",
    name: "Four-Bar Linkage",
    category: "Linkage Mechanisms",
    icon: "🔗",
    description: "Classic four-bar mechanism for converting rotary motion into oscillation.",
    complexity: "beginner",
    tags: ["basic", "rotary", "oscillating", "fabrication-ready"],
    motions: ["Circular", "Oscillatory"],
    goal: "Transforms crank rotation into controlled oscillatory output and coupler paths.",
    parts: ["Ground link", "Input crank", "Coupler", "Output rocker"],
    advantages: ["Versatile", "Reliable", "Simple to fabricate"],
    cautions: ["Watch dead points", "Verify Grashof condition"],
    parameters: {
      ground_link: { name: "Ground Link", type: "float", default: 100, min: 50, max: 220, unit: "mm" },
      input_link: { name: "Input Link", type: "float", default: 45, min: 15, max: 120, unit: "mm" },
      coupler_link: { name: "Coupler", type: "float", default: 90, min: 25, max: 180, unit: "mm" },
      output_link: { name: "Output Link", type: "float", default: 75, min: 25, max: 180, unit: "mm" },
      speed: { name: "Animation Speed", type: "float", default: 1, min: 0.1, max: 5, unit: "x" },
    },
  },
  {
    key: "five_bar",
    name: "Five-Bar Linkage",
    category: "Linkage Mechanisms",
    icon: "🔗",
    description: "Dual-crank linkage with a floating coupler point for expressive cyclic motion.",
    complexity: "intermediate",
    tags: ["linkage", "dual-crank", "coupler"],
    motions: ["Circular", "Oscillatory"],
    goal: "Creates richer coupler trajectories from two grounded pivots.",
    parts: ["Two ground pivots", "Two cranks", "Floating coupler"],
    advantages: ["Flexible output point", "Good for puppet limbs"],
    cautions: ["Check closure between crank ends"],
    parameters: {
      ground_link: { name: "Ground Spacing", type: "float", default: 160, min: 60, max: 260, unit: "mm" },
      input_link: { name: "Left Crank", type: "float", default: 70, min: 20, max: 140, unit: "mm" },
      coupler_link: { name: "Floating Link", type: "float", default: 120, min: 30, max: 220, unit: "mm" },
      output_link: { name: "Right Crank", type: "float", default: 70, min: 20, max: 140, unit: "mm" },
      speed: { name: "Animation Speed", type: "float", default: 0.9, min: 0.1, max: 4, unit: "x" },
    },
  },
  {
    key: "six_bar",
    name: "Six-Bar Linkage",
    category: "Linkage Mechanisms",
    icon: "🔗",
    description: "Two-loop linkage approximation for complex limb-like outputs.",
    complexity: "advanced",
    tags: ["linkage", "complex", "multi-loop"],
    motions: ["Circular", "Oscillatory"],
    goal: "Explores multi-link motion with extra coupler joints.",
    parts: ["Ground", "Input crank", "Couplers", "Output rocker"],
    advantages: ["More expressive than four-bar"],
    cautions: ["More closure and clearance checks needed"],
    parameters: {
      ground_link: { name: "Ground Link", type: "float", default: 150, min: 70, max: 260, unit: "mm" },
      input_link: { name: "Input Link", type: "float", default: 45, min: 20, max: 120, unit: "mm" },
      coupler_link: { name: "Coupler", type: "float", default: 90, min: 30, max: 180, unit: "mm" },
      output_link: { name: "Output Link", type: "float", default: 80, min: 30, max: 180, unit: "mm" },
      pivot_height: { name: "Ternary Pivot Height", type: "float", default: 80, min: 20, max: 180, unit: "mm" },
      speed: { name: "Animation Speed", type: "float", default: 0.8, min: 0.1, max: 4, unit: "x" },
    },
  },
  {
    key: "slider_crank",
    name: "Slider-Crank",
    category: "Linkage Mechanisms",
    icon: "↔️",
    description: "Crank and connecting rod convert rotation to linear slider travel.",
    complexity: "beginner",
    tags: ["linkage", "linear", "reciprocating"],
    motions: ["Circular", "Linear"],
    goal: "Turns rotary motion into straight reciprocating motion.",
    parts: ["Crank", "Connecting rod", "Slider guide"],
    advantages: ["Simple linear output", "Easy to fabricate"],
    cautions: ["Guide must stay aligned"],
    parameters: {
      crank_radius: { name: "Crank Radius", type: "float", default: 35, min: 10, max: 90, unit: "mm" },
      rod_length: { name: "Rod Length", type: "float", default: 110, min: 50, max: 220, unit: "mm" },
      guide_offset: { name: "Guide Offset", type: "float", default: 0, min: -60, max: 60, unit: "mm" },
      speed: { name: "Animation Speed", type: "float", default: 1, min: 0.1, max: 4, unit: "x" },
    },
  },
  {
    key: "cam_follower",
    name: "Cam-Follower",
    category: "Cam Mechanisms",
    icon: "⚙️",
    description: "Rotating cam profile drives a follower with repeatable timing.",
    complexity: "beginner",
    tags: ["basic", "timing", "linear", "cyclic"],
    motions: ["Circular", "Linear", "Oscillatory"],
    goal: "Generates precise follower displacement and timed events.",
    parts: ["Cam", "Follower", "Pushrod", "Return spring", "Base"],
    advantages: ["Precise", "Compact", "Repeatable"],
    cautions: ["Avoid sharp profiles", "Maintain follower contact"],
    parameters: {
      cam_radius: { name: "Base Cam Radius", type: "float", default: 32, min: 12, max: 80, unit: "mm" },
      lobe_height: { name: "Lobe Height", type: "float", default: 18, min: 0, max: 50, unit: "mm" },
      num_lobes: { name: "Number of Lobes", type: "int", default: 1, min: 1, max: 6, unit: "" },
      follower_length: { name: "Follower Length", type: "float", default: 90, min: 30, max: 180, unit: "mm" },
      speed: { name: "Rotation Speed", type: "float", default: 1.2, min: 0.1, max: 5, unit: "x" },
    },
  },
  {
    key: "gear_train",
    name: "Gear Train",
    category: "Gear Systems",
    icon: "⚙️",
    description: "Two meshing gears for speed and torque conversion.",
    complexity: "beginner",
    tags: ["transmission", "speed", "torque"],
    motions: ["Circular"],
    goal: "Transfers rotary motion with a predictable ratio.",
    parts: ["Driver gear", "Driven gear", "Axles", "Base"],
    advantages: ["Predictable ratio", "Fabrication-friendly"],
    cautions: ["Teeth must mesh with clearance"],
    parameters: {
      gear1_teeth: { name: "Driver Teeth", type: "int", default: 16, min: 8, max: 48, unit: "teeth" },
      gear2_teeth: { name: "Driven Teeth", type: "int", default: 28, min: 10, max: 64, unit: "teeth" },
      module: { name: "Module", type: "float", default: 2, min: 1, max: 5, unit: "mm" },
      gear_clearance: { name: "Mesh Clearance", type: "float", default: 1, min: 0, max: 8, unit: "mm" },
      speed: { name: "Input Speed", type: "float", default: 1, min: 0.1, max: 4, unit: "x" },
    },
  },
  {
    key: "gear_linkage",
    name: "Gear + Linkage",
    category: "Gear Systems",
    icon: "⚙️",
    description: "Gear train with an eccentric linkage pin for crank-like output.",
    complexity: "intermediate",
    tags: ["gear", "linkage", "eccentric"],
    motions: ["Circular", "Oscillatory"],
    goal: "Combines ratio control with a mechanical output point.",
    parts: ["Gear pair", "Linkage pin", "Output arm"],
    advantages: ["Compact", "Expressive output path"],
    cautions: ["Pin radius must fit inside gear"],
    parameters: {
      gear1_teeth: { name: "Driver Teeth", type: "int", default: 16, min: 8, max: 48, unit: "teeth" },
      gear2_teeth: { name: "Driven Teeth", type: "int", default: 28, min: 10, max: 64, unit: "teeth" },
      module: { name: "Module", type: "float", default: 2, min: 1, max: 5, unit: "mm" },
      linkage_pin_radius: { name: "Pin Radius", type: "float", default: 18, min: 4, max: 60, unit: "mm" },
      linkage_arm_length: { name: "Output Arm", type: "float", default: 70, min: 20, max: 160, unit: "mm" },
      speed: { name: "Input Speed", type: "float", default: 1, min: 0.1, max: 4, unit: "x" },
    },
  },
  {
    key: "planetary_gear",
    name: "Planetary Gear System",
    category: "Gear Systems",
    icon: "🪐",
    description: "Sun, planet, and ring gears arranged for compact ratios.",
    complexity: "advanced",
    tags: ["advanced", "compact", "high-ratio"],
    motions: ["Circular"],
    goal: "Shows compact differential-like rotary transmission.",
    parts: ["Sun gear", "Planet gears", "Ring gear", "Carrier"],
    advantages: ["Compact", "High ratio potential"],
    cautions: ["Fabrication tolerance sensitive"],
    parameters: {
      sun_teeth: { name: "Sun Teeth", type: "int", default: 18, min: 8, max: 40, unit: "teeth" },
      planet_teeth: { name: "Planet Teeth", type: "int", default: 12, min: 8, max: 32, unit: "teeth" },
      planet_count: { name: "Planet Count", type: "int", default: 3, min: 2, max: 5, unit: "" },
      module: { name: "Module", type: "float", default: 2, min: 1, max: 5, unit: "mm" },
      speed: { name: "Carrier Speed", type: "float", default: 0.8, min: 0.1, max: 3, unit: "x" },
    },
  },
];

const DEMO_JOINTS = [
  ["root", "Root", 200, 200, null],
  ["spine_mid", "Spine Mid", 200, 140, "root"],
  ["spine_top", "Spine Top", 200, 90, "spine_mid"],
  ["head", "Head", 200, 50, "spine_top"],
  ["shoulder_left", "Shoulder Left", 145, 95, "spine_top"],
  ["elbow_left", "Elbow Left", 110, 150, "shoulder_left"],
  ["wrist_left", "Wrist Left", 90, 210, "elbow_left"],
  ["shoulder_right", "Shoulder Right", 255, 95, "spine_top"],
  ["elbow_right", "Elbow Right", 290, 150, "shoulder_right"],
  ["wrist_right", "Wrist Right", 310, 210, "elbow_right"],
  ["hip_left", "Hip Left", 175, 205, "root"],
  ["knee_left", "Knee Left", 165, 290, "hip_left"],
  ["ankle_left", "Ankle Left", 160, 375, "knee_left"],
  ["hip_right", "Hip Right", 225, 205, "root"],
  ["knee_right", "Knee Right", 235, 290, "hip_right"],
  ["ankle_right", "Ankle Right", 240, 375, "knee_right"],
];

const DEMO_PARTS = {
  head: [180, 20, 40, 60, 10, rgba(200, 180, 160), true, "head"],
  torso: [170, 80, 60, 120, 5, rgba(100, 120, 150), true, "spine_mid"],
  upper_arm_left: [120, 90, 50, 60, 6, rgba(180, 160, 140), false, "shoulder_left"],
  lower_arm_left: [80, 150, 50, 70, 7, rgba(180, 160, 140), false, "elbow_left"],
  upper_arm_right: [230, 90, 50, 60, 6, rgba(180, 160, 140), false, "shoulder_right"],
  lower_arm_right: [270, 150, 50, 70, 7, rgba(180, 160, 140), false, "elbow_right"],
  upper_leg_left: [150, 200, 45, 90, 4, rgba(80, 100, 130), false, "hip_left"],
  lower_leg_left: [145, 290, 45, 90, 3, rgba(80, 100, 130), false, "knee_left"],
  upper_leg_right: [205, 200, 45, 90, 4, rgba(80, 100, 130), false, "hip_right"],
  lower_leg_right: [210, 290, 45, 90, 3, rgba(80, 100, 130), false, "knee_right"],
};

export function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

export function uid(prefix = "id") {
  const random = Math.random().toString(36).slice(2, 8);
  return `${prefix}_${Date.now().toString(36)}_${random}`;
}

export function nowIso() {
  return new Date().toISOString();
}

export function canonicalMechanismType(type) {
  const key = String(type || "").trim().toLowerCase();
  return MECHANISM_ALIASES[key] || key;
}

export function getMechanismEntry(type) {
  const canonical = canonicalMechanismType(type);
  return MECHANISM_CATALOG.find((entry) => entry.key === canonical) || null;
}

export function defaultParams(type) {
  const entry = getMechanismEntry(type);
  if (!entry) throw new Error(`Unsupported mechanism type: ${type}`);
  return Object.fromEntries(
    Object.entries(entry.parameters).map(([key, spec]) => [key, Number(spec.default)]),
  );
}

export function createEmptyProject(name = "Untitled") {
  const created = nowIso();
  return {
    metadata: { version: PROJECT_VERSION, name, created_at: created, modified_at: created },
    image_path: null,
    parts: {},
    skeleton: null,
    paths: {},
    mechanisms: {},
  };
}

export function createImageProject({ name = "Image Project", imagePath = null } = {}) {
  const project = createEmptyProject(name);
  project.image_path = imagePath;
  return touch(project);
}

export function createDemoProject({ name = "StickFigure Demo", imagePath = null } = {}) {
  const project = createEmptyProject(name);
  project.image_path = imagePath;
  project.parts = Object.fromEntries(
    Object.entries(DEMO_PARTS).map(([partName, [x, y, w, h, z, color, fixed, joint]]) => [
      partName,
      {
        name: partName,
        texture_path: "",
        mask_path: "",
        anchor_joint: joint,
        transform: { x: 0, y: 0, rotation: 0, scale: 1 },
        z_index: z,
        roi: [x, y, w, h],
        fill_color: color,
        fixed,
        opacity: 1,
        group: partName.includes("arm") ? "arms" : partName.includes("leg") ? "legs" : "body",
        original_svg_path: null,
        enhanced_svg_path: null,
        effective_bbox_offset_x: 0,
        effective_bbox_offset_y: 0,
        show_anchor: false,
        local_pivot_offset: [w / 2, h / 2],
      },
    ]),
  );
  project.skeleton = makeSkeleton(DEMO_JOINTS);
  return touch(project);
}

export function createSegmentedProject({ name = "Segmented Character", imagePath = null, boxes = {}, source = "onnx" } = {}) {
  const project = createImageProject({ name, imagePath });
  const entries = Object.entries(boxes).filter(([, box]) => Array.isArray(box) && box.length >= 4);
  project.parts = Object.fromEntries(entries.map(([partName, box], index) => {
    const [x, y, w, h] = box.map((value) => Number(value) || 0);
    return [partName, makePart(partName, [x, y, Math.max(1, w), Math.max(1, h)], index, source)];
  }));
  project.skeleton = entries.length ? makeSkeletonFromParts(project.parts) : null;
  return touch(project);
}

function makePart(partName, roi, index, source) {
  const [_x, _y, w, h] = roi;
  return {
    name: partName,
    texture_path: "",
    mask_path: "",
    anchor_joint: `${partName}_joint`,
    transform: { x: 0, y: 0, rotation: 0, scale: 1 },
    z_index: index,
    roi,
    fill_color: rgba(80 + (index * 37) % 150, 120 + (index * 29) % 100, 160 + (index * 23) % 80),
    fixed: partName === "torso",
    opacity: 1,
    group: partName.includes("arm") ? "arms" : partName.includes("leg") ? "legs" : "body",
    original_svg_path: null,
    enhanced_svg_path: null,
    effective_bbox_offset_x: 0,
    effective_bbox_offset_y: 0,
    show_anchor: false,
    local_pivot_offset: [w / 2, h / 2],
    segmentation_source: source,
  };
}

function makeSkeletonFromParts(parts) {
  const rootName = parts.torso ? "torso" : Object.keys(parts)[0];
  const rootJoint = `${rootName}_joint`;
  const rows = Object.values(parts).map((part, index) => {
    const [x, y, w, h] = part.roi;
    const parent = part.name === rootName || index === 0 ? null : rootJoint;
    return [`${part.name}_joint`, part.name.replaceAll("_", " "), x + w / 2, y + h / 2, parent];
  });
  return makeSkeleton(rows);
}

function makeSkeleton(rows) {
  const joints = Object.fromEntries(
    rows.map(([id, name, x, y, parent]) => [
      id,
      { id, name, position: [x, y], parent, parent_id: parent, is_locked: false, bend_direction: 1 },
    ]),
  );
  const bones = rows.filter((row) => row[4]).map(([id, _name, _x, _y, parent]) => ({ from: parent, to: id }));
  const hierarchy = {};
  const root_joint_ids = [];
  for (const joint of Object.values(joints)) {
    if (joint.parent) (hierarchy[joint.parent] ||= []).push(joint.id);
    else root_joint_ids.push(joint.id);
  }
  const joint_map = Object.fromEntries(Object.values(joints).map((joint) => [joint.name || joint.id, joint.id]));
  return { root_joint: root_joint_ids[0] || "root", root_joint_ids, joint_map, hierarchy, joints, bones };
}

export function touch(project) {
  const next = clone(project);
  next.metadata ||= {};
  next.metadata.version = PROJECT_VERSION;
  next.metadata.modified_at = nowIso();
  if (!next.metadata.created_at) next.metadata.created_at = next.metadata.modified_at;
  if (!next.metadata.name) next.metadata.name = "Untitled";
  next.parts ||= {};
  next.paths ||= {};
  next.mechanisms ||= {};
  return next;
}

export function migrateProject(raw) {
  if (!raw || typeof raw !== "object") throw new Error("Project file must contain a JSON object.");
  const data = clone(raw);
  data.metadata ||= {};
  const version = String(data.metadata.version || data.version || "1.0");
  if (version.startsWith("1.") || data.layers) {
    data.parts ||= data.layers || {};
    data.paths ||= {};
    data.mechanisms ||= {};
    data.metadata = {
      version: PROJECT_VERSION,
      name: data.project_name || data.metadata.name || "Migrated Project",
      created_at: data.metadata.created_at || nowIso(),
      modified_at: nowIso(),
    };
    delete data.layers;
  }
  data.metadata.version = PROJECT_VERSION;
  data.metadata.name ||= "Untitled";
  data.metadata.created_at ||= nowIso();
  data.metadata.modified_at ||= nowIso();
  data.parts ||= {};
  data.paths ||= {};
  data.mechanisms ||= {};
  if (data.skeleton && data.skeleton.joints) normalizeSkeleton(data.skeleton);
  for (const [name, part] of Object.entries(data.parts)) data.parts[name] = normalizePart(name, part);
  for (const [name, path] of Object.entries(data.paths)) data.paths[name] = normalizePath(name, path);
  for (const [id, mechanism] of Object.entries(data.mechanisms)) data.mechanisms[id] = normalizeMechanism(id, mechanism);
  return data;
}

export function importProjectJson(text) {
  try {
    const project = migrateProject(JSON.parse(text));
    const validation = validateProject(project);
    if (!validation.ok) throw new Error(validation.errors.join("; "));
    return project;
  } catch (error) {
    throw new Error(`Could not load project: ${error.message}`);
  }
}

function normalizePart(name, part = {}) {
  const texture = part.texture_path ?? part.image_path ?? "";
  return {
    name: part.name || name,
    texture_path: String(texture || ""),
    mask_path: String(part.mask_path ?? texture ?? ""),
    anchor_joint: String(part.anchor_joint ?? part.anchor_joint_id ?? "root"),
    transform: { x: 0, y: 0, rotation: 0, scale: 1, ...(part.transform || {}) },
    z_index: Number(part.z_index ?? part.z_value ?? 0),
    roi: Array.isArray(part.roi) ? part.roi.slice(0, 4).map(Number) : null,
    fill_color: part.fill_color || rgba(128, 128, 128),
    fixed: Boolean(part.fixed),
    opacity: Number(part.opacity ?? 1),
    group: part.group || null,
    original_svg_path: part.original_svg_path || null,
    enhanced_svg_path: part.enhanced_svg_path || null,
    effective_bbox_offset_x: Number(part.effective_bbox_offset_x || 0),
    effective_bbox_offset_y: Number(part.effective_bbox_offset_y || 0),
    show_anchor: Boolean(part.show_anchor),
    local_pivot_offset: Array.isArray(part.local_pivot_offset) ? part.local_pivot_offset.slice(0, 2).map(Number) : null,
  };
}

function normalizeSkeleton(skeleton) {
  const joints = skeleton.joints || {};
  for (const [id, joint] of Object.entries(joints)) {
    const pos = joint.position || joint.coordinates || joint.loc || [joint.x || 0, joint.y || 0];
    joints[id] = {
      id,
      name: joint.name || id,
      position: [Number(pos[0] || 0), Number(pos[1] || 0)],
      parent: joint.parent ?? joint.parent_id ?? null,
      parent_id: joint.parent_id ?? joint.parent ?? null,
      is_locked: Boolean(joint.is_locked),
      bend_direction: Number(joint.bend_direction ?? 1),
    };
  }
  skeleton.joints = joints;
  skeleton.bones ||= Object.values(joints).filter((joint) => joint.parent).map((joint) => ({ from: joint.parent, to: joint.id }));
  skeleton.root_joint ||= Object.values(joints).find((joint) => !joint.parent)?.id || "root";
  skeleton.root_joint_ids ||= Object.values(joints).filter((joint) => !joint.parent).map((joint) => joint.id);
  skeleton.joint_map ||= Object.fromEntries(Object.values(joints).map((joint) => [joint.name || joint.id, joint.id]));
  return skeleton;
}

function normalizePath(name, path = {}) {
  const points = (path.points || []).map((point) => [Number(point[0] ?? point.x ?? 0), Number(point[1] ?? point.y ?? 0)]);
  return {
    part_name: path.part_name || name,
    points,
    smoothness: Number(path.smoothness || 0),
    timed_points: path.timed_points || null,
    total_duration: Number(path.total_duration || 0),
    is_closed: Boolean(path.is_closed),
    enabled: path.enabled !== false,
  };
}

function normalizeMechanism(id, mechanism = {}) {
  const type = canonicalMechanismType(mechanism.type);
  const entry = getMechanismEntry(type);
  return {
    id: mechanism.id || id,
    part_name: mechanism.part_name || "",
    type,
    params: entry ? { ...defaultParams(type), ...(mechanism.params || {}) } : { ...(mechanism.params || {}) },
    layer_data: mechanism.layer_data || {},
    enabled: mechanism.enabled !== false,
  };
}

export function addOrUpdatePath(project, partName, points, { isClosed = true, enabled = true, smoothness = 0 } = {}) {
  const next = clone(project);
  next.paths[partName] = {
    part_name: partName,
    points: points.map((point) => [Number(point[0]), Number(point[1])]),
    smoothness: Number(smoothness || 0),
    is_closed: isClosed,
    enabled,
    timed_points: null,
    total_duration: 0,
  };
  return touch(next);
}

export function clearPath(project, partName) {
  const next = clone(project);
  delete next.paths[partName];
  return touch(next);
}

export function createMechanism(partName, type = "four_bar", params = {}) {
  const canonical = canonicalMechanismType(type);
  return {
    id: uid("mech"),
    part_name: partName,
    type: canonical,
    params: { ...defaultParams(canonical), ...params },
    layer_data: { source: "web", created_at: nowIso() },
    enabled: true,
  };
}

export function addMechanism(project, mechanism) {
  const next = clone(project);
  next.mechanisms[mechanism.id] = normalizeMechanism(mechanism.id, mechanism);
  return touch(next);
}

export function updateMechanism(project, mechanismId, patch) {
  const next = clone(project);
  if (!next.mechanisms[mechanismId]) return next;
  next.mechanisms[mechanismId] = normalizeMechanism(mechanismId, {
    ...next.mechanisms[mechanismId],
    ...patch,
    params: { ...next.mechanisms[mechanismId].params, ...(patch.params || {}) },
  });
  return touch(next);
}

export function deleteMechanism(project, mechanismId) {
  const next = clone(project);
  delete next.mechanisms[mechanismId];
  return touch(next);
}

export function recommendMechanism(path) {
  if (!path || !Array.isArray(path.points) || path.points.length < 2) {
    return { type: "four_bar", score: 0, reason: "Draw a motion path first; four-bar is the default starter mechanism." };
  }
  const xs = path.points.map((point) => Number(point[0]));
  const ys = path.points.map((point) => Number(point[1]));
  const width = Math.max(...xs) - Math.min(...xs);
  const height = Math.max(...ys) - Math.min(...ys);
  const closed = Boolean(path.is_closed);
  if (height > width * 1.35) {
    return { type: "cam_follower", score: 0.86, reason: "Mostly vertical travel matches a cam follower." };
  }
  if (closed || width > height * 1.15) {
    return { type: "four_bar", score: 0.82, reason: "Looping/broad travel matches a four-bar coupler path." };
  }
  return { type: "gear_linkage", score: 0.72, reason: "Mixed cyclic path can be approximated by gear-plus-linkage output." };
}

export function pointAtProgress(path, progress) {
  const points = smoothPathPoints(path?.points || [], path?.smoothness || 0, Boolean(path?.is_closed));
  if (!points.length) return null;
  if (points.length === 1) return { x: points[0][0], y: points[0][1] };
  const clamped = Math.max(0, Math.min(1, progress));
  const count = path.is_closed ? points.length : points.length - 1;
  const scaled = clamped * count;
  const i = Math.floor(scaled) % points.length;
  const j = (i + 1) % points.length;
  const a = scaled - Math.floor(scaled);
  return { x: points[i][0] + (points[j][0] - points[i][0]) * a, y: points[i][1] + (points[j][1] - points[i][1]) * a };
}

export function smoothPathPoints(points, smoothness = 0, closed = false) {
  let out = (points || []).map((point) => [Number(point[0]), Number(point[1])]);
  const iterations = Math.min(4, Math.max(0, Math.round(Number(smoothness || 0) / 25)));
  if (out.length < 3 || iterations === 0) return out;
  for (let n = 0; n < iterations; n += 1) {
    const next = [];
    if (!closed) next.push(out[0]);
    const limit = closed ? out.length : out.length - 1;
    for (let i = 0; i < limit; i += 1) {
      const a = out[i];
      const b = out[(i + 1) % out.length];
      next.push([a[0] * 0.75 + b[0] * 0.25, a[1] * 0.75 + b[1] * 0.25]);
      next.push([a[0] * 0.25 + b[0] * 0.75, a[1] * 0.25 + b[1] * 0.75]);
    }
    if (!closed) next.push(out[out.length - 1]);
    out = next;
  }
  return out;
}

export function computeMechanismState(type, params = {}, inputAngle = 0) {
  const canonical = canonicalMechanismType(type);
  const merged = { ...defaultParams(canonical), ...params };
  if (!getMechanismEntry(canonical)) throw new Error(`Unsupported mechanism type: ${type}`);
  if (canonical === "five_bar") return computeFiveBar(merged, inputAngle);
  if (canonical === "six_bar") return computeSixBar(merged, inputAngle);
  if (canonical === "slider_crank") return computeSliderCrank(merged, inputAngle);
  if (canonical === "cam_follower") return computeCamFollower(merged, inputAngle);
  if (canonical === "gear_train") return computeGearTrain(merged, inputAngle, false);
  if (canonical === "gear_linkage") return computeGearTrain(merged, inputAngle, true);
  if (canonical === "planetary_gear") return computePlanetary(merged, inputAngle);
  return computeFourBar(merged, inputAngle);
}

export function computeFourBar(params, inputAngle = 0) {
  const ground = positive(params.ground_link, 100);
  const input = positive(params.input_link, 45);
  const coupler = positive(params.coupler_link, 90);
  const output = positive(params.output_link, 75);
  const theta = (Number(inputAngle) * Math.PI) / 180;
  const O1 = [0, 0];
  const O4 = [ground, 0];
  const A = [input * Math.cos(theta), input * Math.sin(theta)];
  let B = circleIntersection(A, coupler, O4, output, 1);
  let level = "safe";
  let message = "Four-bar nominal";
  if (!B) {
    B = [(A[0] + O4[0]) / 2, (A[1] + O4[1]) / 2];
    level = "danger";
    message = "Links cannot close at this angle";
  }
  const links = [ground, input, coupler, output].sort((a, b) => a - b);
  const grashof = (links[0] + links[3]) / Math.max(links[1] + links[2], 1e-9);
  if (level === "safe" && grashof > 1) {
    level = "warning";
    message = `Limited rotation (Grashof ${grashof.toFixed(2)})`;
  }
  const couplerPoint = [(A[0] + B[0]) / 2, (A[1] + B[1]) / 2];
  return {
    positions: { O1, O4, A, B, coupler_point: couplerPoint },
    safety_status: { level, message, details: { grashof_ratio: grashof } },
    metadata: { type: "four_bar", input_angle: inputAngle, linkage_nodes: ["O1", "A", "B", "O4"], linkage_segments: [["O1", "A"], ["A", "B"], ["B", "O4"], ["O4", "O1"]] },
  };
}

function circleIntersection(a, ar, b, br, side = 1) {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const d = Math.hypot(dx, dy);
  if (d < 1e-9 || d > ar + br || d < Math.abs(ar - br)) return null;
  const along = (ar * ar - br * br + d * d) / (2 * d);
  const h = Math.sqrt(Math.max(0, ar * ar - along * along));
  const mid = [a[0] + (along * dx) / d, a[1] + (along * dy) / d];
  return [mid[0] - side * (dy * h) / d, mid[1] + side * (dx * h) / d];
}

function computeFiveBar(params, inputAngle = 0) {
  const ground = positive(params.ground_link, 160);
  const left = positive(params.input_link, 70);
  const floating = positive(params.coupler_link, 120);
  const right = positive(params.output_link, 70);
  const theta = (Number(inputAngle) * Math.PI) / 180;
  const phi = Math.PI - theta;
  const G1 = [-ground / 2, 0];
  const G2 = [ground / 2, 0];
  const C1 = [G1[0] + left * Math.cos(theta), G1[1] + left * Math.sin(theta)];
  const C2 = [G2[0] + right * Math.cos(phi), G2[1] + right * Math.sin(phi)];
  const P = circleIntersection(C1, floating, C2, floating, 1) || [(C1[0] + C2[0]) / 2, (C1[1] + C2[1]) / 2];
  const closure = Math.hypot(C1[0] - C2[0], C1[1] - C2[1]);
  const level = closure > floating * 2 ? "danger" : "safe";
  return {
    positions: { G1, C1, P, C2, G2, coupler_point: P },
    safety_status: { level, message: level === "danger" ? "Five-bar cannot close" : "Five-bar nominal", details: { closure } },
    metadata: { type: "five_bar", input_angle: inputAngle, linkage_nodes: ["G1", "C1", "P", "C2", "G2"] },
  };
}

function computeSixBar(params, inputAngle = 0) {
  const base = computeFourBar(params, inputAngle);
  const height = positive(params.pivot_height, 80);
  const A = base.positions.A;
  const B = base.positions.B;
  const C = [(A[0] + B[0]) / 2, (A[1] + B[1]) / 2 + height * 0.55];
  const P = [(B[0] + C[0]) / 2, (B[1] + C[1]) / 2];
  return {
    positions: { ...base.positions, C, P, coupler_point: P },
    safety_status: { ...base.safety_status, message: base.safety_status.level === "safe" ? "Six-bar approximation nominal" : base.safety_status.message },
    metadata: { ...base.metadata, type: "six_bar", linkage_nodes: ["O1", "A", "C", "P", "B", "O4"] },
  };
}

function computeSliderCrank(params, inputAngle = 0) {
  const crank = positive(params.crank_radius, 35);
  const rod = positive(params.rod_length, 110);
  const offset = Number(params.guide_offset || 0);
  const theta = (Number(inputAngle) * Math.PI) / 180;
  const O = [0, 0];
  const A = [crank * Math.cos(theta), crank * Math.sin(theta)];
  const under = rod * rod - (A[1] - offset) ** 2;
  const sliderX = A[0] + Math.sqrt(Math.max(0, under));
  const S = [sliderX, offset];
  const level = under < 0 ? "danger" : "safe";
  return {
    positions: { O, A, S, slider: S, coupler_point: S },
    safety_status: { level, message: level === "danger" ? "Slider guide unreachable" : "Slider-crank nominal", details: { travel: sliderX } },
    metadata: { type: "slider_crank", input_angle: inputAngle, linkage_nodes: ["O", "A", "S"] },
  };
}

function computeCamFollower(params, inputAngle = 0) {
  const base = positive(params.cam_radius, 32);
  const lobe = nonNegative(params.lobe_height ?? params.cam_offset, 18);
  const lobes = Math.max(1, Math.round(positive(params.num_lobes ?? params.cam_lobes, 1)));
  const followerLength = positive(params.follower_length, 90);
  const theta = (Number(inputAngle) * Math.PI) / 180;
  const radius = Math.max(base * 0.2, base + lobe * (0.5 + 0.5 * Math.cos(theta * lobes)));
  const camProfile = Array.from({ length: 72 }, (_, i) => {
    const a = (i / 72) * Math.PI * 2;
    const r = Math.max(base * 0.2, base + lobe * (0.5 + 0.5 * Math.cos(a * lobes)));
    return [r * Math.cos(a), r * Math.sin(a)];
  });
  return {
    positions: { cam_center: [0, 0], contact_point: [0, -radius], follower_base: [0, -radius - followerLength], follower_end: [0, -radius] },
    safety_status: { level: lobe > base ? "warning" : "safe", message: lobe > base ? "Large lobe may need smoothing" : "Cam profile nominal", details: { contact_radius: radius } },
    metadata: { type: "cam_follower", cam_profile: camProfile, displacement: radius - base, input_angle: inputAngle },
  };
}

function computeGearTrain(params, inputAngle = 0, withLinkage = false) {
  const teeth1 = Math.max(4, Math.round(positive(params.gear1_teeth, 16)));
  const teeth2 = Math.max(4, Math.round(positive(params.gear2_teeth, 28)));
  const module = positive(params.module, 2);
  const clearance = nonNegative(params.gear_clearance, 1);
  const r1 = (teeth1 * module) / 2;
  const r2 = (teeth2 * module) / 2;
  const d = r1 + r2 + clearance;
  const theta1 = (Number(inputAngle) * Math.PI) / 180;
  const theta2 = Math.PI - theta1 * (teeth1 / teeth2);
  const gear1 = [-d / 2, 0];
  const gear2 = [d / 2, 0];
  const positions = {
    gear1_center: gear1,
    gear2_center: gear2,
    gear1_indicator_end: [gear1[0] + r1 * Math.cos(theta1), gear1[1] + r1 * Math.sin(theta1)],
    gear2_indicator_end: [gear2[0] + r2 * Math.cos(theta2), gear2[1] + r2 * Math.sin(theta2)],
  };
  if (withLinkage) {
    const pin = Math.min(nonNegative(params.linkage_pin_radius, r2 * 0.55), r2 * 0.9);
    const arm = positive(params.linkage_arm_length, 70);
    positions.linkage_pin = [gear2[0] + pin * Math.cos(theta2), gear2[1] + pin * Math.sin(theta2)];
    positions.output_tip = [positions.linkage_pin[0] + arm, positions.linkage_pin[1]];
  }
  return {
    positions,
    safety_status: { level: clearance > module * 2 ? "warning" : "safe", message: clearance > module * 2 ? "Loose gear mesh" : "Gear mesh nominal", details: { ratio: teeth2 / teeth1 } },
    metadata: { type: withLinkage ? "gear_linkage" : "gear_train", gear1_teeth: teeth1, gear2_teeth: teeth2, r1, r2, center_distance: d, input_angle: inputAngle },
  };
}

function computePlanetary(params, inputAngle = 0) {
  const sunTeeth = Math.max(6, Math.round(positive(params.sun_teeth, 18)));
  const planetTeeth = Math.max(6, Math.round(positive(params.planet_teeth, 12)));
  const planetCount = Math.max(2, Math.round(positive(params.planet_count, 3)));
  const module = positive(params.module, 2);
  const sunRadius = (sunTeeth * module) / 2;
  const planetRadius = (planetTeeth * module) / 2;
  const orbit = sunRadius + planetRadius;
  const theta = (Number(inputAngle) * Math.PI) / 180;
  const positions = { sun_center: [0, 0] };
  for (let i = 0; i < planetCount; i += 1) {
    const a = theta + (i / planetCount) * Math.PI * 2;
    positions[`planet_${i + 1}_center`] = [orbit * Math.cos(a), orbit * Math.sin(a)];
  }
  return {
    positions,
    safety_status: { level: "safe", message: "Planetary layout nominal", details: { ring_teeth: sunTeeth + 2 * planetTeeth } },
    metadata: { type: "planetary_gear", sun_radius: sunRadius, planet_radius: planetRadius, ring_radius: sunRadius + 2 * planetRadius, planet_count: planetCount, input_angle: inputAngle },
  };
}

function positive(value, fallback) {
  const n = Number(value);
  return Number.isFinite(n) && n > 0 ? n : fallback;
}

function nonNegative(value, fallback) {
  const n = Number(value);
  return Number.isFinite(n) && n >= 0 ? n : fallback;
}

export function generateBlueprintSvg(project, { width = 900, height = 620 } = {}) {
  const parts = Object.values(project.parts || {});
  const mechanisms = Object.values(project.mechanisms || {});
  const paths = Object.values(project.paths || {});
  const partRects = parts
    .map((part) => {
      const [x = 0, y = 0, w = 30, h = 30] = safeRect(part.roi);
      return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="8" fill="${safeSvgColor(part.fill_color)}" stroke="#334" stroke-width="1"><title>${escapeXml(part.name)}</title></rect>`;
    })
    .join("\n");
  const pathLines = paths
    .map((path) => `<polyline points="${safeSvgPoints(path.points)}" fill="none" stroke="#ff595e" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>`)
    .join("\n");
  const labels = mechanisms
    .map((m, i) => `<text x="520" y="${90 + i * 24}" font-family="Arial" font-size="16" fill="#2f5f7f">${escapeXml(m.part_name)} → ${escapeXml(getMechanismEntry(m.type)?.name || `Unsupported: ${m.type}`)}</text>`)
    .join("\n");
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img" aria-label="Automataii blueprint export">
  <rect width="100%" height="100%" fill="#ffffff"/>
  <text x="32" y="42" font-family="Arial" font-size="28" font-weight="700" fill="#1982c4">${escapeXml(project.metadata?.name || "Automataii Project")}</text>
  <text x="32" y="68" font-family="Arial" font-size="14" fill="#6c757d">Blueprint package — parts, paths, and mechanism layers</text>
  <g transform="translate(40,90)">${partRects}\n${pathLines}</g>
  <g>${labels || `<text x="520" y="90" font-family="Arial" font-size="16" fill="#6c757d">No mechanisms yet</text>`}</g>
</svg>`;
}

export function generateBlueprintPackage(project) {
  const migrated = migrateProject(project);
  const manifest = {
    app: "Automataii Web",
    project_name: migrated.metadata?.name || "Untitled",
    version: PROJECT_VERSION,
    exported_at: nowIso(),
    counts: {
      parts: Object.keys(migrated.parts || {}).length,
      paths: Object.keys(migrated.paths || {}).length,
      mechanisms: Object.keys(migrated.mechanisms || {}).length,
    },
  };
  return {
    manifest,
    project: migrated,
    blueprint_svg: generateBlueprintSvg(migrated),
    assembly: {
      readme: assemblyReadme(manifest),
      recipes: assemblyRecipes(migrated),
      physical_contract: physicalContract(migrated),
      assembly_guide_svg: assemblyGuideSvg(migrated),
      kit_parts_to_cut_svg: kitPartsToCutSvg(migrated),
    },
  };
}

function assemblyReadme(manifest) {
  return `# Automataii exported board assembly guides

This folder is a browser-generated assembly package exported from Automataii Web.

## How to use

1. Print/cut the blueprint and kit parts SVGs included in this package.
2. Open \`assembly/svg-fallback/assembly/assembly-guide.svg\` for board coordinates and step cards.
3. Open \`assembly/svg-fallback/parts/kit-parts-to-cut.svg\` for printable part templates.
4. Check \`physical-contract.json\` before fabrication; warnings mean the design should be reviewed.

## Included data

- \`recipes.json\` lists the exported mechanism recipes.
- \`physical-contract.json\` records validation and project counts.
- \`${manifest.project_name}.automataii\` is the portable project JSON.
- \`blueprint.svg\` is the current design cut sheet.
`;
}

function assemblyRecipes(project) {
  return {
    generated_at: nowIso(),
    recipes: Object.values(project.mechanisms || {}).map((mechanism, index) => ({
      key: mechanism.id || `mechanism-${index + 1}`,
      title: getMechanismEntry(mechanism.type)?.name || mechanism.type,
      part_name: mechanism.part_name,
      mechanism_type: mechanism.type,
      enabled: mechanism.enabled !== false,
      params: mechanism.params || {},
      steps: [
        `Cut and label ${mechanism.part_name}.`,
        `Place ${mechanism.type} pivots on the board according to blueprint.svg.`,
        "Fasten pivots loosely, test motion, then tighten fixed joints.",
      ],
    })),
  };
}

function physicalContract(project) {
  const validation = validateProject(project);
  return {
    app: "Automataii Web",
    project_name: project.metadata?.name || "Untitled",
    validation,
    counts: {
      parts: Object.keys(project.parts || {}).length,
      paths: Object.keys(project.paths || {}).length,
      mechanisms: Object.keys(project.mechanisms || {}).length,
    },
    warnings: validation.ok ? [] : validation.errors,
  };
}

function assemblyGuideSvg(project) {
  const mechanisms = Object.values(project.mechanisms || {});
  const rows = mechanisms.length ? mechanisms.map((mechanism, i) => {
    const y = 120 + i * 72;
    const title = getMechanismEntry(mechanism.type)?.name || mechanism.type;
    return `<g transform="translate(40,${y})"><rect width="720" height="54" rx="10" fill="#f8fafc" stroke="#1982c4"/><text x="18" y="24" font-family="Arial" font-size="16" font-weight="700" fill="#27313b">Step ${i + 1}: ${escapeXml(title)} on ${escapeXml(mechanism.part_name)}</text><text x="18" y="43" font-family="Arial" font-size="12" fill="#6c757d">Align pivots, add spacers, verify clearance, then test by hand.</text></g>`;
  }).join("\n") : `<text x="40" y="130" font-family="Arial" font-size="16" fill="#6c757d">No mechanism recipes yet.</text>`;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="800" height="${Math.max(260, 180 + mechanisms.length * 72)}" viewBox="0 0 800 ${Math.max(260, 180 + mechanisms.length * 72)}"><rect width="100%" height="100%" fill="#fff"/><text x="40" y="52" font-family="Arial" font-size="28" font-weight="700" fill="#1982c4">Assembly guide</text><text x="40" y="82" font-family="Arial" font-size="14" fill="#6c757d">${escapeXml(project.metadata?.name || "Automataii Project")}</text>${rows}</svg>`;
}

function kitPartsToCutSvg(project) {
  const parts = Object.values(project.parts || {});
  const rows = parts.map((part, i) => {
    const [x, y, w, h] = safeRect(part.roi);
    const ox = 40 + (i % 3) * 230;
    const oy = 100 + Math.floor(i / 3) * 170;
    const scale = Math.min(180 / w, 120 / h, 1.5);
    return `<g transform="translate(${ox},${oy})"><rect width="${w * scale}" height="${h * scale}" rx="8" fill="${safeSvgColor(part.fill_color)}" stroke="#27313b"/><text x="0" y="${h * scale + 20}" font-family="Arial" font-size="12" fill="#27313b">${escapeXml(part.name)}</text><text x="0" y="${h * scale + 36}" font-family="Arial" font-size="10" fill="#6c757d">source ROI ${x},${y},${w},${h}</text></g>`;
  }).join("\n");
  return `<svg xmlns="http://www.w3.org/2000/svg" width="760" height="${Math.max(280, 150 + Math.ceil(parts.length / 3) * 170)}" viewBox="0 0 760 ${Math.max(280, 150 + Math.ceil(parts.length / 3) * 170)}"><rect width="100%" height="100%" fill="#fff"/><text x="40" y="52" font-family="Arial" font-size="28" font-weight="700" fill="#1982c4">Kit parts to cut</text><text x="40" y="78" font-family="Arial" font-size="14" fill="#6c757d">Browser SVG fallback for printable kit templates</text>${rows}</svg>`;
}

export function validateProject(project) {
  const errors = [];
  if (!project?.metadata) errors.push("Missing metadata");
  if (!project?.parts || typeof project.parts !== "object") errors.push("Missing parts object");
  if (!project?.paths || typeof project.paths !== "object") errors.push("Missing paths object");
  if (!project?.mechanisms || typeof project.mechanisms !== "object") errors.push("Missing mechanisms object");
  for (const [name, path] of Object.entries(project.paths || {})) {
    if (!project.parts?.[name]) errors.push(`Path references missing part: ${name}`);
    if (!Array.isArray(path.points)) errors.push(`Path ${name} has invalid points`);
  }
  for (const [id, mechanism] of Object.entries(project.mechanisms || {})) {
    if (!mechanism.part_name) errors.push(`Mechanism ${id} missing part_name`);
    if (!getMechanismEntry(mechanism.type)) errors.push(`Mechanism ${id} has unsupported type: ${mechanism.type}`);
  }
  return { ok: errors.length === 0, errors };
}

export { PROJECT_EXTENSION, PROJECT_VERSION };

function safeNumber(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function safeRect(value) {
  const raw = Array.isArray(value) ? value : [0, 0, 30, 30];
  const x = safeNumber(raw[0], 0);
  const y = safeNumber(raw[1], 0);
  const w = Math.max(1, safeNumber(raw[2], 30));
  const h = Math.max(1, safeNumber(raw[3], 30));
  return [x, y, w, h];
}

function safeSvgPoints(points) {
  if (!Array.isArray(points)) return "";
  return points
    .map((point) => Array.isArray(point) ? `${safeNumber(point[0], 0)},${safeNumber(point[1], 0)}` : null)
    .filter(Boolean)
    .join(" ");
}

function safeSvgColor(value) {
  const text = String(value || "#ccd").trim();
  if (/^#[0-9a-fA-F]{3}([0-9a-fA-F]{3})?$/.test(text)) return text;
  const rgbaMatch = text.match(/^rgba?\((\d{1,3}),\s*(\d{1,3}),\s*(\d{1,3})(?:,\s*(0|1|0?\.\d+))?\)$/);
  if (!rgbaMatch) return "#ccd";
  const [r, g, b] = rgbaMatch.slice(1, 4).map(Number);
  if ([r, g, b].some((n) => !Number.isFinite(n) || n < 0 || n > 255)) return "#ccd";
  const a = rgbaMatch[4] === undefined ? 1 : Number(rgbaMatch[4]);
  if (!Number.isFinite(a) || a < 0 || a > 1) return "#ccd";
  return `rgba(${r},${g},${b},${a})`;
}

function escapeXml(value) {
  return String(value).replace(/[<>&'"]/g, (ch) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", "'": "&apos;", '"': "&quot;" })[ch]);
}
