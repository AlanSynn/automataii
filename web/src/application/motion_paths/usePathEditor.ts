import { useCallback, useEffect, useMemo, useState } from 'react'
import type { Point } from '../../domain/project'
import type { ProjectState } from '../../domain/project'

import { buildPathDataFromPoints, smoothPathPoints } from './pathEditing'
import type { PathEditConfig } from './pathEditing'

export interface PathEditorState {
  selectedPart: string | null
  points: Point[]
  previewPoints: Point[]
  isClosed: boolean
  smoothness: number
  timed: boolean
  totalDuration: number
  activePointIndex: number | null
}

export interface PathEditorActions {
  selectPart: (partName: string | null) => void
  setPoints: (points: Point[] | ((current: Point[]) => Point[])) => void
  addPoint: (point: Point) => void
  updatePoint: (index: number, point: Point) => void
  removePoint: (index: number) => void
  setClosed: (value: boolean) => void
  setSmoothness: (value: number) => void
  setTimed: (value: boolean) => void
  setTotalDuration: (value: number) => void
  setActivePointIndex: (index: number | null) => void
  clearPath: () => void
}

const defaultDuration = 4

const clampDuration = (value: number): number =>
  Number.isFinite(value) && value > 0 ? value : defaultDuration

export const usePathEditor = (
  state: ProjectState | null,
  setState: (state: ProjectState | null) => void
): { state: PathEditorState; actions: PathEditorActions } => {
  const [selectedPart, setSelectedPart] = useState<string | null>(null)
  const [points, setPointsState] = useState<Point[]>([])
  const [isClosed, setIsClosed] = useState(false)
  const [smoothness, setSmoothness] = useState(50)
  const [timed, setTimed] = useState(false)
  const [totalDuration, setTotalDuration] = useState(defaultDuration)
  const [activePointIndex, setActivePointIndex] = useState<number | null>(null)

  useEffect(() => {
    if (!state || !selectedPart) {
      return
    }
    const path = state.paths[selectedPart]
    if (!path) {
      setPointsState([])
      setIsClosed(false)
      setTimed(false)
      setTotalDuration(defaultDuration)
      setActivePointIndex(null)
      return
    }
    setPointsState(path.points)
    setIsClosed(path.isClosed)
    setTimed(Boolean(path.timedPoints && path.timedPoints.length > 0))
    setTotalDuration(path.totalDuration ?? defaultDuration)
    setActivePointIndex(null)
  }, [state, selectedPart])

  const previewPoints = useMemo(
    () => smoothPathPoints(points, isClosed, smoothness),
    [points, isClosed, smoothness]
  )

  const commitPath = useCallback(
    (nextPoints: Point[], overrides?: Partial<PathEditConfig>): void => {
      if (!state || !selectedPart) {
        return
      }
      const config: PathEditConfig = {
        partName: selectedPart,
        isClosed: overrides?.isClosed ?? isClosed,
        smoothness: overrides?.smoothness ?? smoothness,
        timed: overrides?.timed ?? timed,
        totalDuration: clampDuration(overrides?.totalDuration ?? totalDuration),
        enabled: true,
      }
      const pathData = buildPathDataFromPoints(nextPoints, config)
      const nextPaths = {
        ...state.paths,
        [selectedPart]: pathData,
      }
      setState(state.withPaths(nextPaths))
    },
    [state, selectedPart, isClosed, smoothness, timed, totalDuration, setState]
  )

  const setPoints = useCallback(
    (nextPoints: Point[] | ((current: Point[]) => Point[])) => {
      setPointsState((current) => {
        const resolved = typeof nextPoints === 'function'
          ? nextPoints(current)
          : nextPoints
        commitPath(resolved)
        return resolved
      })
    },
    [commitPath]
  )

  const addPoint = useCallback(
    (point: Point) => {
      setPoints((current) => [...current, point])
    },
    [setPoints]
  )

  const updatePoint = useCallback(
    (index: number, point: Point) => {
      setPoints((current) =>
        current.map((entry, i) => (i === index ? point : entry))
      )
    },
    [setPoints]
  )

  const removePoint = useCallback(
    (index: number) => {
      setPoints((current) => current.filter((_, i) => i !== index))
      if (activePointIndex === index) {
        setActivePointIndex(null)
      }
    },
    [activePointIndex, setPoints]
  )

  const clearPath = useCallback(() => {
    if (!state || !selectedPart) {
      return
    }
    const nextPaths = { ...state.paths }
    delete nextPaths[selectedPart]
    setState(state.withPaths(nextPaths))
    setPointsState([])
    setActivePointIndex(null)
  }, [state, selectedPart, setState])

  const handleSetClosed = useCallback(
    (value: boolean) => {
      setIsClosed(value)
      commitPath(points, { isClosed: value })
    },
    [commitPath, points]
  )

  const handleSmoothness = useCallback(
    (value: number) => {
      setSmoothness(value)
      commitPath(points, { smoothness: value })
    },
    [commitPath, points]
  )

  const handleTimed = useCallback(
    (value: boolean) => {
      setTimed(value)
      commitPath(points, { timed: value })
    },
    [commitPath, points]
  )

  const handleDuration = useCallback(
    (value: number) => {
      const nextDuration = clampDuration(value)
      setTotalDuration(nextDuration)
      commitPath(points, { totalDuration: nextDuration })
    },
    [commitPath, points]
  )

  return {
    state: {
      selectedPart,
      points,
      previewPoints,
      isClosed,
      smoothness,
      timed,
      totalDuration,
      activePointIndex,
    },
    actions: {
      selectPart: setSelectedPart,
      setPoints,
      addPoint,
      updatePoint,
      removePoint,
      setClosed: handleSetClosed,
      setSmoothness: handleSmoothness,
      setTimed: handleTimed,
      setTotalDuration: handleDuration,
      setActivePointIndex,
      clearPath,
    },
  }
}
