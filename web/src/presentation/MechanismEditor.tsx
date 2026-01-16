import { useState } from 'react'
import type { ProjectState, MechanismData } from '../domain/project'
import { useMechanismForm } from '../application/mechanisms/useMechanismForm'

interface MechanismEditorProps {
  state: ProjectState | null
  setProjectState: (state: ProjectState | null) => void
}

const MECHANISM_TYPES = [
  'fourbar',
  'cam',
  'gear',
  'planetary',
] as const

type MechanismType = (typeof MECHANISM_TYPES)[number]

const DEFAULT_PARAMS: Record<MechanismType, Record<string, number>> = {
  fourbar: {
    l1: 50,
    l2: 50,
    l3: 50,
    l4: 50,
    base_x: 0,
    base_y: 0,
    num_samples: 100,
  },
  cam: {
    cam_center_x: 0,
    cam_center_y: 0,
    follower_radius: 10,
    num_samples: 100,
  },
  gear: {
    radius: 50,
    center_x: 0,
    center_y: 0,
    num_samples: 100,
  },
  planetary: {
    r_sun_mm: 50,
    r_planet_mm: 20,
    center_x: 0,
    center_y: 0,
    num_samples: 100,
  },
}

const toMechanismType = (value: string): MechanismType =>
  MECHANISM_TYPES.find((entry) => entry === value) ?? 'fourbar'

const normalizeMechanismType = (value: string): MechanismType | null => {
  if (value === 'four_bar' || value === '4_bar_linkage' || value === 'fourbar') {
    return 'fourbar'
  }
  if (value === 'cam_follower' || value === 'cam') {
    return 'cam'
  }
  if (value === 'gear_train' || value === 'simple_gear' || value === 'gear') {
    return 'gear'
  }
  if (value === 'planetary_gear' || value === 'planetary') {
    return 'planetary'
  }
  return null
}

export function MechanismEditor({ state, setProjectState }: MechanismEditorProps) {
  const {
    state: { selectedId, mechanisms },
    actions: { selectMechanism, addMechanism, removeMechanism, updateMechanism, updateParams }
  } = useMechanismForm(state, setProjectState)

  const [newMechId, setNewMechId] = useState('')
  const [newMechType, setNewMechType] = useState<MechanismType>('fourbar')
  const [newMechPart, setNewMechPart] = useState('')

  const selectedMech = selectedId ? mechanisms[selectedId] : null
  const normalizedSelectedType = selectedMech ? normalizeMechanismType(selectedMech.type) : null
  const typeOptions = selectedMech && !normalizedSelectedType
    ? [...MECHANISM_TYPES, selectedMech.type]
    : MECHANISM_TYPES
  const selectedTypeValue = normalizedSelectedType ?? selectedMech?.type ?? 'fourbar'

  const handleAdd = () => {
    if (!newMechId) {
      return
    }
    const type = newMechType
    const params = DEFAULT_PARAMS[type]

    addMechanism({
      id: newMechId,
      type,
      partName: newMechPart || newMechId,
      params,
      enabled: true,
    })
    setNewMechId('')
    setNewMechPart('')
  }

  const handleParamChange = (key: string, value: string) => {
    if (!selectedMech) return
    
    const floatVal = parseFloat(value)
    if (isNaN(floatVal)) return

    updateParams(selectedMech.id, {
      ...selectedMech.params,
      [key]: floatVal
    })
  }

  const renderParamFields = (mech: MechanismData) => {
    const normalizedType = normalizeMechanismType(mech.type)
    let fields: string[] = []

    if (normalizedType === 'fourbar') {
      fields = ['l1', 'l2', 'l3', 'l4', 'base_x', 'base_y', 'num_samples']
    } else if (normalizedType === 'cam') {
      fields = ['cam_center_x', 'cam_center_y', 'follower_radius', 'num_samples']
    } else if (normalizedType === 'gear') {
      fields = ['radius', 'center_x', 'center_y', 'num_samples']
    } else if (normalizedType === 'planetary') {
      fields = ['r_sun_mm', 'r_planet_mm', 'center_x', 'center_y', 'num_samples']
    } else {
      return <div>No specific parameters for this type.</div>
    }

    return (
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
        {fields.map((field) => {
          const rawValue = mech.params[field]
          const value = typeof rawValue === 'number' ? rawValue : ''
          return (
            <label key={field} style={{ display: 'flex', flexDirection: 'column' }}>
              <span style={{ fontSize: '0.8em' }}>{field}</span>
              <input
                type="number"
                step="any"
                value={value}
                onChange={(e) => handleParamChange(field, e.target.value)}
              />
            </label>
          )
        })}
      </div>
    )
  }

  return (
    <section style={{ border: '1px solid #ccc', padding: '16px', margin: '16px 0' }}>
      <h3>Mechanism Designer</h3>
      
      <div style={{ display: 'flex', gap: '16px' }}>
        <div style={{ flex: 1, minWidth: '200px' }}>
          <h4>Mechanisms</h4>
          <ul style={{ listStyle: 'none', padding: 0, maxHeight: '300px', overflowY: 'auto' }}>
            {Object.values(mechanisms).map(m => (
              <li 
                key={m.id} 
                style={{ 
                  padding: '8px', 
                  borderBottom: '1px solid #eee',
                  background: selectedId === m.id ? '#f0f8ff' : 'transparent',
                  cursor: 'pointer',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center'
                }}
                onClick={() => selectMechanism(m.id)}
              >
                <span>{m.id} <small>({m.type})</small></span>
                <button 
                  onClick={(e) => { e.stopPropagation(); removeMechanism(m.id); }}
                  style={{ fontSize: '0.8em', padding: '2px 6px' }}
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>

          <div style={{ borderTop: '1px solid #ddd', paddingTop: '8px', marginTop: '8px' }}>
            <h5>Add New</h5>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <input 
                placeholder="ID (e.g. mech1)" 
                value={newMechId}
                onChange={e => setNewMechId(e.target.value)}
              />
              <input 
                placeholder="Part Name (optional)" 
                value={newMechPart}
                onChange={e => setNewMechPart(e.target.value)}
              />
              <select 
                value={newMechType} 
                onChange={(e) => setNewMechType(toMechanismType(e.target.value))}
              >
                {MECHANISM_TYPES.map(t => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
              <button onClick={handleAdd} disabled={!newMechId}>Add Mechanism</button>
            </div>
          </div>
        </div>

        <div style={{ flex: 2, borderLeft: '1px solid #ddd', paddingLeft: '16px' }}>
          {selectedMech ? (
            <div>
              <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <h4 style={{ margin: 0 }}>Editing: {selectedMech.id}</h4>
                <label>
                  <input 
                    type="checkbox" 
                    checked={selectedMech.enabled ?? true} 
                    onChange={e => updateMechanism(selectedMech.id, { enabled: e.target.checked })}
                  /> Enabled
                </label>
              </header>

              <div style={{ marginBottom: '16px' }}>
                <label>
                  Part Name: 
                  <input 
                    value={selectedMech.partName} 
                    onChange={e => updateMechanism(selectedMech.id, { partName: e.target.value })}
                    style={{ marginLeft: '8px' }}
                  />
                </label>
              </div>

              <div style={{ marginBottom: '16px' }}>
                <label>
                  Type:
                  <select
                    value={selectedTypeValue}
                    onChange={(e) =>
                      updateMechanism(selectedMech.id, { type: toMechanismType(e.target.value) })
                    }
                    style={{ marginLeft: '8px' }}
                  >
                    {typeOptions.map((type) => (
                      <option key={type} value={type}>
                        {type}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <fieldset>
                <legend>Parameters</legend>
                {renderParamFields(selectedMech)}
              </fieldset>

              <div style={{ marginTop: '16px' }}>
                <details>
                  <summary>Raw JSON</summary>
                  <pre style={{ fontSize: '0.8em', background: '#f5f5f5', padding: '8px' }}>
                    {JSON.stringify(selectedMech, null, 2)}
                  </pre>
                </details>
              </div>
            </div>
          ) : (
            <div style={{ color: '#888', fontStyle: 'italic' }}>
              Select a mechanism to edit details
            </div>
          )}
        </div>
      </div>
    </section>
  )
}
