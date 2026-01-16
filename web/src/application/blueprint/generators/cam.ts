export interface ScaledBounds {
  width: number
  height: number
}

export interface CamMechanismData {
  key_points?: Record<string, [number, number]>
  total_scale_factor?: number
  real_world_params?: Record<string, number>
  params?: Record<string, number>
}

const CAM_COLOR = '#3498db'
const FOLLOWER_COLOR = '#e74c3c'
const PROFILE_POINTS = 72

export const generateCamSvg = (
  mechData: CamMechanismData,
  bounds: ScaledBounds
): string => {
  const mm = extractMmParams(mechData, ['base_radius_mm', 'lift_mm', 'follower_radius_mm'])
  const baseRadius = mm.base_radius_mm ?? 30
  const lift = mm.lift_mm ?? 15
  const followerRadius = mm.follower_radius_mm ?? 8

  const keyPoints = mechData.key_points ?? {}
  const factor = Number(mechData.total_scale_factor ?? 1)

  const center: [number, number] = keyPoints.cam_center
    ? [keyPoints.cam_center[0] * factor, keyPoints.cam_center[1] * factor]
    : [baseRadius + lift + 20, baseRadius + lift + 20]

  const outerRadius = baseRadius + lift + followerRadius + 20
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

  const centerPacked = pack(center)
  const baseRadiusPx = baseRadius * scale
  const liftPx = lift * scale
  const followerPx = followerRadius * scale

  const profile = calculateProfile(centerPacked, baseRadiusPx, liftPx, PROFILE_POINTS)
  const followerY = centerPacked[1] - baseRadiusPx - liftPx / 2
  const shaftRadius = Math.max(4 * scale, 2)

  const parts = [
    generateCamGradients(),
    drawCamProfile(profile),
    `<circle cx="${centerPacked[0].toFixed(1)}" cy="${centerPacked[1].toFixed(1)}" r="${shaftRadius.toFixed(1)}" fill="#fff" stroke="#2c3e50" stroke-width="1.5"/>`,
    `<circle cx="${centerPacked[0].toFixed(1)}" cy="${centerPacked[1].toFixed(1)}" r="${(shaftRadius * 0.3).toFixed(1)}" fill="#2c3e50"/>`,
    `<circle cx="${centerPacked[0].toFixed(1)}" cy="${followerY.toFixed(1)}" r="${followerPx.toFixed(1)}" fill="url(#follower-gradient)" stroke="${FOLLOWER_COLOR}" stroke-width="1.5"/>`,
    `<line x1="${centerPacked[0].toFixed(1)}" y1="${(followerY + followerPx).toFixed(1)}" x2="${centerPacked[0].toFixed(1)}" y2="${(followerY + followerPx + 30).toFixed(1)}" stroke="#666" stroke-width="2"/>`,
    `<line x1="${centerPacked[0].toFixed(1)}" y1="${centerPacked[1].toFixed(1)}" x2="${(centerPacked[0] + baseRadiusPx).toFixed(1)}" y2="${centerPacked[1].toFixed(1)}" stroke="#666" stroke-width="0.5" stroke-dasharray="2,2"/>`,
    `<text x="${(centerPacked[0] + baseRadiusPx / 2).toFixed(1)}" y="${(centerPacked[1] + 12).toFixed(1)}" font-size="7" text-anchor="middle" fill="#666">Base R: ${baseRadius.toFixed(1)}mm</text>`,
    `<line x1="${(centerPacked[0] + baseRadiusPx + 15).toFixed(1)}" y1="${(centerPacked[1] - baseRadiusPx).toFixed(1)}" x2="${(centerPacked[0] + baseRadiusPx + 15).toFixed(1)}" y2="${(centerPacked[1] - baseRadiusPx - liftPx).toFixed(1)}" stroke="#e74c3c" stroke-width="0.8"/>`,
    `<text x="${(centerPacked[0] + baseRadiusPx + 25).toFixed(1)}" y="${(centerPacked[1] - baseRadiusPx - liftPx / 2).toFixed(1)}" font-size="7" text-anchor="start" fill="#e74c3c">Lift: ${lift.toFixed(1)}mm</text>`,
    generateSpecPanel(bounds, baseRadius, lift, followerRadius),
  ]

  return parts.join('')
}

const calculateProfile = (
  center: [number, number],
  baseRadius: number,
  lift: number,
  points: number
): Array<[number, number]> => {
  const profile: Array<[number, number]> = []
  for (let i = 0; i < points; i += 1) {
    const angle = (2 * Math.PI * i) / points
    const displacement =
      angle < Math.PI
        ? (lift / 2) * (1 - Math.cos(angle))
        : (lift / 2) * (1 + Math.cos(angle - Math.PI))
    const radius = baseRadius + displacement
    const x = center[0] + radius * Math.cos(angle - Math.PI / 2)
    const y = center[1] + radius * Math.sin(angle - Math.PI / 2)
    profile.push([x, y])
  }
  return profile
}

const drawCamProfile = (points: Array<[number, number]>): string => {
  if (points.length === 0) {
    return ''
  }
  const path = points
    .map((point, index) => `${index === 0 ? 'M' : 'L'}${point[0].toFixed(1)},${point[1].toFixed(1)}`)
    .join(' ')
  return `<path d="${path} Z" fill="url(#cam-gradient)" stroke="${CAM_COLOR}" stroke-width="2"/>`
}

const generateCamGradients = (): string =>
  `<defs>
    <linearGradient id="cam-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#aed6f1"/>
      <stop offset="50%" style="stop-color:#5dade2"/>
      <stop offset="100%" style="stop-color:#2980b9"/>
    </linearGradient>
    <linearGradient id="follower-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#f5b7b1"/>
      <stop offset="50%" style="stop-color:#e74c3c"/>
      <stop offset="100%" style="stop-color:#c0392b"/>
    </linearGradient>
  </defs>`

const generateSpecPanel = (
  bounds: ScaledBounds,
  baseRadius: number,
  lift: number,
  followerRadius: number
): string =>
  `<g class="cam-manufacturing-specs">
    <rect x="${(bounds.width - 160).toFixed(1)}" y="10" width="150" height="90" fill="#f8f9fa" stroke="#dee2e6" stroke-width="1" rx="3"/>
    <text x="${(bounds.width - 155).toFixed(1)}" y="25" font-size="8" font-weight="bold">Cam Specifications</text>
    <text x="${(bounds.width - 155).toFixed(1)}" y="40" font-size="7">Base radius: ${baseRadius.toFixed(1)}mm</text>
    <text x="${(bounds.width - 155).toFixed(1)}" y="52" font-size="7">Lift: ${lift.toFixed(1)}mm</text>
    <text x="${(bounds.width - 155).toFixed(1)}" y="64" font-size="7">Follower radius: ${followerRadius.toFixed(1)}mm</text>
  </g>`

const extractMmParams = (
  mechData: CamMechanismData,
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
