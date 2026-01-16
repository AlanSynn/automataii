import { useState } from 'react'
import { ProjectState } from '../domain/project'
import { usePathEditor } from '../application/motion_paths/usePathEditor'

interface PathEditorProps {
  state: ProjectState | null
  setProjectState: (state: ProjectState | null) => void
}

export function PathEditor({ state, setProjectState }: PathEditorProps) {
  const {
    state: editorState,
    actions
  } = usePathEditor(state, setProjectState)

  const [dragIndex, setDragIndex] = useState<number | null>(null)

  return (
    <section className="path-editor">
      <h3>Path Editor</h3>
      
      <div style={{ marginBottom: '1rem' }}>
        <label>
          Select Part:
          <select 
            value={editorState.selectedPart ?? ''}
            onChange={e => actions.selectPart(e.target.value || null)}
          >
            <option value="">-- Select Part --</option>
            {state && Object.values(state.parts).map(part => (
              <option key={part.name} value={part.name}>{part.name}</option>
            ))}
          </select>
        </label>
      </div>

      {editorState.selectedPart && (
        <div style={{ display: 'flex', gap: '20px', alignItems: 'flex-start' }}>
          <div className="controls" style={{ minWidth: '200px' }}>
            <div>
              <label>
                <input 
                  type="checkbox" 
                  checked={editorState.isClosed}
                  onChange={e => actions.setClosed(e.target.checked)}
                />
                Closed Path
              </label>
            </div>
            
            <div>
              <label>
                Smoothness: {editorState.smoothness}
                <input 
                  type="range" 
                  min="0" 
                  max="100" 
                  value={editorState.smoothness}
                  onChange={e => actions.setSmoothness(Number(e.target.value))}
                />
              </label>
            </div>

            <div>
              <label>
                <input 
                  type="checkbox" 
                  checked={editorState.timed}
                  onChange={e => actions.setTimed(e.target.checked)}
                />
                Timed (Constant Speed)
              </label>
            </div>

            {editorState.timed && (
              <div>
                <label>
                  Duration (s):
                  <input 
                    type="number" 
                    value={editorState.totalDuration}
                    onChange={e => actions.setTotalDuration(Number(e.target.value))}
                    step="0.1"
                  />
                </label>
              </div>
            )}

            <div style={{ marginTop: '1rem' }}>
              <button 
                onClick={() => {
                  if (editorState.activePointIndex !== null) {
                    actions.removePoint(editorState.activePointIndex)
                  }
                }}
                disabled={editorState.activePointIndex === null}
              >
                Delete Selected Point
              </button>
            </div>

            <div style={{ marginTop: '0.5rem' }}>
              <button onClick={actions.clearPath}>Clear Path</button>
            </div>
          </div>

          <div style={{ border: '1px solid #ccc', position: 'relative' }}>
            <svg 
              width="600" 
              height="400" 
              style={{ background: '#f9f9f9', cursor: 'crosshair' }}
              onMouseDown={(e) => {
                 if (e.target === e.currentTarget) {
                   const rect = e.currentTarget.getBoundingClientRect()
                   actions.addPoint({
                     x: e.clientX - rect.left,
                     y: e.clientY - rect.top
                   })
                 }
              }}
              onMouseMove={(e) => {
                if (dragIndex !== null) {
                  const rect = e.currentTarget.getBoundingClientRect()
                  actions.updatePoint(dragIndex, {
                    x: e.clientX - rect.left,
                    y: e.clientY - rect.top
                  })
                }
              }}
              onMouseUp={() => setDragIndex(null)}
              onMouseLeave={() => setDragIndex(null)}
            >
              {editorState.previewPoints.length > 1 && (
                <polyline
                  points={editorState.previewPoints.map(p => `${p.x},${p.y}`).join(' ')}
                  fill="none"
                  stroke="#666"
                  strokeWidth="2"
                  strokeDasharray="4 2"
                />
              )}

              {editorState.points.map((p, i) => {
                const next = editorState.points[i + 1]
                return next ? (
                  <line 
                    key={`line-${i}`}
                    x1={p.x} y1={p.y} 
                    x2={next.x} y2={next.y} 
                    stroke="#ddd" 
                    strokeWidth="1"
                  />
                ) : null
              })}

              {editorState.isClosed && editorState.points.length > 2 && (
                <line 
                  x1={editorState.points[editorState.points.length - 1].x} 
                  y1={editorState.points[editorState.points.length - 1].y}
                  x2={editorState.points[0].x}
                  y2={editorState.points[0].y}
                  stroke="#ddd"
                  strokeWidth="1"
                />
              )}

              {editorState.points.map((p, i) => (
                <circle
                  key={`pt-${i}`}
                  cx={p.x}
                  cy={p.y}
                  r={6}
                  fill={i === editorState.activePointIndex ? '#007bff' : '#fff'}
                  stroke="#007bff"
                  strokeWidth="2"
                  style={{ cursor: 'grab' }}
                  onMouseDown={(e) => {
                    e.stopPropagation()
                    actions.setActivePointIndex(i)
                    setDragIndex(i)
                  }}
                />
              ))}
            </svg>
          </div>
        </div>
      )}
    </section>
  )
}
