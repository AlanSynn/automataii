import { describe, expect, it } from 'vitest'

import { buildProjectStateFromSkeleton } from '../../application/onnx/projectStateBuilder'

const buildSkeleton = () => ({
  joints: {
    root: {
      id: 'root',
      position: { x: 1, y: 2 },
      parent: null,
      isLocked: false,
      bendDirection: 'up',
    },
  },
  bones: [],
  rootJoint: 'root',
})

describe('buildProjectStateFromSkeleton', () => {
  it('returns null when skeleton is missing', () => {
    expect(buildProjectStateFromSkeleton(null, null)).toBeNull()
  })

  it('builds a project state with metadata and image path', () => {
    const state = buildProjectStateFromSkeleton(
      { name: 'photo.png', url: 'blob://image', width: 10, height: 10 },
      buildSkeleton(),
      {
        torso: {
          name: 'torso',
          texturePath: 'data:image/png;base64,AA',
          maskPath: 'data:image/png;base64,BB',
          anchorJoint: 'root',
          pivot: { x: 0, y: 0 },
          transform: { x: 0, y: 0, rotation: 0, scale: 1 },
          zIndex: 0,
        },
      }
    )
    expect(state).not.toBeNull()
    if (!state) {
      return
    }
    expect(state.imagePath).toBe('photo.png')
    expect(state.metadata.name).toBe('photo.png')
    expect(state.skeleton?.rootJoint).toBe('root')
    expect(Object.keys(state.parts)).toEqual(['torso'])
  })
})
