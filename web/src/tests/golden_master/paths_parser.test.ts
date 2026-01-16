import { describe, expect, it } from 'vitest'

import { parsePathsJson } from '../../application/motion_paths'

describe('parsePathsJson', () => {
  it('parses path entries', () => {
    const json = JSON.stringify({
      arm: {
        part_name: 'arm',
        points: [
          [0, 0],
          [10, 10],
        ],
        is_closed: true,
      },
    })
    const result = parsePathsJson(json)
    expect(result.success).toBe(true)
    expect(result.paths?.arm.points.length).toBe(2)
    expect(result.paths?.arm.isClosed).toBe(true)
  })

  it('fails on invalid json', () => {
    const result = parsePathsJson('{bad}')
    expect(result.success).toBe(false)
  })
})
