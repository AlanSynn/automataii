import type { ScaledBounds } from '../types'

export interface FourBarMechanismData {
  params?: Record<string, number | number[]>
}

export const generateFourBarSvg = (
  mechData: FourBarMechanismData,
  bounds: ScaledBounds
): string => {
  const params = mechData.params ?? {}
  const anchor1 = toPoint(params.anchor1, [0, 0])
  const anchor2 = toPoint(params.anchor2, [100, 0])
  const crank = toNumber(params.l2, 40)
  const rocker = toNumber(params.l4, 50)

  const minX = Math.min(anchor1[0], anchor2[0], anchor1[0] + crank, anchor2[0] - rocker)
  const maxX = Math.max(anchor1[0], anchor2[0], anchor1[0] + crank, anchor2[0] - rocker)
  const minY = Math.min(anchor1[1], anchor2[1])
  const maxY = Math.max(anchor1[1], anchor2[1])
  const width = Math.max(10, maxX - minX + 40)
  const height = Math.max(10, maxY - minY + 40)

  const margin = 10
  const scale = Math.min(1, (bounds.width - 2 * margin) / width, (bounds.height - 2 * margin) / height)

  const pack = (pt: [number, number]): [number, number] => [
    (pt[0] - minX) * scale + margin,
    (pt[1] - minY) * scale + margin,
  ]

  const a1 = pack(anchor1)
  const a2 = pack(anchor2)
  const crankEnd = pack([anchor1[0] + crank, anchor1[1]])
  const rockerEnd = pack([anchor2[0] - rocker, anchor2[1]])

  return `
    <g>
      <line x1="${a1[0].toFixed(1)}" y1="${a1[1].toFixed(1)}" x2="${a2[0].toFixed(1)}" y2="${a2[1].toFixed(1)}" stroke="#2c3e50" stroke-width="2" stroke-dasharray="5,5"/>
      <line x1="${a1[0].toFixed(1)}" y1="${a1[1].toFixed(1)}" x2="${crankEnd[0].toFixed(1)}" y2="${crankEnd[1].toFixed(1)}" stroke="#2980b9" stroke-width="2"/>
      <line x1="${a2[0].toFixed(1)}" y1="${a2[1].toFixed(1)}" x2="${rockerEnd[0].toFixed(1)}" y2="${rockerEnd[1].toFixed(1)}" stroke="#27ae60" stroke-width="2"/>
      <circle cx="${a1[0].toFixed(1)}" cy="${a1[1].toFixed(1)}" r="4" fill="#c0392b"/>
      <circle cx="${a2[0].toFixed(1)}" cy="${a2[1].toFixed(1)}" r="4" fill="#c0392b"/>
      <text x="${a1[0].toFixed(1)}" y="${(a1[1] + 14).toFixed(1)}" font-size="7" text-anchor="middle">Crank ${crank.toFixed(1)}mm</text>
      <text x="${a2[0].toFixed(1)}" y="${(a2[1] + 14).toFixed(1)}" font-size="7" text-anchor="middle">Rocker ${rocker.toFixed(1)}mm</text>
    </g>`
}

const toNumber = (value: unknown, fallback: number): number =>
  typeof value === 'number' && Number.isFinite(value) ? value : fallback

const toPoint = (value: unknown, fallback: [number, number]): [number, number] => {
  if (Array.isArray(value) && value.length >= 2) {
    const x = typeof value[0] === 'number' ? value[0] : fallback[0]
    const y = typeof value[1] === 'number' ? value[1] : fallback[1]
    return [x, y]
  }
  return fallback
}
