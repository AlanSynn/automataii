import { useMemo, useRef, useState } from 'react';
import type { MechanismConfig, MechanismState, PartData, PathData, Point, ProjectState } from '../types';
import { pointsToPathD } from '../domain/geometry';
import { computeMechanismState, generateTrace, MAX_GEAR_TEETH } from '../domain/mechanisms';
import type { PhysicsReport } from '../domain/physics';
import { colorWithAlpha, safeColor } from '../domain/sanitize';
import { snapPoint } from '../domain/analysis';

interface StudioCanvasProps {
  project: ProjectState;
  angle: number;
  selectedId?: string;
  physicsReport?: PhysicsReport;
  drawingPath: boolean;
  onSelect: (id: string) => void;
  onMoveMechanism: (id: string, delta: Point) => void;
  onMoveMechanismHandle: (id: string, handleName: string, point: Point) => void;
  onMovePathPoint: (partName: string, index: number, point: Point) => void;
  onPanViewport: (delta: Point) => void;
  onAddPathPoint: (point: Point) => void;
}

const toSvgPoint = (svg: SVGSVGElement, clientX: number, clientY: number): Point => {
  const point = svg.createSVGPoint();
  point.x = clientX;
  point.y = clientY;
  const matrix = svg.getScreenCTM();
  if (!matrix) return { x: clientX, y: clientY };
  const transformed = point.matrixTransform(matrix.inverse());
  return { x: transformed.x, y: transformed.y };
};

const gearPath = (radius: number, teeth: number): string => {
  const safeTeeth = Math.min(MAX_GEAR_TEETH, Math.max(6, Math.round(teeth)));
  const inner = radius * 0.86;
  const outer = radius;
  const pieces: string[] = [];
  for (let i = 0; i < safeTeeth; i += 1) {
    const a = (Math.PI * 2 * i) / safeTeeth;
    const b = (Math.PI * 2 * (i + 0.5)) / safeTeeth;
    const c = (Math.PI * 2 * (i + 1)) / safeTeeth;
    const p1 = { x: Math.cos(a) * inner, y: Math.sin(a) * inner };
    const p2 = { x: Math.cos(b) * outer, y: Math.sin(b) * outer };
    const p3 = { x: Math.cos(c) * inner, y: Math.sin(c) * inner };
    pieces.push(`${i === 0 ? 'M' : 'L'} ${p1.x.toFixed(2)} ${p1.y.toFixed(2)} L ${p2.x.toFixed(2)} ${p2.y.toFixed(2)} L ${p3.x.toFixed(2)} ${p3.y.toFixed(2)}`);
  }
  return `${pieces.join(' ')} Z`;
};

const MechanismGlyph = ({
  config,
  state,
  selected,
  showTrace,
  showForces,
  showSafetyZones,
  onSelect,
  onStartDrag,
  onStartHandleDrag
}: {
  config: MechanismConfig;
  state: MechanismState;
  selected: boolean;
  showTrace: boolean;
  showForces: boolean;
  showSafetyZones: boolean;
  onSelect: (id: string) => void;
  onStartDrag: (id: string, point: Point) => void;
  onStartHandleDrag: (id: string, handleName: string, point: Point) => void;
}) => {
  const traceColor = safeColor(config.color);
  const trace = useMemo(() => (showTrace ? generateTrace(config, 110) : []), [config, showTrace]);
  return (
    <g className={`mechanism-glyph ${selected ? 'selected' : ''}`} onPointerDown={(event) => { event.stopPropagation(); onSelect(config.id); const svg = event.currentTarget.ownerSVGElement; if (svg) onStartDrag(config.id, toSvgPoint(svg, event.clientX, event.clientY)); }}>
      <title>{config.name}</title>
      {showTrace && trace.length > 2 && (
        <path className="trace-line" d={pointsToPathD(trace, true)} stroke={traceColor} />
      )}
      {state.profile && state.profile.length > 2 && (
        <path className="cam-profile" d={pointsToPathD(state.profile, true)} fill={colorWithAlpha(config.color)} stroke={traceColor} />
      )}
      {showSafetyZones && state.safety.level !== 'safe' && (
        <circle className={`safety-zone safety-${state.safety.level}`} cx={state.effector.x} cy={state.effector.y} r={state.safety.level === 'danger' ? 38 : 26} />
      )}
      {showForces && Object.entries(state.forces ?? {}).map(([id, vector]) => {
        const radians = (vector.angle * Math.PI) / 180;
        const scale = Math.min(52, Math.max(10, vector.magnitude * 0.18));
        const end = { x: vector.position.x + Math.cos(radians) * scale, y: vector.position.y + Math.sin(radians) * scale };
        return (
          <g key={`force-${id}`} className={`force-vector force-${vector.forceType}`}>
            <line x1={vector.position.x} y1={vector.position.y} x2={end.x} y2={end.y} />
            {selected && <text x={end.x + 4} y={end.y - 4}>{vector.label}</text>}
          </g>
        );
      })}
      {state.gears?.map((gear) => (
        <g key={gear.id} transform={`translate(${gear.center.x} ${gear.center.y}) rotate(${gear.rotationDeg})`}>
          <path className={`gear gear-${gear.role}`} d={gearPath(gear.radius, gear.teeth)} fill={gear.role === 'ring' ? 'none' : colorWithAlpha(config.color, '#38bdf8', '33')} stroke={traceColor} />
          <circle r={Math.max(3, gear.radius * 0.12)} className="joint joint-gear" />
        </g>
      ))}
      {state.links.map((segment, index) => {
        const a = state.positions[segment.start];
        const b = state.positions[segment.end];
        if (!a || !b) return null;
        return (
          <line
            key={`${segment.start}-${segment.end}-${index}`}
            className={`link link-${segment.role ?? 'generic'}`}
            x1={a.x}
            y1={a.y}
            x2={b.x}
            y2={b.y}
            stroke={segment.role === 'ground' ? '#64748b' : segment.role === 'helper' ? '#94a3b8' : traceColor}
          />
        );
      })}
      {Object.entries(state.positions).map(([name, point]) => (
        <g key={name} className="node-label-group">
          <circle
            className={`joint ${name === 'effector' ? 'effector' : ''} ${selected ? 'editable-handle' : ''}`}
            cx={point.x}
            cy={point.y}
            r={name === 'effector' ? 6 : 4}
            stroke={traceColor}
            onPointerDown={(event) => {
              if (!selected) return;
              event.stopPropagation();
              onSelect(config.id);
              const svg = event.currentTarget.ownerSVGElement;
              if (svg) onStartHandleDrag(config.id, name, toSvgPoint(svg, event.clientX, event.clientY));
            }}
          />
          {selected && name !== 'effector' && <text x={point.x + 7} y={point.y - 7}>{name}</text>}
        </g>
      ))}
      {selected && <circle className="selection-ring" cx={state.effector.x} cy={state.effector.y} r="14" />}
    </g>
  );
};

const SkeletonLayer = ({ project }: { project: ProjectState }) => {
  if (!project.skeleton || !project.settings.showSkeleton) return null;
  return (
    <g className="skeleton-layer" transform="translate(820 445)">
      {project.skeleton.bones.map((bone) => {
        const a = project.skeleton?.joints[bone.fromJoint];
        const b = project.skeleton?.joints[bone.toJoint];
        if (!a || !b) return null;
        return <line key={`${bone.fromJoint}-${bone.toJoint}`} x1={a.position.x} y1={a.position.y} x2={b.position.x} y2={b.position.y} />;
      })}
      {Object.values(project.skeleton.joints).map((joint) => (
        <g key={joint.id}>
          <circle cx={joint.position.x} cy={joint.position.y} r="5" />
          <text x={joint.position.x + 7} y={joint.position.y + 4}>{joint.name.replace(' ', '\u00a0')}</text>
        </g>
      ))}
    </g>
  );
};

const PathLayer = ({ paths, onStartDrag }: { paths: Record<string, PathData>; onStartDrag: (partName: string, index: number, point: Point) => void }) => (
  <g className="path-layer">
    {Object.values(paths).map((path) => {
      if (!path.enabled || path.points.length === 0) return null;
      return (
        <g key={path.partName}>
          {path.points.length > 1 && <path d={pointsToPathD(path.points, path.isClosed)} className="user-path" />}
          {path.points.map((point, index) => <circle key={`${path.partName}-${index}`} cx={point.x} cy={point.y} r="6" className="path-point" onPointerDown={(event) => { event.stopPropagation(); const svg = event.currentTarget.ownerSVGElement; if (svg) onStartDrag(path.partName, index, toSvgPoint(svg, event.clientX, event.clientY)); }} />)}
        </g>
      );
    })}
  </g>
);

const characterOrigin: Point = { x: 820, y: 445 };

const partSize = (part: PartData): { width: number; height: number; radius: number } => {
  if (part.name.includes('head')) return { width: 54, height: 54, radius: 27 };
  if (part.name.includes('torso')) return { width: 92, height: 128, radius: 26 };
  if (part.name.includes('arm')) return { width: 34, height: 92, radius: 18 };
  if (part.name.includes('leg')) return { width: 36, height: 112, radius: 18 };
  return { width: 46, height: 76, radius: 18 };
};

const CharacterPartsLayer = ({ project, states }: { project: ProjectState; states: Array<{ config: MechanismConfig; state: MechanismState }> }) => {
  if (!project.settings.showCharacterParts || !project.skeleton) return null;
  const sorted = Object.values(project.parts).sort((a, b) => a.zIndex - b.zIndex);
  return (
    <g className="character-parts-layer">
      {sorted.map((part) => {
        const joint = project.skeleton?.joints[part.anchorJoint] ?? project.skeleton?.joints[project.skeleton.rootJoint];
        if (!joint) return null;
        const driver = states.find(({ config }) => config.partName === part.anchorJoint || config.partName === part.name);
        const offset = driver?.state.valid ? { x: (driver.state.effector.x - driver.config.anchor.x) * 0.16, y: (driver.state.effector.y - driver.config.anchor.y) * 0.16 } : { x: 0, y: 0 };
        const center = {
          x: characterOrigin.x + joint.position.x + part.transform.x + offset.x,
          y: characterOrigin.y + joint.position.y + part.transform.y + offset.y
        };
        const size = partSize(part);
        const color = safeColor(part.fillColor, '#94a3b8');
        return (
          <g key={part.name} transform={`translate(${center.x} ${center.y}) rotate(${part.transform.rotation}) scale(${part.transform.scale})`} opacity={part.opacity}>
            {part.name.includes('head') ? (
              <circle r={size.radius} fill={color} />
            ) : (
              <rect x={-size.width / 2} y={-size.height / 2} width={size.width} height={size.height} rx={size.radius} fill={color} />
            )}
            <circle r="4" className="part-pivot" />
            <text x={size.width * 0.45} y="4">{part.name}</text>
          </g>
        );
      })}
    </g>
  );
};

const PhysicsLayer = ({ report }: { report?: PhysicsReport }) => {
  if (!report || !report.current.valid) return null;
  const current = report.current.position;
  const speedScale = Math.min(44, Math.max(12, report.current.speed * 0.018));
  const accelScale = Math.min(34, Math.max(8, report.current.accelerationMagnitude * 0.00025));
  const velocityMagnitude = Math.hypot(report.current.velocity.x, report.current.velocity.y) || 1;
  const accelerationMagnitude = Math.hypot(report.current.acceleration.x, report.current.acceleration.y) || 1;
  const velocityEnd = {
    x: current.x + (report.current.velocity.x / velocityMagnitude) * speedScale,
    y: current.y + (report.current.velocity.y / velocityMagnitude) * speedScale
  };
  const accelerationEnd = {
    x: current.x + (report.current.acceleration.x / accelerationMagnitude) * accelScale,
    y: current.y + (report.current.acceleration.y / accelerationMagnitude) * accelScale
  };
  const trail = report.samples.filter((sample, index) => sample.valid && index % 3 === 0).map((sample) => sample.position);
  return (
    <g className={`physics-layer physics-${report.status}`} aria-hidden="true">
      {trail.length > 2 && <path className="physics-trail" d={pointsToPathD(trail, true)} />}
      <circle className="kinetic-ring" cx={current.x} cy={current.y} r={12 + report.loadScore * 18} />
      <line className="physics-vector velocity-vector" x1={current.x} y1={current.y} x2={velocityEnd.x} y2={velocityEnd.y} markerEnd="url(#velocityArrow)" />
      <line className="physics-vector acceleration-vector" x1={current.x} y1={current.y} x2={accelerationEnd.x} y2={accelerationEnd.y} markerEnd="url(#accelerationArrow)" />
      <text className="physics-label" x={current.x + 16} y={current.y + 22}>{Math.round(report.current.speed)} px/s</text>
    </g>
  );
};

export const StudioCanvas = ({ project, angle, selectedId, physicsReport, drawingPath, onSelect, onMoveMechanism, onMoveMechanismHandle, onMovePathPoint, onPanViewport, onAddPathPoint }: StudioCanvasProps) => {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [drag, setDrag] = useState<
    | { kind: 'mechanism'; id: string; last: Point }
    | { kind: 'mechanism-handle'; id: string; handleName: string; last: Point }
    | { kind: 'path-point'; partName: string; index: number; last: Point }
    | { kind: 'drawing-path'; last: Point }
    | { kind: 'pan'; last: Point }
    | null
  >(null);
  const states = useMemo(
    () => project.mechanisms.map((config) => ({ config, state: computeMechanismState(config, angle) })),
    [project.mechanisms, angle]
  );
  const viewport = project.settings.viewport;
  const viewWidth = 1120 / viewport.zoom;
  const viewHeight = 760 / viewport.zoom;
  const viewBox = `${viewport.x} ${viewport.y} ${viewWidth} ${viewHeight}`;

  const handlePointerDown = (event: React.PointerEvent<SVGSVGElement>): void => {
    if (!svgRef.current) return;
    const p = toSvgPoint(svgRef.current, event.clientX, event.clientY);
    const snapEnabled = project.settings.showPhysicsSnap && project.settings.physicsSnapMode !== 'off';
    if (viewport.panMode) {
      setDrag({ kind: 'pan', last: p });
      return;
    }
    if (drawingPath) {
      const snapped = snapPoint(p, snapEnabled, project.settings.gridSize);
      onAddPathPoint(snapped);
      setDrag({ kind: 'drawing-path', last: snapped });
      return;
    }
    setDrag(selectedId ? { kind: 'mechanism', id: selectedId, last: p } : null);
  };

  const handlePointerMove = (event: React.PointerEvent<SVGSVGElement>): void => {
    if (!drag || !svgRef.current) return;
    const p = toSvgPoint(svgRef.current, event.clientX, event.clientY);
    const snapEnabled = project.settings.showPhysicsSnap && project.settings.physicsSnapMode !== 'off';
    if (drag.kind === 'pan') {
      onPanViewport({ x: drag.last.x - p.x, y: drag.last.y - p.y });
      setDrag({ ...drag, last: p });
      return;
    }
    if (drag.kind === 'mechanism') {
      onMoveMechanism(drag.id, { x: p.x - drag.last.x, y: p.y - drag.last.y });
      setDrag({ ...drag, last: p });
      return;
    }
    if (drag.kind === 'mechanism-handle') {
      const target = snapPoint(p, snapEnabled, project.settings.gridSize);
      onMoveMechanismHandle(drag.id, drag.handleName, target);
      setDrag({ ...drag, last: target });
      return;
    }
    if (drag.kind === 'drawing-path') {
      const target = snapPoint(p, snapEnabled, project.settings.gridSize);
      if (Math.hypot(target.x - drag.last.x, target.y - drag.last.y) >= Math.max(4, project.settings.gridSize * 0.35)) {
        onAddPathPoint(target);
        setDrag({ kind: 'drawing-path', last: target });
      }
      return;
    }
    onMovePathPoint(drag.partName, drag.index, snapPoint(p, snapEnabled, project.settings.gridSize));
    setDrag({ ...drag, last: p });
  };

  return (
    <div className={`canvas-shell ${drawingPath ? 'drawing' : ''}`}>
      <svg ref={svgRef} viewBox={viewBox} role="img" aria-label="Automataii mechanism studio canvas" onPointerDown={handlePointerDown} onPointerMove={handlePointerMove} onPointerUp={() => setDrag(null)} onPointerLeave={() => setDrag(null)}>
        <defs>
          <pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse">
            <path d="M 32 0 L 0 0 0 32" fill="none" stroke="rgba(148,163,184,0.12)" strokeWidth="1" />
          </pattern>
          <radialGradient id="canvasGlow" cx="50%" cy="45%" r="70%">
            <stop offset="0%" stopColor="#334155" stopOpacity="0.32" />
            <stop offset="100%" stopColor="#020617" stopOpacity="0" />
          </radialGradient>
          <marker id="velocityArrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth">
            <path d="M0,0 L8,4 L0,8 Z" fill="#2563eb" />
          </marker>
          <marker id="accelerationArrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth">
            <path d="M0,0 L8,4 L0,8 Z" fill="#f97316" />
          </marker>
        </defs>
        <rect width="1120" height="760" fill="url(#grid)" />
        <rect width="1120" height="760" fill="url(#canvasGlow)" />
        <PathLayer paths={project.paths} onStartDrag={(partName, index, point) => setDrag({ kind: 'path-point', partName, index, last: point })} />
        <CharacterPartsLayer project={project} states={states} />
        <SkeletonLayer project={project} />
        <PhysicsLayer report={physicsReport} />
        {states.map(({ config, state }) => (
          <MechanismGlyph
            key={config.id}
            config={config}
            state={state}
            selected={config.id === selectedId}
            showTrace={project.settings.showTraces}
            showForces={project.settings.showForces}
            showSafetyZones={project.settings.showSafetyZones}
            onSelect={onSelect}
            onStartDrag={(id, point) => setDrag({ kind: 'mechanism', id, last: point })}
            onStartHandleDrag={(id, handleName, point) => setDrag({ kind: 'mechanism-handle', id, handleName, last: point })}
          />
        ))}
        {drawingPath && <text x="28" y="732" className="canvas-hint">Drawing path: press-drag for timed freehand points, or click to add snapped points.</text>}
      </svg>
    </div>
  );
};
