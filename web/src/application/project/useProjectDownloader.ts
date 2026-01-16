import { useCallback } from 'react'
import type { ProjectState } from '../../domain/project'

import { ProjectSerializer } from './serializer'

export interface DownloadResult {
  success: boolean
  error: string | null
  filename: string | null
}

export const resolveProjectFilename = (
  state: ProjectState,
  fallbackName = 'project'
): string => {
  const baseName = state.metadata.name?.trim() || fallbackName
  return baseName
}

export const useProjectDownloader = (): {
  downloadProject: (state: ProjectState, filename?: string) => DownloadResult
} => {
  const serializer = new ProjectSerializer()

  const downloadProject = useCallback(
    (state: ProjectState, filename?: string): DownloadResult => {
      const baseName = filename?.trim() || resolveProjectFilename(state)
      const result = serializer.serialize(state, baseName, { updateModified: false })
      if (!result.success) {
        return { success: false, error: result.error, filename: null }
      }
      const blob = new Blob([result.contents], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = result.filename
      link.click()
      URL.revokeObjectURL(url)
      return { success: true, error: null, filename: result.filename }
    },
    [serializer]
  )

  return { downloadProject }
}
