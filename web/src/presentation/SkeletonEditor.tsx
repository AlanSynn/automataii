import { useState, type MouseEvent } from 'react'
import type { ProjectState } from '../domain/project'
import { useSkeletonEditor } from '../application/skeleton/useSkeletonEditor'

interface SkeletonEditorProps {
  state: ProjectState | null
  setProjectState: (state: ProjectState | null) => void
}

type EditorMode = 'select' | 'add_joint' | 'add_bone' | 'remove_bone'

export function SkeletonEditor({ state, setProjectState }: SkeletonEditorProps) {
  const {
    state: editorState,
    actions
  } = useSkeletonEditor(state, setProjectState)

  const [mode, setMode] = useState<EditorMode>('select')
  const [dragJointId, setDragJointId] = useState<string | null>(null)
  const [boneStartId, setBoneStartId] = useState<string | null>(null)

  const handleSvgClick = (e: MouseEvent<SVGSVGElement>) => {
    if (mode === 'add_joint') {
      const rect = e.currentTarget.getBoundingClientRect()
      actions.addJoint({
        x: e.clientX - rect.left,
        y: e.clientY - rect.top
      })
    }
  }

  const handleJointClick = (e: MouseEvent<SVGGElement>, jointId: string) => {
    e.stopPropagation()
    
    if (mode === 'add_bone') {
      if (boneStartId === null) {
        setBoneStartId(jointId)
      } else {
        if (boneStartId !== jointId) {
          actions.addBone(boneStartId, jointId)
        }
        setBoneStartId(null)
      }
      return
    }

    if (mode === 'remove_bone') {
      if (boneStartId === null) {
        setBoneStartId(jointId)
      } else {
        actions.removeBone(boneStartId, jointId)
        actions.removeBone(jointId, boneStartId)
        setBoneStartId(null)
      }
      return
    }

    actions.selectJoint(jointId)
  }

  const handleJointMouseDown = (e: MouseEvent<SVGGElement>, jointId: string) => {
    if (mode === 'select') {
       e.stopPropagation()
       setDragJointId(jointId)
       actions.selectJoint(jointId)
    }
  }

  const handleMouseMove = (e: MouseEvent<SVGSVGElement>) => {
    if (dragJointId && mode === 'select') {
      const rect = e.currentTarget.getBoundingClientRect()
      actions.moveJoint(dragJointId, {
        x: e.clientX - rect.left,
        y: e.clientY - rect.top
      })
    }
  }

  const handleMouseUp = () => {
    setDragJointId(null)
  }

  const currentSkeleton = editorState.skeleton
  const selectedJoint = currentSkeleton && editorState.selectedJointId 
    ? currentSkeleton.joints[editorState.selectedJointId] 
    : null

  return (
    <section className="skeleton-editor">
      <h3>Skeleton Editor</h3>
      
      <div style={{ marginBottom: '1rem', display: 'flex', gap: '10px' }}>
        <button 
          onClick={() => { setMode('select'); setBoneStartId(null); }}
          style={{ fontWeight: mode === 'select' ? 'bold' : 'normal' }}
        >
          Select / Move
        </button>
        <button 
          onClick={() => { setMode('add_joint'); setBoneStartId(null); }}
          style={{ fontWeight: mode === 'add_joint' ? 'bold' : 'normal' }}
        >
          Add Joint
        </button>
        <button 
          onClick={() => { setMode('add_bone'); setBoneStartId(null); }}
          style={{ fontWeight: mode === 'add_bone' ? 'bold' : 'normal' }}
        >
          Add Bone
        </button>
        <button 
          onClick={() => { setMode('remove_bone'); setBoneStartId(null); }}
          style={{ fontWeight: mode === 'remove_bone' ? 'bold' : 'normal' }}
        >
          Remove Bone
        </button>
      </div>

      <div style={{ display: 'flex', gap: '20px', alignItems: 'flex-start' }}>
        <div style={{ border: '1px solid #ccc' }}>
          <svg 
            width="600" 
            height="400" 
            style={{ background: '#f0f0f0', cursor: mode === 'add_joint' ? 'crosshair' : 'default' }}
            onClick={handleSvgClick}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
          >
            {currentSkeleton?.bones.map((bone, i) => {
              const start = currentSkeleton.joints[bone.fromJoint]
              const end = currentSkeleton.joints[bone.toJoint]
              if (!start || !end) return null
              
              return (
                <line
                  key={`bone-${i}`}
                  x1={start.position.x}
                  y1={start.position.y}
                  x2={end.position.x}
                  y2={end.position.y}
                  stroke="#444"
                  strokeWidth="4"
                  strokeLinecap="round"
                />
              )
            })}

            {currentSkeleton && Object.values(currentSkeleton.joints).map(joint => {
              const isSelected = joint.id === editorState.selectedJointId
              const isRoot = joint.id === currentSkeleton.rootJoint
              const isBoneStart = joint.id === boneStartId
              
              return (
                <g 
                  key={joint.id}
                  transform={`translate(${joint.position.x}, ${joint.position.y})`}
                  onClick={(e) => handleJointClick(e, joint.id)}
                  onMouseDown={(e) => handleJointMouseDown(e, joint.id)}
                  style={{ cursor: mode === 'select' ? (joint.isLocked ? 'not-allowed' : 'grab') : 'pointer' }}
                >
                  <circle 
                    r={isSelected ? 8 : 6}
                    fill={isRoot ? '#e74c3c' : (isBoneStart ? '#f39c12' : '#3498db')}
                    stroke={isSelected ? '#2c3e50' : '#fff'}
                    strokeWidth="2"
                  />
                  {joint.isLocked && (
                    <text x="8" y="3" fontSize="10">🔒</text>
                  )}
                </g>
              )
            })}
          </svg>
        </div>

        <div className="controls" style={{ minWidth: '250px' }}>
          {selectedJoint ? (
            <>
              <h4>Selected Joint: {selectedJoint.id}</h4>
              <div style={{ marginBottom: '0.5rem' }}>
                <label>
                  <input 
                    type="checkbox"
                    checked={selectedJoint.isLocked}
                    onChange={(e) => actions.setJointLocked(selectedJoint.id, e.target.checked)}
                  />
                  Locked
                </label>
              </div>

              <div style={{ marginBottom: '0.5rem' }}>
                <label>
                  Bend Direction:
                  <select
                    value={selectedJoint.bendDirection}
                    onChange={(e) => actions.setBendDirection(selectedJoint.id, e.target.value)}
                  >
                    <option value="up">Up (Clockwise)</option>
                    <option value="down">Down (Counter-CW)</option>
                  </select>
                </label>
              </div>

              <div style={{ marginBottom: '0.5rem' }}>
                <label>
                  Parent ID:
                  <select
                     value={selectedJoint.parent ?? ''}
                     onChange={(e) => actions.setParent(selectedJoint.id, e.target.value || null)}
                  >
                    <option value="">(No Parent)</option>
                    {currentSkeleton && Object.values(currentSkeleton.joints)
                      .filter(j => j.id !== selectedJoint.id)
                      .map(j => (
                        <option key={j.id} value={j.id}>{j.id}</option>
                      ))
                    }
                  </select>
                </label>
              </div>

              <div style={{ marginBottom: '1rem' }}>
                <button 
                  onClick={() => actions.setRoot(selectedJoint.id)}
                  disabled={currentSkeleton?.rootJoint === selectedJoint.id}
                >
                  Set as Root
                </button>
              </div>

              <div>
                <button 
                  onClick={() => actions.removeJoint(selectedJoint.id)}
                  style={{ color: 'red' }}
                >
                  Delete Joint
                </button>
              </div>
            </>
          ) : (
            <p style={{ color: '#777' }}>Select a joint to edit properties</p>
          )}

          <hr style={{ margin: '1rem 0' }}/>
          <p style={{ fontSize: '0.9em', color: '#666' }}>
            <strong>Instructions:</strong><br/>
            - <strong>Select/Move:</strong> Click to select, Drag to move.<br/>
            - <strong>Add Joint:</strong> Click empty space.<br/>
            - <strong>Add Bone:</strong> Click start joint, then end joint.<br/>
          </p>
        </div>
      </div>
    </section>
  )
}
