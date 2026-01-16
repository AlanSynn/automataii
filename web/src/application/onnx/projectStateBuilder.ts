import { ProjectState } from '../../domain/project'
import type { PartData, SkeletonData } from '../../domain/project'
import type { LoadedImageInfo } from './useImageInference'

export const buildProjectStateFromSkeleton = (
  image: LoadedImageInfo | null,
  skeleton: SkeletonData | null,
  parts: Record<string, PartData> = {}
): ProjectState | null => {
  if (!skeleton) {
    return null
  }
  const base = ProjectState.empty().withSkeleton(skeleton).withParts(parts)
  const imagePath = image?.name ?? null
  const metadata = {
    ...base.metadata,
    name: image?.name ?? base.metadata.name,
  }
  return base.withImagePath(imagePath).withMetadata(metadata)
}
