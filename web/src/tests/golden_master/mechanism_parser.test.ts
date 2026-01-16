import { describe, expect, it } from 'vitest'

import { parseMechanismsJson } from '../../application/mechanisms'

describe('parseMechanismsJson', () => {
  it('parses array form', () => {
    const json = JSON.stringify([
      { id: 'm1', type: 'gear', partName: 'arm', params: { r1_mm: 10 }, enabled: true },
    ])
    const result = parseMechanismsJson(json)
    expect(result.success).toBe(true)
    expect(result.mechanisms?.m1?.type).toBe('gear')
  })

  it('parses record form', () => {
    const json = JSON.stringify({
      m2: { type: 'cam', part_name: 'arm', params: { base_radius_mm: 5 } },
    })
    const result = parseMechanismsJson(json)
    expect(result.success).toBe(true)
    expect(result.mechanisms?.m2?.type).toBe('cam')
  })

  it('fails on invalid json', () => {
    const result = parseMechanismsJson('{bad}')
    expect(result.success).toBe(false)
    expect(result.error).toBeTruthy()
  })
})
