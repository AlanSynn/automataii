import { ProjectState, type ProjectMetadata } from '../../domain/project'

type SaveResult =
  | { success: true; filename: string; contents: string }
  | { success: false; error: string }

type LoadResult =
  | { success: true; state: ProjectState }
  | { success: false; error: string }

interface ProjectMigrator {
  canMigrate(version: string): boolean
  migrate(data: Record<string, unknown>): Record<string, unknown>
}

const FILE_EXTENSION = '.automataii'
const CURRENT_VERSION = '2.0'

export class ProjectSerializer {
  private readonly migrators: ProjectMigrator[] = [new V1ToV2Migrator()]

  serialize(
    state: ProjectState,
    filename: string,
    options?: { updateModified?: boolean }
  ): SaveResult {
    if (!filename.trim()) {
      return { success: false, error: 'Filename is required.' }
    }
    const normalized = ensureExtension(filename)
    const metadata: ProjectMetadata = {
      ...state.metadata,
      version: CURRENT_VERSION,
      modifiedAt: options?.updateModified === false
        ? state.metadata.modifiedAt
        : new Date().toISOString(),
    }
    const stateToSave = state.withMetadata(metadata)
    const contents = JSON.stringify(stateToSave.toDict(), null, 2)
    return { success: true, filename: normalized, contents }
  }

  deserialize(contents: string, projectDir: string | null): LoadResult {
    let parsed: unknown
    try {
      parsed = JSON.parse(contents)
    } catch (error) {
      return { success: false, error: errorMessage(error) }
    }
    if (!isRecord(parsed)) {
      return { success: false, error: 'Project file is not an object.' }
    }
    const migrated = this.migrateIfNeeded(parsed)
    try {
      const state = ProjectState.fromDict(migrated, projectDir)
      return { success: true, state }
    } catch (error) {
      return { success: false, error: errorMessage(error) }
    }
  }

  private migrateIfNeeded(data: Record<string, unknown>): Record<string, unknown> {
    const version = getMetadataVersion(data)
    const migrator = this.migrators.find((candidate) => candidate.canMigrate(version))
    if (!migrator) {
      return data
    }
    return migrator.migrate(data)
  }
}

class V1ToV2Migrator implements ProjectMigrator {
  canMigrate(version: string): boolean {
    return normalizeVersion(version) === '1.0'
  }

  migrate(data: Record<string, unknown>): Record<string, unknown> {
    const output: Record<string, unknown> = { ...data }
    if (!isRecord(output.metadata)) {
      output.metadata = createMetadata(output)
    } else {
      output.metadata = normalizeMetadata(output.metadata)
    }
    if (isRecord(output.layers) && !isRecord(output.parts)) {
      output.parts = output.layers
    }
    if (!isRecord(output.parts)) {
      output.parts = {}
    }
    if (!isRecord(output.paths)) {
      output.paths = {}
    }
    if (!isRecord(output.mechanisms)) {
      output.mechanisms = {}
    }
    delete output.layers
    return output
  }
}

const ensureExtension = (name: string): string =>
  name.endsWith(FILE_EXTENSION) ? name : `${name}${FILE_EXTENSION}`

const normalizeVersion = (version: string): string => {
  const numeric = Number.parseFloat(version)
  if (!Number.isNaN(numeric)) {
    return numeric.toFixed(1)
  }
  return version
}

const getMetadataVersion = (data: Record<string, unknown>): string => {
  if (isRecord(data.metadata)) {
    return String(data.metadata.version ?? '1.0')
  }
  if (typeof data.project_version === 'number' || typeof data.project_version === 'string') {
    return String(data.project_version)
  }
  return '1.0'
}

const createMetadata = (data: Record<string, unknown>): ProjectMetadata => {
  const now = new Date().toISOString()
  return {
    version: CURRENT_VERSION,
    name:
      typeof data.project_name === 'string' && data.project_name.trim().length > 0
        ? data.project_name
        : 'Untitled',
    createdAt: now,
    modifiedAt: now,
  }
}

const normalizeMetadata = (metadata: Record<string, unknown>): ProjectMetadata => ({
  version: typeof metadata.version === 'string' ? metadata.version : CURRENT_VERSION,
  name: typeof metadata.name === 'string' ? metadata.name : 'Untitled',
  createdAt:
    typeof metadata.created_at === 'string' ? metadata.created_at : new Date().toISOString(),
  modifiedAt:
    typeof metadata.modified_at === 'string' ? metadata.modified_at : new Date().toISOString(),
})

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const errorMessage = (error: unknown): string => {
  if (error instanceof Error) {
    return error.message
  }
  return 'Unknown error'
}
