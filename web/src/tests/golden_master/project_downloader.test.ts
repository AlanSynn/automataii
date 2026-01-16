import { describe, expect, it } from 'vitest'

import { resolveProjectFilename } from '../../application/project'
import { ProjectState } from '../../domain/project'

const buildState = (name: string) => {
  const state = ProjectState.empty()
  return state.withMetadata({
    ...state.metadata,
    name,
  })
}

describe('resolveProjectFilename', () => {
  it('uses metadata name when available', () => {
    const state = buildState('My Project')
    expect(resolveProjectFilename(state)).toBe('My Project')
  })

  it('falls back to default for empty names', () => {
    const state = buildState('   ')
    expect(resolveProjectFilename(state)).toBe('project')
  })
})
