import type { MechanismData, PartData, ProjectState } from '../../domain/project'
import type { BlueprintCompositionResult, BlueprintLayoutItem, BlueprintPageConfig } from './types'
import { buildMechanismItem, estimateMechanismBounds } from './mechanismRegistry'

const DEFAULT_PAGE_CONFIG: BlueprintPageConfig = {
  margin: 40,
  itemSpacing: 40,
}

export const composeBlueprint = async (
  state: ProjectState,
  options?: {
    unitSystem?: 'metric' | 'imperial'
    snapshotDataUrl?: string | null
    pageConfig?: BlueprintPageConfig
  }
): Promise<BlueprintCompositionResult> => {
  const unitSystem = options?.unitSystem ?? 'metric'
  const pageConfig = options?.pageConfig ?? DEFAULT_PAGE_CONFIG
  const snapshot = options?.snapshotDataUrl ?? null

  const partItems = await buildPartItems(state.parts)
  const mechanismItems = buildMechanismItems(state.mechanisms)
  const items = [...partItems, ...mechanismItems]

  if (items.length === 0) {
    const svg = buildEmptyBlueprintSvg(unitSystem)
    return { svg, width: 300, height: 200, itemCount: 0 }
  }

  const layout = layoutItems(items, pageConfig)
  const width = layout.pageWidth
  const height = layout.pageHeight

  const content = layout.items
    .map((item) => {
      const transform = `translate(${item.x.toFixed(1)},${item.y.toFixed(1)})`
      return `<g transform="${transform}">${item.svgContent}</g>`
    })
    .join('')

  const snapshotSvg = snapshot
    ? `<image href="${snapshot}" x="${pageConfig.margin}" y="${pageConfig.margin}" width="120" height="80"/>`
    : ''

  const svg = `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${width.toFixed(1)}" height="${height.toFixed(1)}" viewBox="0 0 ${width.toFixed(1)} ${height.toFixed(1)}">
  <rect x="5" y="5" width="${(width - 10).toFixed(1)}" height="${(height - 10).toFixed(1)}" fill="white" stroke="#333" stroke-width="2"/>
  <text x="${pageConfig.margin}" y="${pageConfig.margin - 10}" font-size="12" font-family="Arial" font-weight="bold">Automataii Blueprint (${unitSystem})</text>
  ${snapshotSvg}
  ${content}
</svg>`

  return {
    svg,
    width,
    height,
    itemCount: items.length,
  }
}

const buildPartItems = async (parts: Record<string, PartData>): Promise<BlueprintLayoutItem[]> => {
  const entries = Object.values(parts)
  const items: BlueprintLayoutItem[] = []

  for (const part of entries) {
    if (!part.texturePath) {
      continue
    }
    const dimensions = await loadImageDimensions(part.texturePath)
    if (!dimensions) {
      continue
    }
    items.push({
      name: part.name,
      width: dimensions.width,
      height: dimensions.height,
      svgContent: `<image href="${part.texturePath}" width="${dimensions.width}" height="${dimensions.height}"/>`,
      itemType: 'part',
    })
  }

  return items
}

const buildMechanismItems = (mechanisms: Record<string, MechanismData>): BlueprintLayoutItem[] => {
  return Object.values(mechanisms)
    .filter((mechanism) => mechanism.enabled)
    .map((mechanism) => {
      const bounds = estimateMechanismBounds(mechanism)
      return buildMechanismItem(mechanism, bounds)
    })
}

const layoutItems = (
  items: BlueprintLayoutItem[],
  config: BlueprintPageConfig
): { items: Array<BlueprintLayoutItem & { x: number; y: number }>; pageWidth: number; pageHeight: number } => {
  const columns = Math.max(1, Math.ceil(Math.sqrt(items.length)))
  const columnWidths: number[] = new Array(columns).fill(0)
  const rowHeights: number[] = []

  items.forEach((item, index) => {
    const column = index % columns
    columnWidths[column] = Math.max(columnWidths[column], item.width)
  })

  const rows = Math.ceil(items.length / columns)
  for (let row = 0; row < rows; row += 1) {
    const rowItems = items.slice(row * columns, row * columns + columns)
    rowHeights[row] = Math.max(...rowItems.map((item) => item.height), 0)
  }

  const pageWidth =
    config.margin * 2 + columnWidths.reduce((sum, width) => sum + width, 0) + config.itemSpacing * (columns - 1)
  const pageHeight =
    config.margin * 2 + rowHeights.reduce((sum, height) => sum + height, 0) + config.itemSpacing * (rows - 1)

  const positioned = items.map((item, index) => {
    const column = index % columns
    const row = Math.floor(index / columns)
    const x = config.margin + columnWidths.slice(0, column).reduce((sum, width) => sum + width, 0) + config.itemSpacing * column
    const y = config.margin + rowHeights.slice(0, row).reduce((sum, height) => sum + height, 0) + config.itemSpacing * row
    return { ...item, x, y }
  })

  return { items: positioned, pageWidth, pageHeight }
}

const buildEmptyBlueprintSvg = (unitSystem: string): string =>
  `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="300" height="200" viewBox="0 0 300 200">
  <rect x="5" y="5" width="290" height="190" fill="white" stroke="#333" stroke-width="2"/>
  <text x="20" y="30" font-size="12" font-family="Arial" font-weight="bold">Automataii Blueprint (${unitSystem})</text>
  <text x="20" y="60" font-size="10" font-family="Arial">No items to export</text>
</svg>`

const loadImageDimensions = (source: string): Promise<{ width: number; height: number } | null> =>
  new Promise((resolve) => {
    const image = new Image()
    image.onload = () => resolve({ width: image.naturalWidth, height: image.naturalHeight })
    image.onerror = () => resolve(null)
    image.src = source
  })
