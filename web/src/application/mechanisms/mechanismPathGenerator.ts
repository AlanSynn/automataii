// Mechanism path generator - parity with Python domain/mechanisms compute modules

import { type Point, type PathData, type MechanismData, type MechanismParam, ProjectState } from '../../domain/project';

function toNumber(val: MechanismParam | undefined, fallback: number): number {
  if (typeof val === 'number') return val;
  if (typeof val === 'string') {
    const parsed = parseFloat(val);
    return isNaN(parsed) ? fallback : parsed;
  }
  return fallback;
}

interface FourBarParams {
  ground_link: number;
  input_link: number;
  coupler_link: number;
  output_link: number;
  base_x?: number;
  base_y?: number;
  samples?: number;
}

interface CamParams {
  cam_radius: number;
  cam_offset: number;
  follower_length: number;
  cam_lobes?: number;
  profile_harmonic?: number;
  center_x?: number;
  center_y?: number;
  samples?: number;
}

interface GearParams {
  radius: number;
  center_x?: number;
  center_y?: number;
  samples?: number;
}

interface PlanetaryParams {
  r_sun_mm: number;
  r_planet_mm: number;
  center_x?: number;
  center_y?: number;
  samples?: number;
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function solveFourBarOutputAngle(
  ground: number,
  inputLink: number,
  coupler: number,
  output: number,
  inputAngleRad: number
): number {
  const r1 = ground;
  const r2 = inputLink;
  const r3 = coupler;
  const r4 = output;

  const Ax = r2 * Math.cos(inputAngleRad);
  const Ay = r2 * Math.sin(inputAngleRad);

  const O4x = r1;
  const O4y = 0;

  const L = Math.sqrt((O4x - Ax) ** 2 + (O4y - Ay) ** 2);

  if (L < 1e-10 || r4 < 1e-10) {
    return 0;
  }

  if (L > r3 + r4 || L < Math.abs(r3 - r4)) {
    return -inputAngleRad * 0.3;
  }

  const alpha = Math.atan2(Ay - O4y, Ax - O4x);

  let cosBeta = (r4 * r4 + L * L - r3 * r3) / (2 * r4 * L);
  cosBeta = clamp(cosBeta, -1.0, 1.0);
  const beta = Math.acos(cosBeta);

  return alpha - beta;
}

export function generateFourBarPath(params: FourBarParams): Point[] {
  const {
    ground_link,
    input_link,
    coupler_link,
    output_link,
    base_x = 0,
    base_y = 0,
    samples = 72,
  } = params;

  const points: Point[] = [];
  const O1x = -ground_link / 2 + base_x;
  const O1y = base_y;
  const O4x = ground_link / 2 + base_x;
  const O4y = base_y;

  for (let i = 0; i < samples; i++) {
    const inputAngle = (i / samples) * 2 * Math.PI;

    const Ax = O1x + input_link * Math.cos(inputAngle);
    const Ay = O1y + input_link * Math.sin(inputAngle);

    const outputAngle = solveFourBarOutputAngle(
      ground_link,
      input_link,
      coupler_link,
      output_link,
      inputAngle
    );

    const Bx = O4x + output_link * Math.cos(outputAngle);
    const By = O4y + output_link * Math.sin(outputAngle);

    const couplerMidX = (Ax + Bx) / 2;
    const couplerMidY = (Ay + By) / 2;

    points.push({ x: couplerMidX, y: couplerMidY });
  }

  return points;
}

export function generateCamPath(params: CamParams): Point[] {
  const {
    cam_radius,
    cam_offset,
    follower_length,
    cam_lobes = 1,
    profile_harmonic = 0.3,
    center_x = 0,
    center_y = 0,
    samples = 72,
  } = params;

  const points: Point[] = [];

  for (let i = 0; i < samples; i++) {
    const camAngle = (i / samples) * 2 * Math.PI;

    const followerContactTheta = -Math.PI / 2;
    const thetaNormalized = (followerContactTheta - camAngle + 4 * Math.PI) % (2 * Math.PI);

    const contactRadius =
      cam_radius +
      cam_offset * Math.cos(cam_lobes * thetaNormalized) +
      cam_offset * profile_harmonic * Math.cos(2 * cam_lobes * thetaNormalized);

    const followerY = center_y - contactRadius - follower_length;

    points.push({ x: center_x, y: followerY });
  }

  return points;
}

export function generateGearPath(params: GearParams): Point[] {
  const { radius, center_x = 0, center_y = 0, samples = 72 } = params;

  const points: Point[] = [];

  for (let i = 0; i < samples; i++) {
    const angle = (i / samples) * 2 * Math.PI;
    const x = center_x + radius * Math.cos(angle);
    const y = center_y + radius * Math.sin(angle);
    points.push({ x, y });
  }

  return points;
}

export function generatePlanetaryPath(params: PlanetaryParams): Point[] {
  const { r_sun_mm, r_planet_mm, center_x = 0, center_y = 0, samples = 72 } = params;

  const points: Point[] = [];
  const orbitRadius = r_sun_mm + r_planet_mm;

  const planetToSunRatio = r_planet_mm / r_sun_mm;

  for (let i = 0; i < samples; i++) {
    const sunAngle = (i / samples) * 2 * Math.PI;
    const planetAngle = sunAngle * (1 + 1 / planetToSunRatio);

    const planetCenterX = center_x + orbitRadius * Math.cos(sunAngle);
    const planetCenterY = center_y + orbitRadius * Math.sin(sunAngle);

    const pointOnPlanetX = planetCenterX + r_planet_mm * 0.5 * Math.cos(planetAngle);
    const pointOnPlanetY = planetCenterY + r_planet_mm * 0.5 * Math.sin(planetAngle);

    points.push({ x: pointOnPlanetX, y: pointOnPlanetY });
  }

  return points;
}

export function generateMechanismPath(mechanism: MechanismData): Point[] {
  const { type, params } = mechanism;

  const normalizedType = type
    .toLowerCase()
    .replace('four_bar', 'fourbar')
    .replace('4_bar_linkage', 'fourbar')
    .replace('cam_follower', 'cam')
    .replace('planetary_gear', 'planetary');

  switch (normalizedType) {
    case 'fourbar':
      return generateFourBarPath({
        ground_link: toNumber(params.l1 ?? params.ground_link, 150),
        input_link: toNumber(params.l2 ?? params.input_link, 40),
        coupler_link: toNumber(params.l3 ?? params.coupler_link, 120),
        output_link: toNumber(params.l4 ?? params.output_link, 130),
        base_x: toNumber(params.base_x, 0),
        base_y: toNumber(params.base_y, 0),
        samples: toNumber(params.samples, 72),
      });

    case 'cam':
      return generateCamPath({
        cam_radius: toNumber(params.cam_radius ?? params.base_radius, 60),
        cam_offset: toNumber(params.cam_offset ?? params.lift, 20),
        follower_length: toNumber(params.follower_length ?? params.follower_radius, 100),
        cam_lobes: toNumber(params.cam_lobes, 1),
        profile_harmonic: toNumber(params.profile_harmonic, 0.3),
        center_x: toNumber(params.center_x, 0),
        center_y: toNumber(params.center_y, 0),
        samples: toNumber(params.samples, 72),
      });

    case 'gear':
      return generateGearPath({
        radius: toNumber(params.radius, 50),
        center_x: toNumber(params.center_x, 0),
        center_y: toNumber(params.center_y, 0),
        samples: toNumber(params.samples, 72),
      });

    case 'planetary':
      return generatePlanetaryPath({
        r_sun_mm: toNumber(params.r_sun_mm, 30),
        r_planet_mm: toNumber(params.r_planet_mm, 15),
        center_x: toNumber(params.center_x, 0),
        center_y: toNumber(params.center_y, 0),
        samples: toNumber(params.samples, 72),
      });

    default:
      console.warn(`Unknown mechanism type: ${type}, generating circular path`);
      return generateGearPath({ radius: 50, samples: 72 });
  }
}

export function applyMechanismPathToProject(
  state: ProjectState,
  mechanismId: string,
  partName?: string
): ProjectState {
  const mechanism = state.mechanisms[mechanismId];
  if (!mechanism) {
    console.warn(`Mechanism ${mechanismId} not found`);
    return state;
  }

  const targetPart = partName ?? mechanism.partName;
  if (!targetPart) {
    console.warn(`No part specified for mechanism ${mechanismId}`);
    return state;
  }

  const points = generateMechanismPath(mechanism);
  if (points.length === 0) {
    console.warn(`No path generated for mechanism ${mechanismId}`);
    return state;
  }

  const newPath: PathData = {
    partName: targetPart,
    points,
    isClosed: true,
    enabled: true,
    totalDuration: 1.0,
    timedPoints: points.map((p, i) => ({
      x: p.x,
      y: p.y,
      t: i / points.length,
    })),
  };

  const newPaths = { ...state.paths, [targetPart]: newPath };
  return state.withPaths(newPaths);
}

export function generateAllMechanismPaths(state: ProjectState): ProjectState {
  let result = state;

  for (const [mechId, mechanism] of Object.entries(state.mechanisms)) {
    if (mechanism.enabled !== false) {
      result = applyMechanismPathToProject(result, mechId, mechanism.partName);
    }
  }

  return result;
}
