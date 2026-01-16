export interface MaskData {
  data: Uint8ClampedArray
  width: number
  height: number
}

const ALPHA_THRESHOLD = 10
const LINE_ART_WHITE_THRESHOLD = 240

export const segmentImage = (image: ImageData): MaskData => {
  const { width, height, data } = image
  const hasAlpha = data.length === width * height * 4
  if (hasAlpha) {
    const alphaStats = computeChannelStats(data, 3)
    if (alphaStats.max > 0 && alphaStats.std > 10) {
      const alphaMask = thresholdChannel(data, width, height, 3, ALPHA_THRESHOLD)
      const cleaned = closeOpen(alphaMask, width, height, 1, 1)
      const filled = fillHoles(cleaned, width, height)
      const largest = largestComponent(filled, width, height)
      return { data: largest, width, height }
    }
  }

  const gray = toGrayscale(data, width, height)
  const whitePercentage = countAbove(gray, LINE_ART_WHITE_THRESHOLD) / gray.length

  if (whitePercentage > 0.4) {
    const binary = thresholdArray(gray, LINE_ART_WHITE_THRESHOLD, true)
    const closed = closeOpen(binary, width, height, 3, 0)
    const filled = fillHoles(closed, width, height)
    const largest = largestComponent(filled, width, height)
    return { data: largest, width, height }
  }

  const binary = adaptiveThreshold(gray, width, height, 115, 8)
  const cleaned = closeOpen(binary, width, height, 2, 1)
  const backgroundRemoved = removeEdgeFill(cleaned, width, height)
  const largest = largestComponent(backgroundRemoved, width, height)
  const filled = fillHoles(largest, width, height)
  return { data: filled, width, height }
}

const computeChannelStats = (data: Uint8ClampedArray, channel: number) => {
  let max = 0
  let sum = 0
  let sumSq = 0
  const count = data.length / 4
  for (let index = channel; index < data.length; index += 4) {
    const value = data[index]
    max = Math.max(max, value)
    sum += value
    sumSq += value * value
  }
  const mean = sum / count
  const variance = sumSq / count - mean * mean
  return { max, std: Math.sqrt(Math.max(variance, 0)) }
}

const thresholdChannel = (
  data: Uint8ClampedArray,
  width: number,
  height: number,
  channel: number,
  threshold: number
): Uint8ClampedArray => {
  const mask = new Uint8ClampedArray(width * height)
  let maskIndex = 0
  for (let index = channel; index < data.length; index += 4) {
    mask[maskIndex] = data[index] > threshold ? 255 : 0
    maskIndex += 1
  }
  return mask
}

const toGrayscale = (data: Uint8ClampedArray, width: number, height: number): Uint8ClampedArray => {
  const gray = new Uint8ClampedArray(width * height)
  let pixel = 0
  for (let index = 0; index < data.length; index += 4) {
    const r = data[index]
    const g = data[index + 1]
    const b = data[index + 2]
    gray[pixel] = Math.round(0.299 * r + 0.587 * g + 0.114 * b)
    pixel += 1
  }
  return gray
}

const countAbove = (array: Uint8ClampedArray, threshold: number): number => {
  let count = 0
  for (let index = 0; index < array.length; index += 1) {
    if (array[index] > threshold) {
      count += 1
    }
  }
  return count
}

const thresholdArray = (
  gray: Uint8ClampedArray,
  threshold: number,
  invert: boolean
): Uint8ClampedArray => {
  const mask = new Uint8ClampedArray(gray.length)
  for (let index = 0; index < gray.length; index += 1) {
    const value = gray[index] > threshold ? 255 : 0
    mask[index] = invert ? 255 - value : value
  }
  return mask
}

const adaptiveThreshold = (
  gray: Uint8ClampedArray,
  width: number,
  height: number,
  blockSize: number,
  cValue: number
): Uint8ClampedArray => {
  const size = Math.min(blockSize, width, height)
  const kernel = size % 2 === 0 ? size - 1 : size
  if (kernel <= 1) {
    const mean = gray.reduce((acc, val) => acc + val, 0) / gray.length
    return thresholdArray(gray, mean - cValue, true)
  }
  const radius = Math.floor(kernel / 2)
  const integral = buildIntegral(gray, width, height)
  const output = new Uint8ClampedArray(gray.length)

  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const x1 = Math.max(0, x - radius)
      const y1 = Math.max(0, y - radius)
      const x2 = Math.min(width - 1, x + radius)
      const y2 = Math.min(height - 1, y + radius)
      const area = (x2 - x1 + 1) * (y2 - y1 + 1)
      const sum = integralAt(integral, width, x2, y2) -
        integralAt(integral, width, x1 - 1, y2) -
        integralAt(integral, width, x2, y1 - 1) +
        integralAt(integral, width, x1 - 1, y1 - 1)
      const mean = sum / area
      const idx = y * width + x
      output[idx] = gray[idx] > mean - cValue ? 0 : 255
    }
  }
  return output
}

const buildIntegral = (gray: Uint8ClampedArray, width: number, height: number): Float64Array => {
  const integral = new Float64Array(gray.length)
  for (let y = 0; y < height; y += 1) {
    let rowSum = 0
    for (let x = 0; x < width; x += 1) {
      const idx = y * width + x
      rowSum += gray[idx]
      integral[idx] = rowSum + (y > 0 ? integral[(y - 1) * width + x] : 0)
    }
  }
  return integral
}

const integralAt = (integral: Float64Array, width: number, x: number, y: number): number => {
  if (x < 0 || y < 0) {
    return 0
  }
  return integral[y * width + x]
}

const closeOpen = (
  mask: Uint8ClampedArray,
  width: number,
  height: number,
  closeIterations: number,
  openIterations: number
): Uint8ClampedArray => {
  let result = mask
  for (let i = 0; i < closeIterations; i += 1) {
    result = dilate(result, width, height)
  }
  for (let i = 0; i < closeIterations; i += 1) {
    result = erode(result, width, height)
  }
  for (let i = 0; i < openIterations; i += 1) {
    result = erode(result, width, height)
  }
  for (let i = 0; i < openIterations; i += 1) {
    result = dilate(result, width, height)
  }
  return result
}

const dilate = (mask: Uint8ClampedArray, width: number, height: number): Uint8ClampedArray => {
  const output = new Uint8ClampedArray(mask.length)
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      let max = 0
      for (let dy = -1; dy <= 1; dy += 1) {
        for (let dx = -1; dx <= 1; dx += 1) {
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
      for (let dy = -1; dy <= 1; dy += 1) {
        for (let dx = -1; dx <= 1; dx += 1) {
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

const fillHoles = (mask: Uint8ClampedArray, width: number, height: number): Uint8ClampedArray => {
  const filled = new Uint8ClampedArray(mask)
  const visited = new Uint8Array(mask.length)
  const queue: number[] = []

  for (let x = 0; x < width; x += 1) {
    enqueueIfBackground(filled, visited, queue, x, 0, width)
    enqueueIfBackground(filled, visited, queue, x, height - 1, width)
  }
  for (let y = 0; y < height; y += 1) {
    enqueueIfBackground(filled, visited, queue, 0, y, width)
    enqueueIfBackground(filled, visited, queue, width - 1, y, width)
  }

  while (queue.length > 0) {
    const idx = queue.pop()
    if (idx === undefined) {
      break
    }
    const x = idx % width
    const y = Math.floor(idx / width)
    const neighbors = [
      [x - 1, y],
      [x + 1, y],
      [x, y - 1],
      [x, y + 1],
    ]
    neighbors.forEach(([nx, ny]) => {
      if (nx < 0 || ny < 0 || nx >= width || ny >= height) {
        return
      }
      enqueueIfBackground(filled, visited, queue, nx, ny, width)
    })
  }

  for (let index = 0; index < filled.length; index += 1) {
    if (filled[index] === 0 && visited[index] === 0) {
      filled[index] = 255
    }
  }

  return filled
}

const removeEdgeFill = (mask: Uint8ClampedArray, width: number, height: number): Uint8ClampedArray => {
  const cleaned = new Uint8ClampedArray(mask)
  const visited = new Uint8Array(mask.length)
  const queue: number[] = []

  for (let x = 0; x < width; x += 10) {
    enqueueIfForeground(cleaned, visited, queue, x, 0, width)
    enqueueIfForeground(cleaned, visited, queue, x, height - 1, width)
  }
  for (let y = 0; y < height; y += 10) {
    enqueueIfForeground(cleaned, visited, queue, 0, y, width)
    enqueueIfForeground(cleaned, visited, queue, width - 1, y, width)
  }

  while (queue.length > 0) {
    const idx = queue.pop()
    if (idx === undefined) {
      break
    }
    cleaned[idx] = 0
    const x = idx % width
    const y = Math.floor(idx / width)
    const neighbors = [
      [x - 1, y],
      [x + 1, y],
      [x, y - 1],
      [x, y + 1],
    ]
    neighbors.forEach(([nx, ny]) => {
      if (nx < 0 || ny < 0 || nx >= width || ny >= height) {
        return
      }
      enqueueIfForeground(cleaned, visited, queue, nx, ny, width)
    })
  }

  return cleaned
}

const enqueueIfBackground = (
  mask: Uint8ClampedArray,
  visited: Uint8Array,
  queue: number[],
  x: number,
  y: number,
  width: number
): void => {
  const idx = y * width + x
  if (mask[idx] === 0 && visited[idx] === 0) {
    visited[idx] = 1
    queue.push(idx)
  }
}

const enqueueIfForeground = (
  mask: Uint8ClampedArray,
  visited: Uint8Array,
  queue: number[],
  x: number,
  y: number,
  width: number
): void => {
  const idx = y * width + x
  if (mask[idx] > 0 && visited[idx] === 0) {
    visited[idx] = 1
    queue.push(idx)
  }
}

const largestComponent = (
  mask: Uint8ClampedArray,
  width: number,
  height: number
): Uint8ClampedArray => {
  const visited = new Uint8Array(mask.length)
  let bestCount = 0
  let bestIndices: number[] = []

  for (let index = 0; index < mask.length; index += 1) {
    if (mask[index] === 0 || visited[index] === 1) {
      continue
    }
    const component: number[] = []
    const queue = [index]
    visited[index] = 1
    while (queue.length > 0) {
      const current = queue.pop()
      if (current === undefined) {
        break
      }
      component.push(current)
      const x = current % width
      const y = Math.floor(current / width)
      const neighbors = [
        [x - 1, y],
        [x + 1, y],
        [x, y - 1],
        [x, y + 1],
      ]
      neighbors.forEach(([nx, ny]) => {
        if (nx < 0 || ny < 0 || nx >= width || ny >= height) {
          return
        }
        const idx = ny * width + nx
        if (mask[idx] > 0 && visited[idx] === 0) {
          visited[idx] = 1
          queue.push(idx)
        }
      })
    }
    if (component.length > bestCount) {
      bestCount = component.length
      bestIndices = component
    }
  }

  const output = new Uint8ClampedArray(mask.length)
  bestIndices.forEach((idx) => {
    output[idx] = 255
  })
  if (bestIndices.length === 0) {
    output.fill(255)
  }
  return output
}
