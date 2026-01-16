import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { ProjectSerializer } from '../../application/project'
import { PathUtils } from '../../domain/project'

const readFixture = (relativePath: string): string => {
  const modulePath = fileURLToPath(new URL(`./fixtures/${relativePath}`, import.meta.url))
  const fallbackPath = resolve(
    process.cwd(),
    'src/tests/golden_master/fixtures',
    relativePath
  )
  const fixturePath = existsSync(modulePath) ? modulePath : fallbackPath
  return readFileSync(fixturePath, 'utf8')
}

describe('golden master fixtures', () => {
  it('round-trips the v2 project fixture', () => {
    const serializer = new ProjectSerializer()
    const contents = readFixture('project_state.automataii')
    const loadResult = serializer.deserialize(contents, null)
    expect(loadResult.success).toBe(true)
    if (!loadResult.success) {
      return
    }
    const saveResult = serializer.serialize(loadResult.state, 'fixture', {
      updateModified: false,
    })
    expect(saveResult.success).toBe(true)
    if (!saveResult.success) {
      return
    }
    const original = JSON.parse(contents) as Record<string, unknown>
    const serialized = JSON.parse(saveResult.contents) as Record<string, unknown>
    expect(serialized).toEqual(original)
  })

  it('migrates v1 fixtures to v2 metadata', () => {
    const serializer = new ProjectSerializer()
    const contents = readFixture('project_state_v1.json')
    const loadResult = serializer.deserialize(contents, null)
    expect(loadResult.success).toBe(true)
    if (!loadResult.success) {
      return
    }
    expect(loadResult.state.metadata.version).toBe('2.0')
    expect(Object.keys(loadResult.state.parts).length).toBeGreaterThan(0)
  })

  it('matches golden master path samples', () => {
    const raw = readFixture('path_samples.json')
    const samples = JSON.parse(raw) as {
      uniform: { points: [number, number][]; progress: number[]; expected: [number, number][] }
      timed: {
        timed_points: [number, number, number][]
        total_duration: number
        progress: number[]
        expected: [number, number][]
      }
    }

    const uniformPath = {
      partName: 'torso',
      points: samples.uniform.points.map(([x, y]) => ({ x, y })),
      timedPoints: null,
      totalDuration: null,
      isClosed: false,
      enabled: true,
    }
    const uniformResults = samples.uniform.progress.map((progress) =>
      PathUtils.getPointAtProgress(uniformPath, progress)
    )
    expect(uniformResults.map((point) => [point.x, point.y])).toEqual(
      samples.uniform.expected
    )

    const timedPath = {
      partName: 'torso',
      points: samples.uniform.points.map(([x, y]) => ({ x, y })),
      timedPoints: samples.timed.timed_points.map(([x, y, t]) => ({ x, y, t })),
      totalDuration: samples.timed.total_duration,
      isClosed: false,
      enabled: true,
    }
    const timedResults = samples.timed.progress.map((progress) =>
      PathUtils.getPointAtProgress(timedPath, progress)
    )
    expect(timedResults.map((point) => [point.x, point.y])).toEqual(samples.timed.expected)
  })
})
