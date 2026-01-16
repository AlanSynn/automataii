import type { MechanismData } from '../../domain/project'
import type { BlueprintLayoutItem, ScaledBounds } from './types'
import { generateCamSvg } from './generators/cam'
import { generateFourBarSvg } from './generators/fourBar'
import { generateGearMeshSvg, generatePlanetaryGearSvg } from './generators/gear'

export interface MechanismLayoutItem extends BlueprintLayoutItem {
  mechanismType: string
}

export const buildMechanismItem = (
  mechanism: MechanismData,
  bounds: ScaledBounds
): MechanismLayoutItem => {
  const svgContent = generateMechanismSvg(mechanism, bounds)
  return {
    name: mechanism.id,
    width: bounds.width,
    height: bounds.height,
    svgContent,
    itemType: 'mechanism',
    mechanismType: mechanism.type,
  }
}

export const generateMechanismSvg = (
  mechanism: MechanismData,
  bounds: ScaledBounds
): string => {
  const type = normalizeMechanismType(mechanism.type)
  if (type === '4_bar_linkage') {
    return generateFourBarSvg({ params: mechanism.params as Record<string, number | number[]> }, bounds)
  }
  if (type === 'cam') {
    return generateCamSvg({ params: toParams(mechanism), key_points: readKeyPoints(mechanism) }, bounds)
  }
  if (type === 'gear') {
    return generateGearMeshSvg({ params: toParams(mechanism), key_points: readKeyPoints(mechanism) }, bounds)
  }
  if (type === 'planetary_gear') {
    return generatePlanetaryGearSvg({ params: toParams(mechanism), key_points: readKeyPoints(mechanism) }, bounds)
  }
  return `<text x="10" y="20" font-size="10">Unsupported mechanism: ${mechanism.type}</text>`
}

export const estimateMechanismBounds = (mechanism: MechanismData): ScaledBounds => {
  const type = normalizeMechanismType(mechanism.type)
  if (type === '4_bar_linkage') {
    return { width: 100, height: 30 }
  }
  if (type === 'cam') {
    return { width: 80, height: 80 }
  }
  if (type === 'gear' || type === 'planetary_gear') {
    return { width: 80, height: 80 }
  }
  return { width: 60, height: 60 }
}

const normalizeMechanismType = (value: string): string => {
  if (value === 'four_bar' || value === 'fourbar' || value === '4_bar_linkage') {
    return '4_bar_linkage'
  }
  if (value === 'cam_follower') {
    return 'cam'
  }
  if (value === 'gear_train' || value === 'simple_gear') {
    return 'gear'
  }
  if (value === 'planetary') {
    return 'planetary_gear'
  }
  return value
}

const toParams = (mechanism: MechanismData): Record<string, number> => {
  const output: Record<string, number> = {}
  Object.entries(mechanism.params ?? {}).forEach(([key, value]) => {
    if (typeof value === 'number' && Number.isFinite(value)) {
      output[key] = value
    }
    if (Array.isArray(value) && value.length >= 2 && typeof value[0] === 'number') {
      output[key] = value[0]
    }
  })
  return output
}

const readKeyPoints = (mechanism: MechanismData): Record<string, [number, number]> => {
  const keyPoints = mechanism.params?.key_points
  if (keyPoints && typeof keyPoints === 'object') {
    return keyPoints as Record<string, [number, number]>
  }
  return {}
}
