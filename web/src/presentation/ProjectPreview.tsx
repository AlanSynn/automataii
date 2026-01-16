import { useEffect, useRef, useState } from 'react'
import type { ProjectState } from '../domain/project'
import {
  buildSkeletonSegments,
  buildPathSegments,
  collectPoints,
  computeBounds,
} from '../domain/preview'
import { samplePathsAtProgress } from '../application/motion_paths'

export interface ProjectPreviewProps {
  state: ProjectState
  progress?: number
}

export function ProjectPreview({ state, progress }: ProjectPreviewProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const imageCache = useRef<Map<string, HTMLImageElement>>(new Map())
  const [, setTick] = useState(0)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    Object.values(state.parts).forEach((part) => {
      if (part.texturePath && !imageCache.current.has(part.texturePath)) {
        const img = new Image()
        img.src = part.texturePath
        img.onload = () => setTick((t) => t + 1)
        imageCache.current.set(part.texturePath, img)
      }
    })

    ctx.resetTransform()
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    const skeletonSegments = buildSkeletonSegments(state.skeleton)
    const pathSegments = buildPathSegments(state.paths)
    const allSegments = [...skeletonSegments, ...pathSegments]

    const points = collectPoints(allSegments)
    Object.values(state.parts).forEach((p) => {
      points.push({ x: p.transform.x, y: p.transform.y })
    })

    const bounds = computeBounds(points)

    if (!bounds) return

    const padding = 20
    const availWidth = canvas.width - padding * 2
    const availHeight = canvas.height - padding * 2

    const contentWidth = bounds.maxX - bounds.minX
    const contentHeight = bounds.maxY - bounds.minY

    const scaleX = contentWidth > 0 ? availWidth / contentWidth : 1
    const scaleY = contentHeight > 0 ? availHeight / contentHeight : 1

    let scale = 1
    if (contentWidth === 0 && contentHeight === 0) {
      scale = 1
    } else if (contentWidth === 0) {
      scale = scaleY
    } else if (contentHeight === 0) {
      scale = scaleX
    } else {
      scale = Math.min(scaleX, scaleY)
    }

    if (!Number.isFinite(scale)) {
      scale = 1
    }

    const centerX = (bounds.minX + bounds.maxX) / 2
    const centerY = (bounds.minY + bounds.maxY) / 2

    ctx.translate(canvas.width / 2, canvas.height / 2)
    ctx.scale(scale, scale)
    ctx.translate(-centerX, -centerY)

    const parts = Object.values(state.parts).sort((a, b) => a.zIndex - b.zIndex)
    parts.forEach((part) => {
      if (part.texturePath) {
        const img = imageCache.current.get(part.texturePath)
        if (img && img.complete && img.naturalWidth > 0) {
          const pivot = part.pivot ?? { x: 0, y: 0 }
          ctx.save()
          ctx.translate(part.transform.x + pivot.x, part.transform.y + pivot.y)
          ctx.rotate(part.transform.rotation)
          ctx.scale(part.transform.scale, part.transform.scale)
          ctx.drawImage(img, -pivot.x, -pivot.y)
          ctx.restore()
        }
      }
    })

    ctx.beginPath()
    ctx.strokeStyle = '#000000'
    ctx.lineWidth = 2 / scale

    allSegments.forEach((segment) => {
      ctx.moveTo(segment.start.x, segment.start.y)
      ctx.lineTo(segment.end.x, segment.end.y)
    })

    ctx.stroke()

    if (progress !== undefined) {
      const samples = samplePathsAtProgress(state.paths, progress)
      ctx.fillStyle = '#ff0000'
      const markerRadius = 5 / scale

      Object.values(samples).forEach((point) => {
        if (!point) return
        ctx.beginPath()
        ctx.arc(point.x, point.y, markerRadius, 0, Math.PI * 2)
        ctx.fill()
      })
    }
  }, [state, progress])

  return (
    <section>
      <h3>Preview</h3>
      <figure>
        <canvas
          ref={canvasRef}
          width={400}
          height={400}
          title="Project Preview"
        >
          Your browser does not support the canvas element.
        </canvas>
        <figcaption>Skeleton and motion paths.</figcaption>
      </figure>
    </section>
  )
}
