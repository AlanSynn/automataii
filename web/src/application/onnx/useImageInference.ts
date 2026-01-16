import { useCallback, useRef, useState } from 'react'
import type { ChangeEvent } from 'react'
import type { SerializedTensor } from '../../infra/onnx/onnxRuntime'
import type { ProjectState, SkeletonData } from '../../domain/project'
import { OnnxWorkerClient, type SessionMetadata } from '../../infra/onnx'
import {
  loadImageData,
  preprocessForDetection,
  preprocessForPose,
  type ImageDataBundle,
} from './imagePreprocess'
import {
  applyMargin,
  buildFullImageBox,
  createSkeletonConfig,
  extractKeypointsFromHeatmap,
  type BoundingBox,
  type Keypoint,
  type SkeletonJoint,
} from './keypoints'
import { selectDetectionBox } from './detection'
import { buildProjectSkeleton } from './skeletonMapper'
import { buildProjectStateFromSkeleton } from './projectStateBuilder'
import { buildBodyPartsFromSkeleton } from './bodyPartsSegmenter'
import type { MaskData } from './segmentation'

export type ImageInferenceStatus = 'idle' | 'loading' | 'ready' | 'running' | 'error'

export interface LoadedImageInfo {
  name: string
  url: string
  width: number
  height: number
}

export interface AnnotationAssets {
  maskUrl: string | null
  textureUrl: string | null
  jointOverlayUrl: string | null
}

export interface ImageInferenceState {
  status: ImageInferenceStatus
  error: string | null
  detectionMetadata: SessionMetadata | null
  poseMetadata: SessionMetadata | null
  detectionModelName: string | null
  poseModelName: string | null
  detectionOutputs: Record<string, SerializedTensor> | null
  poseOutputs: Record<string, SerializedTensor> | null
  keypoints: Keypoint[] | null
  skeleton: SkeletonJoint[] | null
  projectSkeleton: SkeletonData | null
  projectState: ProjectState | null
  image: LoadedImageInfo | null
  boundingBox: BoundingBox | null
  annotationAssets: AnnotationAssets | null
}

export interface ImageInferenceController {
  state: ImageInferenceState
  loadDetectionModel: (event: ChangeEvent<HTMLInputElement>) => void
  loadPoseModel: (event: ChangeEvent<HTMLInputElement>) => void
  loadImage: (event: ChangeEvent<HTMLInputElement>) => void
  runPipeline: () => Promise<ImageInferenceState | null>
  reset: () => void
}

const defaultState: ImageInferenceState = {
  status: 'idle',
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
  projectState: null,
  image: null,
  boundingBox: null,
  annotationAssets: null,
}

export const useImageInference = (): ImageInferenceController => {
  const [state, setState] = useState<ImageInferenceState>(defaultState)
  const detectionClientRef = useRef<OnnxWorkerClient | null>(null)
  const poseClientRef = useRef<OnnxWorkerClient | null>(null)
  const imageRef = useRef<ImageDataBundle | null>(null)
  const imageUrlRef = useRef<string | null>(null)

  const loadDetectionModel = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) {
      return
    }
    setState((current) => ({
      ...current,
      status: 'loading',
      error: null,
      detectionOutputs: null,
      poseOutputs: null,
      keypoints: null,
      skeleton: null,
      projectSkeleton: null,
      projectState: null,
      boundingBox: null,
      annotationAssets: null,
    }))

    const client = new OnnxWorkerClient()
    detectionClientRef.current?.terminate()
    detectionClientRef.current = client
    file
      .arrayBuffer()
      .then((buffer) => client.init(buffer, undefined, '/'))
      .then((metadata) => {
        setState((current) => ({
          ...current,
          detectionMetadata: metadata,
          detectionModelName: file.name,
          status: isReadyWith(metadata, current.poseMetadata, current.image) ? 'ready' : 'loading',
        }))
      })
      .catch((error: unknown) => {
        setState((current) => ({
          ...current,
          status: 'error',
          error: error instanceof Error ? error.message : 'Failed to load detection model',
        }))
      })
  }, [])

  const loadPoseModel = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) {
      return
    }
    setState((current) => ({
      ...current,
      status: 'loading',
      error: null,
      detectionOutputs: null,
      poseOutputs: null,
      keypoints: null,
      skeleton: null,
      projectSkeleton: null,
      projectState: null,
      boundingBox: null,
      annotationAssets: null,
    }))

    const client = new OnnxWorkerClient()
    poseClientRef.current?.terminate()
    poseClientRef.current = client
    file
      .arrayBuffer()
      .then((buffer) => client.init(buffer, undefined, '/'))
      .then((metadata) => {
        setState((current) => ({
          ...current,
          poseMetadata: metadata,
          poseModelName: file.name,
          status: isReadyWith(current.detectionMetadata, metadata, current.image) ? 'ready' : 'loading',
        }))
      })
      .catch((error: unknown) => {
        setState((current) => ({
          ...current,
          status: 'error',
          error: error instanceof Error ? error.message : 'Failed to load pose model',
        }))
      })
  }, [])

  const loadImage = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) {
      return
    }
    setState((current) => ({
      ...current,
      status: 'loading',
      error: null,
      detectionOutputs: null,
      poseOutputs: null,
      keypoints: null,
      skeleton: null,
      projectSkeleton: null,
      projectState: null,
      boundingBox: null,
      annotationAssets: null,
    }))
    const url = URL.createObjectURL(file)
    if (imageUrlRef.current) {
      URL.revokeObjectURL(imageUrlRef.current)
    }
    imageUrlRef.current = url
    loadImageData(file)
      .then((bundle) => {
        imageRef.current = bundle
        setState((current) => ({
          ...current,
          image: {
            name: file.name,
            url,
            width: bundle.width,
            height: bundle.height,
          },
          status: isReadyWith(current.detectionMetadata, current.poseMetadata, {
            name: file.name,
            url,
            width: bundle.width,
            height: bundle.height,
          })
            ? 'ready'
            : 'loading',
        }))
      })
      .catch((error: unknown) => {
        setState((current) => ({
          ...current,
          status: 'error',
          error: error instanceof Error ? error.message : 'Failed to load image',
        }))
      })
  }, [])

  const runPipeline = useCallback(async (): Promise<ImageInferenceState | null> => {
    const detectionClient = detectionClientRef.current
    const poseClient = poseClientRef.current
    const imageBundle = imageRef.current
    if (!detectionClient || !poseClient || !imageBundle) {
      setState((current) => ({
        ...current,
        status: 'error',
        error: 'Detection model, pose model, and image must be loaded.',
      }))
      return null
    }
    if (!state.detectionMetadata || !state.poseMetadata) {
      setState((current) => ({
        ...current,
        status: 'error',
        error: 'Model metadata is missing.',
      }))
      return null
    }
    const detectionInputName = state.detectionMetadata.inputNames[0]
    const poseInputName = state.poseMetadata.inputNames[0]
    if (!detectionInputName || !poseInputName) {
      setState((current) => ({
        ...current,
        status: 'error',
        error: 'Model input names are missing.',
      }))
      return null
    }
    setState((current) => ({
      ...current,
      status: 'running',
      error: null,
      keypoints: null,
      skeleton: null,
      projectState: null,
      boundingBox: null,
      annotationAssets: null,
    }))

    try {
      const detection = preprocessForDetection(imageBundle, detectionInputName)
      const detectionOutputs = await detectionClient.run([detection.tensor])
      const detectionBox = selectDetectionBox(detectionOutputs, detection.transform)
      const baseBox = detectionBox ?? buildFullImageBox(imageBundle.width, imageBundle.height)
      const bbox = applyMargin(baseBox, imageBundle.width, imageBundle.height)
      const pose = preprocessForPose(imageBundle, poseInputName, bbox)
      const poseOutputs = await poseClient.run([pose.tensor])

      const heatmap = selectHeatmap(poseOutputs, state.poseMetadata.outputNames)
      if (!heatmap) {
        throw new Error('Pose model did not return a heatmap output.')
      }

      const keypoints = extractKeypointsFromHeatmap(heatmap, bbox)
      const skeleton = createSkeletonConfig(keypoints, bbox)
      const projectSkeleton = buildProjectSkeleton(skeleton)
      const { parts, mask } = buildBodyPartsFromSkeleton(imageBundle, projectSkeleton)
      const annotationAssets = buildAnnotationAssets(imageBundle, mask, projectSkeleton)
      const projectState = buildProjectStateFromSkeleton(state.image, projectSkeleton, parts)

      const nextState: ImageInferenceState = {
        ...state,
        status: 'ready',
        error: null,
        detectionOutputs,
        poseOutputs,
        keypoints,
        skeleton,
        projectSkeleton,
        projectState,
        boundingBox: bbox,
        annotationAssets,
      }
      setState(nextState)
      return nextState
    } catch (error) {
      setState((current) => ({
        ...current,
        status: 'error',
        error: error instanceof Error ? error.message : 'Inference failed',
      }))
      return null
    }
  }, [state])

  const reset = useCallback(() => {
    detectionClientRef.current?.terminate()
    poseClientRef.current?.terminate()
    detectionClientRef.current = null
    poseClientRef.current = null
    imageRef.current = null
    if (imageUrlRef.current) {
      URL.revokeObjectURL(imageUrlRef.current)
    }
    imageUrlRef.current = null
    setState(defaultState)
  }, [])

  const effectiveStatus =
    state.status === 'running' || state.status === 'error'
      ? state.status
      : isReadyWith(state.detectionMetadata, state.poseMetadata, state.image)
        ? 'ready'
        : state.status

  return {
    state: {
      ...state,
      status: effectiveStatus,
    },
    loadDetectionModel,
    loadPoseModel,
    loadImage,
    runPipeline,
    reset,
  }
}

const isReadyWith = (
  detectionMetadata: SessionMetadata | null,
  poseMetadata: SessionMetadata | null,
  image: LoadedImageInfo | null
): boolean => Boolean(detectionMetadata && poseMetadata && image)

const selectHeatmap = (
  outputs: Record<string, SerializedTensor>,
  outputNames: readonly string[]
): SerializedTensor | null => {
  if (outputNames.length > 0 && outputs[outputNames[0]]) {
    return outputs[outputNames[0]]
  }
  const firstKey = Object.keys(outputs)[0]
  return firstKey ? outputs[firstKey] : null
}

const buildAnnotationAssets = (
  imageBundle: ImageDataBundle,
  mask: MaskData,
  skeleton: SkeletonData | null
): AnnotationAssets => ({
  maskUrl: buildMaskDataUrl(mask),
  textureUrl: buildTextureDataUrl(imageBundle, mask),
  jointOverlayUrl: buildJointOverlayUrl(imageBundle, mask, skeleton),
})

const buildMaskDataUrl = (mask: MaskData): string | null => {
  const imageData = new ImageData(mask.width, mask.height)
  for (let index = 0; index < mask.data.length; index += 1) {
    const base = index * 4
    const alpha = mask.data[index]
    imageData.data[base] = 0
    imageData.data[base + 1] = 0
    imageData.data[base + 2] = 0
    imageData.data[base + 3] = alpha
  }
  return imageDataToDataUrl(imageData)
}

const buildTextureImageData = (
  imageBundle: ImageDataBundle,
  mask: MaskData
): ImageData => {
  const imageData = new ImageData(mask.width, mask.height)
  const pixelCount = mask.data.length
  for (let index = 0; index < pixelCount; index += 1) {
    const base = index * 4
    imageData.data[base] = imageBundle.data.data[base]
    imageData.data[base + 1] = imageBundle.data.data[base + 1]
    imageData.data[base + 2] = imageBundle.data.data[base + 2]
    imageData.data[base + 3] = mask.data[index]
  }
  return imageData
}

const buildTextureDataUrl = (
  imageBundle: ImageDataBundle,
  mask: MaskData
): string | null => imageDataToDataUrl(buildTextureImageData(imageBundle, mask))

const buildJointOverlayUrl = (
  imageBundle: ImageDataBundle,
  mask: MaskData,
  skeleton: SkeletonData | null
): string | null => {
  const context = createCanvasContext(mask.width, mask.height)
  if (!context) {
    return null
  }
  const textureImageData = buildTextureImageData(imageBundle, mask)
  context.putImageData(textureImageData, 0, 0)
  if (skeleton) {
    context.fillStyle = 'black'
    context.font = '12px sans-serif'
    Object.values(skeleton.joints).forEach((joint) => {
      context.beginPath()
      context.arc(joint.position.x, joint.position.y, 4, 0, Math.PI * 2)
      context.fill()
      context.fillText(joint.id, joint.position.x + 6, joint.position.y + 6)
    })
  }
  return context.canvas.toDataURL('image/png')
}

const createCanvasContext = (
  width: number,
  height: number
): CanvasRenderingContext2D | null => {
  if (typeof document === 'undefined') {
    return null
  }
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  return canvas.getContext('2d')
}

const imageDataToDataUrl = (imageData: ImageData): string | null => {
  const context = createCanvasContext(imageData.width, imageData.height)
  if (!context) {
    return null
  }
  context.putImageData(imageData, 0, 0)
  return context.canvas.toDataURL('image/png')
}
