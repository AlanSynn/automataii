import type { MechanismConfig, PathData, Point } from '../types';
import { boundsOf, distance } from './geometry';
import { generateTrace } from './mechanisms';

export interface MotionAnalysis {
  pointCount: number;
  bounds: ReturnType<typeof boundsOf>;
  pathLength: number;
  meanStep: number;
  maxStep: number;
  closureError: number;
  warnings: string[];
}

export interface MechanismAnalysis extends MotionAnalysis {
  mechanismId: string;
  mechanismName: string;
  traceCoverage: number;
}

const finitePoint = (point: Point): boolean => Number.isFinite(point.x) && Number.isFinite(point.y);

export const snapPoint = (point: Point, enabled = false, gridSize = 16): Point => {
  if (!enabled) return point;
  const grid = Math.max(1, Math.abs(gridSize));
  return { x: Math.round(point.x / grid) * grid, y: Math.round(point.y / grid) * grid };
};

export const analyzePoints = (points: Point[], closed = false): MotionAnalysis => {
  const clean = points.filter(finitePoint);
  const bounds = boundsOf(clean);
  if (clean.length < 2) {
    return { pointCount: clean.length, bounds, pathLength: 0, meanStep: 0, maxStep: 0, closureError: 0, warnings: ['Need at least two points for motion analysis'] };
  }
  const steps = clean.slice(1).map((point, index) => distance(clean[index], point));
  const closing = closed ? distance(clean[clean.length - 1], clean[0]) : 0;
  const pathLength = steps.reduce((sum, step) => sum + step, closing);
  const allSteps = closed ? [...steps, closing] : steps;
  const meanStep = allSteps.reduce((sum, step) => sum + step, 0) / allSteps.length;
  const maxStep = Math.max(...allSteps);
  const closureError = distance(clean[clean.length - 1], clean[0]);
  const warnings: string[] = [];
  if (closed && closureError > Math.max(18, Math.hypot(bounds.width, bounds.height) * 0.12)) warnings.push('Closed path has a visible seam; consider smoothing or moving endpoints');
  if (maxStep > meanStep * 3.2) warnings.push('Large jump detected; resample or add intermediate points');
  if (pathLength < 10) warnings.push('Motion path is very short');
  return { pointCount: clean.length, bounds, pathLength, meanStep, maxStep, closureError, warnings };
};

export const analyzePath = (path?: PathData): MotionAnalysis => analyzePoints(path?.points ?? [], path?.isClosed ?? false);

export const analyzeMechanismTrace = (mechanism: MechanismConfig, resolution = 96): MechanismAnalysis => {
  const trace = generateTrace(mechanism, resolution);
  const analysis = analyzePoints(trace, true);
  const traceCoverage = Math.hypot(analysis.bounds.width, analysis.bounds.height);
  return { ...analysis, mechanismId: mechanism.id, mechanismName: mechanism.name, traceCoverage };
};
