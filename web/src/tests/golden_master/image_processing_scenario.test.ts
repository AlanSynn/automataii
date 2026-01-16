import { describe, expect, it } from 'vitest'

import { buildImageProcessingScenarioArtifacts } from '../../application/scenarios'
import { ProjectState, type PartData } from '../../domain/project'
import type { ImageInferenceState } from '../../application/onnx/useImageInference'

const buildPart = (): PartData => ({
  name: 'arm',
  texturePath: 'texture.png',
  maskPath: 'mask.png',
  anchorJoint: 'elbow',
  pivot: { x: 5, y: 6 },
  transform: { x: 0, y: 0, rotation: 0, scale: 1 },
  zIndex: 1,
})

const buildImageState = (): ImageInferenceState => ({
  status: 'ready',
  error: null,
  detectionMetadata: null,
  poseMetadata: null,
  detectionModelName: null,
  poseModelName: null,
  detectionOutputs: null,
  poseOutputs: null,
  keypoints: null,
  skeleton: null,
  projectSkeleton: null,
  projectState: ProjectState.empty().withParts({ arm: buildPart() }),
  image: { name: 'sample.png', url: 'sample.png', width: 100, height: 100 },
  boundingBox: { x1: 0, y1: 0, x2: 100, y2: 100 },
  annotationAssets: null,
})

describe('image processing scenario artifacts', () => {
  it('builds manifest and metrics from project state', () => {
    const artifacts = buildImageProcessingScenarioArtifacts(buildImageState(), 123)
    expect(artifacts.manifest.image).toBe('sample.png')
    expect(artifacts.manifest.parts.part_count).toBe(1)
    expect(artifacts.manifest.annotation.bounding_box).toBe('bounding_box.yaml')
    expect(artifacts.metrics.part_count).toBe(1)
    expect(artifacts.metrics.parts_info).toBe('parts/parts_info.json')
  })
})
