import type { PathData, Point } from '../../domain/project'
import { PathUtils } from '../../domain/project'

export const samplePathsAtProgress = (
  paths: Record<string, PathData>,
  progress: number
): Record<string, Point> => {
  const samples: Record<string, Point> = {}
  Object.entries(paths).forEach(([name, path]) => {
    samples[name] = PathUtils.getPointAtProgress(path, progress)
  })
  return samples
}
