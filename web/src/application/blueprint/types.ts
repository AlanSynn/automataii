export type BlueprintItemType = 'part' | 'mechanism'

export interface BlueprintLayoutItem {
  name: string
  width: number
  height: number
  svgContent: string
  itemType: BlueprintItemType
}

export interface BlueprintCompositionResult {
  svg: string
  width: number
  height: number
  itemCount: number
}

export interface BlueprintPageConfig {
  margin: number
  itemSpacing: number
}

export interface ScaledBounds {
  width: number
  height: number
}
