import type { TensorSpec } from '../../infra/onnx/onnxRuntime'

export interface ImageDataBundle {
  data: ImageData
  width: number
  height: number
}

export interface DetectionTransform {
  scale: number
  resized: { width: number; height: number }
  padded: { width: number; height: number }
  original: { width: number; height: number }
}

export interface DetectionPreprocessResult {
  tensor: TensorSpec
  transform: DetectionTransform
}

export interface PosePreprocessResult {
  tensor: TensorSpec
}

export interface BoundingBox {
  x1: number
  y1: number
  x2: number
  y2: number
}

const DETECTOR_MAX_WIDTH = 1333
const DETECTOR_MAX_HEIGHT = 800
const DETECTOR_PAD_STRIDE = 32
const DETECTOR_MEAN = [103.53, 116.28, 123.675]

const POSE_WIDTH = 192
const POSE_HEIGHT = 256
const POSE_MEAN = [0.485, 0.456, 0.406]
const POSE_STD = [0.229, 0.224, 0.225]

export const loadImageData = async (file: File): Promise<ImageDataBundle> => {
  const bitmap = await createImageBitmap(file)
  const canvas = document.createElement('canvas')
  canvas.width = bitmap.width
  canvas.height = bitmap.height
  const ctx = canvas.getContext('2d')
  if (!ctx) {
    bitmap.close()
    throw new Error('Canvas context is not available.')
  }
  ctx.drawImage(bitmap, 0, 0)
  const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height)
  bitmap.close()
  return { data: imageData, width: canvas.width, height: canvas.height }
}

export const preprocessForDetection = (
  bundle: ImageDataBundle,
  inputName: string
): DetectionPreprocessResult => {
  const scale = Math.min(
    DETECTOR_MAX_WIDTH / bundle.width,
    DETECTOR_MAX_HEIGHT / bundle.height
  )
  const resizedWidth = Math.max(1, Math.floor(bundle.width * scale))
  const resizedHeight = Math.max(1, Math.floor(bundle.height * scale))

  const sourceCanvas = imageDataToCanvas(bundle)
  const resizedCanvas = document.createElement('canvas')
  resizedCanvas.width = resizedWidth
  resizedCanvas.height = resizedHeight
  const resizedContext = resizedCanvas.getContext('2d')
  if (!resizedContext) {
    throw new Error('Canvas context is not available for resize.')
  }
  resizedContext.drawImage(
    sourceCanvas,
    0,
    0,
    bundle.width,
    bundle.height,
    0,
    0,
    resizedWidth,
    resizedHeight
  )
  const resizedImage = resizedContext.getImageData(0, 0, resizedWidth, resizedHeight)

  const paddedWidth = Math.ceil(resizedWidth / DETECTOR_PAD_STRIDE) * DETECTOR_PAD_STRIDE
  const paddedHeight = Math.ceil(resizedHeight / DETECTOR_PAD_STRIDE) * DETECTOR_PAD_STRIDE
  const channelSize = paddedWidth * paddedHeight
  const tensorData = new Float32Array(1 * 3 * channelSize)

  for (let y = 0; y < resizedHeight; y += 1) {
    for (let x = 0; x < resizedWidth; x += 1) {
      const pixelIndex = (y * resizedWidth + x) * 4
      const r = resizedImage.data[pixelIndex]
      const g = resizedImage.data[pixelIndex + 1]
      const b = resizedImage.data[pixelIndex + 2]

      const base = y * paddedWidth + x
      tensorData[base] = b - DETECTOR_MEAN[0]
      tensorData[channelSize + base] = g - DETECTOR_MEAN[1]
      tensorData[2 * channelSize + base] = r - DETECTOR_MEAN[2]
    }
  }

  return {
    tensor: {
      name: inputName,
      data: tensorData,
      dims: [1, 3, paddedHeight, paddedWidth],
      type: 'float32',
    },
    transform: {
      scale,
      resized: { width: resizedWidth, height: resizedHeight },
      padded: { width: paddedWidth, height: paddedHeight },
      original: { width: bundle.width, height: bundle.height },
    },
  }
}

export const preprocessForPose = (
  bundle: ImageDataBundle,
  inputName: string,
  bbox?: BoundingBox
): PosePreprocessResult => {
  const crop = bbox ?? {
    x1: 0,
    y1: 0,
    x2: bundle.width,
    y2: bundle.height,
  }
  const cropWidth = Math.max(1, crop.x2 - crop.x1)
  const cropHeight = Math.max(1, crop.y2 - crop.y1)

  const sourceCanvas = imageDataToCanvas(bundle)
  const cropCanvas = document.createElement('canvas')
  cropCanvas.width = POSE_WIDTH
  cropCanvas.height = POSE_HEIGHT
  const cropContext = cropCanvas.getContext('2d')
  if (!cropContext) {
    throw new Error('Canvas context is not available for crop.')
  }
  cropContext.drawImage(
    sourceCanvas,
    crop.x1,
    crop.y1,
    cropWidth,
    cropHeight,
    0,
    0,
    POSE_WIDTH,
    POSE_HEIGHT
  )
  const poseImage = cropContext.getImageData(0, 0, POSE_WIDTH, POSE_HEIGHT)
  const channelSize = POSE_WIDTH * POSE_HEIGHT
  const tensorData = new Float32Array(1 * 3 * channelSize)

  for (let y = 0; y < POSE_HEIGHT; y += 1) {
    for (let x = 0; x < POSE_WIDTH; x += 1) {
      const pixelIndex = (y * POSE_WIDTH + x) * 4
      const r = poseImage.data[pixelIndex] / 255.0
      const g = poseImage.data[pixelIndex + 1] / 255.0
      const b = poseImage.data[pixelIndex + 2] / 255.0

      const base = y * POSE_WIDTH + x
      tensorData[base] = (r - POSE_MEAN[0]) / POSE_STD[0]
      tensorData[channelSize + base] = (g - POSE_MEAN[1]) / POSE_STD[1]
      tensorData[2 * channelSize + base] = (b - POSE_MEAN[2]) / POSE_STD[2]
    }
  }

  return {
    tensor: {
      name: inputName,
      data: tensorData,
      dims: [1, 3, POSE_HEIGHT, POSE_WIDTH],
      type: 'float32',
    },
  }
}

const imageDataToCanvas = (bundle: ImageDataBundle): HTMLCanvasElement => {
  const canvas = document.createElement('canvas')
  canvas.width = bundle.width
  canvas.height = bundle.height
  const ctx = canvas.getContext('2d')
  if (!ctx) {
    throw new Error('Canvas context is not available for source.')
  }
  ctx.putImageData(bundle.data, 0, 0)
  return canvas
}
