import type { ForceType, ForceVector, GearVisual, LinkSegment, MechanismConfig, MechanismState, MechanismTemplate, MechanismType, Point, SafetyStatus } from '../types';
import { boundsOf, circleIntersection, clamp, distance, finite, midpoint, nonNegative, polar, positive, pointsToPathD, toDeg, toRad } from './geometry';

const safety = (level: SafetyStatus['level'], message: string, details: Record<string, unknown> = {}): SafetyStatus => ({
  level,
  message,
  details: { pythonSafetyLevel: level === 'caution' ? 'warning' : level, ...details }
});
const safe = (message = 'Nominal', details: Record<string, unknown> = {}): SafetyStatus => safety('safe', message, details);
const caution = (message: string, details: Record<string, unknown> = {}): SafetyStatus => safety('caution', message, details);
const danger = (message: string, details: Record<string, unknown> = {}): SafetyStatus => safety('danger', message, details);

const forceColors: Record<ForceType, string> = {
  reaction: 'rgba(255,69,0,0.78)',
  applied: 'rgba(0,123,255,0.78)',
  constraint: 'rgba(255,140,0,0.78)',
  friction: 'rgba(128,128,128,0.78)',
  gravity: 'rgba(139,69,19,0.78)'
};

const force = (position: Point, magnitude: number, angle: number, forceType: ForceType, label: string): ForceVector => ({
  position,
  magnitude: finite(Math.abs(magnitude), 0),
  angle: finite(angle, 0),
  forceType,
  label,
  color: forceColors[forceType]
});

const parityMetadata = (config: MechanismConfig, barCount?: number): Record<string, unknown> => ({
  pythonMechanismType: config.type === 'cam-follower' ? 'cam' : config.type.includes('bar') ? 'linkages' : config.type,
  bar_count: barCount,
  renderConfig: {
    show_forces: true,
    show_safety_zones: true,
    show_labels: true,
    show_trails: true
  }
});

export const MAX_GEAR_TEETH = 256;
export const MAX_PLANET_COUNT = 12;
const MAX_CAM_LOBES = 24;

const invalidState = (type: MechanismType, anchor: Point, message: string): MechanismState => ({
  type,
  positions: { anchor },
  forces: { anchor: force(anchor, 0, 0, 'constraint', 'invalid anchor') },
  links: [],
  effector: anchor,
  valid: false,
  safety: danger(message),
  metadata: { message }
});

export const mechanismTemplates: MechanismTemplate[] = [
  {
    type: 'crank',
    label: 'Rotary crank / gear',
    tagline: 'Single pivot rotary output',
    description: 'MechAnim-compatible basic crank primitive for direct circular output and gear-like timing tests.',
    color: '#60a5fa',
    params: {
      crankRadius: 56,
      hubRadius: 18,
      outputOffset: 0
    },
    tags: ['rotary', 'gear', 'trace'],
    complexity: 'intro'
  },
  {
    type: 'four-bar',
    label: 'Four-bar linkage',
    tagline: 'Classic crank-rocker path generator',
    description: 'Mirrors Automataii 4-bar dimensions with ground/input/coupler/output links and a coupler point.',
    color: '#38bdf8',
    params: {
      groundLink: 170,
      inputLink: 56,
      couplerLink: 150,
      outputLink: 120,
      couplerPointDist: 78,
      couplerPointAngle: 42,
      assembly: 1
    },
    tags: ['linkage', 'trace', 'grashof'],
    complexity: 'intro'
  },
  {
    type: 'five-bar',
    label: 'Five-bar linkage',
    tagline: 'Symmetric dual-crank curve composer',
    description: 'Computes G1/G2/C1/C2/P and optional custom coupler interpolation inspired by the Python domain solver.',
    color: '#a78bfa',
    params: {
      groundLink: 190,
      inputLink: 62,
      couplerLink: 136,
      outputLink: 70,
      couplerCustomFraction: 0.5,
      secondarySpeed: -1,
      phase: 180
    },
    tags: ['linkage', 'dual-crank', 'trace'],
    complexity: 'intermediate'
  },
  {
    type: 'six-bar',
    label: 'Six-bar linkage',
    tagline: 'Five-bar base plus rocker guide',
    description: 'Adds the G3/Q rocker construction used by the Automataii six-bar model.',
    color: '#f472b6',
    params: {
      groundLink: 220,
      inputLink: 58,
      couplerLink: 165,
      outputLink: 82,
      rockerLink: 110,
      pivotHeight: 130,
      couplerCustomFraction: 0.6,
      secondarySpeed: -1,
      phase: 180
    },
    tags: ['linkage', 'rocker', 'advanced'],
    complexity: 'advanced'
  },
  {
    type: 'cam-follower',
    label: 'Cam follower',
    tagline: 'Harmonic cam profile with linear follower',
    description: 'Browser port of the cam-radius/offset/follower/lobes parameter family.',
    color: '#fb923c',
    params: {
      camRadius: 58,
      camOffset: 18,
      followerLength: 120,
      camLobes: 2,
      profileHarmonic: 0.28
    },
    tags: ['cam', 'follower', 'profile'],
    complexity: 'intermediate'
  },
  {
    type: 'gear-pair',
    label: 'Gear pair',
    tagline: 'Meshed driver/output gear visualizer',
    description: 'A lightweight web visual for the gear pair workflow present in the Qt layer.',
    color: '#facc15',
    params: {
      inputRadius: 48,
      outputRadius: 72,
      teeth: 16,
      outputTeeth: 24,
      backlash: 0
    },
    tags: ['gear', 'ratio', 'timing'],
    complexity: 'intro'
  },
  {
    type: 'planetary-gear',
    label: 'Planetary gear',
    tagline: 'Sun, planets, carrier, and ring',
    description: 'Planetary gear preview with ring/sun/planet state metadata.',
    color: '#34d399',
    params: {
      sunRadius: 34,
      planetRadius: 22,
      ringRadius: 94,
      planetCount: 3,
      teeth: 18
    },
    tags: ['gear', 'timing', 'compound'],
    complexity: 'advanced'
  },
  {
    type: 'slider-crank',
    label: 'Slider crank / piston',
    tagline: 'Rotary input to linear character push',
    description: 'Crank, connecting rod, slider rail, and piston output for Automataii crank-slider kit workflows.',
    color: '#22d3ee',
    params: {
      crankRadius: 48,
      rodLength: 155,
      sliderOffset: 0,
      railLength: 260,
      couplerPointFraction: 1
    },
    tags: ['linear', 'piston', 'crank-slider'],
    complexity: 'intro'
  },
  {
    type: 'quick-return',
    label: 'Quick-return slotted crank',
    tagline: 'Asymmetric rocker sweep',
    description: 'MechAnim-compatible quick-return/slotted-crank primitive for asymmetric reciprocating paths.',
    color: '#c084fc',
    params: {
      crankRadius: 46,
      pivotDistance: 160,
      pivotOffset: 34,
      rockerLength: 145,
      couplerPointDist: 54,
      couplerPointAngle: 0
    },
    tags: ['linear', 'quick-return', 'slot'],
    complexity: 'intermediate'
  },
  {
    type: 'scotch-yoke',
    label: 'Scotch yoke',
    tagline: 'Sinusoidal slot-and-pin slider',
    description: 'MechAnim-inspired yoke primitive: crank pin rides in a vertical slot to generate clean reciprocating motion.',
    color: '#f97316',
    params: {
      crankRadius: 62,
      slotHeight: 150,
      railLength: 280,
      yokeWidth: 110
    },
    tags: ['linear', 'slot', 'reciprocating'],
    complexity: 'intro'
  }
];

export const templateFor = (type: MechanismType): MechanismTemplate => {
  const template = mechanismTemplates.find((item) => item.type === type);
  if (!template) throw new Error(`Unknown mechanism type: ${type}`);
  return template;
};

export const createMechanism = (type: MechanismType, index = 0): MechanismConfig => {
  const template = templateFor(type);
  return {
    id: `${type}-${Date.now().toString(36)}-${index}`,
    name: template.label,
    type,
    partName: 'right_wrist',
    color: template.color,
    enabled: true,
    anchor: { x: 320 + index * 28, y: 260 + index * 18 },
    rotationDeg: type === 'cam-follower' ? -90 : 0,
    speed: 1,
    params: { ...template.params }
  };
};

const link = (start: string, end: string, role?: LinkSegment['role']): LinkSegment => ({ start, end, role });

const MIN_HANDLE_LENGTH = 4;
const MAX_HANDLE_LENGTH = 900;

const handleTarget = (config: MechanismConfig, target: Point): Point => ({
  x: finite(target.x, config.anchor.x),
  y: finite(target.y, config.anchor.y)
});

const boundedLength = (value: number, fallback: number): number => clamp(finite(value, fallback), MIN_HANDLE_LENGTH, MAX_HANDLE_LENGTH);
const boundedSignedLength = (value: number, fallback: number): number => clamp(finite(value, fallback), -MAX_HANDLE_LENGTH, MAX_HANDLE_LENGTH);
const angleTo = (origin: Point, target: Point): number => toDeg(Math.atan2(target.y - origin.y, target.x - origin.x));
const relativeDegrees = (degrees: number): number => (((finite(degrees) % 360) + 540) % 360) - 180;

const patchMechanismParams = (config: MechanismConfig, params: Record<string, number>, extra: Partial<MechanismConfig> = {}): MechanismConfig => ({
  ...config,
  ...extra,
  params: { ...config.params, ...params }
});

const patchMechanismAnchor = (config: MechanismConfig, anchor: Point): MechanismConfig => ({
  ...config,
  anchor: { ...anchor },
  params: { ...config.params }
});

const axisProjection = (origin: Point, target: Point, degrees: number): number => {
  const r = toRad(degrees);
  return (target.x - origin.x) * Math.cos(r) + (target.y - origin.y) * Math.sin(r);
};

const closestSegmentFraction = (a: Point, b: Point, target: Point): { fraction: number; distanceSq: number } => {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const lenSq = dx * dx + dy * dy;
  if (lenSq < 1e-8) {
    const d = distance(a, target);
    return { fraction: 0, distanceSq: d * d };
  }
  const t = clamp(((target.x - a.x) * dx + (target.y - a.y) * dy) / lenSq, 0, 1);
  const p = { x: a.x + dx * t, y: a.y + dy * t };
  const d = distance(p, target);
  return { fraction: t, distanceSq: d * d };
};

const fractionAlongFiveBarCoupler = (state: MechanismState, target: Point): number | undefined => {
  const c1 = state.positions.C1;
  const p = state.positions.P;
  const c2 = state.positions.C2;
  if (!c1 || !p || !c2) return undefined;
  const left = closestSegmentFraction(c1, p, target);
  const right = closestSegmentFraction(p, c2, target);
  return left.distanceSq <= right.distanceSq
    ? clamp(left.fraction * 0.5, 0, 0.5)
    : clamp(0.5 + right.fraction * 0.5, 0.5, 1);
};

export const applyMechanismHandleDrag = (
  config: MechanismConfig,
  handleName: string,
  rawTarget: Point,
  inputAngleDeg: number
): MechanismConfig => {
  const target = handleTarget(config, rawTarget);
  const state = computeMechanismState(config, inputAngleDeg);
  const driveAngle = inputAngleDeg * config.speed;

  if (['O1', 'G1', 'O', 'camCenter', 'inputCenter', 'sun'].includes(handleName)) {
    return patchMechanismAnchor(config, target);
  }

  switch (config.type) {
    case 'crank': {
      const center = state.positions.O ?? config.anchor;
      if (handleName === 'crankPin' || handleName === 'effector') {
        return patchMechanismParams(config, { crankRadius: boundedLength(distance(center, target), config.params.crankRadius) }, { rotationDeg: relativeDegrees(angleTo(center, target) - driveAngle) });
      }
      return config;
    }

    case 'four-bar': {
      const o1 = state.positions.O1 ?? config.anchor;
      const o4 = state.positions.O4;
      const a = state.positions.A;
      const b = state.positions.B;
      if (handleName === 'O4') {
        return patchMechanismParams(config, { groundLink: boundedLength(distance(o1, target), config.params.groundLink) }, { rotationDeg: angleTo(o1, target) });
      }
      if (handleName === 'A') {
        return patchMechanismParams(config, { inputLink: boundedLength(distance(o1, target), config.params.inputLink) }, { rotationDeg: relativeDegrees(angleTo(o1, target) - driveAngle) });
      }
      if (handleName === 'B' && a && o4) {
        return patchMechanismParams(config, {
          couplerLink: boundedLength(distance(a, target), config.params.couplerLink),
          outputLink: boundedLength(distance(o4, target), config.params.outputLink)
        });
      }
      if (handleName === 'effector' && a && b) {
        const couplerAngle = angleTo(a, b);
        return patchMechanismParams(config, {
          couplerPointDist: boundedLength(distance(a, target), config.params.couplerPointDist),
          couplerPointAngle: relativeDegrees(angleTo(a, target) - couplerAngle)
        });
      }
      return config;
    }

    case 'five-bar':
    case 'six-bar': {
      const g1 = state.positions.G1 ?? config.anchor;
      const g2 = state.positions.G2;
      const c1 = state.positions.C1;
      const c2 = state.positions.C2;
      const p = state.positions.P;
      if (handleName === 'G2') {
        return patchMechanismParams(config, { groundLink: boundedLength(distance(g1, target), config.params.groundLink) }, { rotationDeg: angleTo(g1, target) });
      }
      if (handleName === 'C1') {
        return patchMechanismParams(config, { inputLink: boundedLength(distance(g1, target), config.params.inputLink) }, { rotationDeg: relativeDegrees(angleTo(g1, target) - driveAngle) });
      }
      if (handleName === 'C2' && g2) {
        const secondarySpeed = finite(config.params.secondarySpeed, -1);
        return patchMechanismParams(config, {
          outputLink: boundedLength(distance(g2, target), config.params.outputLink),
          phase: relativeDegrees(angleTo(g2, target) - config.rotationDeg - driveAngle * secondarySpeed)
        });
      }
      if (handleName === 'P' && c1 && c2) {
        return patchMechanismParams(config, { couplerLink: boundedLength((distance(c1, target) + distance(c2, target)) / 2, config.params.couplerLink) });
      }
      if (handleName === 'effector') {
        const fraction = fractionAlongFiveBarCoupler(state, target);
        return fraction === undefined ? config : patchMechanismParams(config, { couplerCustomFraction: fraction });
      }
      if (config.type === 'six-bar' && handleName === 'G3') {
        return patchMechanismParams(config, { pivotHeight: boundedSignedLength(axisProjection(g1, target, config.rotationDeg + 90), config.params.pivotHeight) });
      }
      if (config.type === 'six-bar' && handleName === 'Q') {
        const g3 = state.positions.G3;
        return g3 ? patchMechanismParams(config, { rockerLink: boundedLength(distance(g3, target), config.params.rockerLink) }) : config;
      }
      return config;
    }

    case 'cam-follower': {
      const center = state.positions.camCenter ?? config.anchor;
      const contact = state.positions.contact;
      if (handleName === 'contact' || handleName === 'effector') {
        const camRadius = positive(config.params.camRadius, 58);
        return patchMechanismParams(config, { camOffset: boundedLength(Math.abs(distance(center, target) - camRadius), config.params.camOffset) }, { rotationDeg: relativeDegrees(angleTo(center, target) + 90) });
      }
      if (handleName === 'followerBase' && contact) {
        return patchMechanismParams(config, { followerLength: boundedLength(distance(contact, target), config.params.followerLength) });
      }
      return config;
    }

    case 'gear-pair': {
      const inputCenter = state.positions.inputCenter ?? config.anchor;
      const outputCenter = state.positions.outputCenter;
      if (handleName === 'outputCenter') {
        const inputRadius = positive(config.params.inputRadius, 48);
        const backlash = nonNegative(config.params.backlash, 0);
        return patchMechanismParams(config, { outputRadius: boundedLength(distance(inputCenter, target) - inputRadius - backlash, config.params.outputRadius) }, { rotationDeg: angleTo(inputCenter, target) });
      }
      if (handleName === 'inputPin') {
        return patchMechanismParams(config, { inputRadius: boundedLength(distance(inputCenter, target) / 0.72, config.params.inputRadius) });
      }
      if ((handleName === 'outputPin' || handleName === 'effector') && outputCenter) {
        return patchMechanismParams(config, { outputRadius: boundedLength(distance(outputCenter, target) / 0.72, config.params.outputRadius) });
      }
      return config;
    }

    case 'planetary-gear': {
      const sun = state.positions.sun ?? config.anchor;
      if (handleName.startsWith('planet') || handleName === 'effector') {
        const sunRadius = positive(config.params.sunRadius, 34);
        const planetRadius = boundedLength(distance(sun, target) - sunRadius, config.params.planetRadius);
        return patchMechanismParams(config, {
          planetRadius,
          ringRadius: boundedLength(sunRadius + planetRadius * 2, config.params.ringRadius)
        });
      }
      return config;
    }

    case 'slider-crank': {
      const center = state.positions.O ?? config.anchor;
      const crankPin = state.positions.crankPin;
      if (handleName === 'crankPin') {
        return patchMechanismParams(config, { crankRadius: boundedLength(distance(center, target), config.params.crankRadius) }, { rotationDeg: relativeDegrees(angleTo(center, target) - driveAngle) });
      }
      if (handleName === 'slider' && crankPin) {
        return patchMechanismParams(config, {
          rodLength: boundedLength(distance(crankPin, target), config.params.rodLength),
          sliderOffset: boundedSignedLength(axisProjection(center, target, config.rotationDeg + 90), config.params.sliderOffset)
        });
      }
      if (handleName === 'railA' || handleName === 'railB') {
        const rotationDeg = handleName === 'railA' ? relativeDegrees(angleTo(center, target) + 180) : angleTo(center, target);
        return patchMechanismParams(config, { railLength: boundedLength(distance(center, target) * 2, config.params.railLength) }, { rotationDeg });
      }
      if (handleName === 'effector' && crankPin) {
        return patchMechanismParams(config, { couplerPointFraction: clamp(distance(crankPin, target) / Math.max(1, distance(crankPin, state.positions.slider ?? target)), 0, 1.25) });
      }
      return config;
    }

    case 'quick-return': {
      const center = state.positions.O ?? config.anchor;
      const pivot = state.positions.pivot;
      const rockerTip = state.positions.rockerTip;
      if (handleName === 'crankPin') {
        return patchMechanismParams(config, { crankRadius: boundedLength(distance(center, target), config.params.crankRadius) }, { rotationDeg: relativeDegrees(angleTo(center, target) - driveAngle) });
      }
      if (handleName === 'pivot') {
        return patchMechanismParams(config, {
          pivotDistance: boundedSignedLength(axisProjection(center, target, config.rotationDeg), config.params.pivotDistance),
          pivotOffset: boundedSignedLength(axisProjection(center, target, config.rotationDeg + 90), config.params.pivotOffset)
        });
      }
      if (handleName === 'rockerTip' && pivot) {
        return patchMechanismParams(config, { rockerLength: boundedLength(distance(pivot, target), config.params.rockerLength) });
      }
      if ((handleName === 'effector' || handleName === 'slotOutput') && rockerTip && pivot) {
        const armAngle = angleTo(pivot, rockerTip);
        return patchMechanismParams(config, {
          couplerPointDist: boundedLength(distance(rockerTip, target), config.params.couplerPointDist),
          couplerPointAngle: relativeDegrees(angleTo(rockerTip, target) - armAngle)
        });
      }
      return config;
    }

    case 'scotch-yoke': {
      const center = state.positions.O ?? config.anchor;
      const yokeCenter = state.positions.yokeCenter;
      if (handleName === 'crankPin') {
        return patchMechanismParams(config, { crankRadius: boundedLength(distance(center, target), config.params.crankRadius) }, { rotationDeg: relativeDegrees(angleTo(center, target) - driveAngle) });
      }
      if ((handleName === 'slotA' || handleName === 'slotB') && yokeCenter) {
        return patchMechanismParams(config, { slotHeight: boundedLength(Math.abs(axisProjection(yokeCenter, target, config.rotationDeg + 90)) * 2, config.params.slotHeight) });
      }
      if ((handleName === 'yokeLeft' || handleName === 'yokeRight') && yokeCenter) {
        return patchMechanismParams(config, { yokeWidth: boundedLength(Math.abs(axisProjection(yokeCenter, target, config.rotationDeg)) * 2, config.params.yokeWidth) });
      }
      if (handleName === 'railA' || handleName === 'railB') {
        const rotationDeg = handleName === 'railA' ? relativeDegrees(angleTo(center, target) + 180) : angleTo(center, target);
        return patchMechanismParams(config, { railLength: boundedLength(distance(center, target) * 2, config.params.railLength) }, { rotationDeg });
      }
      if (handleName === 'yokeCenter' || handleName === 'effector') {
        return patchMechanismParams(config, { crankRadius: boundedLength(Math.abs(axisProjection(center, target, config.rotationDeg)), config.params.crankRadius) });
      }
      return config;
    }

    default:
      return config;
  }
};

export const computeMechanismState = (config: MechanismConfig, inputAngleDeg: number): MechanismState => {
  if (!config.enabled) return invalidState(config.type, config.anchor, 'Disabled');
  const angle = inputAngleDeg * config.speed;
  switch (config.type) {
    case 'crank':
      return computeCrank(config, angle);
    case 'four-bar':
      return computeFourBar(config, angle);
    case 'five-bar':
      return computeFiveBar(config, angle);
    case 'six-bar':
      return computeSixBar(config, angle);
    case 'cam-follower':
      return computeCamFollower(config, angle);
    case 'gear-pair':
      return computeGearPair(config, angle);
    case 'planetary-gear':
      return computePlanetaryGear(config, angle);
    case 'slider-crank':
      return computeSliderCrank(config, angle);
    case 'quick-return':
      return computeQuickReturn(config, angle);
    case 'scotch-yoke':
      return computeScotchYoke(config, angle);
    default:
      return invalidState(config.type, config.anchor, 'Unsupported mechanism');
  }
};

const computeFourBar = (config: MechanismConfig, inputAngleDeg: number): MechanismState => {
  const ground = positive(config.params.groundLink, 170);
  const input = positive(config.params.inputLink, 56);
  const coupler = positive(config.params.couplerLink, 150);
  const output = positive(config.params.outputLink, 120);
  const assembly = finite(config.params.assembly, 1) >= 0 ? 1 : -1;
  const o1 = config.anchor;
  const o4 = polar(o1, ground, config.rotationDeg);
  const a = polar(o1, input, config.rotationDeg + inputAngleDeg);
  const b = circleIntersection(a, coupler, o4, output, assembly > 0);

  if (!b) {
    return invalidState('four-bar', o1, 'Four-bar links cannot close at this angle');
  }

  const couplerAngle = toDeg(Math.atan2(b.y - a.y, b.x - a.x));
  const effector = polar(
    a,
    nonNegative(config.params.couplerPointDist, coupler * 0.5),
    couplerAngle + finite(config.params.couplerPointAngle, 0)
  );
  const shortest = Math.min(ground, input, coupler, output);
  const longest = Math.max(ground, input, coupler, output);
  const remaining = ground + input + coupler + output - shortest - longest;
  const grashof = shortest + longest <= remaining;
  return {
    type: 'four-bar',
    positions: { O1: o1, O4: o4, A: a, B: b, effector },
    forces: {
      O1: force(o1, input * 0.45, config.rotationDeg + inputAngleDeg + 180, 'reaction', 'ground reaction'),
      A: force(a, coupler * 0.28, couplerAngle, 'constraint', 'coupler load'),
      B: force(b, output * 0.3, couplerAngle + 180, 'reaction', 'output reaction'),
      effector: force(effector, distance(a, effector) * 0.25, couplerAngle + finite(config.params.couplerPointAngle, 0), 'applied', 'effector load')
    },
    links: [link('O1', 'O4', 'ground'), link('O1', 'A', 'input'), link('A', 'B', 'coupler'), link('B', 'O4', 'output'), link('A', 'effector', 'helper'), link('B', 'effector', 'helper')],
    effector,
    valid: true,
    safety: grashof ? safe('Grashof-compatible nominal linkage', { grashof }) : caution('Non-Grashof linkage: motion may rock through limited range', { grashof }),
    metadata: { ...parityMetadata(config, 4), ground, input, coupler, output, inputAngleDeg, grashof }
  };
};

const computeFiveBar = (config: MechanismConfig, inputAngleDeg: number): MechanismState => {
  const ground = positive(config.params.groundLink, 190);
  const left = positive(config.params.inputLink, 62);
  const right = positive(config.params.outputLink, 70);
  const floating = positive(config.params.couplerLink, 136);
  const p1 = config.anchor;
  const p2 = polar(p1, ground, config.rotationDeg);
  const j1 = polar(p1, left, config.rotationDeg + inputAngleDeg);
  const secondarySpeed = finite(config.params.secondarySpeed, -1);
  const phase = finite(config.params.phase, 180);
  const j2 = polar(p2, right, config.rotationDeg + phase + inputAngleDeg * secondarySpeed);
  const intersection = circleIntersection(j1, floating, j2, floating, true);
  const closureFallback = intersection === null;
  const p = intersection ?? midpoint(j1, j2);
  const fraction = clamp(finite(config.params.couplerCustomFraction, 0.5), 0, 1);
  const custom = interpolateCoupler(j1, p, j2, fraction);
  return {
    type: 'five-bar',
    positions: { G1: p1, G2: p2, C1: j1, C2: j2, P: p, effector: custom },
    forces: {
      G1: force(p1, left * 0.38, config.rotationDeg + inputAngleDeg + 180, 'reaction', 'left ground reaction'),
      G2: force(p2, right * 0.38, config.rotationDeg + phase + inputAngleDeg * secondarySpeed + 180, 'reaction', 'right ground reaction'),
      P: force(p, floating * (closureFallback ? 0.7 : 0.34), angleTo(p, custom), closureFallback ? 'constraint' : 'applied', 'floating coupler load'),
      effector: force(custom, distance(p, custom) * 0.4, angleTo(p, custom), 'applied', 'effector load')
    },
    links: [link('G1', 'G2', 'ground'), link('G1', 'C1', 'input'), link('G2', 'C2', 'input'), link('C1', 'P', 'coupler'), link('P', 'C2', 'coupler'), link('P', 'effector', 'helper')],
    effector: custom,
    valid: !closureFallback,
    safety: closureFallback ? caution('Five-bar cannot close at this angle; showing midpoint fallback', { closureFallback }) : safe('Five-bar solved with mirrored floating chain', { closureFallback }),
    metadata: { ...parityMetadata(config, 5), ground, left, right, floating, fraction, inputAngleDeg, closureFallback }
  };
};

const interpolateCoupler = (c1: Point, p: Point, c2: Point, fraction: number): Point => {
  if (fraction <= 0.5) {
    const local = fraction * 2;
    return { x: c1.x + (p.x - c1.x) * local, y: c1.y + (p.y - c1.y) * local };
  }
  const local = (fraction - 0.5) * 2;
  return { x: p.x + (c2.x - p.x) * local, y: p.y + (c2.y - p.y) * local };
};

const computeCrank = (config: MechanismConfig, inputAngleDeg: number): MechanismState => {
  const crankRadius = positive(config.params.crankRadius, 56);
  const hubRadius = nonNegative(config.params.hubRadius, 18);
  const outputOffset = finite(config.params.outputOffset, 0);
  const center = config.anchor;
  const crankPin = polar(center, crankRadius, config.rotationDeg + inputAngleDeg);
  const offsetPoint = outputOffset === 0 ? crankPin : polar(crankPin, outputOffset, config.rotationDeg + inputAngleDeg + 90);
  const effector = offsetPoint;
  return {
    type: 'crank',
    positions: { O: center, crankPin, effector },
    forces: {
      O: force(center, crankRadius * 0.34, config.rotationDeg + inputAngleDeg + 180, 'reaction', 'crank bearing reaction'),
      crankPin: force(crankPin, crankRadius * 0.22, config.rotationDeg + inputAngleDeg, 'applied', 'rotary output load'),
      effector: force(effector, Math.max(crankRadius, outputOffset) * 0.18, config.rotationDeg + inputAngleDeg, 'applied', 'effector load')
    },
    links: [link('O', 'crankPin', 'input'), link('crankPin', 'effector', 'helper')],
    effector,
    valid: true,
    safety: hubRadius >= crankRadius ? caution('Hub radius overlaps the crank pin', { hubRadius, crankRadius }) : safe('Rotary crank output finite', { hubRadius, crankRadius }),
    metadata: { ...parityMetadata(config), mechAnimType: 'crank', webOnlyDomain: true, crankRadius, hubRadius, outputOffset }
  };
};

const computeSixBar = (config: MechanismConfig, inputAngleDeg: number): MechanismState => {
  const base = computeFiveBar({ ...config, type: 'five-bar' }, inputAngleDeg);
  const ground = positive(config.params.groundLink, 220);
  const rocker = positive(config.params.rockerLink, 110);
  const pivotHeight = finite(config.params.pivotHeight, 0.6 * ground);
  const g1 = base.positions.G1;
  const g3 = polar(g1, pivotHeight, config.rotationDeg + 90);
  const p = base.positions.P;
  const dist = distance(g3, p);
  const q = dist < 1e-6 ? g3 : { x: g3.x + ((p.x - g3.x) * Math.min(rocker, dist)) / dist, y: g3.y + ((p.y - g3.y) * Math.min(rocker, dist)) / dist };
  const effector = q;
  return {
    ...base,
    type: 'six-bar',
    positions: { ...base.positions, G3: g3, Q: q, effector },
    links: [...base.links, link('G3', 'Q', 'output'), link('P', 'Q', 'helper')],
    effector,
    valid: base.valid,
    safety: !base.valid ? caution('Six-bar base linkage cannot close; showing fallback rocker pose', { baseValid: base.valid }) : dist > rocker * 1.75 ? caution('Rocker is extended near its travel limit', { rockerExtension: dist / rocker }) : safe('Six-bar rocker nominal', { baseValid: base.valid }),
    forces: {
      ...base.forces,
      G3: force(g3, rocker * 0.32, angleTo(g3, q), 'reaction', 'rocker ground reaction'),
      Q: force(q, Math.min(rocker, dist) * 0.42, angleTo(q, p), 'constraint', 'rocker constraint')
    },
    metadata: { ...base.metadata, ...parityMetadata(config, 6), rocker, pivotHeight }
  };
};

const computeCamFollower = (config: MechanismConfig, inputAngleDeg: number): MechanismState => {
  const camRadius = positive(config.params.camRadius, 58);
  const camOffset = nonNegative(config.params.camOffset, 18);
  const followerLength = positive(config.params.followerLength, 120);
  const lobes = clamp(Math.round(finite(config.params.camLobes, 1)), 1, MAX_CAM_LOBES);
  const harmonic = finite(config.params.profileHarmonic, 0.28);
  const center = config.anchor;
  const profile: Point[] = [];
  let contactRadius = camRadius;

  for (let i = 0; i < 120; i += 1) {
    const t = (i / 120) * Math.PI * 2;
    const r = Math.max(camRadius * 0.05, camRadius + camOffset * Math.sin(lobes * t) + camRadius * harmonic * Math.sin((lobes + 1) * t) * 0.25);
    const worldAngle = t + toRad(config.rotationDeg + inputAngleDeg);
    profile.push({ x: center.x + r * Math.cos(worldAngle), y: center.y + r * Math.sin(worldAngle) });
    if (Math.abs(Math.sin(worldAngle + Math.PI / 2)) < 0.05) contactRadius = Math.max(contactRadius, r);
  }

  const contact = polar(center, contactRadius, config.rotationDeg - 90);
  const followerBase = polar(contact, followerLength, config.rotationDeg - 90);
  const effector = contact;
  return {
    type: 'cam-follower',
    positions: { camCenter: center, contact, followerBase, effector },
    forces: {
      camCenter: force(center, camRadius * 0.35, config.rotationDeg + inputAngleDeg + 90, 'reaction', 'cam shaft reaction'),
      contact: force(contact, contactRadius * 0.28, config.rotationDeg - 90, 'constraint', 'follower contact normal'),
      followerBase: force(followerBase, followerLength * 0.18, config.rotationDeg + 90, 'applied', 'follower spring load')
    },
    links: [link('followerBase', 'contact', 'output')],
    effector,
    valid: true,
    safety: Math.abs(harmonic) > 1 ? caution('High harmonic may invert the cam profile', { harmonic }) : safe('Cam profile finite', { harmonic }),
    profile,
    metadata: { ...parityMetadata(config), camRadius, camOffset, followerLength, lobes, harmonic, profileD: pointsToPathD(profile, true) }
  };
};

const gear = (id: string, center: Point, radius: number, teeth: number, rotationDeg: number, role: GearVisual['role']): GearVisual => ({ id, center, radius, teeth, rotationDeg, role });

const computeGearPair = (config: MechanismConfig, inputAngleDeg: number): MechanismState => {
  const inputRadius = positive(config.params.inputRadius, 48);
  const outputRadius = positive(config.params.outputRadius, 72);
  const teeth = clamp(Math.round(finite(config.params.teeth, 16)), 6, MAX_GEAR_TEETH);
  const outputTeeth = clamp(Math.round(finite(config.params.outputTeeth, 24)), 6, MAX_GEAR_TEETH);
  const p1 = config.anchor;
  const p2 = polar(p1, inputRadius + outputRadius + nonNegative(config.params.backlash, 0), config.rotationDeg);
  const outputRotation = -inputAngleDeg * (inputRadius / outputRadius);
  const inputPin = polar(p1, inputRadius * 0.72, inputAngleDeg);
  const outputPin = polar(p2, outputRadius * 0.72, outputRotation);
  const effector = outputPin;
  return {
    type: 'gear-pair',
    positions: { inputCenter: p1, outputCenter: p2, inputPin, outputPin, effector },
    forces: {
      inputCenter: force(p1, inputRadius * 0.3, inputAngleDeg + 180, 'reaction', 'driver bearing reaction'),
      outputCenter: force(p2, outputRadius * 0.3, outputRotation + 180, 'reaction', 'output bearing reaction'),
      outputPin: force(outputPin, outputRadius * 0.18, outputRotation, 'applied', 'output torque proxy')
    },
    links: [link('inputCenter', 'inputPin', 'input'), link('outputCenter', 'outputPin', 'output'), link('inputCenter', 'outputCenter', 'ground')],
    effector,
    valid: true,
    safety: safe('Gear centers meshed', { backlash: nonNegative(config.params.backlash, 0) }),
    gears: [gear('input', p1, inputRadius, teeth, inputAngleDeg, 'input'), gear('output', p2, outputRadius, outputTeeth, outputRotation, 'output')],
    metadata: { ...parityMetadata(config), webOnlyDomain: true, pythonPresentationFamily: 'gear_train', ratio: outputRadius / inputRadius, teeth, outputTeeth }
  };
};

const computePlanetaryGear = (config: MechanismConfig, inputAngleDeg: number): MechanismState => {
  const sunRadius = positive(config.params.sunRadius, 34);
  const planetRadius = positive(config.params.planetRadius, 22);
  const ringRadius = Math.max(sunRadius + planetRadius * 2, positive(config.params.ringRadius, 94));
  const count = clamp(Math.round(finite(config.params.planetCount, 3)), 2, MAX_PLANET_COUNT);
  const center = config.anchor;
  const carrierRadius = sunRadius + planetRadius;
  const planetCenters: Point[] = [];
  const sunTeeth = clamp(Math.round(finite(config.params.teeth, 18)), 6, MAX_GEAR_TEETH);
  const gears: GearVisual[] = [gear('sun', center, sunRadius, sunTeeth, inputAngleDeg, 'sun')];

  for (let i = 0; i < count; i += 1) {
    const angle = config.rotationDeg + inputAngleDeg * 0.35 + (i / count) * 360;
    const planetCenter = polar(center, carrierRadius, angle);
    planetCenters.push(planetCenter);
    gears.push(gear(`planet-${i + 1}`, planetCenter, planetRadius, 12, -inputAngleDeg * 1.8, 'planet'));
  }
  gears.push(gear('ring', center, ringRadius, 48, 0, 'ring'));
  const effector = planetCenters[0] ?? center;
  const positions: Record<string, Point> = { sun: center, effector };
  planetCenters.forEach((p, i) => {
    positions[`planet${i + 1}`] = p;
  });
  return {
    type: 'planetary-gear',
    positions,
    forces: {
      sun: force(center, sunRadius * 0.42, inputAngleDeg + 180, 'reaction', 'sun bearing reaction'),
      effector: force(effector, planetRadius * 0.4, angleTo(center, effector), 'applied', 'carrier load proxy')
    },
    links: planetCenters.map((_, i) => link('sun', `planet${i + 1}`, 'helper')),
    effector,
    valid: true,
    safety: safe('Planetary train visualized', { planetCount: count }),
    gears,
    metadata: { ...parityMetadata(config), webOnlyDomain: true, pythonPresentationFamily: 'gear_train', sunRadius, planetRadius, ringRadius, count }
  };
};

const axis = (rotationDeg: number): { u: Point; n: Point } => {
  const r = toRad(rotationDeg);
  const u = { x: Math.cos(r), y: Math.sin(r) };
  const n = { x: -Math.sin(r), y: Math.cos(r) };
  return { u, n };
};

const addScaled = (origin: Point, u: Point, along: number, n?: Point, normal = 0): Point => ({
  x: origin.x + u.x * along + (n?.x ?? 0) * normal,
  y: origin.y + u.y * along + (n?.y ?? 0) * normal
});

const dotFrom = (origin: Point, point: Point, direction: Point): number => (point.x - origin.x) * direction.x + (point.y - origin.y) * direction.y;

const computeSliderCrank = (config: MechanismConfig, inputAngleDeg: number): MechanismState => {
  const crankRadius = positive(config.params.crankRadius, 48);
  const rodLength = positive(config.params.rodLength, 155);
  const sliderOffset = finite(config.params.sliderOffset, 0);
  const railLength = positive(config.params.railLength, 260);
  const fraction = clamp(finite(config.params.couplerPointFraction, 1), 0, 1.25);
  const center = config.anchor;
  const { u, n } = axis(config.rotationDeg);
  const crankPin = polar(center, crankRadius, config.rotationDeg + inputAngleDeg);
  const alongPin = dotFrom(center, crankPin, u);
  const normalPin = dotFrom(center, crankPin, n) - sliderOffset;
  const reachable = Math.abs(normalPin) <= rodLength;
  const rodAlong = reachable ? Math.sqrt(Math.max(0, rodLength * rodLength - normalPin * normalPin)) : 0;
  const sliderAlong = alongPin + rodAlong;
  const slider = addScaled(center, u, sliderAlong, n, sliderOffset);
  const railA = addScaled(center, u, -railLength * 0.5, n, sliderOffset);
  const railB = addScaled(center, u, railLength * 0.5, n, sliderOffset);
  const effector = {
    x: crankPin.x + (slider.x - crankPin.x) * fraction,
    y: crankPin.y + (slider.y - crankPin.y) * fraction
  };
  const nearRailEnd = Math.abs(sliderAlong) > railLength * 0.48;
  return {
    type: 'slider-crank',
    positions: { O: center, crankPin, slider, railA, railB, effector },
    forces: {
      O: force(center, crankRadius * 0.44, config.rotationDeg + inputAngleDeg + 180, 'reaction', 'crank bearing reaction'),
      slider: force(slider, Math.abs(sliderAlong) * 0.2, config.rotationDeg, 'constraint', 'slider rail load'),
      effector: force(effector, rodLength * 0.16, angleTo(crankPin, slider), 'applied', 'piston output load')
    },
    links: [link('railA', 'railB', 'ground'), link('O', 'crankPin', 'input'), link('crankPin', 'slider', 'coupler'), link('slider', 'effector', 'slider')],
    effector,
    valid: reachable,
    safety: !reachable ? caution('Connecting rod cannot reach the slider rail at this angle', { reachable }) : nearRailEnd ? caution('Slider near rail travel limit', { sliderAlong, railLength }) : safe('Slider-crank finite', { reachable }),
    metadata: { ...parityMetadata(config), pythonContentFamily: 'slider_crank', crankRadius, rodLength, sliderOffset, railLength, fraction, reachable, sliderAlong }
  };
};

const computeQuickReturn = (config: MechanismConfig, inputAngleDeg: number): MechanismState => {
  const crankRadius = positive(config.params.crankRadius, 46);
  const pivotDistance = finite(config.params.pivotDistance, 160);
  const pivotOffset = finite(config.params.pivotOffset, 34);
  const rockerLength = positive(config.params.rockerLength, 145);
  const couplerPointDist = nonNegative(config.params.couplerPointDist, 54);
  const couplerPointAngle = finite(config.params.couplerPointAngle, 0);
  const center = config.anchor;
  const { u, n } = axis(config.rotationDeg);
  const crankPin = polar(center, crankRadius, config.rotationDeg + inputAngleDeg);
  const pivot = addScaled(center, u, pivotDistance, n, pivotOffset);
  const armAngle = angleTo(pivot, crankPin);
  const rockerTip = polar(pivot, rockerLength, armAngle);
  const effector = polar(rockerTip, couplerPointDist, armAngle + couplerPointAngle);
  const slotOutput = {
    x: (crankPin.x + rockerTip.x) * 0.5,
    y: (crankPin.y + rockerTip.y) * 0.5
  };
  const pivotReach = distance(pivot, crankPin);
  return {
    type: 'quick-return',
    positions: { O: center, crankPin, pivot, rockerTip, slotOutput, effector },
    forces: {
      O: force(center, crankRadius * 0.42, config.rotationDeg + inputAngleDeg + 180, 'reaction', 'crank bearing reaction'),
      pivot: force(pivot, rockerLength * 0.35, armAngle + 180, 'reaction', 'rocker pivot reaction'),
      rockerTip: force(rockerTip, pivotReach * 0.2, armAngle, 'constraint', 'slotted arm contact'),
      effector: force(effector, couplerPointDist * 0.24, armAngle + couplerPointAngle, 'applied', 'quick-return output load')
    },
    links: [
      link('O', 'crankPin', 'input'),
      link('pivot', 'rockerTip', 'output'),
      link('crankPin', 'slotOutput', 'helper'),
      link('slotOutput', 'rockerTip', 'slider'),
      link('rockerTip', 'effector', 'helper')
    ],
    effector,
    valid: true,
    safety: pivotReach < crankRadius * 0.25 ? caution('Quick-return pivot is close to the crank pin', { pivotReach, crankRadius }) : safe('Quick-return slotted crank finite', { pivotReach }),
    metadata: { ...parityMetadata(config), mechAnimType: 'quick-return', webOnlyDomain: true, crankRadius, pivotDistance, pivotOffset, rockerLength, couplerPointDist, couplerPointAngle }
  };
};

const computeScotchYoke = (config: MechanismConfig, inputAngleDeg: number): MechanismState => {
  const crankRadius = positive(config.params.crankRadius, 62);
  const slotHeight = positive(config.params.slotHeight, 150);
  const railLength = positive(config.params.railLength, 280);
  const yokeWidth = positive(config.params.yokeWidth, 110);
  const center = config.anchor;
  const { u, n } = axis(config.rotationDeg);
  const crankPin = polar(center, crankRadius, config.rotationDeg + inputAngleDeg);
  const yokeAlong = dotFrom(center, crankPin, u);
  const yokeCenter = addScaled(center, u, yokeAlong);
  const slotA = addScaled(yokeCenter, u, 0, n, -slotHeight * 0.5);
  const slotB = addScaled(yokeCenter, u, 0, n, slotHeight * 0.5);
  const railA = addScaled(center, u, -railLength * 0.5);
  const railB = addScaled(center, u, railLength * 0.5);
  const yokeLeft = addScaled(yokeCenter, u, -yokeWidth * 0.5);
  const yokeRight = addScaled(yokeCenter, u, yokeWidth * 0.5);
  const effector = yokeCenter;
  return {
    type: 'scotch-yoke',
    positions: { O: center, crankPin, yokeCenter, slotA, slotB, railA, railB, yokeLeft, yokeRight, effector },
    forces: {
      O: force(center, crankRadius * 0.35, config.rotationDeg + inputAngleDeg + 180, 'reaction', 'crank bearing reaction'),
      yokeCenter: force(yokeCenter, Math.abs(yokeAlong) * 0.22, config.rotationDeg, 'constraint', 'slot reaction'),
      effector: force(effector, yokeWidth * 0.18, config.rotationDeg, 'applied', 'reciprocating output load')
    },
    links: [
      link('railA', 'railB', 'ground'),
      link('O', 'crankPin', 'input'),
      link('slotA', 'slotB', 'slider'),
      link('yokeLeft', 'yokeRight', 'coupler'),
      link('crankPin', 'yokeCenter', 'helper')
    ],
    effector,
    valid: true,
    safety: Math.abs(yokeAlong) > railLength * 0.48 ? caution('Yoke near rail travel limit', { yokeAlong, railLength }) : safe('Scotch yoke sinusoidal output', { yokeAlong }),
    metadata: { ...parityMetadata(config), webOnlyDomain: true, mechAnimInspired: true, crankRadius, slotHeight, railLength, yokeWidth, yokeAlong }
  };
};

export const generateTrace = (config: MechanismConfig, resolution = 96): Point[] => {
  const points: Point[] = [];
  const loops = config.type === 'five-bar' || config.type === 'six-bar' ? 2 : 1;
  const count = clamp(Math.round(finite(resolution, 96) * loops), 8, 720);
  for (let i = 0; i < count; i += 1) {
    const angle = (i / count) * 360 * loops;
    const state = computeMechanismState(config, angle);
    if (state.valid && Number.isFinite(state.effector.x) && Number.isFinite(state.effector.y)) {
      points.push(state.effector);
    }
  }
  return points;
};

export const mechanismBounds = (configs: MechanismConfig[], angle: number): ReturnType<typeof boundsOf> => {
  const points = configs.flatMap((config) => {
    const state = computeMechanismState(config, angle);
    return Object.values(state.positions);
  });
  return boundsOf(points);
};
