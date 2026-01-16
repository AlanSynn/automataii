import { useCallback, useEffect, useRef, useState } from 'react'

export type TimingProfile =
  | 'linear'
  | 'ease_in_out'
  | 'ease_in'
  | 'ease_out'
  | 'bounce'
  | 'elastic'

export interface PathPlaybackState {
  progress: number
  rawProgress: number
  isPlaying: boolean
  durationSeconds: number
  loop: boolean
  timingProfile: TimingProfile
}

export interface PathPlaybackControls {
  state: PathPlaybackState
  setProgress: (value: number) => void
  setDurationSeconds: (value: number) => void
  setLoop: (value: boolean) => void
  setTimingProfile: (value: TimingProfile) => void
  play: () => void
  pause: () => void
  toggle: () => void
  reset: () => void
}

export const clampProgress = (value: number): number =>
  Math.min(1, Math.max(0, Number.isFinite(value) ? value : 0))

export const applyTimingProfile = (
  progress: number,
  profile: TimingProfile
): number => {
  const t = clampProgress(progress)
  switch (profile) {
    case 'ease_in_out':
      return 0.5 * (1 - Math.cos(Math.PI * t))
    case 'ease_in':
      return t * t
    case 'ease_out':
      return 1 - (1 - t) * (1 - t)
    case 'bounce':
      if (t < 0.5) {
        return 2 * t * t
      }
      {
        const x = 2 * t - 1
        return 1 - (1 - x) * (1 - x) * 0.5 + 0.5
      }
    case 'elastic': {
      if (t === 0 || t === 1) {
        return t
      }
      const p = 0.3
      const s = p / 4
      if (t < 0.5) {
        const t2 = 2 * t
        return -0.5 * (2 ** (10 * (t2 - 1))) * Math.sin(((t2 - 1 - s) * 2 * Math.PI) / p)
      }
      const t2 = 2 * t - 1
      return 0.5 * (2 ** (-10 * t2)) * Math.sin(((t2 - s) * 2 * Math.PI) / p) + 1
    }
    default:
      return t
  }
}

export const usePathPlayback = (initialDurationSeconds = 4): PathPlaybackControls => {
  const [rawProgress, setRawProgressState] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [durationSeconds, setDurationSecondsState] = useState(
    initialDurationSeconds > 0 ? initialDurationSeconds : 4
  )
  const [loop, setLoop] = useState(true)
  const [timingProfile, setTimingProfile] = useState<TimingProfile>('linear')
  const frameRef = useRef<number | null>(null)
  const lastTimeRef = useRef<number | null>(null)

  useEffect(() => {
    if (!isPlaying) {
      if (frameRef.current !== null) {
        cancelAnimationFrame(frameRef.current)
        frameRef.current = null
      }
      lastTimeRef.current = null
      return
    }

    const step = (timestamp: number): void => {
      if (lastTimeRef.current === null) {
        lastTimeRef.current = timestamp
      } else {
        const delta = (timestamp - lastTimeRef.current) / 1000
        lastTimeRef.current = timestamp
        if (durationSeconds > 0) {
          setRawProgressState((current) => {
            const next = current + delta / durationSeconds
            if (loop) {
              return next > 1 ? next % 1 : next
            }
            if (next >= 1) {
              setIsPlaying(false)
              return 1
            }
            return next
          })
        }
      }
      frameRef.current = requestAnimationFrame(step)
    }

    frameRef.current = requestAnimationFrame(step)
    return () => {
      if (frameRef.current !== null) {
        cancelAnimationFrame(frameRef.current)
      }
      frameRef.current = null
      lastTimeRef.current = null
    }
  }, [isPlaying, durationSeconds, loop])

  const setProgress = useCallback((value: number) => {
    setRawProgressState(clampProgress(value))
  }, [])

  const setDurationSeconds = useCallback((value: number) => {
    if (Number.isFinite(value) && value > 0) {
      setDurationSecondsState(value)
    }
  }, [])

  const play = useCallback(() => setIsPlaying(true), [])
  const pause = useCallback(() => setIsPlaying(false), [])
  const toggle = useCallback(() => setIsPlaying((current) => !current), [])
  const reset = useCallback(() => {
    setIsPlaying(false)
    setRawProgressState(0)
  }, [])

  const progress = applyTimingProfile(rawProgress, timingProfile)

  return {
    state: { progress, rawProgress, isPlaying, durationSeconds, loop, timingProfile },
    setProgress,
    setDurationSeconds,
    setLoop,
    setTimingProfile,
    play,
    pause,
    toggle,
    reset,
  }
}
