import type { MechanismConfig, MechanismType, PathData, Point } from '../types';
import { boundsOf, clamp, distance } from './geometry';
import { computeMechanismState, createMechanism, generateTrace, mechanismTemplates } from './mechanisms';

export interface FitResult {
  candidate: MechanismConfig;
  initialScore: number;
  score: number;
  iterations: number;
  improved: boolean;
}

export interface Recommendation {
  type: MechanismType;
  label: string;
  reason: string;
  score: number;
}

const lcg = (seed: number): () => number => {
  let state = seed >>> 0;
  return () => {
    state = (1664525 * state + 1013904223) >>> 0;
    return state / 0xffffffff;
  };
};

const finitePoint = (point: Point): boolean => Number.isFinite(point.x) && Number.isFinite(point.y);

const nearestDistance = (point: Point, targets: Point[]): number => targets.reduce((best, target) => Math.min(best, distance(point, target)), Number.POSITIVE_INFINITY);

export const scoreTraceToPath = (trace: Point[], target: Point[]): number => {
  const cleanTrace = trace.filter(finitePoint);
  const cleanTarget = target.filter(finitePoint);
  if (cleanTrace.length === 0 || cleanTarget.length === 0) return Number.POSITIVE_INFINITY;
  const targetBounds = boundsOf(cleanTarget);
  const normalizer = Math.max(1, Math.hypot(targetBounds.width, targetBounds.height));
  const forward = cleanTrace.reduce((sum, point) => sum + nearestDistance(point, cleanTarget), 0) / cleanTrace.length;
  const backward = cleanTarget.reduce((sum, point) => sum + nearestDistance(point, cleanTrace), 0) / cleanTarget.length;
  return (forward * 0.55 + backward * 0.45) / normalizer;
};

const parameterStep = (key: string, value: number): number => {
  if (key.toLowerCase().includes('speed') || key.toLowerCase().includes('fraction')) return 0.08;
  if (key.toLowerCase().includes('assembly')) return 2;
  if (key.toLowerCase().includes('phase') || key.toLowerCase().includes('angle')) return 10;
  return Math.max(2, Math.abs(value) * 0.12);
};

const mutate = (config: MechanismConfig, rand: () => number, temperature: number): MechanismConfig => {
  const params = { ...config.params };
  const keys = Object.keys(params);
  const edits = Math.max(1, Math.ceil(keys.length * 0.3));
  for (let i = 0; i < edits; i += 1) {
    const key = keys[Math.floor(rand() * keys.length)];
    const value = params[key];
    const delta = (rand() * 2 - 1) * parameterStep(key, value) * temperature;
    if (key.toLowerCase().includes('assembly')) params[key] = value >= 0 ? -1 : 1;
    else if (key.toLowerCase().includes('fraction')) params[key] = clamp(value + delta, 0, 1.25);
    else if (key.toLowerCase().includes('count') || key.toLowerCase().includes('lobes') || key.toLowerCase().includes('teeth')) params[key] = Math.round(clamp(value + delta, 1, 256));
    else params[key] = clamp(value + delta, -720, 900);
  }
  const anchor = {
    x: config.anchor.x + (rand() * 2 - 1) * 24 * temperature,
    y: config.anchor.y + (rand() * 2 - 1) * 24 * temperature
  };
  return { ...config, anchor, rotationDeg: config.rotationDeg + (rand() * 2 - 1) * 6 * temperature, params };
};

export const fitMechanismToPath = (config: MechanismConfig, path: PathData, iterations = 180, seed = 42): FitResult => {
  const target = path.points;
  const initialTrace = generateTrace(config, 72);
  const initialScore = scoreTraceToPath(initialTrace, target);
  let best = config;
  let bestScore = initialScore;
  const rand = lcg(seed);
  const safeIterations = Math.max(1, Math.min(1200, Math.round(iterations)));

  for (let i = 0; i < safeIterations; i += 1) {
    const temperature = 1 - i / safeIterations;
    const candidate = mutate(best, rand, Math.max(0.18, temperature));
    const state = computeMechanismState(candidate, (i * 137.5) % 360);
    if (!state.valid) continue;
    const score = scoreTraceToPath(generateTrace(candidate, 72), target);
    if (score < bestScore) {
      best = candidate;
      bestScore = score;
    }
  }

  return { candidate: best, initialScore, score: bestScore, iterations: safeIterations, improved: bestScore <= initialScore };
};

export const recommendMechanismsForPath = (path?: PathData): Recommendation[] => {
  if (!path || path.points.length < 2) {
    return mechanismTemplates.map((template, index) => ({ type: template.type, label: template.label, reason: 'Ready for freeform exploration', score: 1 - index * 0.04 }));
  }
  const bounds = boundsOf(path.points);
  const aspect = bounds.width / Math.max(1, bounds.height);
  const closedBonus = path.isClosed ? 0.2 : 0;
  const linearBonus = aspect > 2.1 || aspect < 0.48 ? 0.34 : 0;
  const loopBonus = path.isClosed ? 0.28 : 0;
  const scored = mechanismTemplates.map((template): Recommendation => {
    let score = 0.45;
    let reason = 'Balanced candidate for the target trace';
    if (template.tags.includes('linear')) {
      score += linearBonus + (path.isClosed ? -0.08 : 0.18);
      reason = 'Linear travel matches elongated or push/pull paths';
    }
    if (template.tags.includes('linkage')) {
      score += loopBonus + closedBonus;
      reason = 'Linkage traces are strong for closed drawn loops';
    }
    if (template.tags.includes('cam')) {
      score += path.isClosed ? 0.16 : 0.08;
      reason = 'Cam follower can encode repeated rise/fall motion';
    }
    if (template.tags.includes('gear')) {
      score += 0.05;
      reason = 'Gear timing coordinates character motion with ratios';
    }
    return { type: template.type, label: template.label, reason, score };
  });
  return scored.sort((a, b) => b.score - a.score).slice(0, 5);
};

export const createRecommendedMechanism = (path: PathData | undefined, index: number): MechanismConfig => {
  const recommendation = recommendMechanismsForPath(path)[0];
  return createMechanism(recommendation.type, index);
};
