import type { BoneData, JointData, PartData, Point, SkeletonData, TrackingAnnotation, Transform, VisionAssistState } from '../types';
import { boundsOf, clamp, distance } from './geometry';

export interface VisionAssistResult {
  skeleton: SkeletonData;
  parts: Record<string, PartData>;
  pathPoints: Point[];
  status: VisionAssistState;
  stages: VisionAssistStage[];
  parity: VisionParityClassification;
}

export interface VisionAssistStage {
  id: 'preprocess' | 'tracking-normalization' | 'skeleton-inference' | 'part-classification' | 'parity-classification';
  label: string;
  status: 'complete' | 'warning' | 'blocked';
  evidence: string;
}

export interface VisionParityClassification {
  mode: 'browser-safe' | 'insufficient-input';
  pythonReference: string;
  nonWebInfrastructure: string[];
  browserSafeRationale: string;
}

const transform = (point: Point, scale = 1): Transform => ({ x: point.x, y: point.y, rotation: 0, scale });

const joint = (id: string, name: string, position: Point, parent?: string): JointData => ({
  id,
  name,
  position,
  parent,
  isLocked: false,
  bendDirection: 1
});

const part = (name: string, anchorJoint: string, fillColor: string, zIndex: number, position: Point, scale = 1): PartData => ({
  name,
  texturePath: '',
  maskPath: '',
  anchorJoint,
  transform: transform(position, scale),
  zIndex,
  fillColor,
  opacity: 0.84,
  fixed: false,
  group: 'vision-assist'
});

const finite = (point: Point): boolean => Number.isFinite(point.x) && Number.isFinite(point.y);

const sample = (points: Point[], ratio: number): Point => points[Math.min(points.length - 1, Math.max(0, Math.round((points.length - 1) * ratio)))] ?? { x: 0, y: 0 };

export const inferVisionAssistFromTracking = (annotation?: TrackingAnnotation): VisionAssistResult => {
  const points = (annotation?.smoothedPoints.length ? annotation.smoothedPoints : annotation?.points ?? []).filter(finite);
  const parityInfrastructure = ['ONNX detector', 'OpenCV segmentation', 'desktop filesystem model loading'];
  if (points.length < 2) {
    const empty: SkeletonData = { joints: { root: joint('root', 'Root', { x: 0, y: 0 }) }, bones: [], rootJoint: 'root' };
    return {
      skeleton: empty,
      parts: {},
      pathPoints: [],
      status: {
        confidence: 0,
        warnings: ['Need at least two tracking points for browser-safe vision assist; Python ONNX/OpenCV inference remains non-web infrastructure'],
        inferredJointCount: 1,
        inferredPartCount: 0,
        parityMode: 'insufficient-input',
        nonWebInfrastructure: parityInfrastructure
      },
      stages: [
        { id: 'preprocess', label: 'Preprocess media/tracking input', status: 'blocked', evidence: 'No usable tracking path' },
        { id: 'tracking-normalization', label: 'Normalize tracking points', status: 'blocked', evidence: `${points.length} finite point(s)` },
        { id: 'skeleton-inference', label: 'Infer browser skeleton', status: 'blocked', evidence: 'Requires at least two points' },
        { id: 'part-classification', label: 'Classify browser parts', status: 'blocked', evidence: 'No skeleton generated' },
        { id: 'parity-classification', label: 'Classify desktop/web vision parity', status: 'warning', evidence: 'Browser-safe fallback, not ONNX/OpenCV execution' }
      ],
      parity: {
        mode: 'insufficient-input',
        pythonReference: 'src/automataii/domain/animation/image_to_annotations.py',
        nonWebInfrastructure: parityInfrastructure,
        browserSafeRationale: 'The browser app uses manual tracking and deterministic rig inference instead of loading desktop ONNX/OpenCV assets.'
      }
    };
  }

  const bounds = boundsOf(points);
  const center = { x: bounds.minX + bounds.width / 2, y: bounds.minY + bounds.height / 2 };
  const rootPoint = { x: center.x, y: center.y + bounds.height * 0.18 };
  const spinePoint = { x: center.x, y: center.y - bounds.height * 0.12 };
  const headPoint = { x: center.x, y: bounds.minY - Math.max(18, bounds.height * 0.1) };
  const first = sample(points, 0);
  const quarter = sample(points, 0.25);
  const half = sample(points, 0.5);
  const threeQuarter = sample(points, 0.75);
  const last = sample(points, 1);

  const joints: Record<string, JointData> = {
    root: joint('root', 'Root', rootPoint),
    spine: joint('spine', 'Spine', spinePoint, 'root'),
    head: joint('head', 'Head', headPoint, 'spine'),
    left_wrist: joint('left_wrist', 'Left wrist', first, 'spine'),
    right_wrist: joint('right_wrist', 'Right wrist', half, 'spine'),
    left_ankle: joint('left_ankle', 'Left ankle', quarter, 'root'),
    right_ankle: joint('right_ankle', 'Right ankle', threeQuarter, 'root'),
    tail: joint('tail', 'Tail / end effector', last, 'root')
  };
  const bones: BoneData[] = Object.values(joints).filter((item) => item.parent).map((item) => ({ fromJoint: item.parent as string, toJoint: item.id }));
  const skeleton = { joints, bones, rootJoint: 'root' };
  const diagonal = Math.max(1, Math.hypot(bounds.width, bounds.height));
  const pathTravel = points.slice(1).reduce((sum, point, index) => sum + distance(points[index], point), 0);
  const confidence = clamp(points.length / 32, 0.25, 0.92) * clamp(pathTravel / diagonal, 0.35, 1.15);
  const parts: Record<string, PartData> = {
    torso: part('torso', 'spine', 'rgba(56,189,248,0.34)', 1, { x: 0, y: -36 }, clamp(diagonal / 260, 0.65, 1.5)),
    head: part('head', 'head', 'rgba(251,146,60,0.44)', 3, { x: 0, y: 0 }, clamp(diagonal / 320, 0.55, 1.2)),
    left_arm: part('left_arm', 'left_wrist', 'rgba(167,139,250,0.38)', 2, { x: 0, y: 0 }, 1),
    right_arm: part('right_arm', 'right_wrist', 'rgba(52,211,153,0.38)', 2, { x: 0, y: 0 }, 1),
    left_leg: part('left_leg', 'left_ankle', 'rgba(244,114,182,0.34)', 0, { x: 0, y: 0 }, 1),
    right_leg: part('right_leg', 'right_ankle', 'rgba(250,204,21,0.32)', 0, { x: 0, y: 0 }, 1)
  };

  const warnings = confidence < 0.45 ? ['Low-confidence rig: add more manual tracking points'] : [];
  warnings.push('Browser-safe vision parity: deterministic tracking-based rig inference; ONNX/OpenCV desktop model loading is classified as non-web infrastructure');
  return {
    skeleton,
    parts,
    pathPoints: points,
    status: {
      lastRunAt: new Date().toISOString(),
      confidence: Math.min(0.96, confidence),
      warnings,
      inferredJointCount: Object.keys(joints).length,
      inferredPartCount: Object.keys(parts).length,
      parityMode: 'browser-safe',
      nonWebInfrastructure: parityInfrastructure
    },
    stages: [
      { id: 'preprocess', label: 'Preprocess media/tracking input', status: 'complete', evidence: `${points.length} finite tracking points` },
      { id: 'tracking-normalization', label: 'Normalize tracking points', status: 'complete', evidence: `${Math.round(bounds.width)}×${Math.round(bounds.height)} bounds` },
      { id: 'skeleton-inference', label: 'Infer browser skeleton', status: 'complete', evidence: `${Object.keys(joints).length} joints` },
      { id: 'part-classification', label: 'Classify browser parts', status: 'complete', evidence: `${Object.keys(parts).length} parts` },
      { id: 'parity-classification', label: 'Classify desktop/web vision parity', status: 'warning', evidence: 'Browser-safe inference replaces non-web ONNX/OpenCV model runtime' }
    ],
    parity: {
      mode: 'browser-safe',
      pythonReference: 'src/automataii/domain/animation/image_to_annotations.py',
      nonWebInfrastructure: parityInfrastructure,
      browserSafeRationale: 'Manual tracking, smoothing, deterministic joint inference, and editable generated parts preserve the web workflow without shipping desktop ML assets.'
    }
  };
};
