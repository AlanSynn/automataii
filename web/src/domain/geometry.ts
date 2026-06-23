import type { Point } from '../types';

export const EPSILON = 1e-7;
export const MAX_PATH_POINTS = 5000;
export const MAX_TRACKING_POINTS = 5000;
export const MAX_RESAMPLE_POINTS = 2000;

export const finite = (value: unknown, fallback = 0): number => {
  const num = Number(value);
  return Number.isFinite(num) ? num : fallback;
};

export const positive = (value: unknown, fallback = 1): number => {
  const num = finite(value, fallback);
  return num > 0 ? num : fallback;
};

export const nonNegative = (value: unknown, fallback = 0): number => {
  const num = finite(value, fallback);
  return num >= 0 ? num : fallback;
};

export const clamp = (value: number, min: number, max: number): number => Math.max(min, Math.min(max, value));

export const toRad = (degrees: number): number => (degrees * Math.PI) / 180;
export const toDeg = (radians: number): number => (radians * 180) / Math.PI;

export const point = (x: unknown, y: unknown): Point => ({ x: finite(x), y: finite(y) });

export const add = (a: Point, b: Point): Point => ({ x: a.x + b.x, y: a.y + b.y });
export const subtract = (a: Point, b: Point): Point => ({ x: a.x - b.x, y: a.y - b.y });
export const scale = (p: Point, amount: number): Point => ({ x: p.x * amount, y: p.y * amount });
export const distance = (a: Point, b: Point): number => Math.hypot(a.x - b.x, a.y - b.y);
export const midpoint = (a: Point, b: Point): Point => ({ x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 });

export const isFinitePoint = (p: Point): boolean => Number.isFinite(p.x) && Number.isFinite(p.y);

export const decimatePoints = (points: Point[], maxPoints = MAX_PATH_POINTS): Point[] => {
  const limit = Math.max(1, Math.floor(finite(maxPoints, MAX_PATH_POINTS)));
  const clean = points.filter(isFinitePoint);
  if (clean.length <= limit) return clean;
  if (limit === 1) return [clean[0]];
  const last = clean.length - 1;
  return Array.from({ length: limit }, (_, index) => clean[Math.round((index * last) / (limit - 1))]);
};

export const rotateAround = (p: Point, origin: Point, degrees: number): Point => {
  const angle = toRad(degrees);
  const s = Math.sin(angle);
  const c = Math.cos(angle);
  const dx = p.x - origin.x;
  const dy = p.y - origin.y;
  return {
    x: origin.x + dx * c - dy * s,
    y: origin.y + dx * s + dy * c
  };
};

export const polar = (origin: Point, radius: number, degrees: number): Point => {
  const angle = toRad(degrees);
  return {
    x: origin.x + radius * Math.cos(angle),
    y: origin.y + radius * Math.sin(angle)
  };
};

export const circleIntersection = (
  centerA: Point,
  radiusA: number,
  centerB: Point,
  radiusB: number,
  preferUpper = true
): Point | null => {
  const dx = centerB.x - centerA.x;
  const dy = centerB.y - centerA.y;
  const d = Math.hypot(dx, dy);

  if (d < EPSILON || d > radiusA + radiusB + EPSILON || d < Math.abs(radiusA - radiusB) - EPSILON) {
    return null;
  }

  const a = (radiusA * radiusA - radiusB * radiusB + d * d) / (2 * d);
  const hSq = radiusA * radiusA - a * a;
  const h = Math.sqrt(Math.max(0, hSq));
  const xm = centerA.x + (a * dx) / d;
  const ym = centerA.y + (a * dy) / d;
  const rx = (-dy * h) / d;
  const ry = (dx * h) / d;

  return preferUpper ? { x: xm + rx, y: ym + ry } : { x: xm - rx, y: ym - ry };
};

export const pathLength = (points: Point[], closed = false): number => {
  if (points.length < 2) return 0;
  let total = 0;
  for (let i = 1; i < points.length; i += 1) {
    total += distance(points[i - 1], points[i]);
  }
  if (closed) total += distance(points[points.length - 1], points[0]);
  return total;
};

export const boundsOf = (points: Point[]): { minX: number; minY: number; maxX: number; maxY: number; width: number; height: number; cx: number; cy: number } => {
  let minX = Number.POSITIVE_INFINITY;
  let maxX = Number.NEGATIVE_INFINITY;
  let minY = Number.POSITIVE_INFINITY;
  let maxY = Number.NEGATIVE_INFINITY;
  for (const p of points) {
    if (!isFinitePoint(p)) continue;
    minX = Math.min(minX, p.x);
    maxX = Math.max(maxX, p.x);
    minY = Math.min(minY, p.y);
    maxY = Math.max(maxY, p.y);
  }
  if (!Number.isFinite(minX) || !Number.isFinite(maxX) || !Number.isFinite(minY) || !Number.isFinite(maxY)) {
    return { minX: 0, minY: 0, maxX: 0, maxY: 0, width: 0, height: 0, cx: 0, cy: 0 };
  }
  return {
    minX,
    minY,
    maxX,
    maxY,
    width: maxX - minX,
    height: maxY - minY,
    cx: (minX + maxX) / 2,
    cy: (minY + maxY) / 2
  };
};

export const resamplePath = (points: Point[], count: number, closed = false): Point[] => {
  const targetCount = clamp(Math.round(finite(count, points.length || 1)), 1, MAX_RESAMPLE_POINTS);
  const clean = decimatePoints(points, MAX_PATH_POINTS);
  if (clean.length === 0) return [];
  if (clean.length === 1 || targetCount <= 1) return [clean[0]];

  const source = closed ? [...clean, clean[0]] : [...clean];
  const segmentLengths: number[] = [];
  let total = 0;
  for (let i = 1; i < source.length; i += 1) {
    const len = distance(source[i - 1], source[i]);
    segmentLengths.push(len);
    total += len;
  }
  if (total < EPSILON) return Array.from({ length: targetCount }, () => clean[0]);

  const out: Point[] = [];
  for (let i = 0; i < targetCount; i += 1) {
    const target = (i / Math.max(1, targetCount - 1)) * total;
    let walked = 0;
    let chosen = source[source.length - 1];
    for (let s = 0; s < segmentLengths.length; s += 1) {
      const seg = segmentLengths[s];
      if (walked + seg >= target) {
        const t = seg < EPSILON ? 0 : (target - walked) / seg;
        chosen = {
          x: source[s].x + (source[s + 1].x - source[s].x) * t,
          y: source[s].y + (source[s + 1].y - source[s].y) * t
        };
        break;
      }
      walked += seg;
    }
    out.push(chosen);
  }
  return out;
};

export const pointsToPathD = (points: Point[], close = false): string => {
  if (points.length === 0) return '';
  const [first, ...rest] = points;
  const body = rest.map((p) => `L ${p.x.toFixed(2)} ${p.y.toFixed(2)}`).join(' ');
  return `M ${first.x.toFixed(2)} ${first.y.toFixed(2)} ${body}${close ? ' Z' : ''}`.trim();
};
