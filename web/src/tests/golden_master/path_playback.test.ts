import { describe, expect, it } from 'vitest'

import { applyTimingProfile, clampProgress, type TimingProfile } from '../../application/motion_paths'

describe('clampProgress', () => {
  it('clamps values to 0..1', () => {
    expect(clampProgress(-1)).toBe(0)
    expect(clampProgress(0.5)).toBe(0.5)
    expect(clampProgress(2)).toBe(1)
  })
})

describe('applyTimingProfile', () => {
  const profiles: TimingProfile[] = [
    'linear',
    'ease_in_out',
    'ease_in',
    'ease_out',
    'elastic',
  ]

  it('preserves endpoints for non-bounce profiles', () => {
    profiles.forEach((profile) => {
      expect(applyTimingProfile(0, profile)).toBeCloseTo(0)
      expect(applyTimingProfile(1, profile)).toBeCloseTo(1)
    })
  })

  it('bounces past 1.0 at the end', () => {
    expect(applyTimingProfile(1, 'bounce')).toBeCloseTo(1.5)
  })
})
