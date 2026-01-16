import { useCallback, useState } from 'react'
import type { ChangeEvent } from 'react'

import { ProjectState } from '../../domain/project'
import { ProjectSerializer } from './serializer'

interface ProjectLoadState {
  state: ProjectState | null
  raw: string | null
  filename: string | null
  error: string | null
}

const defaultState: ProjectLoadState = {
  state: null,
  raw: null,
  filename: null,
  error: null,
}

export const useProjectLoader = (): [
  ProjectLoadState,
  (event: ChangeEvent<HTMLInputElement>) => void,
  (state: ProjectState | null) => void
] => {
  const [loadState, setLoadState] = useState<ProjectLoadState>(defaultState)
  const serializer = new ProjectSerializer()

  const handleFileChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0] ?? null
      if (!file) {
        setLoadState(defaultState)
        return
      }
      file
        .text()
        .then((contents) => {
          const result = serializer.deserialize(contents, null)
          if (!result.success) {
            setLoadState({
              state: null,
              raw: contents,
              filename: file.name,
              error: result.error,
            })
            return
          }
          setLoadState({
            state: result.state,
            raw: contents,
            filename: file.name,
            error: null,
          })
        })
        .catch((error: unknown) => {
          setLoadState({
            state: null,
            raw: null,
            filename: file.name,
            error: error instanceof Error ? error.message : 'Failed to read file',
          })
        })
    },
    [serializer]
  )

  const setProjectState = useCallback((state: ProjectState | null) => {
    setLoadState((current) => ({
      ...current,
      state,
      error: null,
    }))
  }, [])

  return [loadState, handleFileChange, setProjectState]
}
