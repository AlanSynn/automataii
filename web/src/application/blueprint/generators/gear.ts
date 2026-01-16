import type { ScaledBounds } from '../types'

export interface GearMechanismData {
  key_points?: Record<string, [number, number]>
  total_scale_factor?: number
  real_world_params?: Record<string, number>
  params?: Record<string, number>
}

const MODULE_MM = 2
const HUB_RATIO = 0.4
const SHAFT_DIAMETER_MM = 6
const MIN_TEETH = 8

export const generateGearMeshSvg = (
  mechData: GearMechanismData,
  bounds: ScaledBounds
): string => {
  const mm = extractMmParams(mechData, ['r1_mm', 'r2_mm'])
  const r1 = mm.r1_mm ?? 30
  const r2 = mm.r2_mm ?? 20

  const keyPoints = mechData.key_points ?? {}
  const factor = Number(mechData.total_scale_factor ?? 1)
  const c1: [number, number] = keyPoints.gear1_center
    ? [keyPoints.gear1_center[0] * factor, keyPoints.gear1_center[1] * factor]
    : [0, 0]
  const c2: [number, number] = keyPoints.gear2_center
    ? [keyPoints.gear2_center[0] * factor, keyPoints.gear2_center[1] * factor]
    : [r1 + r2, 0]

  const xs = [c1[0] - r1, c1[0] + r1, c2[0] - r2, c2[0] + r2]
  const ys = [c1[1] - r1, c1[1] + r1, c2[1] - r2, c2[1] + r2]
  const minX = Math.min(...xs)
  const maxX = Math.max(...xs)
  const minY = Math.min(...ys)
  const maxY = Math.max(...ys)
  const width = Math.max(10, maxX - minX)
  const height = Math.max(10, maxY - minY)

  const margin = 8
  const availW = Math.max(10, bounds.width - 2 * margin)
  const availH = Math.max(10, bounds.height - 2 * margin)
  const scale = Math.min(1, availW / width, availH / height)

  const pack = (pt: [number, number]): [number, number] => [
    (pt[0] - minX) * scale + margin,
    (pt[1] - minY) * scale + margin,
  ]

  const c1p = pack(c1)
  const c2p = pack(c2)
  const r1p = r1 * scale
  const r2p = r2 * scale

  const teeth1 = Math.max(Math.trunc((2 * r1) / MODULE_MM), MIN_TEETH)
  const teeth2 = Math.max(Math.trunc((2 * r2) / MODULE_MM), MIN_TEETH)
  const gearRatio = r2 > 0 ? r1 / r2 : 1

  const parts = [
    generateGearGradients(),
    generateDetailedGear(c1p, r1p, teeth1, 'gear-gradient-1', 'Gear 1', r1, scale),
    generateDetailedGear(c2p, r2p, teeth2, 'gear-gradient-2', 'Gear 2', r2, scale),
    `<line x1="${c1p[0].toFixed(1)}" y1="${c1p[1].toFixed(1)}" x2="${c2p[0].toFixed(1)}" y2="${c2p[1].toFixed(1)}" stroke="#666" stroke-width="0.8" stroke-dasharray="3,3"/>`,
    `<text x="${((c1p[0] + c2p[0]) / 2).toFixed(1)}" y="${((c1p[1] + c2p[1]) / 2 - 8).toFixed(1)}" font-size="7" text-anchor="middle" fill="#666">Center: ${(r1 + r2).toFixed(1)}mm</text>`,
    generateSpecPanel(bounds, r1, r2, teeth1, teeth2, gearRatio),
  ]

  return parts.join('')
}

export const generatePlanetaryGearSvg = (
  mechData: GearMechanismData,
  bounds: ScaledBounds
): string => {
  const mm = extractMmParams(mechData, ['r_sun_mm', 'r_planet_mm'])
  const rs = mm.r_sun_mm ?? 20
  const rp = mm.r_planet_mm ?? 12
  const rr = rs + 2 * rp
  const numPlanets = 3

  const keyPoints = mechData.key_points ?? {}
  const factor = Number(mechData.total_scale_factor ?? 1)
  const center: [number, number] = keyPoints.sun_center
    ? [keyPoints.sun_center[0] * factor, keyPoints.sun_center[1] * factor]
    : [rr, rr]

  const outerRadius = rr + 10
  const minX = center[0] - outerRadius
  const maxX = center[0] + outerRadius
  const minY = center[1] - outerRadius
  const maxY = center[1] + outerRadius
  const width = Math.max(10, maxX - minX)
  const height = Math.max(10, maxY - minY)

  const margin = 8
  const availW = Math.max(10, bounds.width - 2 * margin)
  const availH = Math.max(10, bounds.height - 2 * margin)
  const scale = Math.min(1, availW / width, availH / height)

  const pack = (pt: [number, number]): [number, number] => [
    (pt[0] - minX) * scale + margin,
    (pt[1] - minY) * scale + margin,
  ]

  const cp = pack(center)
  const rsp = rs * scale
  const rpp = rp * scale
  const rrp = rr * scale

  const parts = [generatePlanetaryGradients()]
  parts.push(
    `<circle cx="${cp[0].toFixed(1)}" cy="${cp[1].toFixed(1)}" r="${rrp.toFixed(1)}" fill="none" stroke="#34495e" stroke-width="3"/>`
  )
  parts.push(
    `<circle cx="${cp[0].toFixed(1)}" cy="${cp[1].toFixed(1)}" r="${(rrp + 5).toFixed(1)}" fill="none" stroke="#7f8c8d" stroke-width="1" stroke-dasharray="2,2"/>`
  )

  const sunTeeth = Math.max(Math.trunc((2 * rs) / MODULE_MM), MIN_TEETH)
  parts.push(generateDetailedGear(cp, rsp, sunTeeth, 'sun-gradient', 'Sun', rs, scale))

  const planetOrbit = rs + rp
  const planetTeeth = Math.max(Math.trunc((2 * rp) / MODULE_MM), MIN_TEETH)
  for (let i = 0; i < numPlanets; i += 1) {
    const angle = (2 * Math.PI * i) / numPlanets
    const px = cp[0] + planetOrbit * scale * Math.cos(angle)
    const py = cp[1] + planetOrbit * scale * Math.sin(angle)
    parts.push(
      generateDetailedGear([px, py], rpp, planetTeeth, 'planet-gradient', `P${i + 1}`, rp, scale)
    )
  }

  parts.push(
    `<circle cx="${cp[0].toFixed(1)}" cy="${cp[1].toFixed(1)}" r="${(planetOrbit * scale).toFixed(1)}" fill="none" stroke="#e74c3c" stroke-width="1" stroke-dasharray="5,3"/>`
  )

  return parts.join('')
}

const generateDetailedGear = (
  center: [number, number],
  radius: number,
  teeth: number,
  gradientId: string,
  gearName: string,
  actualRadiusMm: number,
  scale: number
): string => {
  const hubRadius = radius * HUB_RATIO
  const shaftRadius = (SHAFT_DIAMETER_MM / 2) * scale
  const toothHeight = Math.max(2 * scale, 1)
  const keywayWidth = Math.max(2 * scale, 1)

  const toothPath = generateTeethPath(center, radius, teeth, toothHeight)

  return `
    <g>
      <path d="${toothPath}" fill="url(#${gradientId})" stroke="#2c3e50" stroke-width="1"/>
      <circle cx="${center[0].toFixed(1)}" cy="${center[1].toFixed(1)}" r="${hubRadius.toFixed(1)}" fill="#fff" stroke="#2c3e50" stroke-width="1"/>
      <circle cx="${center[0].toFixed(1)}" cy="${center[1].toFixed(1)}" r="${shaftRadius.toFixed(1)}" fill="#2c3e50"/>
      <rect x="${(center[0] - keywayWidth / 2).toFixed(1)}" y="${(center[1] - hubRadius).toFixed(1)}" width="${keywayWidth.toFixed(1)}" height="${hubRadius.toFixed(1)}" fill="#fff" stroke="#2c3e50" stroke-width="0.6"/>
      <text x="${center[0].toFixed(1)}" y="${(center[1] - radius - 8).toFixed(1)}" font-size="8" text-anchor="middle">${gearName}</text>
      <text x="${center[0].toFixed(1)}" y="${(center[1] + radius + 12).toFixed(1)}" font-size="7" text-anchor="middle">${actualRadiusMm.toFixed(1)}mm</text>
    </g>`
}

const generateTeethPath = (
  center: [number, number],
  radius: number,
  teeth: number,
  toothHeight: number
): string => {
  const points: Array<[number, number]> = []
  const total = teeth * 2
  for (let i = 0; i < total; i += 1) {
    const angle = (2 * Math.PI * i) / total
    const r = i % 2 === 0 ? radius + toothHeight : radius
    points.push([center[0] + r * Math.cos(angle), center[1] + r * Math.sin(angle)])
  }
  const path = points
    .map((point, index) => `${index === 0 ? 'M' : 'L'}${point[0].toFixed(1)},${point[1].toFixed(1)}`)
    .join(' ')
  return `${path} Z`
}

const generateGearGradients = (): string =>
  `<defs>
    <linearGradient id="gear-gradient-1" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#f7dc6f"/>
      <stop offset="50%" style="stop-color:#f1c40f"/>
      <stop offset="100%" style="stop-color:#b7950b"/>
    </linearGradient>
    <linearGradient id="gear-gradient-2" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#d5dbdb"/>
      <stop offset="50%" style="stop-color:#95a5a6"/>
      <stop offset="100%" style="stop-color:#566573"/>
    </linearGradient>
    <linearGradient id="sun-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#f9e79f"/>
      <stop offset="50%" style="stop-color:#f5cba7"/>
      <stop offset="100%" style="stop-color:#d35400"/>
    </linearGradient>
    <linearGradient id="planet-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#aed6f1"/>
      <stop offset="50%" style="stop-color:#5dade2"/>
      <stop offset="100%" style="stop-color:#2e86c1"/>
    </linearGradient>
  </defs>`

const generatePlanetaryGradients = (): string =>
  `<defs>
    <linearGradient id="sun-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#f9e79f"/>
      <stop offset="50%" style="stop-color:#f5cba7"/>
      <stop offset="100%" style="stop-color:#d35400"/>
    </linearGradient>
    <linearGradient id="planet-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#aed6f1"/>
      <stop offset="50%" style="stop-color:#5dade2"/>
      <stop offset="100%" style="stop-color:#2e86c1"/>
    </linearGradient>
  </defs>`

const generateSpecPanel = (
  bounds: ScaledBounds,
  r1: number,
  r2: number,
  teeth1: number,
  teeth2: number,
  ratio: number
): string =>
  `<g class="gear-manufacturing-specs">
    <rect x="${(bounds.width - 160).toFixed(1)}" y="10" width="150" height="110" fill="#f8f9fa" stroke="#dee2e6" stroke-width="1" rx="3"/>
    <text x="${(bounds.width - 155).toFixed(1)}" y="25" font-size="8" font-weight="bold">Gear Specifications</text>
    <text x="${(bounds.width - 155).toFixed(1)}" y="40" font-size="7">Gear 1 radius: ${r1.toFixed(1)}mm</text>
    <text x="${(bounds.width - 155).toFixed(1)}" y="52" font-size="7">Gear 2 radius: ${r2.toFixed(1)}mm</text>
    <text x="${(bounds.width - 155).toFixed(1)}" y="64" font-size="7">Teeth: ${teeth1}/${teeth2}</text>
    <text x="${(bounds.width - 155).toFixed(1)}" y="76" font-size="7">Ratio: ${ratio.toFixed(2)}:1</text>
  </g>`

const extractMmParams = (
  mechData: GearMechanismData,
  keys: string[]
): Record<string, number> => {
  const real = mechData.real_world_params ?? {}
  const params = mechData.params ?? {}
  const output: Record<string, number> = {}
  keys.forEach((key) => {
    const value = real[key] ?? params[key]
    if (typeof value === 'number' && Number.isFinite(value)) {
      output[key] = value
    }
  })
  return output
}
