import { useState } from 'react'
import { useProjectLoader } from './application/project/useProjectLoader'
import { useProjectDownloader } from './application/project/useProjectDownloader'
import { useProjectJsonEditor } from './application/project/useProjectJsonEditor'
import { useMechanismEditor } from './application/mechanisms'
import {
  useMechanismPathGenerator,
  usePathJsonEditor,
  samplePathsAtProgress,
  usePathPlayback,
  type TimingProfile
} from './application/motion_paths'
import { useImageInference, useOnnxModel } from './application/onnx'
import { ProjectPreview } from './presentation/ProjectPreview'
import { PathEditor } from './presentation/PathEditor'
import { ProjectState } from './domain/project'
import { SkeletonEditor } from './presentation/SkeletonEditor'
import { MechanismEditor } from './presentation/MechanismEditor'
import { exportBlueprint, buildMechanismPreview } from './application/blueprint'
import {
  buildBlueprintScenarioArtifacts,
  downloadBlueprintScenarioArtifacts,
  buildImageProcessingScenarioArtifacts,
  downloadImageProcessingScenarioArtifacts
} from './application/scenarios'
import './App.css'

function App() {
  const [loadState, handleFileChange, setProjectState] = useProjectLoader()
  const { state, filename, error } = loadState

  const { downloadProject } = useProjectDownloader()
  const [downloadError, setDownloadError] = useState<string | null>(null)
  const [blueprintError, setBlueprintError] = useState<string | null>(null)
  const [unitSystem, setUnitSystem] = useState<'metric' | 'imperial'>('metric')

  const handleDownload = (projectState: ProjectState, baseName?: string) => {
    setDownloadError(null)
    const result = downloadProject(projectState, baseName)
    if (!result.success) {
      setDownloadError(result.error || 'Download failed')
    }
  }

  const handleBlueprintExport = async (projectState: ProjectState, baseName?: string) => {
    setBlueprintError(null)
    const result = await exportBlueprint(projectState, baseName, unitSystem)
    if (!result.success) {
      setBlueprintError(result.error || 'Blueprint export failed')
    }
  }

  const onnx = useOnnxModel()
  const imageInference = useImageInference()
  const [feedsJson, setFeedsJson] = useState('')

  const [mechanismsJson, setMechanismsJson] = useState('')
  const [mechanismsError, setMechanismsError] = useState<string | null>(null)

  const [projectJson, setProjectJson] = useState('')
  const [projectJsonError, setProjectJsonError] = useState<string | null>(null)
  const { applyProjectJson } = useProjectJsonEditor(
    state?.projectDir ?? null,
    setProjectState
  )

  const handleApplyProjectJson = () => {
    setProjectJsonError(null)
    const result = applyProjectJson(projectJson)
    if (!result.success) {
      setProjectJsonError(result.error)
    }
  }

  const { applyMechanismsJson } = useMechanismEditor(state, setProjectState)

  const handleApplyMechanisms = () => {
    setMechanismsError(null)
    const result = applyMechanismsJson(mechanismsJson)
    if (!result.success) {
      setMechanismsError(result.error)
    }
  }

  const { status: pathGenStatus, generatePaths } = useMechanismPathGenerator(
    state,
    setProjectState
  )
  const playback = usePathPlayback()
  const { applyPathsJson } = usePathJsonEditor(state, setProjectState)
  const [pathsJson, setPathsJson] = useState('')
  const [pathsError, setPathsError] = useState<string | null>(null)
  const [pathProgress, setPathProgress] = useState(0)

  const handleApplyPaths = () => {
    setPathsError(null)
    const result = applyPathsJson(pathsJson)
    if (!result.success) {
      setPathsError(result.error)
    }
  }

  const handleBlueprintScenario = async () => {
    if (!state) return
    const artifacts = await buildBlueprintScenarioArtifacts(state, 'metric')
    downloadBlueprintScenarioArtifacts(artifacts)
  }

  const handleImageProcessingScenario = async () => {
    const start = performance.now()
    const result = await imageInference.runPipeline()
    const duration = performance.now() - start
    const finalState = result ?? imageInference.state
    const artifacts = await buildImageProcessingScenarioArtifacts(
      finalState,
      duration
    )
    await downloadImageProcessingScenarioArtifacts(artifacts)
  }

  return (
    <main>
      <header>
        <h1>Automataii Project Loader</h1>
      </header>

      <section>
        <label htmlFor="project-file">Load Project File:</label>
        <input
          id="project-file"
          type="file"
          accept=".automataii"
          onChange={handleFileChange}
        />
      </section>

      {error ? (
        <section>
          <h2>Error</h2>
          <p>{error}</p>
        </section>
      ) : null}

      {downloadError ? (
        <section>
          <h2>Download Error</h2>
          <p>{downloadError}</p>
        </section>
      ) : null}

      {blueprintError ? (
        <section>
          <h2>Blueprint Export Error</h2>
          <p>{blueprintError}</p>
        </section>
      ) : null}

      {state ? (
        <article>
          <header>
            <h2>Project Summary: {filename ?? 'Loaded Project'}</h2>
            <button
              onClick={() => handleDownload(state, filename ?? undefined)}
            >
              Download Project
            </button>
            <label>
              Blueprint Units:
              <select
                value={unitSystem}
                onChange={(e) =>
                  setUnitSystem(e.target.value as 'metric' | 'imperial')
                }
              >
                <option value="metric">Metric</option>
                <option value="imperial">Imperial</option>
              </select>
            </label>
            <button
              onClick={() =>
                handleBlueprintExport(state, filename ?? undefined)
              }
            >
              Export Blueprint
            </button>
          </header>

          <ProjectPreview state={state} progress={playback.state.progress} />

          <section>
            <h3>Metadata</h3>
            <dl>
              <dt>Name</dt>
              <dd>{state.metadata.name}</dd>
              <dt>Version</dt>
              <dd>{state.metadata.version}</dd>
              <dt>Created</dt>
              <dd>{state.metadata.createdAt}</dd>
              <dt>Modified</dt>
              <dd>{state.metadata.modifiedAt}</dd>
            </dl>
          </section>

          <SkeletonEditor state={state} setProjectState={setProjectState} />
          
          <PathEditor state={state} setProjectState={setProjectState} />

          <section>
            <h3>Statistics</h3>
            <ul>
              <li>Parts: {Object.keys(state.parts).length}</li>
              <li>Paths: {Object.keys(state.paths).length}</li>
              <li>Mechanisms: {Object.keys(state.mechanisms).length}</li>
            </ul>
          </section>

          <section>
            <h3>Project JSON Editor</h3>
            <label htmlFor="project-json">Project JSON:</label>
            <textarea
              id="project-json"
              value={projectJson}
              onChange={(e) => setProjectJson(e.target.value)}
              rows={10}
              cols={50}
              placeholder="Paste full project JSON here..."
            />
            <button onClick={handleApplyProjectJson}>Apply</button>
            {projectJsonError ? <p>{projectJsonError}</p> : null}
          </section>

          <section>
            <h3>Mechanism Editor</h3>
            <label htmlFor="mechanisms-json">Mechanisms JSON:</label>
            <textarea
              id="mechanisms-json"
              value={mechanismsJson}
              onChange={(e) => setMechanismsJson(e.target.value)}
              rows={5}
              cols={50}
              placeholder='[{"id": "mech1", "type": "four_bar", ...}]'
            />
            <button onClick={handleApplyMechanisms}>Apply</button>
            {mechanismsError ? <p>{mechanismsError}</p> : null}
          </section>

          <MechanismEditor state={state} setProjectState={setProjectState} />

          <section>
            <h3>Motion Path Tools</h3>
            <div>
              <button onClick={generatePaths}>
                Generate Paths From Mechanisms
              </button>
              {pathGenStatus.updates.length > 0 && (
                <ul>
                  {pathGenStatus.updates.map((update, i) => (
                    <li key={i}>
                      {update.mechanismId} - {update.partName}:{' '}
                      {update.success ? 'Success' : `Error: ${update.error}`}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div>
              <label htmlFor="paths-json">Paths JSON:</label>
              <textarea
                id="paths-json"
                value={pathsJson}
                onChange={(e) => setPathsJson(e.target.value)}
                rows={5}
                cols={50}
                placeholder="Paste paths JSON here..."
              />
              <button onClick={handleApplyPaths}>Apply</button>
              {pathsError && <p>{pathsError}</p>}
            </div>

            {state && Object.keys(state.paths).length > 0 && (
              <div>
                <label htmlFor="path-progress">Sample Progress (0-1):</label>
                <input
                  id="path-progress"
                  type="number"
                  min="0"
                  max="1"
                  step="0.01"
                  value={pathProgress}
                  onChange={(e) => setPathProgress(parseFloat(e.target.value))}
                />
                <pre>
                  {JSON.stringify(
                    samplePathsAtProgress(state.paths, pathProgress),
                    null,
                    2
                  )}
                </pre>
              </div>
            )}
          </section>

          <section>
            <h3>Path Playback</h3>
            <div>
              <button
                onClick={playback.state.isPlaying ? playback.pause : playback.play}
              >
                {playback.state.isPlaying ? 'Pause' : 'Play'}
              </button>
              <button onClick={playback.reset}>Stop/Reset</button>
              <label>
                <input
                  type="checkbox"
                  checked={playback.state.loop}
                  onChange={(e) => playback.setLoop(e.target.checked)}
                />
                Loop
              </label>
            </div>
            <div>
              <label>
                Timing:
                <select
                  value={playback.state.timingProfile}
                  onChange={(e) =>
                      playback.setTimingProfile(e.target.value as TimingProfile)

                  }
                >
                  <option value="linear">Linear</option>
                  <option value="ease_in_out">Ease In/Out</option>
                  <option value="ease_in">Ease In</option>
                  <option value="ease_out">Ease Out</option>
                  <option value="bounce">Bounce</option>
                  <option value="elastic">Elastic</option>
                </select>
              </label>
            </div>
            <div>
              <label>
                Duration (seconds):
                <input
                  type="number"
                  min="0.1"
                  step="0.1"
                  value={playback.state.durationSeconds}
                  onChange={(e) =>
                    playback.setDurationSeconds(parseFloat(e.target.value))
                  }
                />
              </label>
            </div>
            <div>
              <label>
                Progress:
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.001"
                  value={playback.state.rawProgress}
                  onChange={(e) =>
                    playback.setProgress(parseFloat(e.target.value))
                  }
                />
              </label>
              <span>
                Raw: {playback.state.rawProgress.toFixed(3)} | Eased:{' '}
                {playback.state.progress.toFixed(3)}
              </span>
            </div>
          </section>

          <section>
            <h3>Mechanism Previews</h3>
            {Object.keys(state.mechanisms).length === 0 ? (
              <p>No mechanisms found.</p>
            ) : (
              <div>
                {Object.values(state.mechanisms).map((mech) => {
                  const preview = buildMechanismPreview(mech)
                  return (
                    <div key={mech.id}>
                      <h4>
                        {mech.id} ({mech.type})
                      </h4>
                      <div dangerouslySetInnerHTML={{ __html: preview.svg }} />
                    </div>
                  )
                })}
              </div>
            )}
          </section>
        </article>
      ) : null}

      <hr />

      <section>
        <h2>ONNX Model Inference</h2>
        <section>
          <label htmlFor="onnx-file">Load ONNX Model:</label>
          <input
            id="onnx-file"
            type="file"
            accept=".onnx"
            onChange={onnx.loadModel}
          />
        </section>

        <section>
          <h3>Status</h3>
          <dl>
            <dt>Status</dt>
            <dd>{onnx.state.status}</dd>
            <dt>Model Name</dt>
            <dd>{onnx.state.modelName || 'None'}</dd>
            {onnx.state.error ? (
              <>
                <dt>Error</dt>
                <dd>{onnx.state.error}</dd>
              </>
            ) : null}
          </dl>
        </section>

        {onnx.state.metadata ? (
          <section>
            <h3>Model Metadata</h3>
            <dl>
              <dt>Inputs</dt>
              <dd>{onnx.state.metadata.inputNames.join(', ')}</dd>
              <dt>Outputs</dt>
              <dd>{onnx.state.metadata.outputNames.join(', ')}</dd>
            </dl>
            <section>
              <h4>Input Details</h4>
              <ul>
                {onnx.state.metadata.inputMetadata.map((entry) => (
                  <li key={`input-${entry.name}`}>
                    {entry.name} ({entry.isTensor ? 'tensor' : 'value'}) - {entry.type ?? 'unknown'}
                    {entry.shape ? ` [${entry.shape.join(', ')}]` : ''}
                  </li>
                ))}
              </ul>
            </section>
            <section>
              <h4>Output Details</h4>
              <ul>
                {onnx.state.metadata.outputMetadata.map((entry) => (
                  <li key={`output-${entry.name}`}>
                    {entry.name} ({entry.isTensor ? 'tensor' : 'value'}) - {entry.type ?? 'unknown'}
                    {entry.shape ? ` [${entry.shape.join(', ')}]` : ''}
                  </li>
                ))}
              </ul>
            </section>
          </section>
        ) : null}

        <section>
          <h3>Inference</h3>
          <label htmlFor="feeds-json">Feeds (JSON):</label>
          <textarea
            id="feeds-json"
            value={feedsJson}
            onChange={(event) => setFeedsJson(event.target.value)}
            placeholder='{"input_name": {"type": "float32", "dims": [1, 3], "data": [1, 2, 3]}}'
            rows={5}
            cols={50}
          />
          <button
            onClick={() => onnx.runInference(feedsJson)}
            disabled={onnx.state.status !== 'ready'}
          >
            Run Inference
          </button>
        </section>

        {onnx.state.outputs ? (
          <section>
            <h3>Outputs</h3>
            <pre>{JSON.stringify(onnx.state.outputs, null, 2)}</pre>
          </section>
        ) : null}
      </section>

      <hr />

      <section>
        <h2>Image Inference Pipeline</h2>
        <section>
          <h3>Configuration</h3>
          <section>
            <label htmlFor="detection-model">Detection Model (.onnx):</label>
            <input
              id="detection-model"
              type="file"
              accept=".onnx"
              onChange={imageInference.loadDetectionModel}
            />
          </section>
          <section>
            <label htmlFor="pose-model">Pose Model (.onnx):</label>
            <input
              id="pose-model"
              type="file"
              accept=".onnx"
              onChange={imageInference.loadPoseModel}
            />
          </section>
          <section>
            <label htmlFor="image-file">Image File:</label>
            <input
              id="image-file"
              type="file"
              accept="image/*"
              onChange={imageInference.loadImage}
            />
          </section>
        </section>

        <section>
          <h3>Status</h3>
          <dl>
            <dt>Status</dt>
            <dd>{imageInference.state.status}</dd>
            <dt>Detection Model</dt>
            <dd>{imageInference.state.detectionModelName || 'None'}</dd>
            <dt>Pose Model</dt>
            <dd>{imageInference.state.poseModelName || 'None'}</dd>
            {imageInference.state.error ? (
              <>
                <dt>Error</dt>
                <dd>{imageInference.state.error}</dd>
              </>
            ) : null}
          </dl>
        </section>

        {imageInference.state.image ? (
          <section>
            <h3>Image Preview</h3>
            <img
              src={imageInference.state.image.url}
              alt={imageInference.state.image.name}
            />
            <dl>
              <dt>Name</dt>
              <dd>{imageInference.state.image.name}</dd>
              <dt>Dimensions</dt>
              <dd>
                {imageInference.state.image.width} x {imageInference.state.image.height}
              </dd>
            </dl>
          </section>
        ) : null}

        <section>
          <h3>Actions</h3>
          <button
            onClick={imageInference.runPipeline}
            disabled={imageInference.state.status !== 'ready'}
          >
            Run Pipeline
          </button>
          {imageInference.state.projectState ? (
            <>
              <button
                onClick={() => {
                  const ps = imageInference.state.projectState;
                  if (ps) handleDownload(ps, 'inferred_project');
                }}
              >
                Download Inferred Project
              </button>
              <label>
                Blueprint Units:
                <select
                  value={unitSystem}
                  onChange={(e) =>
                    setUnitSystem(e.target.value as 'metric' | 'imperial')
                  }
                >
                  <option value="metric">Metric</option>
                  <option value="imperial">Imperial</option>
                </select>
              </label>
              <button
                onClick={() => {
                  const ps = imageInference.state.projectState;
                  if (ps) handleBlueprintExport(ps, 'inferred_project');
                }}
              >
                Export Blueprint
              </button>
            </>
          ) : null}
        </section>

        {imageInference.state.projectState ? (
          <ProjectPreview
            state={imageInference.state.projectState}
            progress={playback.state.progress}
          />
        ) : null}

        {imageInference.state.detectionOutputs || imageInference.state.poseOutputs || imageInference.state.keypoints || imageInference.state.skeleton || imageInference.state.projectSkeleton ? (
          <section>
            <h3>Pipeline Outputs</h3>
            {imageInference.state.detectionOutputs ? (
              <section>
                <h4>Detection Outputs</h4>
                <pre>{JSON.stringify(imageInference.state.detectionOutputs, null, 2)}</pre>
              </section>
            ) : null}
            {imageInference.state.poseOutputs ? (
              <section>
                <h4>Pose Outputs</h4>
                <pre>{JSON.stringify(imageInference.state.poseOutputs, null, 2)}</pre>
              </section>
            ) : null}
            {imageInference.state.keypoints ? (
              <section>
                <h4>Keypoints ({imageInference.state.keypoints.length})</h4>
                <pre>{JSON.stringify(imageInference.state.keypoints, null, 2)}</pre>
              </section>
            ) : null}
            {imageInference.state.skeleton ? (
              <section>
                <h4>Skeleton ({imageInference.state.skeleton.length})</h4>
                <pre>{JSON.stringify(imageInference.state.skeleton, null, 2)}</pre>
              </section>
            ) : null}
            {imageInference.state.projectSkeleton ? (
              <section>
                <h4>
                  Project Skeleton (Joints: {Object.keys(imageInference.state.projectSkeleton.joints).length}, Bones:{' '}
                  {imageInference.state.projectSkeleton.bones.length})
                </h4>
                <pre>{JSON.stringify(imageInference.state.projectSkeleton, null, 2)}</pre>
              </section>
            ) : null}
          </section>
        ) : null}
      </section>

      <hr />

      <section>
        <h2>Scenario Runner</h2>
        <div style={{ display: 'flex', gap: '1rem', padding: '1rem 0' }}>
          <button onClick={handleBlueprintScenario} disabled={!state}>
            Run Blueprint Scenario
          </button>
          <button
            onClick={handleImageProcessingScenario}
            disabled={imageInference.state.status !== 'ready'}
          >
            Run Image Processing Scenario
          </button>
        </div>
      </section>
    </main>
  )
}

export default App
