import type { PathData, Point, TrackingAnnotation } from '../types';
import { clamp, decimatePoints, distance, isFinitePoint, MAX_TRACKING_POINTS } from './geometry';

const catmull = (p0: Point, p1: Point, p2: Point, p3: Point, t: number): Point => {
  const t2 = t * t;
  const t3 = t2 * t;
  return {
    x: 0.5 * ((2 * p1.x) + (-p0.x + p2.x) * t + (2 * p0.x - 5 * p1.x + 4 * p2.x - p3.x) * t2 + (-p0.x + 3 * p1.x - 3 * p2.x + p3.x) * t3),
    y: 0.5 * ((2 * p1.y) + (-p0.y + p2.y) * t + (2 * p0.y - 5 * p1.y + 4 * p2.y - p3.y) * t2 + (-p0.y + 3 * p1.y - 3 * p2.y + p3.y) * t3)
  };
};

export const smoothTrackingPoints = (points: Point[], closed = false, samplesPerSegment = 8): Point[] => {
  const clean = decimatePoints(points.filter(isFinitePoint), MAX_TRACKING_POINTS);
  if (clean.length < 3) return clean;
  const requestedSamples = Math.max(1, Math.min(24, Math.round(samplesPerSegment)));
  const result: Point[] = [];
  const count = closed ? clean.length : clean.length - 1;
  const samples = Math.max(1, Math.min(requestedSamples, Math.floor(MAX_TRACKING_POINTS / Math.max(1, count))));
  for (let i = 0; i < count; i += 1) {
    const p0 = clean[(i - 1 + clean.length) % clean.length] ?? clean[0];
    const p1 = clean[i];
    const p2 = clean[(i + 1) % clean.length];
    const p3 = clean[(i + 2) % clean.length] ?? clean[clean.length - 1];
    for (let s = 0; s < samples; s += 1) result.push(catmull(p0, p1, p2, p3, s / samples));
  }
  if (!closed) result.push(clean[clean.length - 1]);
  return decimatePoints(result.filter(isFinitePoint), MAX_TRACKING_POINTS);
};

export const createTrackingAnnotation = (sourceName: string, sourceKind: TrackingAnnotation['sourceKind'], points: Point[], closed = false, duration = 2.4): TrackingAnnotation => ({
  id: `tracking-${Date.now().toString(36)}`,
  sourceName,
  sourceKind,
  points: decimatePoints(points.filter(isFinitePoint), MAX_TRACKING_POINTS),
  smoothedPoints: smoothTrackingPoints(points, closed),
  isClosed: closed,
  duration: clamp(duration, 0.25, 120),
  createdAt: new Date().toISOString()
});

export const trackingToPath = (annotation: TrackingAnnotation, partName: string): PathData => {
  const points = annotation.smoothedPoints.length > 1 ? annotation.smoothedPoints : annotation.points;
  const bounded = decimatePoints(points, MAX_TRACKING_POINTS);
  const total = bounded.slice(1).reduce((sum, point, index) => sum + distance(bounded[index], point), 0);
  return {
    partName,
    points: bounded,
    totalDuration: Math.max(0.25, annotation.duration || Math.max(0.6, total / 180)),
    isClosed: annotation.isClosed,
    enabled: true
  };
};

export const normalizeTrackerPoint = (clientPoint: Point, bounds: { left: number; top: number; width: number; height: number }, viewBoxWidth = 1120, viewBoxHeight = 760): Point => ({
  x: ((clientPoint.x - bounds.left) / Math.max(1, bounds.width)) * viewBoxWidth,
  y: ((clientPoint.y - bounds.top) / Math.max(1, bounds.height)) * viewBoxHeight
});
