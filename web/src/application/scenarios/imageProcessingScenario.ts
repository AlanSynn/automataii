import type { PartData, ProjectState, SkeletonData } from '../../domain/project'
import type { ImageInferenceState } from '../onnx/useImageInference'
import type { BoundingBox, SkeletonJoint } from '../onnx/keypoints'
import { downloadDataUrlFile, downloadTextFile } from './downloads'

export interface ImageProcessingScenarioManifest {
  generated_at: string
  image: string
  annotation: {
    dir: string
    char_cfg: string
    texture: string
    mask: string
    joint_overlay: string
    bounding_box: string | null
  }
  parts: {
    dir: string
    parts_info: string
    part_count: number
  }
}

export interface ImageProcessingScenarioMetrics {
  duration_ms: number
  part_count: number
  image: string
  manifest: string
  parts_info: string
}

export interface PartInfoEntry {
  name: string
  roi: [number, number, number, number] | null
  image_path: string
  fill_color: string
  local_pivot_offset: [number, number]
  z_value: number
  fixed: boolean
  anchor_joint_id: string | null
}

export interface SkeletonJointEntry {
  id: string
  name: string
  position: [number, number]
  parent: string | null
}

export interface PartsInfoData {
  character: {
    name: string
    parts: Record<string, PartInfoEntry>
    skeleton_joints: SkeletonJointEntry[]
  }
}

export interface BoundingBoxData {
  left: number
  top: number
  right: number
  bottom: number
  score: number | null
  original_width: number | null
  original_height: number | null
}

export interface CharCfgData {
  skeleton: Array<{
    name: string
    parent: string | null
    loc: [number, number]
    loc_original: [number, number]
  }>
  height: number
  width: number
  bbox_origin_x: number | null
  bbox_origin_y: number | null
  bbox_origin_r: number | null
  bbox_origin_b: number | null
  resize_scale: number
}

export interface ImageProcessingScenarioArtifacts {
  manifest: ImageProcessingScenarioManifest
  metrics: ImageProcessingScenarioMetrics
  partsInfoData: PartsInfoData
  boundingBoxData: BoundingBoxData | null
  charCfgData: CharCfgData | null
  annotationAssets: {
    maskUrl: string | null
    textureUrl: string | null
    jointOverlayUrl: string | null
  } | null
}

const buildPartsInfoData = (
  state: ProjectState | null,
  characterName: string,
  skeleton: SkeletonData | null
): PartsInfoData => {
  const parts: Record<string, PartInfoEntry> = {}
  if (state) {
    Object.values(state.parts).forEach((part: PartData) => {
      parts[part.name] = {
        name: part.name,
        roi: null,
        image_path: '',
        fill_color: 'rgba(128,128,128,0.5)',
        local_pivot_offset: [part.pivot.x, part.pivot.y],
        z_value: part.zIndex,
        fixed: false,
        anchor_joint_id: part.anchorJoint,
      }
    })
  }
  const skeleton_joints = skeleton
    ? Object.values(skeleton.joints).map((joint) => ({
        id: joint.id,
        name: joint.id,
        position: [joint.position.x, joint.position.y] as [number, number],
        parent: joint.parent,
      }))
    : []

  return {
    character: {
      name: characterName,
      parts,
      skeleton_joints,
    },
  }
}

const buildBoundingBoxData = (
  boundingBox: BoundingBox | null,
  imageState: ImageInferenceState
): BoundingBoxData | null => {
  if (!boundingBox) {
    return null
  }
  return {
    left: boundingBox.x1,
    top: boundingBox.y1,
    right: boundingBox.x2,
    bottom: boundingBox.y2,
    score: null,
    original_width: imageState.image?.width ?? null,
    original_height: imageState.image?.height ?? null,
  }
}

const buildCharCfgData = (imageState: ImageInferenceState): CharCfgData | null => {
  if (!imageState.skeleton) {
    return null
  }
  const bbox = imageState.boundingBox
  return {
    skeleton: imageState.skeleton.map((joint: SkeletonJoint) => ({
      name: joint.name,
      parent: joint.parent,
      loc: joint.loc,
      loc_original: joint.locOriginal,
    })),
    height: imageState.image?.height ?? 0,
    width: imageState.image?.width ?? 0,
    bbox_origin_x: bbox?.x1 ?? null,
    bbox_origin_y: bbox?.y1 ?? null,
    bbox_origin_r: bbox?.x2 ?? null,
    bbox_origin_b: bbox?.y2 ?? null,
    resize_scale: 1.0,
  }
}

export const buildImageProcessingScenarioArtifacts = (
  imageState: ImageInferenceState,
  durationMs: number
): ImageProcessingScenarioArtifacts => {
  const generatedAt = new Date().toISOString()
  const imageName = imageState.image?.name ?? 'unknown'
  const partsInfoData = buildPartsInfoData(
    imageState.projectState,
    imageName,
    imageState.projectSkeleton
  )
  const boundingBoxData = buildBoundingBoxData(imageState.boundingBox, imageState)
  const charCfgData = buildCharCfgData(imageState)
  const annotationAssets = imageState.annotationAssets ?? null

  const manifest: ImageProcessingScenarioManifest = {
    generated_at: generatedAt,
    image: imageName,
    annotation: {
      dir: 'annotations',
      char_cfg: 'char_cfg.yaml',
      texture: 'texture.png',
      mask: 'mask.png',
      joint_overlay: 'joint_overlay.png',
      bounding_box: boundingBoxData ? 'bounding_box.yaml' : null,
    },
    parts: {
      dir: 'parts',
      parts_info: 'parts_info.json',
      part_count: Object.keys(partsInfoData.character.parts).length,
    },
  }

  const metrics: ImageProcessingScenarioMetrics = {
    duration_ms: Math.round(durationMs),
    part_count: Object.keys(partsInfoData.character.parts).length,
    image: imageName,
    manifest: 'image_processing_manifest.json',
    parts_info: `${manifest.parts.dir}/${manifest.parts.parts_info}`,
  }

  return {
    manifest,
    metrics,
    partsInfoData,
    boundingBoxData,
    charCfgData,
    annotationAssets,
  }
}

export const downloadImageProcessingScenarioArtifacts = async (
  artifacts: ImageProcessingScenarioArtifacts
): Promise<void> => {
  downloadTextFile(
    'image_processing_manifest.json',
    JSON.stringify(artifacts.manifest, null, 2),
    'application/json'
  )
  downloadTextFile(
    'image_processing_metrics.json',
    JSON.stringify(artifacts.metrics, null, 2),
    'application/json'
  )
  downloadTextFile(
    'parts_info.json',
    JSON.stringify(artifacts.partsInfoData, null, 2),
    'application/json'
  )
  if (artifacts.boundingBoxData) {
    downloadTextFile(
      'bounding_box.yaml',
      JSON.stringify(artifacts.boundingBoxData, null, 2),
      'application/json'
    )
  }
  if (artifacts.charCfgData) {
    downloadTextFile(
      'char_cfg.yaml',
      JSON.stringify(artifacts.charCfgData, null, 2),
      'application/json'
    )
  }
  if (artifacts.annotationAssets?.maskUrl) {
    await downloadDataUrlFile('mask.png', artifacts.annotationAssets.maskUrl)
  }
  if (artifacts.annotationAssets?.textureUrl) {
    await downloadDataUrlFile('texture.png', artifacts.annotationAssets.textureUrl)
  }
  if (artifacts.annotationAssets?.jointOverlayUrl) {
    await downloadDataUrlFile('joint_overlay.png', artifacts.annotationAssets.jointOverlayUrl)
  }
}
