import type { GearVisual, MechanismConfig, MechanismState, Point, ProjectState } from '../types';
import { pointsToPathD } from './geometry';
import { computeMechanismState, generateTrace, MAX_GEAR_TEETH } from './mechanisms';
import { buildMS4NExportPayload } from './ms4n';
import { serializeProject } from './project';
import { colorWithAlpha, safeColor } from './sanitize';

const esc = (value: string): string => value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
const dxfLayer = (value: string): string => value.replace(/[^A-Za-z0-9_-]+/g, '_').slice(0, 64) || 'layer';
const safeJson = (value: unknown): string => JSON.stringify(value, null, 2).replace(/[<>&]/g, (char) => ({ '<': '\\u003c', '>': '\\u003e', '&': '\\u0026' })[char] ?? char);

const gearPath = (gear: GearVisual): string => {
  const teeth = Math.min(MAX_GEAR_TEETH, Math.max(6, Math.round(gear.teeth)));
  const inner = gear.radius * 0.86;
  const outer = gear.radius;
  const parts: string[] = [];
  for (let i = 0; i < teeth; i += 1) {
    const a = (Math.PI * 2 * i) / teeth;
    const b = (Math.PI * 2 * (i + 0.5)) / teeth;
    const c = (Math.PI * 2 * (i + 1)) / teeth;
    const p1 = { x: Math.cos(a) * inner, y: Math.sin(a) * inner };
    const p2 = { x: Math.cos(b) * outer, y: Math.sin(b) * outer };
    const p3 = { x: Math.cos(c) * inner, y: Math.sin(c) * inner };
    parts.push(`${i === 0 ? 'M' : 'L'} ${p1.x.toFixed(2)} ${p1.y.toFixed(2)} L ${p2.x.toFixed(2)} ${p2.y.toFixed(2)} L ${p3.x.toFixed(2)} ${p3.y.toFixed(2)}`);
  }
  return `${parts.join(' ')} Z`;
};

const renderStateSvg = (state: MechanismState, config: MechanismConfig): string => {
  const mechanismColor = safeColor(config.color);
  const mechanismFill = colorWithAlpha(config.color);
  const mechanismFillStrong = colorWithAlpha(config.color, '#38bdf8', '33');
  const lines = state.links
    .map((segment) => {
      const a = state.positions[segment.start];
      const b = state.positions[segment.end];
      if (!a || !b) return '';
      const width = segment.role === 'ground' ? 6 : segment.role === 'helper' ? 1.5 : 4;
      const color = segment.role === 'ground' ? '#64748b' : segment.role === 'helper' ? '#94a3b8' : mechanismColor;
      return `<line x1="${a.x.toFixed(2)}" y1="${a.y.toFixed(2)}" x2="${b.x.toFixed(2)}" y2="${b.y.toFixed(2)}" stroke="${color}" stroke-width="${width}" stroke-linecap="round" />`;
    })
    .join('');
  const profile = state.profile?.length ? `<path d="${pointsToPathD(state.profile, true)}" fill="${mechanismFill}" stroke="${mechanismColor}" stroke-width="2" />` : '';
  const gears = state.gears
    ?.map((g) => `<g transform="translate(${g.center.x.toFixed(2)} ${g.center.y.toFixed(2)}) rotate(${g.rotationDeg.toFixed(2)})"><path d="${gearPath(g)}" fill="${g.role === 'ring' ? 'none' : mechanismFillStrong}" stroke="${mechanismColor}" stroke-width="2" /><circle cx="0" cy="0" r="${Math.max(3, g.radius * 0.12).toFixed(2)}" fill="#0f172a" stroke="#f8fafc" /></g>`)
    .join('') ?? '';
  const nodes = Object.entries(state.positions)
    .map(([name, p]) => `<circle cx="${p.x.toFixed(2)}" cy="${p.y.toFixed(2)}" r="${name === 'effector' ? 5 : 3}" fill="${name === 'effector' ? '#ef4444' : '#f8fafc'}" stroke="${mechanismColor}" stroke-width="1.5"><title>${esc(name)}</title></circle>`)
    .join('');
  return `<g data-mechanism="${esc(config.id)}"><title>${esc(config.name)}</title>${gears}${profile}${lines}${nodes}</g>`;
};

export const exportProjectJson = (project: ProjectState): string => serializeProject(project);

const dxfLine = (a: Point, b: Point, layer: string): string => `0\nLINE\n8\n${dxfLayer(layer)}\n10\n${a.x.toFixed(3)}\n20\n${(-a.y).toFixed(3)}\n30\n0\n11\n${b.x.toFixed(3)}\n21\n${(-b.y).toFixed(3)}\n31\n0`;
const dxfCircle = (p: Point, radius: number, layer: string): string => `0\nCIRCLE\n8\n${dxfLayer(layer)}\n10\n${p.x.toFixed(3)}\n20\n${(-p.y).toFixed(3)}\n30\n0\n40\n${radius.toFixed(3)}`;

export const exportSceneDxf = (project: ProjectState, angleDeg: number): string => {
  const entities: string[] = [];
  Object.values(project.paths).forEach((path) => {
    path.points.slice(1).forEach((point, index) => entities.push(dxfLine(path.points[index], point, `path_${path.partName}`)));
    if (path.isClosed && path.points.length > 2) entities.push(dxfLine(path.points[path.points.length - 1], path.points[0], `path_${path.partName}`));
  });
  project.mechanisms.forEach((mechanism) => {
    const state = computeMechanismState(mechanism, angleDeg);
    state.links.forEach((segment) => {
      const a = state.positions[segment.start];
      const b = state.positions[segment.end];
      if (a && b) entities.push(dxfLine(a, b, mechanism.type));
    });
    Object.values(state.positions).forEach((point) => entities.push(dxfCircle(point, 3, `${mechanism.type}_joints`)));
  });
  return ['0', 'SECTION', '2', 'HEADER', '9', '$ACADVER', '1', 'AC1009', '0', 'ENDSEC', '0', 'SECTION', '2', 'ENTITIES', ...entities, '0', 'ENDSEC', '0', 'EOF'].join('\n');
};

export const exportStudyBundle = (project: ProjectState, angleDeg: number): string => {
  const snapshots = project.mechanisms.map((mechanism) => {
    const state = computeMechanismState(mechanism, angleDeg);
    return {
      mechanism_id: mechanism.id,
      mechanism_type: mechanism.type,
      part_name: mechanism.partName,
      valid: state.valid,
      safety: state.safety,
      effector: state.effector,
      parameters: mechanism.params,
      trace_points: generateTrace(mechanism, 64)
    };
  });
  const traceSummary = {
    mechanism_count: snapshots.length,
    valid_snapshot_count: snapshots.filter((snapshot) => snapshot.valid).length,
    average_trace_points: snapshots.length > 0
      ? snapshots.reduce((sum, snapshot) => sum + snapshot.trace_points.length, 0) / snapshots.length
      : 0
  };
  const ms4n = buildMS4NExportPayload(project, traceSummary);
  const jsonl = project.lab.episodes.map((episode) => JSON.stringify({ kind: 'episode', ...episode })).join('\n');
  const codingCsv = [
    'episode_id,status,symptom,suspected_cause,repair_action,notes',
    ...project.lab.episodes.map((episode) => [episode.id, episode.status, episode.symptom, episode.suspectedCause, episode.repairAction, episode.notes].map((value) => `"${String(value).replaceAll('"', '""')}"`).join(','))
  ].join('\n');
  return safeJson({
    schema_version: 'automataii.web.study_bundle.v1',
    exported_at: new Date().toISOString(),
    project: project.metadata,
    compatibility: project.compatibility,
    kit_assets: project.lab.kitAssets,
    mechanism_snapshots: snapshots,
    ms4n,
    paths: project.paths,
    tracking: project.tracking.annotations,
    episode_jsonl: jsonl,
    coding_csv: codingCsv
  });
};

export const exportBlueprintSvg = (project: ProjectState, angleDeg: number, width = 1180, height = 820): string => {
  const title = esc(`${project.metadata.name} fabrication blueprint`);
  const mechanisms = project.mechanisms.map((mechanism, index) => {
    const state = computeMechanismState(mechanism, angleDeg);
    const offsetY = 92 + index * 92;
    const label = esc(`${mechanism.name} · ${mechanism.type} · ${mechanism.partName}`);
    const linkRows = state.links.map((segment) => {
      const a = state.positions[segment.start];
      const b = state.positions[segment.end];
      if (!a || !b) return '';
      return `<line data-layer="cut-${esc(segment.role ?? 'link')}" x1="${(a.x * 0.45 + 40).toFixed(2)}" y1="${(a.y * 0.45 + offsetY).toFixed(2)}" x2="${(b.x * 0.45 + 40).toFixed(2)}" y2="${(b.y * 0.45 + offsetY).toFixed(2)}" stroke="${segment.role === 'ground' ? '#0f172a' : safeColor(mechanism.color)}" stroke-width="${segment.role === 'ground' ? 8 : 4}" stroke-linecap="round" />`;
    }).join('');
    const holes = Object.entries(state.positions).map(([name, point]) => `<g data-layer="drill"><circle cx="${(point.x * 0.45 + 40).toFixed(2)}" cy="${(point.y * 0.45 + offsetY).toFixed(2)}" r="${name === 'effector' ? 5 : 3.2}" fill="none" stroke="#ef4444" stroke-width="1.5" /><text x="${(point.x * 0.45 + 48).toFixed(2)}" y="${(point.y * 0.45 + offsetY - 5).toFixed(2)}" font-size="9" fill="#334155">${esc(name)}</text></g>`).join('');
    return `<g data-mechanism="${esc(mechanism.id)}"><text x="36" y="${offsetY - 18}" font-size="14" font-weight="700" fill="#0f172a">${label}</text>${linkRows}${holes}</g>`;
  }).join('');
  const kitRows = project.lab.kitAssets.map((asset, index) => `<text x="760" y="${118 + index * 26}" font-size="12" fill="#334155">${esc(asset.pilotPriority)} · ${esc(asset.label)} · ${esc(asset.filename)}</text>`).join('');
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" data-schema="automataii.web.blueprint.v1"><rect width="100%" height="100%" fill="#f8fafc" /><text x="32" y="42" fill="#0f172a" font-family="Inter, sans-serif" font-size="24" font-weight="800">${title}</text><text x="32" y="66" fill="#64748b" font-size="12">Layers: cut-link, cut-ground, drill, label. Units: ${esc(project.settings.units)}. Angle: ${angleDeg.toFixed(1)}°.</text><g>${mechanisms}</g><g data-layer="kit-manifest"><text x="760" y="82" font-size="16" font-weight="800" fill="#0f172a">MS4N kit manifest</text>${kitRows}</g></svg>`;
};

export const exportSceneSvg = (project: ProjectState, angleDeg: number, width = 1100, height = 740): string => {
  const traces = project.settings.showTraces
    ? project.mechanisms
        .map((m) => {
          const trace = generateTrace(m, 90);
          if (trace.length < 2) return '';
          return `<path d="${pointsToPathD(trace, true)}" fill="none" stroke="${safeColor(m.color)}" stroke-width="1.5" opacity="0.42" stroke-dasharray="5 5" />`;
        })
        .join('')
    : '';
  const userPaths = Object.values(project.paths)
    .filter((path) => path.enabled && path.points.length > 1)
    .map((path) => `<path d="${pointsToPathD(path.points, path.isClosed)}" fill="${path.isClosed ? '#38bdf822' : 'none'}" stroke="#38bdf8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />`)
    .join('');
  const skeleton = project.skeleton && project.settings.showSkeleton
    ? `<g opacity="0.58" transform="translate(790 410)">${project.skeleton.bones
        .map((bone) => {
          const a = project.skeleton?.joints[bone.fromJoint];
          const b = project.skeleton?.joints[bone.toJoint];
          if (!a || !b) return '';
          return `<line x1="${a.position.x}" y1="${a.position.y}" x2="${b.position.x}" y2="${b.position.y}" stroke="#cbd5e1" stroke-width="4" stroke-linecap="round" />`;
        })
        .join('')}${Object.values(project.skeleton.joints)
        .map((j) => `<circle cx="${j.position.x}" cy="${j.position.y}" r="5" fill="#0f172a" stroke="#f8fafc" />`)
        .join('')}</g>`
    : '';
  const mechanisms = project.mechanisms.map((m) => renderStateSvg(computeMechanismState(m, angleDeg), m)).join('');
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" width="${width}" height="${height}"><rect width="100%" height="100%" fill="#0f172a" /><text x="28" y="42" fill="#f8fafc" font-family="Inter, sans-serif" font-size="22" font-weight="700">${esc(project.metadata.name)}</text><g>${traces}${userPaths}${skeleton}${mechanisms}</g></svg>`;
};
