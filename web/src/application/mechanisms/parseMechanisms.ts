import type { MechanismData } from '../../domain/project'

export interface MechanismParseResult {
  success: boolean
  error: string | null
  mechanisms: Record<string, MechanismData> | null
}

export const parseMechanismsJson = (json: string): MechanismParseResult => {
  let parsed: unknown
  try {
    parsed = JSON.parse(json)
  } catch (error) {
    return { success: false, error: errorMessage(error), mechanisms: null }
  }
  const normalized = normalizeMechanisms(parsed)
  if (!normalized.success) {
    return { success: false, error: normalized.error, mechanisms: null }
  }
  return { success: true, error: null, mechanisms: normalized.value }
}

const normalizeMechanisms = (
  input: unknown
): { success: true; value: Record<string, MechanismData> } | { success: false; error: string } => {
  if (Array.isArray(input)) {
    const record: Record<string, MechanismData> = {}
    for (const item of input) {
      if (!isRecord(item)) {
        return { success: false, error: 'Mechanism entries must be objects.' }
      }
      const entry = toMechanismData(item)
      if (!entry.success) {
        return entry
      }
      record[entry.value.id] = entry.value
    }
    return { success: true, value: record }
  }
  if (isRecord(input)) {
    const record: Record<string, MechanismData> = {}
    for (const [key, value] of Object.entries(input)) {
      if (!isRecord(value)) {
        return { success: false, error: `Mechanism ${key} must be an object.` }
      }
      const entry = toMechanismData({ ...value, id: value.id ?? key })
      if (!entry.success) {
        return entry
      }
      record[entry.value.id] = entry.value
    }
    return { success: true, value: record }
  }
  return { success: false, error: 'Mechanisms JSON must be an array or object.' }
}

const toMechanismData = (
  value: Record<string, unknown>
): { success: true; value: MechanismData } | { success: false; error: string } => {
  const id = typeof value.id === 'string' ? value.id : null
  const type = typeof value.type === 'string' ? value.type : null
  const partName = typeof value.part_name === 'string'
    ? value.part_name
    : typeof value.partName === 'string'
      ? value.partName
      : ''
  const enabled = typeof value.enabled === 'boolean' ? value.enabled : true
  if (!id || !type) {
    return { success: false, error: 'Mechanism id and type are required.' }
  }
  return {
    success: true,
    value: {
      id,
      type,
      partName,
      params: isRecord(value.params) ? (value.params as Record<string, string | number | boolean | null>) : {},
      enabled,
    },
  }
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const errorMessage = (error: unknown): string => {
  if (error instanceof Error) {
    return error.message
  }
  return 'Invalid JSON'
}
