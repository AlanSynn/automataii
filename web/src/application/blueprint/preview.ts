import type { MechanismData } from '../../domain/project'
import { estimateMechanismBounds, generateMechanismSvg } from './mechanismRegistry'

export interface MechanismPreviewResult {
  svg: string
  width: number
  height: number
}

export const buildMechanismPreview = (mechanism: MechanismData): MechanismPreviewResult => {
  const bounds = estimateMechanismBounds(mechanism)
  const content = generateMechanismSvg(mechanism, bounds)
  const svg = `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${bounds.width}" height="${bounds.height}" viewBox="0 0 ${bounds.width} ${bounds.height}">
  ${content}
</svg>`
  return { svg, width: bounds.width, height: bounds.height }
}
