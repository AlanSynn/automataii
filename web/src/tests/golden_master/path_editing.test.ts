import { describe, expect, it } from 'vitest'

import {
  buildPathDataFromPoints,
  buildTimedPoints,
  smoothPathPoints,
} from '../../application/motion_paths/pathEditing'

const buildSquare = () => [
  { x: 0, y: 0 },
  { x: 10, y: 0 },
  { x: 10, y: 10 },
  { x: 0, y: 10 },
]

describe('path editing helpers', () => {
  it('smooths paths with additional points', () => {
    const points = buildSquare()
    const smoothed = smoothPathPoints(points, false, 60)
    expect(smoothed.length).toBeGreaterThan(points.length)
    expect(smoothed[0]).toEqual(points[0])
    expect(smoothed[smoothed.length - 1]).toEqual(points[points.length - 1])
  })

  it('builds timed points with total duration', () => {
    const points = buildSquare()
    const timed = buildTimedPoints(points, 4)
    expect(timed).not.toBeNull()
    if (!timed) {
      return
    }
    expect(timed[0].t).toBeCloseTo(0)
    expect(timed[timed.length - 1].t).toBeCloseTo(4)
  })

  it('builds path data with timing and closure', () => {
    const points = buildSquare()
    const path = buildPathDataFromPoints(points, {
      partName: 'arm',
      isClosed: true,
      smoothness: 40,
      timed: true,
      totalDuration: 5,
    })
    expect(path.partName).toBe('arm')
    expect(path.isClosed).toBe(true)
    expect(path.totalDuration).toBe(5)
    expect(path.timedPoints).not.toBeNull()
  })
})
