import type { ProjectState } from '../types';

export interface SchedulerTask {
  id: string;
  priority: number;
}

export interface SchedulerPolicy {
  targetFps: number;
  frameIntervalMs: number;
  maxStepsPerFrame: number;
  sampleBudget: number;
  animationEnabled: boolean;
  performancePreset: ProjectState['settings']['performancePreset'];
}

export interface SchedulerStep {
  index: number;
  dtSeconds: number;
}

export interface SchedulerFramePlan {
  steps: SchedulerStep[];
  skippedFrames: number;
  remainingMs: number;
  consumedMs: number;
  angleDeltaDeg: number;
  orderedTaskIds: string[];
}

const presetBudget: Record<ProjectState['settings']['performancePreset'], { maxSteps: number; samples: number }> = {
  quality: { maxSteps: 8, samples: 160 },
  balanced: { maxSteps: 5, samples: 96 },
  performance: { maxSteps: 3, samples: 48 }
};

const clamp = (value: number, min: number, max: number): number => Math.min(max, Math.max(min, value));

export const createSchedulerPolicy = (settings: ProjectState['settings']): SchedulerPolicy => {
  const targetFps = Math.round(clamp(settings.targetFps, 12, 120));
  const budget = presetBudget[settings.performancePreset] ?? presetBudget.balanced;
  return {
    targetFps,
    frameIntervalMs: 1000 / targetFps,
    maxStepsPerFrame: budget.maxSteps,
    sampleBudget: budget.samples,
    animationEnabled: !settings.reducedMotion,
    performancePreset: settings.performancePreset
  };
};

export const orderSchedulerTasks = (tasks: SchedulerTask[]): SchedulerTask[] =>
  tasks
    .map((task, index) => ({ task, index }))
    .sort((a, b) => b.task.priority - a.task.priority || a.index - b.index)
    .map(({ task }) => task);

export const planAnimationFrame = (
  policy: SchedulerPolicy,
  elapsedMs: number,
  animationDurationSeconds: number,
  tasks: SchedulerTask[] = []
): SchedulerFramePlan => {
  if (!policy.animationEnabled || elapsedMs < policy.frameIntervalMs) {
    return {
      steps: [],
      skippedFrames: 0,
      remainingMs: Math.max(0, elapsedMs),
      consumedMs: 0,
      angleDeltaDeg: 0,
      orderedTaskIds: orderSchedulerTasks(tasks).map((task) => task.id)
    };
  }
  const rawStepCount = Math.floor(elapsedMs / policy.frameIntervalMs);
  const stepCount = Math.min(rawStepCount, policy.maxStepsPerFrame);
  const skippedFrames = Math.max(0, rawStepCount - stepCount);
  const consumedMs = stepCount * policy.frameIntervalMs;
  const duration = clamp(animationDurationSeconds, 0.25, 120);
  return {
    steps: Array.from({ length: stepCount }, (_, index) => ({
      index,
      dtSeconds: policy.frameIntervalMs / 1000
    })),
    skippedFrames,
    remainingMs: skippedFrames > 0 ? 0 : Math.max(0, elapsedMs - consumedMs),
    consumedMs,
    angleDeltaDeg: (consumedMs / 1000) * (360 / duration),
    orderedTaskIds: orderSchedulerTasks(tasks).map((task) => task.id)
  };
};

export const schedulerStatusText = (policy: SchedulerPolicy, skippedFrames: number): string =>
  `Scheduler · Target FPS ${policy.targetFps} · ${policy.performancePreset} · skipped ${skippedFrames}`;
