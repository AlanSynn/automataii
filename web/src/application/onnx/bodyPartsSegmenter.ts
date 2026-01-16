import type { PartData, SkeletonData } from '../../domain/project'
import { DEFAULT_TRANSFORM } from '../../domain/project'

import type { ImageDataBundle } from './imagePreprocess'
import { BODY_PARTS, type BodyPartDefinition } from './partDefinitions'
import { segmentImage, type MaskData } from './segmentation'

interface JointMap {
  [jointName: string]: [number, number]
}

export interface BodyPartsResult {
  parts: Record<string, PartData>
  mask: MaskData
}

export const buildBodyPartsFromSkeleton = (
  imageBundle: ImageDataBundle,
  skeleton: SkeletonData | null,
  definitions: Record<string, BodyPartDefinition> = BODY_PARTS
): BodyPartsResult => {
  const mask = segmentImage(imageBundle.data)
  if (!skeleton) {
    return { parts: {}, mask }
  }
  const jointMap = buildJointMap(skeleton)
  const partMasks = segmentBodyParts(mask, jointMap, definitions)
  const parts = extractParts(imageBundle, partMasks, jointMap, definitions)
  return { parts, mask }
}

const buildJointMap = (skeleton: SkeletonData): JointMap => {
  const jointMap: JointMap = {}
  Object.values(skeleton.joints).forEach((joint) => {
    jointMap[joint.id] = [Math.trunc(joint.position.x), Math.trunc(joint.position.y)]
  })
  return jointMap
}

const segmentBodyParts = (
  mask: MaskData,
  jointMap: JointMap,
  definitions: Record<string, BodyPartDefinition>
): Record<string, Uint8ClampedArray> => {
  const maxDim = Math.max(mask.width, mask.height)
  const scaleFactor = maxDim > 1024 ? 512 / maxDim : maxDim > 512 ? 0.7 : 1.0
  const scaledWidth = Math.max(1, Math.floor(mask.width * scaleFactor))
  const scaledHeight = Math.max(1, Math.floor(mask.height * scaleFactor))

  const scaledMask = resizeMaskNearest(mask.data, mask.width, mask.height, scaledWidth, scaledHeight)
  const influences: Record<string, Float32Array> = {}

  Object.entries(definitions).forEach(([partName, def]) => {
    const influence = createPartInfluence(partName, def, jointMap, scaledWidth, scaledHeight, scaleFactor)
    if (influence) {
      influences[partName] = influence
    }
  })

  const partMasks: Record<string, Uint8ClampedArray> = {}
  const partNames = Object.keys(definitions)
  const influenceStack = partNames.map((name) => influences[name] ?? new Float32Array(scaledWidth * scaledHeight))

  for (let index = 0; index < scaledMask.length; index += 1) {
    if (scaledMask[index] === 0) {
      continue
    }
    let bestIndex = 0
    let bestValue = -Infinity
    for (let partIndex = 0; partIndex < influenceStack.length; partIndex += 1) {
      const value = influenceStack[partIndex][index]
      if (value > bestValue) {
        bestValue = value
        bestIndex = partIndex
      }
    }
    const partName = partNames[bestIndex]
    if (!partMasks[partName]) {
      partMasks[partName] = new Uint8ClampedArray(scaledWidth * scaledHeight)
    }
    partMasks[partName][index] = 255
  }

  partNames.forEach((partName) => {
    const scaledPartMask = partMasks[partName] ?? new Uint8ClampedArray(scaledWidth * scaledHeight)
    const upscaled = resizeMaskNearest(scaledPartMask, scaledWidth, scaledHeight, mask.width, mask.height)
    const cleaned = closeMask(upscaled, mask.width, mask.height)
    partMasks[partName] = cleaned
  })

  return partMasks
}

const createPartInfluence = (
  partName: string,
  def: BodyPartDefinition,
  jointMap: JointMap,
  width: number,
  height: number,
  scaleFactor: number
): Float32Array | null => {
  const mapped = mapJoints(def.joints, jointMap)
  if (mapped.length === 0) {
    return null
  }
  const scaledJoints = mapped.map(([x, y]) => [Math.trunc(x * scaleFactor), Math.trunc(y * scaleFactor)] as [number, number])
  const influence = new Float32Array(width * height)

  for (let idx = 0; idx < scaledJoints.length - 1; idx += 1) {
    const p1 = scaledJoints[idx]
    const p2 = scaledJoints[idx + 1]
    const boneInfluence = createBoneInfluence(p1, p2, width, height, scaleFactor)
    for (let i = 0; i < influence.length; i += 1) {
      if (boneInfluence[i] > influence[i]) {
        influence[i] = boneInfluence[i]
      }
    }
  }

  const jointInfluence = createJointInfluence(scaledJoints, width, height, 30 * scaleFactor)
  for (let i = 0; i < influence.length; i += 1) {
    if (jointInfluence[i] > influence[i]) {
      influence[i] = jointInfluence[i]
    }
  }

  return applyPartModulation(partName, influence, width, height)
}

const mapJoints = (jointNames: string[], jointMap: JointMap): Array<[number, number]> => {
  const mapped: Array<[number, number]> = []
  jointNames.forEach((jointName) => {
    if (jointMap[jointName]) {
      mapped.push(jointMap[jointName])
      return
    }
    const fallback = Object.keys(jointMap).find((name) => name.startsWith(jointName))
    if (fallback) {
      mapped.push(jointMap[fallback])
    }
  })
  return mapped
}

const resolveAnchorJoint = (
  jointId: string | null,
  jointMap: JointMap
): [number, number] | null => {
  if (!jointId) {
    return null
  }
  if (jointMap[jointId]) {
    return jointMap[jointId]
  }
  const fallback = Object.keys(jointMap).find((name) => name.startsWith(jointId))
  return fallback ? jointMap[fallback] : null
}

const createBoneInfluence = (
  p1: [number, number],
  p2: [number, number],
  width: number,
  height: number,
  scaleFactor: number
): Float32Array => {
  const output = new Float32Array(width * height)
  const dx = p2[0] - p1[0]
  const dy = p2[1] - p1[1]
  const length = Math.hypot(dx, dy)
  if (length === 0) {
    return output
  }
  const sigma = (20 + length * 0.1) * scaleFactor
  const sigmaSq = sigma * sigma

  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const t = ((x - p1[0]) * dx + (y - p1[1]) * dy) / (length * length)
      const clamped = Math.max(0, Math.min(1, t))
      const closestX = p1[0] + clamped * dx
      const closestY = p1[1] + clamped * dy
      const distSq = (x - closestX) ** 2 + (y - closestY) ** 2
      const value = Math.exp(-distSq / (2 * sigmaSq))
      output[y * width + x] = value
    }
  }
  return output
}

const createJointInfluence = (
  joints: Array<[number, number]>,
  width: number,
  height: number,
  sigma: number
): Float32Array => {
  const output = new Float32Array(width * height)
  if (joints.length === 0) {
    return output
  }
  const sigmaSq = sigma * sigma
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      let maxValue = 0
      joints.forEach(([jx, jy]) => {
        const distSq = (x - jx) ** 2 + (y - jy) ** 2
        const value = Math.exp(-distSq / (2 * sigmaSq))
        if (value > maxValue) {
          maxValue = value
        }
      })
      output[y * width + x] = maxValue
    }
  }
  return output
}

const applyPartModulation = (
  partName: string,
  influence: Float32Array,
  width: number,
  height: number
): Float32Array => {
  const output = new Float32Array(influence)
  if (partName.includes('head')) {
    for (let y = 0; y < height; y += 1) {
      const gradient = 1 + 0.5 * (1 - y / Math.max(height - 1, 1))
      for (let x = 0; x < width; x += 1) {
        const idx = y * width + x
        output[idx] *= gradient
      }
    }
  } else if (partName.includes('torso')) {
    blurInPlace(output, width, height, 2)
    for (let i = 0; i < output.length; i += 1) {
      output[i] *= 1.2
    }
  } else if (partName.includes('arm') || partName.includes('leg')) {
    blurInPlace(output, width, height, 1)
  }
  return output
}

const blurInPlace = (data: Float32Array, width: number, height: number, radius: number): void => {
  const temp = new Float32Array(data.length)
  const kernelSize = radius * 2 + 1
  const weight = 1 / (kernelSize * kernelSize)

  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      let sum = 0
      for (let dy = -radius; dy <= radius; dy += 1) {
        for (let dx = -radius; dx <= radius; dx += 1) {
          const nx = Math.min(width - 1, Math.max(0, x + dx))
          const ny = Math.min(height - 1, Math.max(0, y + dy))
          sum += data[ny * width + nx]
        }
      }
      temp[y * width + x] = sum * weight
    }
  }
  data.set(temp)
}

const resizeMaskNearest = (
  mask: Uint8ClampedArray,
  srcWidth: number,
  srcHeight: number,
  destWidth: number,
  destHeight: number
): Uint8ClampedArray => {
  const output = new Uint8ClampedArray(destWidth * destHeight)
  for (let y = 0; y < destHeight; y += 1) {
    const srcY = Math.min(srcHeight - 1, Math.floor((y / destHeight) * srcHeight))
    for (let x = 0; x < destWidth; x += 1) {
      const srcX = Math.min(srcWidth - 1, Math.floor((x / destWidth) * srcWidth))
      output[y * destWidth + x] = mask[srcY * srcWidth + srcX]
    }
  }
  return output
}

const closeMask = (mask: Uint8ClampedArray, width: number, height: number): Uint8ClampedArray => {
  let result = mask
  result = dilate(result, width, height)
  result = dilate(result, width, height)
  result = erode(result, width, height)
  result = erode(result, width, height)
  return result
}

const dilate = (mask: Uint8ClampedArray, width: number, height: number): Uint8ClampedArray => {
  const output = new Uint8ClampedArray(mask.length)
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      let max = 0
      for (let dy = -2; dy <= 2; dy += 1) {
        for (let dx = -2; dx <= 2; dx += 1) {
          const nx = x + dx
          const ny = y + dy
          if (nx < 0 || ny < 0 || nx >= width || ny >= height) {
            continue
          }
          const value = mask[ny * width + nx]
          if (value > max) {
            max = value
          }
        }
      }
      output[y * width + x] = max
    }
  }
  return output
}

const erode = (mask: Uint8ClampedArray, width: number, height: number): Uint8ClampedArray => {
  const output = new Uint8ClampedArray(mask.length)
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      let min = 255
      for (let dy = -2; dy <= 2; dy += 1) {
        for (let dx = -2; dx <= 2; dx += 1) {
          const nx = x + dx
          const ny = y + dy
          if (nx < 0 || ny < 0 || nx >= width || ny >= height) {
            continue
          }
          const value = mask[ny * width + nx]
          if (value < min) {
            min = value
          }
        }
      }
      output[y * width + x] = min
    }
  }
  return output
}

const extractParts = (
  imageBundle: ImageDataBundle,
  partMasks: Record<string, Uint8ClampedArray>,
  jointMap: JointMap,
  definitions: Record<string, BodyPartDefinition>
): Record<string, PartData> => {
  const parts: Record<string, PartData> = {}
  const { width, height } = imageBundle

  Object.entries(definitions).forEach(([partName, def]) => {
    const mask = partMasks[partName]
    if (!mask) {
      return
    }
    const bbox = computeBoundingBox(mask, width, height)
    if (!bbox) {
      return
    }
    const [x, y, w, h] = bbox
    const texture = buildCroppedTexture(imageBundle.data, mask, width, height, x, y, w, h)
    const maskData = buildMaskImage(mask, width, height, x, y, w, h)
    const defaultPivot = { x: w / 2, y: h / 2 }
    const anchor = resolveAnchorJoint(def.anchorJoint, jointMap)
    const pivot = anchor
      ? { x: anchor[0] - x, y: anchor[1] - y }
      : defaultPivot
    const safePivot = Number.isFinite(pivot.x) && Number.isFinite(pivot.y)
      ? pivot
      : defaultPivot
    parts[partName] = {
      name: partName,
      texturePath: texture,
      maskPath: maskData,
      anchorJoint: def.anchorJoint,
      pivot: safePivot,
      transform: { ...DEFAULT_TRANSFORM, x, y },
      zIndex: def.zValue,
    }
  })

  return parts
}

const computeBoundingBox = (
  mask: Uint8ClampedArray,
  width: number,
  height: number
): [number, number, number, number] | null => {
  let minX = width
  let minY = height
  let maxX = 0
  let maxY = 0
  let found = false

  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      if (mask[y * width + x] > 0) {
        found = true
        minX = Math.min(minX, x)
        minY = Math.min(minY, y)
        maxX = Math.max(maxX, x)
        maxY = Math.max(maxY, y)
      }
    }
  }

  if (!found) {
    return null
  }

  const padding = 3
  const x = Math.max(0, minX - padding)
  const y = Math.max(0, minY - padding)
  const w = Math.min(width - x, maxX - minX + 1 + padding * 2)
  const h = Math.min(height - y, maxY - minY + 1 + padding * 2)
  if (w <= 0 || h <= 0) {
    return null
  }
  return [x, y, w, h]
}

const buildCroppedTexture = (
  image: ImageData,
  mask: Uint8ClampedArray,
  width: number,
  _height: number,
  x: number,
  y: number,
  w: number,
  h: number
): string => {
  const output = new ImageData(w, h)
  for (let row = 0; row < h; row += 1) {
    for (let col = 0; col < w; col += 1) {
      const srcX = x + col
      const srcY = y + row
      const srcIndex = (srcY * width + srcX) * 4
      const destIndex = (row * w + col) * 4
      const alpha = mask[srcY * width + srcX]
      output.data[destIndex] = image.data[srcIndex]
      output.data[destIndex + 1] = image.data[srcIndex + 1]
      output.data[destIndex + 2] = image.data[srcIndex + 2]
      output.data[destIndex + 3] = alpha
    }
  }
  return imageDataToDataUrl(output)
}

const buildMaskImage = (
  mask: Uint8ClampedArray,
  width: number,
  _height: number,
  x: number,
  y: number,
  w: number,
  h: number
): string => {
  const output = new ImageData(w, h)
  for (let row = 0; row < h; row += 1) {
    for (let col = 0; col < w; col += 1) {
      const srcX = x + col
      const srcY = y + row
      const srcIndex = (srcY * width + srcX)
      const destIndex = (row * w + col) * 4
      const alpha = mask[srcIndex]
      output.data[destIndex] = 0
      output.data[destIndex + 1] = 0
      output.data[destIndex + 2] = 0
      output.data[destIndex + 3] = alpha
    }
  }
  return imageDataToDataUrl(output)
}

const imageDataToDataUrl = (image: ImageData): string => {
  const canvas = document.createElement('canvas')
  canvas.width = image.width
  canvas.height = image.height
  const ctx = canvas.getContext('2d')
  if (!ctx) {
    return ''
  }
  ctx.putImageData(image, 0, 0)
  return canvas.toDataURL('image/png')
}
