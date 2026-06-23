import type { MechanismConfig, Point, SafetyLevel } from '../types';
import { clamp, distance, finite } from './geometry';
import { computeMechanismState } from './mechanisms';

export interface PhysicsSample {
  angleDeg: number;
  time: number;
  position: Point;
  velocity: Point;
  acceleration: Point;
  speed: number;
  accelerationMagnitude: number;
  kineticEnergy: number;
  valid: boolean;
}

export interface PhysicsReport {
  mechanismId: string;
  mechanismName: string;
  status: SafetyLevel;
  samples: PhysicsSample[];
  current: PhysicsSample;
  maxSpeed: number;
  meanSpeed: number;
  maxAcceleration: number;
  peakKineticEnergy: number;
  loadScore: number;
  smoothnessScore: number;
  stabilityScore: number;
  invalidFrameCount: number;
  warnings: string[];
}

const zeroPoint = (): Point => ({ x: 0, y: 0 });
const magnitude = (point: Point): number => Math.hypot(point.x, point.y);
const subtract = (a: Point, b: Point): Point => ({ x: a.x - b.x, y: a.y - b.y });
const scale = (point: Point, amount: number): Point => ({ x: point.x * amount, y: point.y * amount });

const safeDuration = (durationSeconds: number): number => clamp(finite(durationSeconds, 4), 0.25, 120);
const mechanismMassEstimate = (config: MechanismConfig): number => {
  const lengths = Object.entries(config.params)
    .filter(([key]) => /radius|length|link|height|width/i.test(key))
    .map(([, value]) => Math.abs(finite(value, 0)))
    .filter((value) => value > 0);
  const meanLength = lengths.length > 0 ? lengths.reduce((sum, value) => sum + value, 0) / lengths.length : 60;
  return clamp(meanLength / 75, 0.35, 5);
};

const classifyStatus = (warnings: string[], invalidFrameCount: number, loadScore: number, smoothnessScore: number): SafetyLevel => {
  if (invalidFrameCount > 0 || loadScore > 0.86 || smoothnessScore < 0.32) return 'danger';
  if (warnings.length > 0 || loadScore > 0.62 || smoothnessScore < 0.52) return 'caution';
  return 'safe';
};

export const simulateMechanismPhysics = (
  config: MechanismConfig,
  durationSeconds: number,
  currentAngleDeg: number,
  sampleCount = 96
): PhysicsReport => {
  const duration = safeDuration(durationSeconds);
  const count = clamp(Math.round(finite(sampleCount, 96)), 16, 360);
  const dt = duration / count;
  const raw = Array.from({ length: count }, (_, index) => {
    const angleDeg = (index / count) * 360;
    const state = computeMechanismState(config, angleDeg);
    return {
      angleDeg,
      time: (index / count) * duration,
      position: state.effector,
      valid: state.valid && Number.isFinite(state.effector.x) && Number.isFinite(state.effector.y),
      safetyMessage: state.safety.message,
      safetyLevel: state.safety.level
    };
  });

  const mass = mechanismMassEstimate(config);
  const samples = raw.map((sample, index): PhysicsSample => {
    const prev = raw[(index - 1 + count) % count];
    const next = raw[(index + 1) % count];
    const velocity = sample.valid && prev.valid && next.valid ? scale(subtract(next.position, prev.position), 1 / (2 * dt)) : zeroPoint();
    const previousVelocity = sample.valid && prev.valid
      ? scale(subtract(sample.position, prev.position), 1 / dt)
      : zeroPoint();
    const nextVelocity = sample.valid && next.valid
      ? scale(subtract(next.position, sample.position), 1 / dt)
      : zeroPoint();
    const acceleration = scale(subtract(nextVelocity, previousVelocity), 1 / Math.max(dt, 1e-6));
    const speed = magnitude(velocity);
    const accelerationMagnitude = magnitude(acceleration);
    return {
      angleDeg: sample.angleDeg,
      time: sample.time,
      position: sample.position,
      velocity,
      acceleration,
      speed,
      accelerationMagnitude,
      kineticEnergy: 0.5 * mass * speed * speed,
      valid: sample.valid
    };
  });

  const validSamples = samples.filter((sample) => sample.valid);
  const speeds = validSamples.map((sample) => sample.speed);
  const accelerations = validSamples.map((sample) => sample.accelerationMagnitude);
  const energies = validSamples.map((sample) => sample.kineticEnergy);
  const maxSpeed = Math.max(0, ...speeds);
  const meanSpeed = speeds.length > 0 ? speeds.reduce((sum, value) => sum + value, 0) / speeds.length : 0;
  const maxAcceleration = Math.max(0, ...accelerations);
  const peakKineticEnergy = Math.max(0, ...energies);
  const jerkProxy = validSamples.reduce((peak, sample, index) => {
    if (index === 0) return peak;
    return Math.max(peak, distance(sample.acceleration, validSamples[index - 1].acceleration) / Math.max(dt, 1e-6));
  }, 0);
  const invalidFrameCount = count - validSamples.length;
  const loadScore = clamp(maxAcceleration / 120_000 + maxSpeed / 2_000, 0, 1);
  const smoothnessScore = clamp(1 - jerkProxy / 3_000_000, 0, 1);
  const stabilityScore = clamp((validSamples.length / count) * (1 - loadScore * 0.48) * (0.72 + smoothnessScore * 0.28), 0, 1);
  const warnings: string[] = [];
  if (invalidFrameCount > 0) warnings.push(`${invalidFrameCount} sampled frames cannot close; adjust lengths or assembly`);
  if (duration <= 0.75) warnings.push('Animation duration is very short; loads and acceleration spikes will be high');
  if (maxAcceleration > 85_000) warnings.push('High acceleration spike detected; slow timing or smooth the mechanism');
  if (jerkProxy > 1_600_000) warnings.push('Abrupt jerk detected; motion may chatter in physical builds');
  const unsafe = raw.find((sample) => sample.safetyLevel !== 'safe');
  if (unsafe) warnings.push(unsafe.safetyMessage);
  const status = classifyStatus(warnings, invalidFrameCount, loadScore, smoothnessScore);
  const currentIndex = ((Math.round((((finite(currentAngleDeg) % 360) + 360) % 360) / 360 * count) % count) + count) % count;

  return {
    mechanismId: config.id,
    mechanismName: config.name,
    status,
    samples,
    current: samples[currentIndex],
    maxSpeed,
    meanSpeed,
    maxAcceleration,
    peakKineticEnergy,
    loadScore,
    smoothnessScore,
    stabilityScore,
    invalidFrameCount,
    warnings
  };
};
